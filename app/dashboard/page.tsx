import type { Metadata } from "next";
import { Dashboard } from "./Dashboard";

export const metadata: Metadata = {
  title: "Control room | SiracusaDaily",
  description: "Dashboard editoriale, tecnica e di business di SiracusaDaily.",
  robots: { index: false, follow: false },
};

export default function DashboardPage() {
  return <Dashboard />;
}
