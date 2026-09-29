import re
import unicodedata


def normalizar(texto: str | None) -> str:
    """Minúsculas, sem acento e com espaços simples."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def normalizar_unidade(un: str | None) -> str:
    return re.sub(r"\s+", " ", (un or "")).strip().upper()


def limpar(texto: str | None) -> str | None:
    """Tira espaços; string vazia vira None."""
    if texto is None:
        return None
    t = str(texto).strip()
    return t or None
