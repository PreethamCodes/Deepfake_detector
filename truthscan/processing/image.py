"""Bounded decoding and the D³ validation transform."""

from io import BytesIO
from pathlib import Path
from struct import error as StructError

from PIL import Image
from torchvision.transforms import Compose, Normalize, Resize, ToTensor

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 24_000_000
TRANSFORM = Compose([
    Resize((224, 224)),
    ToTensor(),
    Normalize((0.48145466, 0.4578275, 0.40821073),
              (0.26862954, 0.26130258, 0.27577711)),
])


class ImageInputError(ValueError):
    pass


def preprocess(path: Path):
    try:
        if not path.is_file():
            raise ImageInputError("Expected a readable image file.")
        with path.open("rb") as stream:
            encoded = stream.read(MAX_BYTES + 1)
        if len(encoded) > MAX_BYTES:
            raise ImageInputError("File exceeds the 20 MiB limit.")
        with Image.open(BytesIO(encoded)) as image:
            if image.format not in ("JPEG", "PNG"):
                raise ImageInputError("Unsupported format. Supply a JPEG or PNG.")
            if image.width * image.height > MAX_PIXELS:
                raise ImageInputError("Image exceeds the 24 megapixel limit.")
            if getattr(image, "is_animated", False):
                raise ImageInputError("Animated PNG is unsupported.")
            image.verify()
        with Image.open(BytesIO(encoded)) as image:
            return TRANSFORM(image.convert("RGB")).unsqueeze(0)
    except Image.DecompressionBombError as exc:
        raise ImageInputError("Image exceeds the pixel limit.") from exc
    except ImageInputError:
        raise
    except (OSError, SyntaxError, ValueError, StructError) as exc:
        raise ImageInputError("Unreadable, invalid or corrupted image.") from exc
