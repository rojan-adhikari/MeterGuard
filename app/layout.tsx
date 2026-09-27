import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MeterGuard | Smart Meter-Based Electricity Fraud Risk Prediction",
  description: "MeterGuard analyzes smart-meter consumption and prioritizes account investigations.",
  other: {
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
