from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://h3:h3@localhost:5432/cotacoes"
    secret_key: str = "troque-esta-chave"
    jwt_expire_hours: int = 12
    cookie_secure: bool = False
    cors_origins: str = ""  # lista separada por vírgula (só necessário se o frontend estiver em outro domínio)

    # Qual IA lê as cotações: "gemini" (Google, tem camada gratuita) ou "anthropic" (Claude, paga por uso).
    ia_provedor: Literal["gemini", "anthropic"] = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    ia_max_mb: int = 20
    # Preço em US$ por milhão de tokens, só para a estimativa de custo no painel admin.
    # Se não definir, usa 0 para o Gemini (camada gratuita) e o preço do Claude Sonnet 5.5 para a Anthropic.
    ia_preco_entrada_mtok: float | None = None
    ia_preco_saida_mtok: float | None = None

    frontend_dist: str = ""  # pasta do build do frontend servida pelo FastAPI (produção)

    def precos_ia(self) -> tuple[float, float]:
        """(entrada, saída) em US$ por milhão de tokens."""
        padrao = (0.0, 0.0) if self.ia_provedor == "gemini" else (2.0, 10.0)
        return (
            padrao[0] if self.ia_preco_entrada_mtok is None else self.ia_preco_entrada_mtok,
            padrao[1] if self.ia_preco_saida_mtok is None else self.ia_preco_saida_mtok,
        )

    @field_validator("ia_preco_entrada_mtok", "ia_preco_saida_mtok", mode="before")
    @classmethod
    def _preco_vazio(cls, v):
        return None if v == "" else v

    @field_validator("ia_provedor", mode="before")
    @classmethod
    def _provedor(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

    @field_validator("database_url")
    @classmethod
    def _driver(cls, v: str) -> str:
        # Render/Railway entregam "postgres://" ou "postgresql://"; o SQLAlchemy precisa do driver psycopg.
        for prefixo in ("postgres://", "postgresql://"):
            if v.startswith(prefixo):
                return "postgresql+psycopg://" + v[len(prefixo):]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
