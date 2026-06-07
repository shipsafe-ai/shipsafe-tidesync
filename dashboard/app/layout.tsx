import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TideSync",
  description: "Silent staleness detection for Fivetran + BigQuery pipelines",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-bg-base min-h-screen text-zinc-100">
        <header className="border-b border-border px-6 py-4 flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-accent" />
          <span className="font-semibold tracking-tight text-sm">TideSync</span>
          <span className="text-muted text-xs font-mono ml-auto">Fivetran + BigQuery</span>
        </header>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
