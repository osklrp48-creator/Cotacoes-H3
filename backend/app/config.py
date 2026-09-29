from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://h3:h3@localhost:5432/cotacoes"
    secret_key: str = "troque-esta-chave"
    jwt_expire_hours: int = 12
    cookie_secure: bool = False
    cors_origins: str = ""  # lista separada por vírgula (só necessário se o frontend estiver em outro domínio)

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    ia_max_mb: int = 20
    # Preço em US$ por milhão de tokens, só para a estimativa de custo no painel admin.
    ia_preco_entrada_mtok: float = 2.0
    ia_preco_saida_mtok: float = 10.0

    frontend_dist: str = ""  # pasta do build do frontend servida pelo FastAPI (produção)

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
