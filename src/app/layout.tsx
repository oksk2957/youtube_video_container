import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Video Studio | 동영상 편집",
  description: "영상을 업로드하고 브라우저에서 컷 편집하는 프로젝트 스튜디오",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className={(geistSans.variable + " " + geistMono.variable + " h-full antialiased")}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
