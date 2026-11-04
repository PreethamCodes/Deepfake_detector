"""Evaluate the existing detectors on a labelled folder of media.

Layout: ROOT/{image,video|videos,audio}/{real,fake}/<files>. The folder name is the ground truth.
Detectors run unchanged with their published decision rules; AI-GENERATED is the positive class.
Metrics count only samples that received a prediction. Failures are listed separately.
"""

import argparse
import csv
import ctypes
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from time import perf_counter, process_time

EXTENSIONS = {"image": {".jpg", ".jpeg", ".png"}, "video": {".mp4", ".mov", ".avi", ".mkv"},
              "audio": {".wav", ".mp3", ".flac"}}
FOLDERS = {"image": ["image"], "video": ["video", "videos"], "audio": ["audio"]}
LABELS = {"real": "REAL", "fake": "AI-GENERATED"}
SCOPE = ("Preliminary, manually curated test set. Not a formal benchmark: samples are few, were not drawn "
         "from a standard dataset protocol, and may differ between classes in format, resolution, source and "
         "watermarks. Results describe these files only and do not estimate real-world reliability.")


def peak_memory_mib() -> float | None:
    """Peak working set of this process on Windows, else None."""
    if sys.platform != "win32":
        return None

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

    counters = Counters(cb=ctypes.sizeof(Counters))
    kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return None
    return counters.PeakWorkingSetSize / 1024**2


def detectors():
    from truthscan.models.audio.detector import AASISTDetector
    from truthscan.models.image.detector import D3Detector
    from truthscan.models.video.detector import GenDDetector
    return {"image": D3Detector(), "video": GenDDetector(), "audio": AASISTDetector()}


def samples(root: Path, modality: str):
    for folder in FOLDERS[modality]:
        for label_dir, label in LABELS.items():
            directory = root / folder / label_dir
            if directory.is_dir():
                for path in sorted(directory.iterdir()):
                    if path.is_file():
                        yield path, label


def wilson(successes: int, n: int) -> list[float] | None:
    """95% Wilson score interval for a proportion."""
    if not n:
        return None
    z, p = 1.959964, successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def metrics(rows: list[dict]) -> dict:
    scored = [r for r in rows if r["prediction"]]
    tp = sum(r["truth"] == r["prediction"] == "AI-GENERATED" for r in scored)
    tn = sum(r["truth"] == r["prediction"] == "REAL" for r in scored)
    fp = sum(r["truth"] == "REAL" and r["prediction"] == "AI-GENERATED" for r in scored)
    fn = sum(r["truth"] == "AI-GENERATED" and r["prediction"] == "REAL" for r in scored)
    precision, recall = ratio(tp, tp + fp), ratio(tp, tp + fn)
    # F1 is 0 when both precision and recall are defined and zero; null when either is undefined.
    f1 = (None if precision is None or recall is None
          else round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0)
    times = [r["processing_time_ms"] for r in rows]
    warm = times[1:]
    return {
        "samples": len(rows),
        "real_samples": sum(r["truth"] == "REAL" for r in rows),
        "fake_samples": sum(r["truth"] == "AI-GENERATED" for r in rows),
        "scored": len(scored),
        "failed": len(rows) - len(scored),
        "coverage": ratio(len(scored), len(rows)),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        "accuracy": ratio(tp + tn, len(scored)),
        "accuracy_ci95": wilson(tp + tn, len(scored)),
        "precision": precision,
        "precision_ci95": wilson(tp, tp + fp),
        "recall": recall,
        "recall_ci95": wilson(tp, tp + fn),
        "specificity": ratio(tn, tn + fp),
        "f1": f1,
        "cold_start_ms": round(times[0], 1) if times else None,
        "warm_mean_ms": round(mean(warm), 1) if warm else None,
        "warm_median_ms": round(median(warm), 1) if warm else None,
        "warm_max_ms": round(max(warm), 1) if warm else None,
        "cpu_seconds_total": round(sum(r["cpu_seconds"] for r in rows), 2),
    }


def evaluate(root: Path, modalities: list[str]) -> dict:
    models = detectors()
    rows, peaks = [], {}
    for modality in modalities:
        peaks[modality] = None
        for path, truth in samples(root, modality):
            row = {"modality": modality, "file": path.relative_to(root).as_posix(), "truth": truth,
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16]}
            if path.suffix.lower() not in EXTENSIONS[modality]:
                rows.append(row | {"prediction": None, "error_code": "unsupported_extension",
                                   "processing_time_ms": 0.0, "cpu_seconds": 0.0})
                continue
            wall, cpu = perf_counter(), process_time()
            result = models[modality].detect(path)
            wall, cpu = (perf_counter() - wall) * 1000, process_time() - cpu
            data = result.model_dump(mode="json", exclude={"frames"})
            frames = getattr(result, "frames", None) or []
            row |= {
                "prediction": data.get("prediction"),
                "correct": None if data.get("prediction") is None else data["prediction"] == truth,
                "detection_score": data.get("detection_score"),
                "raw_score": data.get("raw_score"),
                "spoof_logit": data.get("spoof_logit"),
                "error_code": data.get("error_code"),
                "processing_time_ms": round(wall, 1),
                "detector_reported_ms": round(data["processing_time_ms"], 1),
                "cpu_seconds": round(cpu, 2),
                "cpu_cores_used": round(cpu / (wall / 1000), 2) if wall else None,
                "frames_sampled": len(frames) if modality == "video" else None,
                "frames_scored": sum(f.status == "scored" for f in frames) if modality == "video" else None,
                "frames_flagged": (sum(f.prediction == "AI-GENERATED" for f in frames)
                                   if modality == "video" else None),
            }
            rows.append(row)
            print(f"{modality:5} {truth:12} {str(row['prediction']):12} {row['processing_time_ms']:>9.1f} ms  "
                  f"{row['file']}", file=sys.stderr, flush=True)
        peak = peak_memory_mib()
        peaks[modality] = round(peak, 1) if peak else None
    by_modality = {m: metrics([r for r in rows if r["modality"] == m])
                   | {"process_peak_memory_mib_so_far": peaks[m]}
                   for m in modalities if any(r["modality"] == m for r in rows)}
    return {
        "scope": SCOPE,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "positive_class": "AI-GENERATED",
        "decision_rules": {
            "image": "D³ sigmoid score > 0.5 → AI-GENERATED (unchanged)",
            "video": "GenD mean score over scored faces > 0.5 → AI-GENERATED (unchanged, 8 samples at 512 px)",
            "audio": "AASIST bona fide logit > spoof logit → REAL (unchanged)",
        },
        "metric_notes": ("Metrics use scored samples only; failed samples count toward coverage, not the "
                         "confusion matrix. Precision, recall and F1 are null when undefined. CI95 are "
                         "Wilson score intervals. Times are wall-clock per call; the first call of each "
                         "detector includes model loading and is reported as cold start."),
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "processor": platform.processor(), "device": "CPU",
                        "peak_memory_note": "Process peak working set is cumulative in run order."},
        "metrics": by_modality,
        "samples": rows,
    }


def write_csv(path: Path, rows: list[dict]):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, nargs="?", default=Path("data/eval"))
    parser.add_argument("--out", type=Path, default=Path("docs/evaluation"))
    parser.add_argument("--modality", choices=list(EXTENSIONS), action="append")
    args = parser.parse_args()
    report = evaluate(args.root, args.modality or list(EXTENSIONS))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(args.out / "samples.csv", report["samples"])
    write_csv(args.out / "metrics.csv", [{"modality": m} | v for m, v in report["metrics"].items()])
    print(json.dumps(report["metrics"], indent=2))


if __name__ == "__main__":
    main()
