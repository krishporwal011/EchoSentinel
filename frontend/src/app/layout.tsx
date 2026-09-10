import type { Metadata } from "next";
import { Cormorant_Garamond, Inter } from "next/font/google";
import "./globals.css";
import { GrainOverlay } from "../components/GrainOverlay";
import { CustomCursor } from "../components/CustomCursor";
import { CinematicBackground } from "../components/CinematicBackground";
import { Navbar } from "../components/Navbar";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-serif",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "EchoSentinel — Real-Time Voice Safety",
  description: "AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${cormorant.variable} ${inter.variable} dark`}>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0" />
      </head>
      <body className="bg-[#090b11] text-[#f4f5f7] min-h-screen relative font-sans-ui overflow-x-hidden selection:bg-[#66b7ff]/20">
        {/* Persistent Cinematic Visual Atmosphere */}
        <CinematicBackground />
        <GrainOverlay />
        <CustomCursor />

        {/* Global Transparent Navbar */}
        <Navbar />

        {/* Dynamic Route Content */}
        <main className="relative z-10 flex flex-col min-h-screen pt-20 sm:pt-24">
          {children}
        </main>
      </body>
    </html>
  );
}
