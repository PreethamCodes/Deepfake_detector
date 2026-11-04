"""Bound multipart ingress before passing local files to the detectors."""

from pathlib import Path, PureWindowsPath
from shutil import copyfileobj

from fastapi import HTTPException, Request
from starlette.datastructures import FormData
from starlette.formparsers import MultiPartException, MultiPartParser

from truthscan.processing.limits import AUDIO_BYTES, IMAGE_BYTES, VIDEO_BYTES

EXTENSIONS = {"image": {".jpg", ".jpeg", ".png"}, "video": {".mp4", ".mov", ".avi", ".mkv"},
              "audio": {".wav", ".mp3", ".flac"}}
LIMITS = {"image": IMAGE_BYTES, "video": VIDEO_BYTES, "audio": AUDIO_BYTES}
BODY_LIMIT = sum(LIMITS.values()) + 64 * 1024


class UploadParser(MultiPartParser):
    """Use Starlette spooling, enforcing file limits as each part arrives."""

    complete = False

    def on_headers_finished(self):
        super().on_headers_finished()
        name = self._current_part.field_name
        if name not in LIMITS or any(key == name for key, _ in self.items):
            raise HTTPException(422, "Supply at most one file per image, video or audio field.")
        self.part_limit = LIMITS[name]
        self.part_bytes = 0

    def on_part_data(self, data, start, end):
        self.part_bytes += end - start
        if self.part_bytes > self.part_limit:
            raise HTTPException(413, "File exceeds the upload limit for its modality.")
        super().on_part_data(data, start, end)

    def on_end(self):
        self.complete = True


async def read_uploads(request: Request) -> FormData:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise HTTPException(415, "Use multipart/form-data with image, video or audio files.")
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isascii() or not declared.isdigit() or len(declared) > 20:
            raise HTTPException(400, "Invalid Content-Length.")
        if int(declared) > BODY_LIMIT:
            raise HTTPException(413, "Request exceeds the total upload limit.")

    async def bounded_stream():
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > BODY_LIMIT:
                raise HTTPException(413, "Request exceeds the total upload limit.")
            yield chunk
        # Raising inside parse also closes unfinished spooled files on truncation.
        if not parser.complete:
            raise HTTPException(400, "Incomplete multipart upload.")

    parser = UploadParser(request.headers, bounded_stream(), max_files=3, max_fields=0)
    try:
        form = await parser.parse()
    except MultiPartException:
        raise HTTPException(400, "Invalid multipart data. Supply up to three file fields.") from None
    if not form:
        raise HTTPException(422, "Supply at least one image, video or audio file.")
    return form


def signature_matches(ext: str, header: bytes) -> bool:
    if ext in (".jpg", ".jpeg"):
        return header.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".mkv":
        return header.startswith(b"\x1a\x45\xdf\xa3")
    if ext == ".avi":
        return header[:4] == b"RIFF" and header[8:12] == b"AVI "
    if ext == ".wav":
        return header[:4] in (b"RIFF", b"RF64", b"BW64", b"RIFX") and header[8:12] == b"WAVE"
    if ext == ".mp3":
        return header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 255 and header[1] & 224 == 224)
    if ext == ".flac":
        return header.startswith((b"fLaC", b"ID3"))
    return header[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot")


def save_uploads(form: FormData, directory: Path) -> dict[str, Path]:
    paths = {}
    for modality, upload in form.multi_items():
        # Only use the allowlisted suffix. Client filenames never enter paths or reports.
        ext = PureWindowsPath(upload.filename or "").suffix.lower()
        if ext not in EXTENSIONS[modality]:
            raise HTTPException(415, f"Unsupported {modality} filename extension.")
        header = upload.file.read(16)
        if not header:
            raise HTTPException(422, f"The {modality} file is empty.")
        if not signature_matches(ext, header):
            raise HTTPException(415, f"The {modality} file signature does not match its extension.")
        path = directory / (modality + ext)
        with path.open("xb") as out:
            out.write(header)
            copyfileobj(upload.file, out, length=1024 * 1024)
        paths[modality] = path
    return paths
