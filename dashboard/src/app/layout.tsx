import type { Metadata, Viewport } from "next";
import { JetBrains_Mono } from "next/font/google";
import { AuthKitProvider } from "@workos-inc/authkit-nextjs/components";
import "./globals.css";
import { DashboardLayout } from "@/components/layout/dashboard-layout";

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Signal Copier | Dashboard",
  description: "Beginner-first MT5 copy trading dashboard",
};

// Emitted into <head> ahead of the stylesheet link, so the browser starts on a
// dark canvas. Without it Firefox and Safari paint their default white page for
// as long as globals.css takes to arrive, which reads as a flash on first load.
export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#050506",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${jetbrainsMono.variable} font-sans antialiased bg-mesh noise-overlay`}
      >
        <AuthKitProvider>
          <DashboardLayout>{children}</DashboardLayout>
        </AuthKitProvider>
      </body>
    </html>
  );
}
