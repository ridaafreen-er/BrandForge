import "./globals.css";
import { Bricolage_Grotesque, Instrument_Sans } from "next/font/google";
const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display" });
const body = Instrument_Sans({ subsets: ["latin"], variable: "--font-body" });
export const metadata = { title: "BrandForge", description: "One brand idea in. Publish-ready content for every platform out." };
export default function Root({ children }: { children: React.ReactNode }) {
  return <html lang="en" className={`${display.variable} ${body.variable}`}><body>{children}</body></html>;
}
