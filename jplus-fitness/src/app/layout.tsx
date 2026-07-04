import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "J Plus Fitness | Elite Personal Training in Central, Hong Kong",
  description:
    "Hong Kong's premier private personal-training studio. Science-based one-on-one coaching, body-composition analysis and nutrition guidance at 6/F Abdoolally House, 20 Stanley Street, Central. Rated 5.0 on Google.",
  keywords: [
    "personal training Hong Kong",
    "personal trainer Central",
    "J Plus Fitness",
    "weight loss coaching",
    "strength training Hong Kong",
  ],
  openGraph: {
    title: "J Plus Fitness | Elite Personal Training in Central, Hong Kong",
    description:
      "Transform your body with Hong Kong's elite personal trainers. Rated 5.0 on Google with 27+ five-star reviews.",
    type: "website",
    locale: "en_HK",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
