#!/usr/bin/env python3
"""Deploy ButterflyOS to an AWS Lightsail VPS (Docker Compose behind nginx) with one command.

  python deploy/deploy_lightsail.py --profile personal            # create + deploy
  python deploy/deploy_lightsail.py --profile personal --update   # re-ship code to the existing server
  python deploy/deploy_lightsail.py --profile personal --destroy  # delete everything (stops billing)
  python deploy/deploy_lightsail.py --plan                        # dry run: show what would happen, build the bundle only

Runs entirely with YOUR AWS credentials on YOUR machine. Needs: pip install boto3, and OpenSSH (ssh/scp) on PATH.
"""
import argparse
import os
import secrets
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".venv", "node_modules", ".next", "__pycache__", ".git", "scratch"}
EXCLUDE_SUFFIX = (".err", ".out", ".pyc", ".log")
INCLUDE_TOP = ["backend", "frontend", "deploy", "Dockerfile.backend", "Dockerfile.frontend", "docker-compose.prod.yml", ".dockerignore", "README.md"]

USER_DATA = """#!/bin/bash
exec > /var/log/butterfly-bootstrap.log 2>&1
set -x
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 curl tar
systemctl enable --now docker
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
mkdir -p /opt/butterfly && chown ubuntu:ubuntu /opt/butterfly
touch /opt/butterfly/.bootstrap-done
"""


def log(msg):
    print(f"[deploy] {msg}", flush=True)


def build_bundle() -> Path:
    out = Path(tempfile.gettempdir()) / "butterfly-bundle.tgz"
    with tarfile.open(out, "w:gz") as tar:
        for top in INCLUDE_TOP:
            p = ROOT / top
            if not p.exists():
                continue
            if p.is_file():
                tar.add(p, arcname=top)
                continue
            for dp, dns, fns in os.walk(p):
                dns[:] = [d for d in dns if d not in EXCLUDE_DIRS]
                for fn in fns:
                    if fn.endswith(EXCLUDE_SUFFIX):
                        continue
                    fp = Path(dp) / fn
                    tar.add(fp, arcname=str(fp.relative_to(ROOT)).replace("\\", "/"))
    log(f"bundle built: {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


def run(cmd, check=True, capture=False, timeout=None):
    return subprocess.run(cmd, check=check, text=True, capture_output=capture, timeout=timeout)


def ssh_base(key: Path, ip: str):
    return ["ssh", "-i", str(key), "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=30", f"ubuntu@{ip}"]


def protect_key(key: Path):
    if os.name == "nt":
        user = os.environ.get("USERNAME", "")
        run(["icacls", str(key), "/inheritance:r"], check=False, capture=True)
        run(["icacls", str(key), "/grant:r", f"{user}:R"], check=False, capture=True)
    else:
        key.chmod(stat.S_IRUSR | stat.S_IWUSR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None, help="AWS CLI profile of YOUR personal account")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--zone", default=None, help="availability zone (default <region>a)")
    ap.add_argument("--name", default="butterflyos-demo")
    ap.add_argument("--bundle", default="small_3_0", help="small_3_0 = 2 GB RAM, about $12/month")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--destroy", action="store_true")
    ap.add_argument("--plan", action="store_true", help="dry run: build the bundle, touch nothing in AWS")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    a = ap.parse_args()

    bundle = build_bundle()
    if a.plan:
        log(f"PLAN: would create Lightsail instance '{a.name}' ({a.bundle}, ubuntu_24_04) in {a.region}, open 80 (all) and 22 (your IP),"
            " attach a static IP, ship the bundle over SSH and run docker compose. Nothing was changed.")
        return

    import boto3
    sess = boto3.Session(profile_name=a.profile, region_name=a.region)
    acct = sess.client("sts").get_caller_identity()
    log(f"AWS account: {acct['Account']}  ({acct['Arn']})")
    ls = sess.client("lightsail")
    key_name = f"{a.name}-key"
    ip_name = f"{a.name}-ip"
    key_path = Path.home() / ".ssh" / f"{a.name}.pem"

    if a.destroy:
        if not a.yes and input(f"Delete instance '{a.name}', static IP and key pair in account {acct['Account']}? [y/N] ").lower() != "y":
            return
        for fn, kw in [(ls.release_static_ip, {"staticIpName": ip_name}), (ls.delete_instance, {"instanceName": a.name}),
                       (ls.delete_key_pair, {"keyPairName": key_name})]:
            try:
                fn(**kw)
                log(f"deleted {list(kw.values())[0]}")
            except Exception as e:
                log(f"skip: {str(e)[:100]}")
        return

    if a.update:
        ip = ls.get_static_ip(staticIpName=ip_name)["staticIp"]["ipAddress"]
        ship_and_start(ip, key_path, bundle, admin_token=None)
        return

    if not a.yes:
        print(f"\nThis creates a ~$12/month Lightsail VPS in account {acct['Account']} ({a.region}).")
        if input("Continue? [y/N] ").lower() != "y":
            return

    my_ip = urllib.request.urlopen("https://checkip.amazonaws.com").read().decode().strip()
    kp = ls.create_key_pair(keyPairName=key_name)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(kp["privateKeyBase64"])
    protect_key(key_path)
    log(f"SSH key saved to {key_path}")

    ls.create_instances(instanceNames=[a.name], availabilityZone=a.zone or f"{a.region}a", blueprintId="ubuntu_24_04",
                        bundleId=a.bundle, keyPairName=key_name, userData=USER_DATA,
                        tags=[{"key": "Project", "value": "ButterflyOS"}])
    log("instance requested; waiting for it to run ...")
    for _ in range(60):
        st = ls.get_instance_state(instanceName=a.name)["state"]["name"]
        if st == "running":
            break
        time.sleep(5)
    ls.put_instance_public_ports(instanceName=a.name, portInfos=[
        {"fromPort": 80, "toPort": 80, "protocol": "tcp", "cidrs": ["0.0.0.0/0"]},
        {"fromPort": 22, "toPort": 22, "protocol": "tcp", "cidrs": [f"{my_ip}/32"]},
    ])
    ls.allocate_static_ip(staticIpName=ip_name)
    ls.attach_static_ip(staticIpName=ip_name, instanceName=a.name)
    ip = ls.get_static_ip(staticIpName=ip_name)["staticIp"]["ipAddress"]
    log(f"static IP: {ip}")
    ship_and_start(ip, key_path, bundle, admin_token=secrets.token_urlsafe(18), wait_bootstrap=True)


def ship_and_start(ip: str, key: Path, bundle: Path, admin_token, wait_bootstrap=False):
    ssh = ssh_base(key, ip)
    if wait_bootstrap:
        log("waiting for the server to finish installing Docker (2-5 minutes) ...")
        for i in range(90):
            r = run(ssh + ["test -f /opt/butterfly/.bootstrap-done"], check=False, capture=True)
            if r.returncode == 0:
                break
            time.sleep(10)
        else:
            sys.exit("server bootstrap did not finish; check /var/log/butterfly-bootstrap.log on the instance")
    log("uploading code ...")
    run(["scp", "-i", str(key), "-o", "StrictHostKeyChecking=accept-new", str(bundle), f"ubuntu@{ip}:/opt/butterfly/bundle.tgz"])
    env = f"ADMIN_TOKEN={admin_token}\n" if admin_token else ""
    cmd = ("cd /opt/butterfly && tar xzf bundle.tgz && "
           + (f"printf '%s' '{env}' > .env && " if env else "")
           + "sudo docker compose -f docker-compose.prod.yml up -d --build")
    log("building and starting the stack on the server (first build takes ~5-10 minutes) ...")
    run(ssh + [cmd], timeout=3000)
    log("waiting for the app to answer ...")
    for _ in range(60):
        try:
            if b'"ok":true' in urllib.request.urlopen(f"http://{ip}/api/health", timeout=8).read().replace(b" ", b""):
                break
        except Exception:
            pass
        time.sleep(5)
    else:
        sys.exit("stack started but /api/health never answered; run: ssh ... 'sudo docker compose -f /opt/butterfly/docker-compose.prod.yml logs'")
    print("\n" + "=" * 60)
    print(f"  LIVE:  http://{ip}/")
    print(f"  Console:  http://{ip}/console")
    if admin_token:
        print(f"  Admin token (hard reset header X-Admin-Token): {admin_token}")
    print("  Delete everything later with:  python deploy/deploy_lightsail.py --profile <p> --destroy")
    print("=" * 60)


if __name__ == "__main__":
    main()
