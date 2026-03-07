from __future__ import annotations

import hashlib
import secrets

import bcrypt


def get_password_hash(password: str) -> str:
    encoded_password = password.encode("utf-8")
    return bcrypt.hashpw(encoded_password, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        return False


def generate_secure_token(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()