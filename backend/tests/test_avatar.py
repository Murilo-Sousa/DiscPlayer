"""Foto de perfil enviada como imagem: validação, reprocessamento, entrega e privacidade."""
from __future__ import annotations

import io
import sys
import warnings

import pytest
from PIL import Image, ImageOps

from app import create_app
from app import db as database

from . import images
from .conftest import HADES, Api

UPLOAD = "/api/auth/me/avatar"


def webp(raw: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(raw))
    assert image.format == "WEBP"
    return image


def upload_ok(client, file, **kw):
    response = client.upload(UPLOAD, file, **kw)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["user"]


def stored_rows(app):
    raw = database.connect(app.config["DATABASE"])
    try:
        return raw.execute("SELECT user_id, token, length(data) AS size FROM user_avatars").fetchall()
    finally:
        raw.close()


# ------------------------------------------------------------------ envio e entrega
def test_upload_returns_an_internal_address_and_the_image_is_served(ana, api):
    user = upload_ok(ana, images.encode(images.two_halves(600, 600), "JPEG"))
    assert user["avatar_url"].startswith("/api/avatars/")
    assert ana.get("/api/auth/me").get_json()["user"]["avatar_url"] == user["avatar_url"]

    response = api.get(user["avatar_url"])  # visitantes também veem a foto
    assert response.status_code == 200
    assert response.mimetype == "image/webp"
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in response.headers["Content-Security-Policy"]
    image = webp(response.data)
    assert image.size == (256, 256)


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_jpeg_png_and_webp_are_accepted(ana, api, fmt):
    user = upload_ok(ana, images.encode(images.two_halves(300, 300), fmt))
    assert webp(api.get(user["avatar_url"]).data).size == (256, 256)


def test_the_stored_file_is_a_new_webp_never_the_original(ana, api, app):
    original = images.encode(images.two_halves(400, 400), "PNG")
    user = upload_ok(ana, original)
    served = api.get(user["avatar_url"]).data
    assert served[:4] == b"RIFF" and served[8:12] == b"WEBP"
    assert served != original and not served.startswith(b"\x89PNG")
    [row] = stored_rows(app)
    assert row["size"] == len(served) <= 256 * 1024


def test_non_square_images_are_cropped_around_the_center(ana, api):
    user = upload_ok(ana, images.encode(images.two_halves(400, 200), "PNG"))
    image = webp(api.get(user["avatar_url"]).data).convert("RGB")
    assert image.size == (200, 200)  # menor que 256: não é ampliada
    assert images.close(image.getpixel((10, 100)), images.RED)
    assert images.close(image.getpixel((190, 100)), images.BLUE)


def test_small_images_are_not_upscaled_and_big_ones_are_shrunk(ana, api):
    small = upload_ok(ana, images.encode(images.two_halves(80, 80), "PNG"))
    assert webp(api.get(small["avatar_url"]).data).size == (80, 80)
    big = upload_ok(ana, images.encode(images.two_halves(3000, 2000), "JPEG"))
    assert webp(api.get(big["avatar_url"]).data).size == (256, 256)


def test_transparency_is_kept(ana, api):
    rgba = Image.new("RGBA", (200, 200), (255, 0, 0, 255))
    rgba.paste((0, 0, 0, 0), (0, 0, 100, 200))
    user = upload_ok(ana, images.encode(rgba, "PNG"))
    image = webp(api.get(user["avatar_url"]).data).convert("RGBA")
    assert image.getpixel((20, 100))[3] < 20 and image.getpixel((180, 100))[3] > 235


def test_exif_orientation_is_applied(ana, api):
    # 300 x 200 "deitada", metade vermelha à esquerda; o EXIF manda girar: a vermelha vai para cima.
    wide = images.jpeg_with_exif(300, 200, orientation=6)
    user = upload_ok(ana, wide)
    image = webp(api.get(user["avatar_url"]).data).convert("RGB")
    assert image.size == (200, 200)
    assert images.close(image.getpixel((100, 10)), images.RED)
    assert images.close(image.getpixel((100, 190)), images.BLUE)


@pytest.mark.parametrize("offset, value", [(11, 0), (13, 5), (56, 1)])
def test_corrupted_exif_is_never_a_server_error(ana, api, offset, value):
    raw = images.jpeg_with_corrupted_exif(offset, value)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            probe = Image.open(io.BytesIO(raw))
            probe.load()
            ImageOps.exif_transpose(probe)
        except Exception:  # é o defeito coberto aqui: o Pillow falha de um jeito inesperado
            pass
        else:
            pytest.skip("Este Pillow lê o EXIF adulterado sem erro; nada a provar aqui.")
    response = ana.upload(UPLOAD, raw)
    assert response.status_code in (200, 422), response.get_data()[:200]
    if response.status_code == 200:  # sem girar, mas a foto é aceita
        assert webp(api.get(response.get_json()["user"]["avatar_url"]).data).size == (200, 200)


def test_16_bit_grayscale_is_scaled_not_clipped_to_white(ana, api):
    user = upload_ok(ana, images.gray16_ramp())
    image = webp(api.get(user["avatar_url"]).data).convert("L")
    left, middle, right = image.getpixel((4, 64)), image.getpixel((64, 64)), image.getpixel((123, 64))
    assert left < 40 and 100 < middle < 160 and right > 215, (left, middle, right)


def test_metadata_does_not_survive(ana, api):
    marker = "SEGREDO-GPS-E-CAMERA-123"
    original = images.jpeg_with_exif(300, 300, orientation=1, marker=marker)
    assert marker.encode() in original  # a imagem de teste realmente carrega o dado
    user = upload_ok(ana, original)
    served = api.get(user["avatar_url"]).data
    assert marker.encode() not in served
    image = webp(served)
    assert not image.getexif() and "exif" not in image.info and "icc_profile" not in image.info


def test_data_appended_after_the_image_is_dropped(ana, api):
    payload = b"<script>alert(1)</script>" * 20
    user = upload_ok(ana, images.encode(images.two_halves(300, 300), "PNG") + payload)
    assert b"<script>" not in api.get(user["avatar_url"]).data


def test_noisy_photos_still_fit_in_the_size_limit(ana, api, app):
    user = upload_ok(ana, images.encode(images.noise(1200, 1200), "PNG"))
    assert webp(api.get(user["avatar_url"]).data).size == (256, 256)
    assert stored_rows(app)[0]["size"] <= 256 * 1024


def test_changing_the_photo_replaces_the_old_one(ana, api, app):
    first = upload_ok(ana, images.encode(images.two_halves(300, 300), "PNG"))["avatar_url"]
    second = upload_ok(ana, images.encode(images.two_halves(300, 300, vertical=True), "PNG"))["avatar_url"]
    assert first != second
    assert api.get(first).status_code == 404 and api.get(second).status_code == 200
    assert len(stored_rows(app)) == 1


def test_remove_the_photo(ana, api, app):
    url = upload_ok(ana, images.encode(images.two_halves(300, 300), "PNG"))["avatar_url"]
    response = ana.delete(UPLOAD)
    assert response.status_code == 200 and response.get_json()["user"]["avatar_url"] is None
    assert api.get(url).status_code == 404 and stored_rows(app) == []
    assert ana.delete(UPLOAD).status_code == 200  # sem foto: continua tudo bem


# -------------------------------------------------------------------- recusas
def jpeg_bytes() -> bytes:
    return images.encode(images.two_halves(300, 300), "JPEG")


@pytest.mark.parametrize(
    "label, content, filename",
    [
        ("texto com nome de imagem", b"isto nao e uma imagem", "foto.png"),
        ("html disfarçado", b"<html><script>alert(1)</script></html>", "foto.jpg"),
        ("svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect width="9" height="9"/></svg>', "foto.svg"),
        ("vazio", b"", "foto.png"),
        ("cabeçalho PNG com lixo", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "foto.png"),
        ("JPEG truncado", jpeg_bytes()[:200], "foto.jpg"),
        ("PNG truncado", images.encode(images.noise(300, 300), "PNG")[:5000], "foto.png"),
        ("gif", images.encode(images.two_halves(300, 300), "GIF"), "foto.gif"),
        ("bmp", images.encode(images.two_halves(300, 300), "BMP"), "foto.bmp"),
        ("pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF", "foto.png"),
    ],
)
def test_files_that_are_not_valid_jpeg_png_or_webp_are_rejected(ana, app, label, content, filename):
    response = ana.upload(UPLOAD, content, filename=filename)
    assert response.status_code in (422, 400), label
    assert "file" in response.get_json()["error"]["fields"], label
    assert stored_rows(app) == [] and ana.get("/api/auth/me").get_json()["user"]["avatar_url"] is None


def test_the_name_and_declared_type_of_the_file_do_not_matter_only_the_content(ana, api):
    user = upload_ok(ana, jpeg_bytes(), filename="documento.txt")
    assert webp(api.get(user["avatar_url"]).data).size == (256, 256)


def test_too_small_images_are_rejected(ana):
    response = ana.upload(UPLOAD, images.encode(images.two_halves(32, 32), "PNG"))
    assert response.status_code == 422 and "pequena" in response.get_json()["error"]["fields"]["file"]


@pytest.mark.parametrize("width, height", [(12000, 12000), (8000, 4000)])
def test_images_with_too_many_pixels_are_rejected_before_decoding(ana, app, width, height):
    # Em 1 bit por pixel o PNG pesa poucos KB, mas descomprimiria para dezenas de milhões de pixels
    # (o segundo caso passa do nosso limite de 25 milhões, mas ainda não do alarme do próprio Pillow).
    bomb = images.encode(Image.new("1", (width, height), 0), "PNG", optimize=False)
    assert len(bomb) < 1024 * 1024
    response = ana.upload(UPLOAD, bomb)
    assert response.status_code == 422 and "grande demais" in response.get_json()["error"]["fields"]["file"]
    assert stored_rows(app) == []


def test_files_over_the_size_limit_are_rejected_with_413(ana, app):
    response = ana.upload(UPLOAD, b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024 + 1024 * 20))
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "payload_too_large"
    assert stored_rows(app) == []


def test_a_file_just_under_the_limit_is_read_normally(ana, api):
    big = images.encode(images.noise(1200, 1200), "PNG")
    assert 3_000_000 < len(big) < 5 * 1024 * 1024
    assert ana.upload(UPLOAD, big).status_code == 200


def test_missing_file_or_wrong_field_name_or_json_body_is_a_422(ana):
    assert ana.upload(UPLOAD, None).status_code == 422
    assert ana.upload(UPLOAD, jpeg_bytes(), name="foto").status_code == 422
    assert ana.upload(UPLOAD, jpeg_bytes(), filename="").status_code == 422
    json_attempt = ana.post(UPLOAD, {"file": "aGVsbG8="})
    assert json_attempt.status_code == 422 and "file" in json_attempt.get_json()["error"]["fields"]


def test_other_routes_keep_the_small_body_limit(ana):
    upload_ok(ana, jpeg_bytes())
    response = ana.post("/api/lists", {"title": "Lista", "description": "x" * 200_000})
    assert response.status_code == 413


def test_the_photo_cannot_be_set_by_sending_an_address(ana, bruno, app):
    ana.patch("/api/auth/me", {"avatar_url": "https://exemplo.com/a.png"})
    ana.patch("/api/auth/me", {"avatar_url": "/api/avatars/qualquer-coisa"})
    assert ana.get("/api/auth/me").get_json()["user"]["avatar_url"] is None
    # nem copiando o endereço da foto de outra pessoa
    his = upload_ok(bruno, jpeg_bytes())["avatar_url"]
    ana.patch("/api/auth/me", {"avatar_url": his})
    assert ana.get("/api/auth/me").get_json()["user"]["avatar_url"] is None


def test_unknown_or_malformed_tokens_are_a_404(api):
    for token in ["nao-existe", "x" * 500, "..%2f..%2fetc%2fpasswd", "%00"]:
        assert api.get(f"/api/avatars/{token}").status_code == 404


# ------------------------------------------------------------ autenticação e CSRF
def test_upload_and_removal_need_login_and_csrf(api, ana):
    assert api.upload(UPLOAD, jpeg_bytes()).status_code == 401
    assert api.delete(UPLOAD).status_code == 401
    assert ana.upload(UPLOAD, jpeg_bytes(), csrf=False).status_code == 403
    assert ana.delete(UPLOAD, csrf=False).status_code == 403
    assert ana.upload(UPLOAD, jpeg_bytes(), headers={"Origin": "https://site-malicioso.example"}).status_code == 403


def test_upload_is_rate_limited(app):
    limited = create_app({"TESTING": True, "DATABASE": app.config["DATABASE"] + ".rl", "RATELIMIT_ENABLED": True})
    client = Api(limited)
    client.register("ana")
    statuses = [client.upload(UPLOAD, b"nao-e-imagem").status_code for _ in range(22)]
    assert statuses[:20] == [422] * 20
    assert statuses[20] == 429


def test_without_pillow_the_server_says_so_instead_of_crashing(ana, monkeypatch):
    photo = jpeg_bytes()  # gerada antes de "desinstalar" o Pillow
    monkeypatch.setitem(sys.modules, "PIL", None)
    response = ana.upload(UPLOAD, photo)
    assert response.status_code == 503 and response.get_json()["error"]["code"] == "image_support_missing"


# ----------------------------------------------------------------- aparece nos lugares certos
def test_the_photo_address_shows_up_for_everyone_without_leaking_anything_else(ana, bruno, api):
    url = upload_ok(ana, jpeg_bytes())["avatar_url"]
    bruno.put("/api/users/ana/follow")
    ana.put("/api/users/bruno/follow")
    ana.play(HADES)
    ana.post(f"/api/games/{HADES}/reviews", {"rating": 8, "body": "Bom."})
    list_id = ana.post("/api/lists", {"title": "Favoritos"}).get_json()["list"]["id"]
    ana.post(f"/api/lists/{list_id}/games", {"rawg_id": HADES})

    seen = {
        "perfil": api.get("/api/users/ana").get_json()["user"],
        "reviews do jogo": api.get(f"/api/games/{HADES}/reviews").get_json()["items"][0]["user"],
        "atividade": api.get("/api/activity").get_json()["items"][0]["user"],
        "seguidores de bruno": api.get("/api/users/bruno/followers").get_json()["items"][0],  # é a ana
        "seguidos por bruno": api.get("/api/users/bruno/following").get_json()["items"][0],  # também a ana
        "busca": api.get("/api/search?q=ana").get_json()["users"][0],
        "listas": api.get("/api/lists").get_json()["items"][0]["owner"],
    }
    for where, user in seen.items():
        assert user["username"] == "ana", where
        assert user["avatar_url"] == url, where
        assert "email" not in user, where


def test_public_cached_photo_never_carries_a_session_cookie(ana, api):
    """Um cache compartilhado (proxy/CDN) poderia guardar o Set-Cookie e entregá-lo a outras pessoas."""
    user = upload_ok(ana, images.encode(images.two_halves(300, 300), "PNG"))
    response = ana.get(user["avatar_url"])  # com a sessão da Ana
    assert response.status_code == 200 and "public" in response.headers["Cache-Control"]
    assert "Set-Cookie" not in response.headers
    assert ana.get("/api/auth/me").status_code == 200  # a sessão em si continua valendo
