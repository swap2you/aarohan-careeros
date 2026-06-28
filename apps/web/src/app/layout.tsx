import "./globals.css";
import type { Metadata } from "next";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "Aarohan CareerOS",
  description: "Supervised career operations dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="layout">
          <Nav />
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
