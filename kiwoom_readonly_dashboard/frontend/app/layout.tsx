import type React from "react";
import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Kiwoom Readonly Dashboard",
  description: "Read-only market dashboard powered by Kiwoom REST and WebSocket."
};

export default function RootLayout({
  children
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className="dark">
      <body>{children}</body>
    </html>
  );
}
