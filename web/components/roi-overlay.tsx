import { ROI_META } from "@/lib/copy";
import type { AnalysisResult } from "@/lib/schemas";

export function RoiOverlay({ result }: { result: AnalysisResult }) {
  return (
    <div className="card p-4 h-full flex flex-col">
      <h2 className="font-semibold mb-3">What was analysed</h2>
      {result.overlay_jpeg_b64 ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={`data:image/jpeg;base64,${result.overlay_jpeg_b64}`}
          alt="Video frame with the forehead, left cheek and right cheek regions outlined"
          className="w-full rounded-lg border border-border"
        />
      ) : (
        <div className="flex-1 min-h-40 rounded-lg border border-dashed border-border grid place-items-center p-6 text-center text-sm text-muted">
          {result.source?.type === "synthetic"
            ? "Synthetic scenario: signals were generated directly, so there is no video frame."
            : "No face frame available for this clip."}
        </div>
      )}
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {Object.entries(ROI_META).map(([k, m]) => (
          <li key={k} className="flex items-center gap-1.5">
            <span
              className="inline-block size-3 rounded-sm"
              style={{ background: m.color, outline: k === "background" ? "1px dashed var(--muted)" : undefined }}
            />
            {m.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
