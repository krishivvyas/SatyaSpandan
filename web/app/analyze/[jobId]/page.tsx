import { Suspense } from "react";
import { ResultsView } from "@/components/results-view";

export default function AnalyzePage() {
  return (
    <Suspense fallback={<div className="card h-72 animate-pulse" />}>
      <ResultsView />
    </Suspense>
  );
}
