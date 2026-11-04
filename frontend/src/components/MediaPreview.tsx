import { useEffect, useState, type RefObject } from "react";
import type { Modality } from "@/lib/api";
export function MediaPreview({
  file,
  kind,
  videoRef,
}: {
  file: File;
  kind: Modality;
  videoRef?: RefObject<HTMLVideoElement | null>;
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState(false);
  useEffect(() => {
    const next = URL.createObjectURL(file);
    setUrl(next);
    setError(false);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  if (!url) return null;
  if (error)
    return (
      <p className="hint">
        This browser cannot preview this codec. The backend checks the file
        separately.
      </p>
    );
  if (kind === "image")
    return (
      <img
        className="preview"
        src={url}
        alt="Selected image"
        onError={() => setError(true)}
      />
    );
  if (kind === "video")
    return (
      <video
        ref={videoRef}
        className="preview"
        src={url}
        controls
        preload="metadata"
        playsInline
        onError={() => setError(true)}
      />
    );
  return (
    <audio
      src={url}
      controls
      preload="metadata"
      onError={() => setError(true)}
    />
  );
}
