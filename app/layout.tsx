import type { Metadata } from "next";
import "./globals.css";

const title = "SiracusaDaily | Le notizie di Siracusa, ogni giorno";
const description = "Una selezione chiara delle notizie più importanti di Siracusa e provincia, direttamente nella tua email.";

export const metadata: Metadata = {
  metadataBase: new URL("https://siracusadaily.com"),
  title,
  description,
  icons: {
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
    shortcut: "/favicon.svg",
  },
  openGraph: {
    title,
    description,
    type: "website",
    locale: "it_IT",
    images: [{ url: "/og.png", alt: "SiracusaDaily, le notizie di Siracusa ogni giorno" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og.png"],
  },
};

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
