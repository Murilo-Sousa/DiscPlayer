"""Foto de perfil enviada pela pessoa: validação, reprocessamento e armazenamento.

O arquivo enviado NUNCA é guardado nem servido como veio. O servidor:

  1. identifica o formato pelo CONTEÚDO (JPEG, PNG ou WebP), ignorando o nome do
     arquivo e o Content-Type declarados pelo navegador;
  2. recusa imagens com dimensões absurdas antes de decodificá-las (bombas de
     descompressão: um PNG minúsculo pode descomprimir para gigabytes);
  3. aplica a rotação do EXIF, recorta um quadrado central e reduz para no máximo
     256 x 256;
  4. grava uma imagem NOVA em WebP. Como o arquivo original não é reaproveitado,
     metadados (localização GPS, modelo da câmera etc.) e qualquer dado escondido
     no arquivo não sobrevivem.

A imagem fica no próprio SQLite (tabela `user_avatars`) e é entregue em
`/api/avatars/<token>`. O token é aleatório e muda a cada troca de foto, então a
resposta pode ser guardada em cache para sempre.
"""
from __future__ import annotations

import io
import secrets
import sqlite3
import warnings

from ..db import execute, fetch_one, transaction
from ..errors import ApiError
from ..utils.dates import utcnow_iso

ALLOWED_FORMATS = ("JPEG", "PNG", "WEBP")
MAX_PIXELS = 25_000_000  # ~5000 x 5000: cobre as câmeras de celular e barra as bombas
MIN_SIDE = 64
OUTPUT_SIDE = 256
MAX_STORED_BYTES = 256 * 1024  # a mesma conta do CHECK da tabela
_QUALITIES = (85, 70, 50)
TOKEN_BYTES = 16
_TOO_BIG = f"A imagem é grande demais. Use uma foto de até {MAX_PIXELS // 1_000_000} megapixels."
_HIGH_BIT_GRAY = ("I", "I;16", "I;16L", "I;16B", "I;16N")


def _invalid(message: str, status: int = 422) -> ApiError:
    return ApiError(status, "invalid_image", "Revise a foto escolhida.", fields={"file": message})


def process_image(raw: bytes) -> bytes:
    """Valida e reprocessa a imagem enviada. Devolve os bytes de um WebP quadrado."""
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # dependência instalada com `pip install -r requirements.txt`
        raise ApiError(
            503,
            "image_support_missing",
            "O envio de fotos está indisponível: falta instalar o Pillow no servidor.",
        ) from exc

    if not raw:
        raise _invalid("O arquivo está vazio.")

    try:
        # Um aviso de "possível bomba de descompressão" do Pillow vira erro.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw), formats=ALLOWED_FORMATS)
            width, height = image.size  # só lê o cabeçalho
            if width * height > MAX_PIXELS:
                raise _invalid(_TOO_BIG)
            if min(width, height) < MIN_SIDE:
                raise _invalid(f"A imagem é pequena demais. Use uma foto de pelo menos {MIN_SIDE} x {MIN_SIDE} pixels.")
            if image.format == "JPEG":
                # O decodificador já entrega a imagem reduzida: usa muito menos memória.
                image.draft("RGB", (OUTPUT_SIDE * 2, OUTPUT_SIDE * 2))
            image.load()  # decodifica tudo agora (arquivo truncado ou corrompido falha aqui)
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:  # noqa: BLE001 - EXIF corrompido (TypeError, struct.error...): segue sem girar
                pass
            if image.mode in _HIGH_BIT_GRAY:
                # Cinza de 16 bits: converter direto cortaria tudo acima de 255 (a foto ficaria branca).
                image = image.point(lambda value: value * (1 / 256))
            image = image.convert("RGBA" if has_alpha else "RGB")
    except ApiError:
        raise
    except (MemoryError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise _invalid(_TOO_BIG) from None
    except Exception:  # noqa: BLE001 - o Pillow lança tipos variados diante de arquivos corrompidos
        raise _invalid("Não foi possível ler este arquivo. Envie uma imagem JPG, PNG ou WebP.") from None

    side = min(image.size)
    left, top = (image.width - side) // 2, (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    if side > OUTPUT_SIDE:
        image = image.resize((OUTPUT_SIDE, OUTPUT_SIDE), Image.LANCZOS)

    for quality in _QUALITIES:
        out = io.BytesIO()
        image.save(out, "WEBP", quality=quality, method=4)  # sem exif/icc: nada do original é copiado
        if out.tell() <= MAX_STORED_BYTES:
            return out.getvalue()
    raise _invalid("Não conseguimos reduzir esta imagem o bastante. Tente outra foto.")


def _public_path(token: str) -> str:
    return f"/api/avatars/{token}"


def set_avatar(user_id: int, raw: bytes) -> str:
    """Troca a foto do usuário e devolve o novo endereço (também gravado em users.avatar_url)."""
    data = process_image(raw)  # trabalho pesado fora da transação de escrita
    token = secrets.token_urlsafe(TOKEN_BYTES)
    with transaction():
        execute("DELETE FROM user_avatars WHERE user_id = ?", (user_id,))
        execute(
            "INSERT INTO user_avatars (user_id, token, data, updated_at) VALUES (?, ?, ?, ?)",
            (user_id, token, data, utcnow_iso()),
        )
        execute("UPDATE users SET avatar_url = ? WHERE id = ?", (_public_path(token), user_id))
    return _public_path(token)


def remove_avatar(user_id: int) -> None:
    with transaction():
        execute("DELETE FROM user_avatars WHERE user_id = ?", (user_id,))
        execute("UPDATE users SET avatar_url = NULL WHERE id = ?", (user_id,))


def get_by_token(token: str) -> sqlite3.Row | None:
    return fetch_one("SELECT data FROM user_avatars WHERE token = ?", (token,))
