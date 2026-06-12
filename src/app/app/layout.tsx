import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Локальный предсказатель",
  description: "Анализатор и предсказатель лотерей — 183 модели, DualBayesRing, k-fold CV, Monte Carlo",
  keywords: ["lottery", "prediction", "анализ", "лотерея", "предсказание"],
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
        style={{ background: 'linear-gradient(135deg, #0a0f1e 0%, #0d1117 50%, #0a0f1e 100%)', minHeight: '100vh' }}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
