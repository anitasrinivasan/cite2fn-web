import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "cite2fn — citation converter",
  description:
    "Upload a .docx with linked sources and get back a document with properly formatted Bluebook or APA footnotes, endnotes, or a reference list.",
};

// Runs in the document <head> before first paint — reads the stored theme
// (or the system preference) and applies the `dark` class to <html>. Prevents
// a flash of light content on dark-mode loads.
const THEME_BOOT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem('cite2fn-theme');
    var theme = stored === 'dark' || stored === 'light'
      ? stored
      : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    if (theme === 'dark') document.documentElement.classList.add('dark');
  } catch (_) {}
})();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
