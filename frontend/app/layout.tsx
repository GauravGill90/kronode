import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import ClerkTokenSync from "@/components/ClerkTokenSync";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kronode — Organizational Memory",
  description: "Team conventions, docs, and reviewer patterns served to any AI coding tool via MCP",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body>
          <ClerkTokenSync />
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
