import type { Metadata } from "next";
import "@fontsource/fraunces/600.css";
import "@fontsource/fraunces/700.css";
import "@fontsource/noto-sans/400.css";
import "@fontsource/noto-sans/600.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Korean Learning Platform",
  description: "Học tiếng Hàn có nguồn trích dẫn rõ ràng.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
