import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HybridGuard Browser Probe",
  description:
    "Public HTTPS entry point for HybridGuard available-browser environment collection.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
