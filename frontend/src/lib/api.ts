export type Modality = "image" | "video" | "audio";
export type Verdict = "REAL" | "AI-GENERATED" | "INCONCLUSIVE";
export type Files = Partial<Record<Modality, File>>;
export interface Frame {
  index: number;
  timestamp_seconds: number;
  status: "scored" | "no_face";
  prediction: Verdict | null;
  detection_score: number | null;
}
export interface Finding {
  source: string;
  result: {
    model_name: string;
    prediction: Verdict | null;
    processing_time_ms?: number;
    detection_score?: number | null;
    raw_score?: number | null;
    spoof_logit?: number;
    warning?: string;
    error?: string;
    error_code?: string;
    frames?: Frame[];
    metadata?: Record<string, string | number> | null;
  };
}
export interface Summary {
  analysis_id: string;
  status: "completed" | "partial" | "failed";
  created_at: string;
  processing_time_ms: number;
}
export interface Entry extends Summary {
  assessment: Verdict;
  modalities: Modality[];
}
export interface Analysis extends Summary {
  report: {
    assessment: Verdict;
    agreement: string;
    reason: string;
    findings: Partial<Record<Modality, Finding>>;
    not_supplied: Modality[];
    flagged_modalities: Modality[];
    flagged_video_frames: { index: number; timestamp_seconds: number }[];
    scope: string;
  };
}
async function request<T>(
  path: string,
  init?: RequestInit,
  savedFailure = false,
): Promise<T> {
  const timer = AbortSignal.timeout(init?.method === "POST" ? 900_000 : 12_000);
  let res: Response;
  try {
    res = await fetch(path, { ...init, signal: timer });
  } catch {
    throw new Error(
      timer.aborted
        ? "The request timed out. Check history before submitting again."
        : "Cannot reach the backend. Check that FastAPI is running and retry.",
    );
  }
  const body = await res.json().catch(() => null);
  if (!res.ok && !(savedFailure && body?.data?.report && body.data.analysis_id))
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "The backend could not complete this request. Check the service and retry.",
    );
  if (!body?.data)
    throw new Error("The backend returned an unexpected response.");
  return body.data;
}
export const api = {
  health: () => request<{ status: "ok" }>("/health"),
  history: () => request<Entry[]>("/api/v1/results?limit=100"),
  result: (id: string) =>
    request<Analysis>("/api/v1/results/" + encodeURIComponent(id)),
  submit: (files: Files) => {
    const body = new FormData();
    for (const [name, file] of Object.entries(files)) body.append(name, file);
    return request<Analysis>("/api/v1/analyze", { method: "POST", body }, true);
  },
};
export const media = {
  image: { name: "Image", model: "D³", ext: ["jpg", "jpeg", "png"], limit: 20 },
  video: {
    name: "Video",
    model: "GenD",
    ext: ["mp4", "mov", "avi", "mkv"],
    limit: 256,
  },
  audio: {
    name: "Audio",
    model: "AASIST",
    ext: ["wav", "flac", "mp3"],
    limit: 64,
  },
} as const;
export const modes: Modality[] = ["image", "video", "audio"];
export const time = (ms?: number) =>
  ms == null ? "Unavailable" : (ms / 1000).toFixed(2) + " s";
export const date = (s: string) =>
  new Date(s).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
