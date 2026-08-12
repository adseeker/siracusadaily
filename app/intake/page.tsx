import type { Metadata } from "next";
import { Intake } from "./Intake";

export const metadata: Metadata = {
  title: "Intake social | SiracusaDaily",
  description: "Raccolta manuale di eventi, news e opportunità dai social.",
  robots: { index: false, follow: false },
};

export default function IntakePage() {
  return <Intake />;
}
