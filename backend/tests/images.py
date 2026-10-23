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


def jpeg_with_corrupted_exif(offset: int, value: int) -> bytes:
    """JPEG válido cujo EXIF (orientação + GPS) tem UM byte adulterado.

    Alguns desses bytes fazem o `ImageOps.exif_transpose` do Pillow lançar TypeError, struct.error ou
    AttributeError em vez de ValueError/OSError; foram achados por fuzzing. `offset` conta a partir do
    cabeçalho TIFF do EXIF.
    """
    exif = Image.Exif()
    exif[0x0112] = 6
    exif[0x010F] = "Make"
    gps = exif.get_ifd(0x8825)
    gps[1] = "N"
    gps[2] = (1.0, 2.0, 3.0)
    data = bytearray(encode(two_halves(300, 200), "JPEG", exif=exif.tobytes(), quality=90))
    data[data.index(b"Exif\x00\x00") + 6 + offset] = value
    return bytes(data)


def gray16_ramp(side: int = 128) -> bytes:
    """PNG de 16 bits em tons de cinza: preto à esquerda, branco à direita."""
    image = Image.new("I;16", (side, side))
    image.putdata([round(x * 65535 / (side - 1)) for _ in range(side) for x in range(side)])
    return encode(image, "PNG")


def close(pixel, target, tolerance: int = 60) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(pixel[:3], target))
