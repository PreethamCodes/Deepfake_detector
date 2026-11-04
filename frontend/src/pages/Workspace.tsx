import { useState } from "react";
import {
  ArrowRight,
  Cpu,
  Layers3,
  Plus,
  ScanLine,
  Search,
  Target,
  TriangleAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Badge,
  CaseTable,
  ScanPlate,
  tone,
  verdicts,
} from "@/components/shared";
import { type Entry, media, modes } from "@/lib/api";
export function Dashboard({ entries }: { entries: Entry[] | null }) {
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">SHODHA AI</span>
          <h1>Uncovering the truth behind digital media</h1>
          <p>
            Examine images, video and speech for signs of synthetic media, then
            trace every assessment back to the detectors that produced it.
          </p>
          <Button asChild>
            <a href="#/analyze">
              <Plus size={18} />
              New analysis
            </a>
          </Button>
        </div>
        <ScanPlate />
      </section>
      <section className="section">
        <div className="section-title">
          <h2>Archive overview</h2>
          <span className="muted">Latest 100 reports</span>
        </div>
        <div className="metrics">
          <div>
            <span>Stored analyses</span>
            <strong>{entries?.length ?? "—"}</strong>
          </div>
          {verdicts.map((v) => (
            <div key={v}>
              <Badge value={v} />
              <strong>
                {entries
                  ? entries.filter((e) => e.assessment === v).length
                  : "—"}
              </strong>
            </div>
          ))}
        </div>
        {entries && entries.length > 0 && <Distribution entries={entries} />}
      </section>
      <section className="section">
        <div className="section-title">
          <h2>Recent investigations</h2>
          <a className="text-link" href="#/history">
            View history <ArrowRight size={15} />
          </a>
        </div>
        {entries ? (
          <CaseTable entries={entries.slice(0, 5)} />
        ) : (
          <p className="empty">Waiting for archive data.</p>
        )}
      </section>
    </>
  );
}
function Distribution({ entries }: { entries: Entry[] }) {
  // Share of stored assessments; counts come straight from the archive.
  return (
    <div className="distribution">
      <div
        className="distribution-bar"
        role="img"
        aria-label={verdicts
          .map((v) => v + " " + entries.filter((e) => e.assessment === v).length)
          .join(", ")}
      >
        {verdicts.map((v) => {
          const n = entries.filter((e) => e.assessment === v).length;
          return n ? (
            <span
              key={v}
              className={tone(v)}
              style={{ flexGrow: n }}
              title={v + ": " + n}
            />
          ) : null;
        })}
      </div>
      <span className="muted">
        Cases by modality ·{" "}
        {modes
          .map(
            (m) =>
              media[m].name +
              " " +
              entries.filter((e) => e.modalities.includes(m)).length,
          )
          .join(" · ")}
      </span>
    </div>
  );
}
export function History({ entries }: { entries: Entry[] | null }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All assessments");
  const visible = (entries ?? []).filter(
    (e) =>
      e.analysis_id.toLowerCase().includes(query.toLowerCase().trim()) &&
      (filter === "All assessments" || e.assessment === filter),
  );
  return (
    <>
      <h1>Investigation history</h1>
      <p className="lede">Review saved reports from the local archive.</p>
      <div className="filters">
        <label>
          <Search size={17} />
          <input
            aria-label="Search by analysis ID"
            placeholder="Search by analysis ID"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <select
          aria-label="Filter assessment"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          {["All assessments", ...verdicts].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
      </div>
      {entries ? (
        <CaseTable entries={visible} />
      ) : (
        <p className="empty">Waiting for archive data.</p>
      )}
    </>
  );
}
const pipeline = [
  ["Browser", "React workspace selects related image, video and speech files."],
  ["FastAPI", "Validates type, signature and size, then stores files privately."],
  ["Detectors", "D³, GenD and AASIST run independently on CPU."],
  ["Fusion", "Compares labels for agreement or conflict without averaging scores."],
  ["Report", "SQLite keeps the sanitized report. Source media is deleted."],
];
export function About() {
  return (
    <>
      <div className="hero">
        <div className="hero-copy">
          <span className="eyebrow">About</span>
          <h1>SHODHA AI</h1>
          <p>
            Uncovering the Truth Behind Digital Media. A multimodal deepfake
            detection and digital-forensics workspace.
          </p>
        </div>
        <ScanPlate />
      </div>
      <section className="section prose">
        <h2>
          <Search /> The problem
        </h2>
        <p>
          Generated images, face-swapped video and cloned voices can be
          difficult to distinguish by eye or ear. They are used for fraud,
          impersonation and misinformation, and a single detector rarely covers
          every kind of media in a case.
        </p>
      </section>
      <section className="section prose">
        <h2>
          <Target /> Objective
        </h2>
        <p>
          SHODHA (शोध, “investigation”) brings three specialised detectors
          into one case. Each assessment stays traceable to the model, score
          and sample that produced it, so an investigator can review the
          evidence instead of trusting a single number.
        </p>
      </section>
      <section className="section prose">
        <h2>
          <Cpu /> Detection technologies
        </h2>
        <div className="rules">
          {modes.map((m) => (
            <div key={m}>
              <b>{media[m].model}</b>
              <span>
                {
                  {
                    image:
                      "Image. Scores the whole still with a CLIP ViT-L/14 encoder and a discrepancy-trained head (CVPR 2025).",
                    video:
                      "Video. Scores the largest detected face in sampled frames with a CLIP-L/14 classifier (WACV 2026).",
                    audio:
                      "Speech. A spectro-temporal graph attention network compares bona fide and spoof logits over the opening 4.04 seconds.",
                  }[m]
                }
              </span>
            </div>
          ))}
        </div>
      </section>
      <section className="section prose">
        <h2>
          <Layers3 /> System architecture
        </h2>
        <ol className="pipeline">
          {pipeline.map(([name, text], i) => (
            <li key={name}>
              <span>{String(i + 1).padStart(2, "0")}</span>
              <b>{name}</b>
              <small>{text}</small>
            </li>
          ))}
        </ol>
        <p>
          Fusion keeps a shared label when detectors agree and returns
          INCONCLUSIVE when they conflict or a requested detector fails. The
          archive retains the latest 100 reports.
        </p>
      </section>
      <section className="section prose">
        <h2>
          <TriangleAlert /> Limitations
        </h2>
        <ul className="limits">
          <li>
            Detector scores are uncalibrated and have different meanings, so no
            overall confidence is calculated.
          </li>
          <li>
            GenD examines faces only. Sampled frames can miss short
            manipulations, and videos without a visible face cannot be scored.
          </li>
          <li>
            AASIST examines the first 4.04 seconds of speech and was trained
            on ASVspoof 2019, so newer voice-cloning systems may evade it.
          </li>
          <li>
            Accuracy on media outside each model’s training distribution is not
            established. A flagged sample can be genuine.
          </li>
        </ul>
      </section>
      <section className="section prose">
        <h2>
          <ScanLine /> Responsible use
        </h2>
        <p>
          Media authenticity and factual truth are different questions. A REAL
          label does not make a claim true, and an AI-GENERATED label does not
          make it false. Consider the source and corroborating evidence before
          drawing conclusions about a person, event or claim.
        </p>
      </section>
    </>
  );
}
