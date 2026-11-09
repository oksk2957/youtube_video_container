import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "One-Shot AI Video Editor",
  description: "로그인 없이 업로드하고 AI로 편집한 뒤 바로 내려받는 로컬 영상 편집기",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className={geistSans.variable + " " + geistMono.variable + " antialiased"}>
      <body>{children}</body>
    </html>
  );
}
