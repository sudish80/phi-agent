"""Crypto tools — UUID, password, hash, encrypt/decrypt, hash verification."""

import uuid
import hashlib
import secrets
import string
import logging

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def generate_uuid(version: int = 4) -> str:
    if version == 4:
        return str(uuid.uuid4())
    elif version == 1:
        return str(uuid.uuid1())
    elif version == 7:
        return str(uuid.uuid7())
    else:
        return f"Error: unsupported UUID version: {version}. Use 1, 4, or 7"


def generate_password(length: int = 16, include_digits: bool = True, include_symbols: bool = True) -> str:
    chars = string.ascii_letters
    if include_digits: chars += string.digits
    if include_symbols: chars += string.punctuation
    if length < 4:
        return "Error: minimum length is 4"
    return "".join(secrets.choice(chars) for _ in range(length))


def generate_hash(text: str, algorithm: str = "sha256") -> str:
    algo = algorithm.lower()
    if algo not in ("md5", "sha1", "sha256", "sha512"):
        return f"Error: unsupported algorithm: {algorithm}"
    h = hashlib.new(algo, text.encode("utf-8"))
    return f"{algo.upper()}: {h.hexdigest()}"


def check_hash(text: str, hash_value: str, algorithm: str = "sha256") -> str:
    algo = algorithm.lower()
    if algo not in ("md5", "sha1", "sha256", "sha512"):
        return f"Error: unsupported algorithm: {algorithm}"
    h = hashlib.new(algo, text.encode("utf-8"))
    expected = h.hexdigest()
    match = h.hexdigest() == hash_value.strip().upper().replace(f"{algo.upper()}:", "").strip()
    return f"Match: {match}\nExpected: {expected}\nProvided: {hash_value}"


def encrypt_text(plaintext: str, key: str = "") -> str:
    if not HAS_CRYPTO:
        return "Error: cryptography not installed. Run: pip install cryptography"
    try:
        k = key.encode() if key else Fernet.generate_key()
        f = Fernet(k if isinstance(k, bytes) else k.encode())
        encrypted = f.encrypt(plaintext.encode())
        return f"Encrypted: {encrypted.decode()}\nKey: {k.decode() if isinstance(k, bytes) else k}"
    except Exception as e:
        return f"Encryption error: {e}"


def decrypt_text(ciphertext: str, key: str) -> str:
    if not HAS_CRYPTO:
        return "Error: cryptography not installed. Run: pip install cryptography"
    try:
        f = Fernet(key.encode())
        decrypted = f.decrypt(ciphertext.encode())
        return f"Decrypted: {decrypted.decode()}"
    except Exception as e:
        return f"Decryption error: {e}"
