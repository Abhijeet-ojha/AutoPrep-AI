import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AutoPrep AI",
  description: "Intelligent Dataset Cleaning, Profiling, and EDA Assistant"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-zinc-950 text-zinc-50 min-h-screen">
        {children}
      </body>
    </html>
  );
}
