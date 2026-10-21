"""Imagens geradas em memória para os testes de envio de foto (nenhum arquivo no repositório)."""
from __future__ import annotations

import io
import os

from PIL import Image

RED, BLUE = (220, 30, 30), (30, 30, 220)


def encode(image: Image.Image, fmt: str = "PNG", **options) -> bytes:
    out = io.BytesIO()
    image.save(out, fmt, **options)
    return out.getvalue()


def two_halves(width: int, height: int, *, vertical: bool = False, mode: str = "RGB") -> Image.Image:
    """Metade vermelha e metade azul (esquerda/direita, ou em cima/embaixo com vertical=True)."""
    image = Image.new(mode, (width, height), RED)
    box = (0, height // 2, width, height) if vertical else (width // 2, 0, width, height)
    image.paste(BLUE, box)
    return image


def noise(width: int, height: int) -> Image.Image:
    return Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))


def jpeg_with_exif(width: int = 300, height: int = 300, *, orientation: int | None = None, marker: str = "") -> bytes:
    image = two_halves(width, height)
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation
    if marker:
        exif[0x013B] = marker  # Artist
        exif[0x010F] = marker  # Make
    return encode(image, "JPEG", exif=exif.tobytes(), quality=90)


def close(pixel, target, tolerance: int = 60) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(pixel[:3], target))
