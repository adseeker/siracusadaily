import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

const title = "SiracusaDaily | Le notizie di Siracusa, ogni giorno";
const description = "Una selezione chiara delle notizie più importanti di Siracusa e provincia, direttamente nella tua email.";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "siracusadaily.com";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const base = new URL(`${protocol}://${host}`);
  const socialImage = new URL("/og.png", base).toString();

  return {
    metadataBase: base,
    title,
    description,
    openGraph: {
      title,
      description,
      type: "website",
      locale: "it_IT",
      images: [{ url: socialImage, alt: "SiracusaDaily, le notizie di Siracusa ogni giorno" }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [socialImage],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it">
      <head>
        <link rel="stylesheet" href="https://sibforms.com/forms/end-form/build/sib-styles.css" />
      </head>
      <body>{children}</body>
    </html>
  );
}
