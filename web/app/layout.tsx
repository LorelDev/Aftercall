import type { Metadata } from "next";
import { Frank_Ruhl_Libre, Heebo, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const frank = Frank_Ruhl_Libre({
  subsets: ["hebrew", "latin"],
  weight: ["500", "700", "800", "900"],
  variable: "--font-display",
});

const heebo = Heebo({
  subsets: ["hebrew", "latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono2",
});

export const metadata: Metadata = {
  title: "בסדר — מתקשרים לכולם. שומעים שהכל בסדר.",
  description:
    "מערך שיחות AI שמתקשר לכל תושב אחרי אירוע חירום, אוסף את מה שחשוב ומציף את מי שצריך עזרה — בדקות.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="he"
      dir="rtl"
      className={`${frank.variable} ${heebo.variable} ${plexMono.variable}`}
    >
      <body className="font-[family-name:var(--font-body)] antialiased">
        {children}
      </body>
    </html>
  );
}
