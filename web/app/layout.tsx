import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "cite2fn — citation converter",
  description:
    "Upload a .docx with linked sources and get back a document with properly formatted Bluebook or APA footnotes, endnotes, or a reference list.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
