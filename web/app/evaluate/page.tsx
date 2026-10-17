import type { Metadata } from "next";
import { EvalDashboard } from "@/components/evaluate/eval-dashboard";

export const metadata: Metadata = { title: "Accuracy testing · SatyaSpandan" };

export default function EvaluatePage() {
  return <EvalDashboard />;
}
