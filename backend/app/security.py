from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import get_settings

COOKIE_NAME = "h3_sessao"
ALGORITMO = "HS256"


def gerar_hash(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode())
    except ValueError:
        return False


def criar_token(usuario_id: int) -> str:
    s = get_settings()
    agora = datetime.now(timezone.utc)
    payload = {"sub": str(usuario_id), "iat": agora, "exp": agora + timedelta(hours=s.jwt_expire_hours)}
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITMO)


def ler_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITMO])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
