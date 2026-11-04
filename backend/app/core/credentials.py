"""Versioned password hashing and opaque token fingerprints; no framework dependencies."""
import hashlib
import secrets

# OWASP scrypt alternative: N=2^15, r=8, p=3 (32 MiB).
# A version prefix allows a deliberate upgrade policy without silently changing stored hashes.
SCRYPT_PARAMETERS = {'n': 32768, 'r': 8, 'p': 3, 'maxmem': 64 * 1024 * 1024}


def hash_pin(pin: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt.encode(), **SCRYPT_PARAMETERS).hex()
    return f'scrypt-v1${salt}${digest}'


def verify_pin(pin: str, value: str) -> bool:
    try:
        scheme, salt, expected = value.split('$')
        if scheme != 'scrypt-v1' or len(salt) != 32 or len(expected) != 128:
            return False
        actual = hashlib.scrypt(pin.encode(), salt=salt.encode(), **SCRYPT_PARAMETERS).hex()
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
