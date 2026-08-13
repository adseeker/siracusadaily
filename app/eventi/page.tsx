import type { Metadata } from "next";
import { Eventi } from "./Eventi";

export const metadata: Metadata = {
  title: "Eventi a Siracusa e provincia | SiracusaDaily",
  description: "Tutti gli eventi a Siracusa e in provincia, raccolti da SiracusaDaily: concerti, cultura, sport, festival e appuntamenti.",
};

export default function EventiPage() {
  return <Eventi />;
}
