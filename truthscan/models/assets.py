import hashlib
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.request import urlopen


def verify(path: Path, digest: str) -> None:
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != digest:
        raise ValueError(f"SHA-256 mismatch for {path.name}")


def install_assets(directory: Path, assets: dict[str, tuple[str, str]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in assets.items():
        target = directory / name
        if target.exists():
            verify(target, digest)
            continue
        with NamedTemporaryFile(dir=directory, delete=False) as temp:
            partial = Path(temp.name)
        try:
            with urlopen(url, timeout=120) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output)
            verify(partial, digest)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
