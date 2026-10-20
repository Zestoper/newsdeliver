"""비밀번호 해시 (표준 라이브러리 PBKDF2-SHA256).

저장 형식: pbkdf2_sha256$<반복 횟수>$<salt hex>$<hash hex>
예전에 평문으로 저장된 비밀번호도 로그인은 되게 하고, 로그인에 성공하면 그 자리에서 해시로 바꾼다.
"""
import hashlib
import hmac
import secrets

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 310_000  # OWASP 권장 수준


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()
    return f"{_ALGO}${_ITERATIONS}${salt}${digest}"


def is_hashed(stored: str | None) -> bool:
    return bool(stored) and stored.startswith(_ALGO + "$")


def verify_password(password: str, stored: str | None) -> bool:
    """입력한 비밀번호가 저장된 값과 맞는지 확인. 예전 평문 저장값도 비교한다."""
    if not stored or password is None:
        return False
    if is_hashed(stored):
        try:
            _, iterations, salt, digest = stored.split("$")
            check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(check, digest)
    return hmac.compare_digest(stored.encode(), password.encode())  # 예전 평문 저장값
