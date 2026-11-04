# SHODHA AI — Phase 8 preliminary evaluation

> **Scope.** This is a *preliminary, manually curated* test of 37 files. It is **not a formal benchmark**. The samples are few, were not drawn under a standard dataset protocol, and differ between classes in format, resolution, source and watermarking. The numbers below describe these files only. They do not estimate real-world detection reliability and must not be quoted as model accuracy.

Run date: 4 November 2026 · CPU only (Windows 11, Intel64 Family 6 Model 186, Python 3.11.15) · Detectors, weights and decision thresholds unchanged.

Artifacts in this folder:

| File | Contents |
| --- | --- |
| `results.json` | Full run: scope, decision rules, environment, per-modality metrics, per-sample results |
| `metrics.csv` | One row per modality: confusion matrix, metrics with 95% intervals, timing, CPU |
| `samples.csv` | One row per file: label, prediction, original scores, error code, timing, CPU, frame counts |
| `control-fake-images-as-jpeg/` | Same three files for the image-format control described below |

Reproduce with:

```powershell
uv run --locked --all-extras python -m truthscan.evaluation data/eval --out docs/evaluation
```

## 1. Evaluation media

Ground truth is the folder name (`real` → REAL, `fake` → AI-GENERATED). The evaluator also accepts the `videos/` folder name used here. The sources are inferred from file names and should be confirmed by the curator.

| Modality | Real | Fake | Formats | Apparent sources |
| --- | --- | --- | --- | --- |
| Image | 10 | 10 | Real: JPEG RGB, 375–640 px, 0.06–0.34 MB. Fake: PNG RGBA 2752×1536 (9), PNG RGB 880×1168 (1), 1.4–10.9 MB | Real: COCO-style file names. Fake: Google Gemini (9), Kling (1) |
| Video | 5 | 4 | All H.264 MP4. Real: 1080p–4K stock footage, 5.5–21.7 s, no audio. Fake: 480×854 or 720p, 3–10 s | Real: stock-footage IDs (Pexels-style). Fake: Magic Hour (2), Gemini (2) |
| Audio | 3 | 5 | All MP3 | Real: recordings named like Wikimedia Commons uploads. Fake: voicemaker.in TTS |

### Validation

| Check | Result |
| --- | --- |
| Files counted | 37 (20 image, 9 video, 8 audio) |
| Readable | All 20 images decode fully with Pillow. All 17 videos and audio files probe cleanly with FFprobe. The FFmpeg CLI decoded 7 of 9 videos end to end with no errors (the check was stopped before the last two). The project's processors decode the full stream before scoring, and did so without error for every video except one (below) and for all audio |
| Supported by the detectors | Every extension and container is within the allowlists (JPG/PNG, MP4, MP3). Every file is within the size, pixel (≤ 24 MP image, ≤ 3840×2160 video) and duration limits |
| Duplicates | No byte-identical files. The two 480×854 fakes are different people (frame PSNR 14.7 dB) |
| Labels preserved | Labels come only from folder names and are recorded with a SHA-256 prefix per file in `samples.csv` |

### Unsuitable or problematic samples

Nothing was excluded. These samples are kept and flagged, so the metrics include them:

| Sample | Issue | Effect |
| --- | --- | --- |
| `videos/real/7263179-uhd_2160_3840_24fps.mp4` | A valid file (FFmpeg decodes all 240 frames), but the project's PyAV decoder fails with `avcodec_send_packet()` on this 2160×3840 High@5.2 stream | `invalid_video`. Counted as a failure, not a prediction. This is a **processor limitation**, not data corruption |
| `videos/fake/gemini_generated_video_fc983235.mp4` | Hot-air-balloon scene with no face | `no_faces`. GenD analyses faces only, so this sample is out of scope |
| `videos/real/*` (crowds) | Small, distant or profile faces in group scenes | Outside GenD's close-up face domain (see §3) |
| `videos/fake/*` | Visible "Magic Hour" and Gemini watermarks; fully generated video rather than face swaps | Watermarks are a class-specific artefact. GenD targets face manipulation |
| `audio/real/English_male_voice_speech_word_No.mp3` | 0.36 s single word | AASIST repeat-pads it to 4.04 s. Correct (REAL), but by a very small margin (+1.12 logit) |
| `audio/real/Gloria_patri.mp3` | Liturgical recitation, possibly chanted rather than conversational | Misclassified (see §3) |
| All image pairs | Real images are small JPEGs; fakes are large PNGs, 9 of them RGBA | A **format/resolution confound**. Tested with a control in §4 |

## 2. Results

Positive class: AI-GENERATED. The metrics count only samples that received a prediction. Coverage is the share of samples that received one. 95% intervals are Wilson score intervals, and their width reflects the very small sample counts.

| Modality | Detector | Scored / total | TP | TN | FP | FN | Accuracy (95% CI) | Precision | Recall | Specificity | F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Image | D³ | 20 / 20 | 9 | 9 | 1 | 1 | 0.90 (0.70–0.97) | 0.90 | 0.90 | 0.90 | 0.90 |
| Video | GenD | 7 / 9 | 0 | 0 | 4 | 3 | 0.00 (0.00–0.35) | 0.00 | 0.00 | 0.00 | 0.00 |
| Audio | AASIST | 8 / 8 | 5 | 2 | 1 | 0 | 0.875 (0.53–0.98) | 0.83 | 1.00 | 0.67 | 0.91 |

Each detector ran over the whole set twice, and both runs produced identical predictions and scores.

Misclassifications:
- **Image FP:** `000000000139.jpg`, D³ score 0.726.
- **Image FN:** `Gemini_Generated_Image_2xx9…png`, score 0.296. All other fakes scored 0.888–0.9999.
- **Video FPs:** all four scored real clips, with mean frame scores 0.570–0.702. 4–7 of 8 frames were flagged in each.
- **Video FNs:** all three scored fakes, with scores 0.109–0.372. 0 or 1 of 8 frames were flagged in each.
- **Audio FP:** `Gloria_patri.mp3`, bona fide logit −3.61 against spoof logit +3.66.

## 3. Interpretation

- **Image (D³).** Separation was strong on this set, but see §4: part of the measured performance depends on the format and resolution gap between the classes.
- **Video (GenD).** The result is inverted: every real clip was flagged and every fake passed. This does not show that GenD performs below chance in general. The test set falls outside what GenD is designed for:
  - The fakes are fully generated videos (Magic Hour, Gemini) rather than face swaps or reenactments of real footage.
  - The real clips are 4K group scenes whose faces become small after sampling to 512 px.
  - GenD's published evaluation covers close-up face-manipulation benchmarks.

  What this does show is that the video verdict should not be trusted on fully synthetic or crowd footage. The UI and README must say so.
- **Audio (AASIST).** All five TTS clips were caught. The only miss is a recitation that may be chanted, and that kind of audio is outside AASIST's ASVspoof 2019 training domain. With three real samples, specificity (0.67) means very little.
- **Fusion** was not evaluated. The set has no related image, video and audio triples from the same case.

## 4. Control: does D³ depend on the image format?

The 10 fake PNGs were re-encoded as JPEG (FFmpeg MJPEG, quality 3, 4:2:0) and downscaled to a 640 px long side to match the real COCO images. The control copies were kept outside the repository and the originals were not modified.

| Fake set | Detected as AI-GENERATED | Recall |
| --- | --- | --- |
| Original PNGs | 9 / 10 | 0.90 |
| JPEG, 640 px | 6 / 10 | 0.60 |

Three Gemini images dropped from scores of 0.976–0.999 to 0.031–0.123. D³'s detection on this set is therefore sensitive to compression and resolution, and the 0.90 figure overstates how it would perform on fakes that have been re-shared (and so re-compressed). Results are in `control-fake-images-as-jpeg/`.

## 5. Processing time and CPU

Wall-clock time per `detect()` call, including decoding and preprocessing. The first call of each detector also loads its model and is reported separately as cold start. CPU cores = process CPU time ÷ wall time.

| Modality | Cold start | Warm median | Warm mean | Warm max | CPU cores used (typical) | Process peak memory (cumulative) |
| --- | --- | --- | --- | --- | --- | --- |
| Image (D³) | 5.9 s | 2.30 s | 2.42 s | 2.97 s | ≈ 12 | 1.78 GB |
| Video (GenD, 8 frames) | 36.5 s* | 12.9 s | 15.7 s | 36.5 s | 5–14 | 3.09 GB |
| Audio (AASIST) | 0.85 s | 0.45 s | 0.46 s | 0.61 s | ≈ 12 | 3.20 GB |

\* The first video was also a 19 s 1080p clip. Video time depends mainly on the source length and resolution, because every frame is decoded: 4K clips took 22.8–36.5 s and 3–10 s clips at 480×854 or 720p took 12.1–13.6 s. The two failures returned within 0.3 s and 1.2 s.

API overhead was not measured here. The Phase 7 browser runs showed it is small compared with inference: an image-plus-video case took 53.7 s cold through the full UI and API path.

## 6. Limitations of this evaluation

1. **Sample size.** 8–20 files per modality. The confidence intervals span roughly 30–45 percentage points.
2. **Confounds between classes.** Format, resolution, source and watermarks all differ between real and fake, so a detector can be right for the wrong reason (§4).
3. **Out-of-scope video.** The fakes are fully generated video, not face manipulation, and the real clips are crowd footage.
4. **No threshold tuning.** None was done, so there is no separate tuning split. Every number is a test on unchanged rules.
5. **Not representative.** No standard protocol (e.g. FaceForensics++, Celeb-DF, ASVspoof, GenImage) was followed. The results do not generalise to other media.

## 7. Recommendations before any public metric claim

- Match formats between classes, e.g. JPEG for both, or report per-format results.
- Use a formal held-out set per modality, with at least 100 files per class where CPU time allows:
  - images: COCO or RAISE real photos alongside Synthbuster or GenImage fakes;
  - video: Celeb-DF v2 or the DFDC sample, which are face-manipulation benchmarks GenD is designed for;
  - audio: ASVspoof 2019 LA eval and In-the-Wild.
- Report fully generated video separately from face manipulation, and state in the app that GenD covers faces only.
- Investigate the PyAV decode failure on 2160×3840 High@5.2 H.264 as a separate processing bug.
