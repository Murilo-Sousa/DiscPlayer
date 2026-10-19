from __future__ import annotations

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

# Hash de uma senha que ninguém conhece. Quando o usuário não existe, a
# verificação roda contra ele para que a resposta demore o mesmo tempo e não
# revele quais e-mails estão cadastrados.
_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = generate_password_hash(
            "senha-que-ninguem-conhece", method=current_app.config["PASSWORD_HASH_METHOD"]
        )
    return _DUMMY_HASH


def hash_password(password: str) -> str:
    """Hash com sal (scrypt por padrão); a senha nunca é guardada em texto."""
    return generate_password_hash(password, method=current_app.config["PASSWORD_HASH_METHOD"])


def check_password(stored_hash: str | None, password: str) -> bool:
    valid = check_password_hash(stored_hash or _dummy_hash(), password)
    return valid and stored_hash is not None
