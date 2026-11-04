import { useRef, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import { ArrowLeft, ChevronRight, Flag } from "lucide-react";
import { Badge, icons, Notice } from "@/components/shared";
import { MediaPreview } from "@/components/MediaPreview";
import {
  date,
  time,
  modes,
  media,
  type Analysis,
  type Files,
  type Finding,
  type Frame,
} from "@/lib/api";

// Display rounding only; the full value stays available in the title tooltip.
const score = (n?: number | null) => (n == null ? "—" : n.toFixed(4));
const agreement: Record<string, string> = {
  none: "No detector verdicts",
  single: "Single detector",
  agree: "Detectors agree",
  conflict: "Detectors conflict",
};
const fields: Record<string, [label: string, unit?: string, digits?: number]> =
  {
    width: ["Width", "px"],
    height: ["Height", "px"],
    frame_count: ["Decoded frames"],
    duration_seconds: ["Duration", "s", 3],
    fps: ["Average FPS", "", 2],
    format: ["Container"],
    codec: ["Codec"],
    sample_rate: ["Source sample rate", "Hz"],
    channels: ["Channels"],
    analyzed_seconds: ["Analyzed window", "s", 3],
  };

function Metadata({ data }: { data: Finding["result"]["metadata"] }) {
  return data ? (
    <dl className="metadata">
      {Object.entries(data).map(([k, v]) => {
        const [label, unit, digits] = fields[k] ?? [k.replaceAll("_", " ")];
        const value =
          typeof v === "number"
            ? digits != null
              ? v.toFixed(digits)
              : Number.isInteger(v)
                ? v
                : Number(v.toFixed(5))
            : v;
        return (
          <div key={k}>
            <dt>{label}</dt>
            <dd>
              {value}
              {unit ? " " + unit : ""}
            </dd>
          </div>
        );
      })}
    </dl>
  ) : null;
}
function FrameStill({ still, frame }: { still: string; frame?: Frame }) {
  return frame ? (
    <figure className="still">
      {still ? (
        <img src={still} alt={"Video frame near " + frame.timestamp_seconds.toFixed(3) + " s"} />
      ) : (
        <div className="still-empty">
          Select your local video above to view this frame.
        </div>
      )}
      <figcaption>
        <b>Frame {frame.index}</b>
        <span>{frame.timestamp_seconds.toFixed(3)} s</span>
        {frame.prediction ? <Badge value={frame.prediction} /> : <span>No face</span>}
        <span title={String(frame.detection_score ?? "")}>
          GenD score <code>{score(frame.detection_score)}</code>
        </span>
        <small>
          Browser seek to the source timestamp. The nearest decoded frame is
          shown.
        </small>
      </figcaption>
    </figure>
  ) : null;
}
function Evidence({
  kind,
  finding,
  file,
}: {
  kind: "audio" | "video";
  finding: Finding;
  file?: File;
}) {
  const [local, setLocal] = useState<File>();
  const [selected, setSelected] = useState<number>();
  const [still, setStill] = useState("");
  const video = useRef<HTMLVideoElement>(null);
  const r = finding.result,
    frames = r.frames || [],
    flagged = frames.filter((f) => f.prediction === "AI-GENERATED"),
    scored = frames.filter((f) => f.status === "scored"),
    current = file || local;
  function inspect(index: number, seconds: number) {
    setSelected(index);
    setStill("");
    const v = video.current;
    if (v && v.readyState >= 1) {
      v.pause();
      v.addEventListener(
        "seeked",
        () => {
          const canvas = document.createElement("canvas");
          canvas.width = v.videoWidth;
          canvas.height = v.videoHeight;
          canvas.getContext("2d")?.drawImage(v, 0, 0);
          try {
            setStill(canvas.toDataURL("image/jpeg", 0.88));
          } catch {
            setStill("");
          }
        },
        { once: true },
      );
      v.currentTime = seconds;
    }
  }
  return (
    <>
      <section className="section">
        <h2>{kind === "audio" ? "Audio playback" : "Video inspection"}</h2>
        {current ? (
          <>
            <MediaPreview file={current} kind={kind} videoRef={video} />
            {local && (
              <small>
                Local reference selected by you. Source identity is unverified.
              </small>
            )}
          </>
        ) : (
          <div className="empty">
            <p>
              Source media was removed after analysis. Select your original file
              for local playback.
            </p>
            <label className="file-label">
              Choose local {kind}
              <input
                aria-label={"Choose local " + kind}
                type="file"
                accept={media[kind].ext.map((e) => "." + e).join(",")}
                onChange={(e) => setLocal(e.target.files?.[0])}
              />
            </label>
          </div>
        )}
      </section>
      {r.error && <Notice message={r.error} />}
      {kind === "video" && (
        <section className="section">
          <h2>Sampled faces</h2>
          <div className="frame-summary">
            <span>
              <strong>{frames.length}</strong> sampled
            </span>
            <span>
              <strong>{scored.length}</strong> scored
            </span>
            <span className={flagged.length ? "flag" : ""}>
              <strong>{flagged.length}</strong> flagged
            </span>
            {flagged.length > 0 && (
              <div className="flag-chips" aria-label="Flagged frames">
                {flagged.map((f) => (
                  <button
                    key={f.index}
                    aria-pressed={selected === f.index}
                    onClick={() => inspect(f.index, f.timestamp_seconds)}
                  >
                    <Flag size={12} />
                    Frame {f.index} · {f.timestamp_seconds.toFixed(3)} s
                  </button>
                ))}
              </div>
            )}
          </div>
          <p className="hint">
            Select a frame to seek the video and capture it. Gaps in the chart
            are samples without a detected face. Scores above 0.5 are labelled
            AI-GENERATED; they are not calibrated probabilities.
          </p>
          {scored.length > 0 && (
            <div className="chart" aria-label="GenD scores by sampled frame">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={frames}>
                  <XAxis dataKey="index" stroke="#a7b6c8" fontSize={12} />
                  <YAxis domain={[0, 1]} stroke="#a7b6c8" fontSize={12} />
                  <ReferenceLine
                    y={0.5}
                    stroke="#5d7088"
                    strokeDasharray="4 4"
                    label={{
                      value: "0.5 threshold",
                      fill: "#a7b6c8",
                      fontSize: 11,
                      position: "insideTopRight",
                    }}
                  />
                  <Tooltip
                    cursor={{ fill: "#253447" }}
                    contentStyle={{
                      background: "#111b28",
                      color: "#edf4fc",
                      border: "1px solid #43536a",
                    }}
                    labelFormatter={(i) => "Frame " + i}
                  />
                  <Bar
                    dataKey="detection_score"
                    name="GenD score"
                    maxBarSize={32}
                    isAnimationActive={false}
                  >
                    {frames.map((f) => (
                      <Cell
                        key={f.index}
                        cursor="pointer"
                        onClick={() => inspect(f.index, f.timestamp_seconds)}
                        fill={
                          f.prediction === "AI-GENERATED"
                            ? "#ff9c99"
                            : "#78cbde"
                        }
                        fillOpacity={
                          selected == null || selected === f.index ? 1 : 0.55
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          {selected != null && (
            <FrameStill
              still={still}
              frame={frames.find((f) => f.index === selected)}
            />
          )}
          <div className="ledger">
            <table>
              <thead>
                <tr>
                  <th>Frame</th>
                  <th>Source time</th>
                  <th>Finding</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {frames.map((f) => (
                  <tr
                    key={f.index}
                    className={
                      (selected === f.index ? "selected " : "") +
                      (f.prediction === "AI-GENERATED" ? "flagged" : "")
                    }
                  >
                    <td>
                      <button
                        aria-pressed={selected === f.index}
                        onClick={() => inspect(f.index, f.timestamp_seconds)}
                      >
                        Inspect {f.index}
                      </button>
                    </td>
                    <td>{f.timestamp_seconds.toFixed(3)} s</td>
                    <td>
                      {f.prediction ? (
                        <Badge value={f.prediction} />
                      ) : (
                        "No face"
                      )}
                    </td>
                    <td title={String(f.detection_score ?? "")}>
                      <code>{score(f.detection_score)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!frames.length && (
            <p className="empty">No sampled frame results were returned.</p>
          )}
          {selected != null && (
            <p role="status" className="hint">
              Selected frame {selected} ·{" "}
              {frames
                .find((f) => f.index === selected)
                ?.timestamp_seconds.toFixed(3)}{" "}
              s
            </p>
          )}
        </section>
      )}
      <section className="section">
        <h2>{r.model_name} findings</h2>
        <FindingDetail finding={finding} />
        {kind === "audio" && r.raw_score != null && r.spoof_logit != null && (
          <p className="hint">
            AASIST predicts REAL when the bona fide logit exceeds the spoof
            logit. Margin (bona fide − spoof){" "}
            <code>{(r.raw_score - r.spoof_logit).toFixed(4)}</code>. Logits are
            not probabilities.
          </p>
        )}
        <Metadata data={r.metadata} />
      </section>
    </>
  );
}
function FindingDetail({ finding }: { finding: Finding }) {
  const r = finding.result;
  return (
    <>
      <div className="detail-line">
        {r.prediction ? (
          <Badge value={r.prediction} />
        ) : (
          <span className="failed">Failed</span>
        )}
        <span>{time(r.processing_time_ms)}</span>
      </div>
      {r.detection_score != null && (
        <p>
          Detection score <code>{r.detection_score}</code>
        </p>
      )}
      {r.raw_score != null && (
        <p>
          Bona fide logit <code>{r.raw_score}</code>
        </p>
      )}
      {r.spoof_logit != null && (
        <p>
          Spoof logit <code>{r.spoof_logit}</code>
        </p>
      )}
      {(r.warning || r.error) && <small>{r.error || r.warning}</small>}
    </>
  );
}
export function Report({
  record,
  files,
  tab,
}: {
  record: Analysis;
  files: Files;
  tab: string;
}) {
  const { report, analysis_id: id } = record;
  const root = "#/report/" + id;
  const kind = tab === "audio" || tab === "video" ? tab : null;
  const failed = modes.filter((m) => report.findings[m]?.result.error);
  return (
    <>
      <a className="text-link" href="#/history">
        <ArrowLeft size={14} />
        Investigation history
      </a>
      <h1 className="report-title">Forensic report</h1>
      <p className="case-meta">
        <code>{id}</code> · {date(record.created_at)}
      </p>
      <nav className="tabs" aria-label="Report sections">
        {[
          ["", "Overview"],
          ["video", "Video forensics"],
          ["audio", "Audio forensics"],
        ].map(([path, label]) => (
          <a
            key={path}
            className={tab === path ? "active" : ""}
            href={root + (path ? "/" + path : "")}
          >
            {label}
          </a>
        ))}
      </nav>
      {kind ? (
        report.findings[kind] ? (
          <Evidence
            key={kind}
            kind={kind}
            finding={report.findings[kind]!}
            file={files[kind]}
          />
        ) : (
          <p className="empty">
            No {kind} was submitted for this investigation.
          </p>
        )
      ) : (
        <>
          <section className={"assessment " + record.status}>
            <div>
              <h2>Overall assessment</h2>
              <Badge value={report.assessment} />
              <p>{report.reason}</p>
            </div>
            <dl>
              <dt>Case status</dt>
              <dd>{record.status}</dd>
              <dt>Agreement</dt>
              <dd>{agreement[report.agreement] ?? report.agreement}</dd>
              <dt>Detectors run</dt>
              <dd>{Object.keys(report.findings).length}</dd>
              <dt>Processing time</dt>
              <dd>{time(record.processing_time_ms)}</dd>
            </dl>
          </section>
          {failed.length > 0 && (
            <section className="section">
              <h2>Failed modalities</h2>
              {failed.map((m) => (
                <Notice
                  key={m}
                  message={
                    media[m].name +
                    " (" +
                    media[m].model +
                    "): " +
                    report.findings[m]!.result.error
                  }
                />
              ))}
            </section>
          )}
          <section className="section">
            <h2>Detector evidence</h2>
            <div className="selection">
              {modes
                .filter((m) => report.findings[m])
                .map((m) => {
                  const f = report.findings[m]!,
                    Icon = icons[m];
                  return (
                    <article key={m} className="file-row">
                      <div className="file-head">
                        <Icon />
                        <div>
                          <b>{f.result.model_name}</b>
                          <small>
                            {media[m].name} · {f.source}
                          </small>
                        </div>
                      </div>
                      <FindingDetail finding={f} />
                      {m !== "image" && (
                        <a className="text-link" href={root + "/" + m}>
                          Inspect {m}
                          <ChevronRight size={14} />
                        </a>
                      )}
                    </article>
                  );
                })}
            </div>
          </section>
          <section className="section prose">
            <h2>Evidence notes</h2>
            <p>
              {report.flagged_modalities.length
                ? "Flagged modalities: " +
                  report.flagged_modalities.join(", ") +
                  "."
                : "No modality returned an AI-GENERATED verdict."}{" "}
              {report.flagged_video_frames.length > 0 && (
                <a href={root + "/video"}>
                  {report.flagged_video_frames.length} flagged video samples
                  {" at "}
                  {report.flagged_video_frames
                    .map((f) => f.timestamp_seconds.toFixed(3) + " s")
                    .join(", ")}
                  .
                </a>
              )}
            </p>
            {report.not_supplied.length > 0 && (
              <p>Not supplied: {report.not_supplied.join(", ")}.</p>
            )}
            <p>{report.scope}</p>
          </section>
        </>
      )}
    </>
  );
}
