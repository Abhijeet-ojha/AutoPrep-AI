import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AutoPrep AI",
  description: "Intelligent Dataset Cleaning, Profiling, and EDA Assistant"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-6">{children}</div>
      </body>
    </html>
  );
}
