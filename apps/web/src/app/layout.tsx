import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AlphaPulse AI — Stock Market Research Assistant",
  description:
    "Conversational AI stock market assistant with technical charts, SEC fundamentals, Python sandbox modeling, and Celery background jobs.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
