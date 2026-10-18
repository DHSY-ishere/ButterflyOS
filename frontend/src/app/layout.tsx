import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ButterflyOS — Chaos, Blast-Radius & Bus-Factor Time-Machine",
  description: "A neuro-symbolic agent system for engineering resilience, powered by the FalkorDB multigraph",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
