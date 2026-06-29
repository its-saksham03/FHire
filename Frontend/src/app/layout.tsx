/* eslint-disable @next/next/no-page-custom-font */
/* eslint-disable @next/next/google-font-display */
import type { Metadata } from "next";
import { Navbar } from "@/components/navbar";
import { ShaderBackground } from "@/components/shader-background";
import "./globals.css";

export const metadata: Metadata = {
  title: "FHire — We rank hiring decisions",
  description:
    "FHire evaluates every candidate the way an elite recruiter thinks. AI-powered recruiting intelligence dashboard.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Archivo Narrow + Space Grotesk + JetBrains Mono */}
        <link
          href="https://fonts.googleapis.com/css2?family=Archivo+Narrow:wght@400;500;700&family=JetBrains+Mono:wght@300;400;500&family=Space+Grotesk:wght@300;400;500;700&display=swap"
          rel="stylesheet"
        />
        {/* Material Symbols — icon font, display=block is intentional */}
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=block"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-background text-on-surface font-body-md antialiased selection:bg-tertiary/30 selection:text-tertiary">
        <ShaderBackground />
        <Navbar />
        <main>{children}</main>
      </body>
    </html>
  );
}
