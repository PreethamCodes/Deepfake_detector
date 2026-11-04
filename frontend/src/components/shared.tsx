import {
  AudioLines,
  Film,
  Image,
  ArrowUpRight,
  CircleAlert,
} from "lucide-react";
import {
  date,
  media,
  type Entry,
  type Modality,
  type Verdict,
} from "@/lib/api";
export const icons = { image: Image, video: Film, audio: AudioLines };
export const verdicts: Verdict[] = ["REAL", "AI-GENERATED", "INCONCLUSIVE"];
export const tone = (v: Verdict) =>
  ({ REAL: "real", "AI-GENERATED": "synthetic", INCONCLUSIVE: "uncertain" })[v];
export function Badge({ value }: { value: Verdict }) {
  return (
    <span className={"badge " + tone(value)}>
      <i />
      {value}
    </span>
  );
}
export function Modalities({ items }: { items: Modality[] }) {
  return (
    <span className="media-list">
      {items.map((m) => {
        const Icon = icons[m];
        return (
          <span key={m}>
            <Icon size={15} />
            {media[m].name}
          </span>
        );
      })}
    </span>
  );
}
export function Notice({ message }: { message: string }) {
  return (
    <p role="alert" className="notice">
      <CircleAlert size={17} />
      {message}
    </p>
  );
}
export function CaseTable({ entries }: { entries: Entry[] }) {
  return (
    <div className="ledger">
      {entries.length === 0 ? (
        <p className="empty">
          No investigations found. Submit media to create a report, or adjust
          your search.
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Investigation</th>
              <th>Media</th>
              <th>Assessment</th>
              <th>Created</th>
              <th>
                <span className="sr-only">Open</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {entries.map((r) => (
              <tr key={r.analysis_id}>
                <td>
                  <a
                    className="case-id"
                    title={r.analysis_id}
                    href={"#/report/" + r.analysis_id}
                  >
                    {r.analysis_id.slice(0, 8)}
                    <span className="sr-only">{r.analysis_id.slice(8)}</span>
                  </a>
                </td>
                <td>
                  <Modalities items={r.modalities} />
                </td>
                <td>
                  <Badge value={r.assessment} />
                </td>
                <td>{date(r.created_at)}</td>
                <td>
                  <a
                    href={"#/report/" + r.analysis_id}
                    aria-label={"Open report " + r.analysis_id}
                  >
                    <ArrowUpRight size={17} />
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
export function ScanPlate() {
  // Isometric brand engraving, independent of case data.
  const project = (x: number, y: number) => {
    const z =
      47 * Math.exp(-(x * x * 0.75 + y * y) * 2) * Math.cos(5 * x - 2 * y) +
      9 * Math.sin(y * 6 + x * 3);
    return (
      (214 + 124 * x + 83 * y).toFixed(1) +
      "," +
      (101 + 24 * x - 36 * y - z).toFixed(1)
    );
  };
  return (
    <svg
      aria-hidden="true"
      className="scan-plate"
      viewBox="0 0 430 210"
      fill="none"
    >
      <defs>
        <linearGradient id="mesh" x1="0" y1="1" x2="1" y2="0">
          <stop stopColor="#3376df" />
          <stop offset=".56" stopColor="#5cebf9" />
          <stop offset="1" stopColor="#608bdc" />
        </linearGradient>
      </defs>
      <g stroke="#47708b" opacity=".62">
        <path d="M22 44V24h21m342 0h21v20M22 166v20h21m342 0h21v-20" />
        <path strokeDasharray="2 6" d="M14 110h402M215 14v182" />
      </g>
      <g stroke="url(#mesh)" strokeWidth=".95">
        {Array.from({ length: 40 }, (_, i) => (
          <polyline
            key={i}
            points={Array.from({ length: 68 }, (_, j) =>
              project(j / 33.5 - 1, i / 19.5 - 1),
            ).join(" ")}
          />
        ))}
      </g>
      <g stroke="#5baad8" opacity=".36" strokeWidth=".6">
        {Array.from({ length: 28 }, (_, i) => (
          <polyline
            key={i}
            points={Array.from({ length: 50 }, (_, j) =>
              project(i / 13.5 - 1, j / 24.5 - 1),
            ).join(" ")}
          />
        ))}
      </g>
    </svg>
  );
}
