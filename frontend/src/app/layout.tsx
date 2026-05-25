import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/sidebar";
import QueryProvider from "@/lib/query-provider";

export const metadata: Metadata = {
  title: "Daily Scheduler",
  description: "AI-powered daily news & trading report system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        <QueryProvider>
          <Sidebar />
          <main className="ml-60 min-h-screen p-8">{children}</main>
        </QueryProvider>
      </body>
    </html>
  );
}
