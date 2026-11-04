import { useRef, useState, type DragEvent } from "react";
import { UploadCloud, X, ScanLine, LoaderCircle } from "lucide-react";
import { media, modes, type Files } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Notice, icons } from "@/components/shared";
import { MediaPreview } from "@/components/MediaPreview";
export function Upload({
  files,
  setFiles,
  onAnalyze,
  busy,
  error,
}: {
  files: Files;
  setFiles: (v: Files) => void;
  onAnalyze: () => void;
  busy: boolean;
  error: string;
}) {
  const [problem, setProblem] = useState("");
  const [over, setOver] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  function add(list: File[]) {
    if (busy || !list.length) return;
    const next = { ...files };
    for (const file of list) {
      const ext = file.name.toLowerCase().split(".").pop() || "";
      const m = modes.find((m) =>
        (media[m].ext as readonly string[]).includes(ext),
      );
      if (!m) {
        setProblem("Unsupported file type. Choose a format listed below.");
        return;
      }
      if (!file.size || file.size > media[m].limit * 1024 ** 2) {
        setProblem(
          media[m].name +
            " files must be non-empty and at most " +
            media[m].limit +
            " MiB.",
        );
        return;
      }
      if (next[m]) {
        setProblem(
          "Only one " +
            m +
            " per investigation. Remove the selected file to replace it.",
        );
        return;
      }
      next[m] = file;
    }
    setFiles(next);
    setProblem("");
  }
  function drop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    add(Array.from(e.dataTransfer.files));
  }
  return (
    <>
      <h1>Media analysis</h1>
      <p className="lede">
        Add related files to one investigation. Each detector examines its own
        modality.
      </p>
      <section
        className={"dropzone " + (over ? "over" : "")}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
      >
        <UploadCloud size={34} />
        <h2>Drop evidence files here</h2>
        <p>Choose one image, video or audio file, or combine all three.</p>
        <input
          ref={picker}
          type="file"
          hidden
          multiple
          aria-label="Evidence files"
          accept={modes
            .flatMap((m) => media[m].ext.map((e) => "." + e))
            .join(",")}
          onChange={(e) => {
            add(Array.from(e.target.files || []));
            e.target.value = "";
          }}
        />
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() => picker.current?.click()}
        >
          Browse files
        </Button>
      </section>
      {(problem || error) && <Notice message={problem || error} />}
      <section className="section">
        <h2>Evidence selection</h2>
        <div className="selection">
          {modes.map((m) => {
            const Icon = icons[m],
              file = files[m];
            return (
              <div className="file-row" key={m}>
                <div className="file-head">
                  <Icon />
                  <div>
                    <b>{media[m].name}</b>
                    <small>
                      {media[m].ext.join(" · ").toUpperCase()} ·{" "}
                      {media[m].limit} MiB max
                    </small>
                  </div>
                  {file && (
                    <button
                      className="icon-button"
                      disabled={busy}
                      aria-label={"Remove " + m}
                      onClick={() => {
                        const next = { ...files };
                        delete next[m];
                        setFiles(next);
                        setProblem("");
                      }}
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
                {file && (
                  <>
                    <p className="filename">
                      {file.name} · {(file.size / 1024 ** 2).toFixed(2)} MiB
                    </p>
                    <MediaPreview file={file} kind={m} />
                  </>
                )}
              </div>
            );
          })}
        </div>
      </section>
      <div className="submit-bar">
        <span role="status">
          {busy
            ? "Processing on CPU. Keep this workspace open."
            : Object.keys(files).length + " of 3 files selected"}
        </span>
        <Button
          disabled={busy || !Object.keys(files).length}
          onClick={() => {
            setProblem("");
            onAnalyze();
          }}
        >
          {busy ? <LoaderCircle className="spin" /> : <ScanLine />}
          {busy ? "Analyzing…" : "Run analysis"}
        </Button>
      </div>
    </>
  );
}
