import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import ClerkTokenSync from "@/components/ClerkTokenSync";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kronode",
  description: "Your autonomous AI developer",
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
