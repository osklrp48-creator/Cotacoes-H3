from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import admin, auth, fornecedores, ia, produtos, registros, unidades, usuarios

NOMES_CAMPOS = {
    "data_recebimento": "data",
    "produto": "produto",
    "valor_unitario": "valor unitário",
    "quantidade": "quantidade",
    "valor_frete": "valor do frete",
    "itens": "itens",
    "email": "e-mail",
    "senha": "senha",
    "nome": "nome",
    "unidade_id": "unidade",
    "status": "status",
    "frete": "frete",
}


def _mensagem_validacao(exc: RequestValidationError) -> str:
    partes = []
    for erro in exc.errors():
        loc = [str(p) for p in erro.get("loc", []) if p not in ("body", "query")]
        campo = next((NOMES_CAMPOS.get(p, p) for p in reversed(loc) if not p.isdigit()), "")
        item = next((int(p) + 1 for p in loc if p.isdigit()), None)
        tipo = erro.get("type", "")
        if tipo in ("missing", "string_type") or (tipo == "too_short" and campo == "itens"):
            texto = "é obrigatório" if campo != "itens" else "informe pelo menos um item"
        elif tipo.startswith("decimal") or tipo in ("float_parsing", "decimal_parsing"):
            texto = "número inválido (máx. 4 casas decimais no valor unitário)"
        elif tipo == "greater_than_equal":
            texto = "não pode ser negativo"
        elif tipo.startswith("date"):
            texto = "data inválida"
        elif tipo == "string_too_short" and campo == "senha":
            texto = "deve ter pelo menos 8 caracteres"
        elif tipo == "string_too_long":
            texto = "texto muito longo"
        elif tipo == "value_error" and campo == "e-mail":
            texto = "e-mail inválido"
        else:
            texto = "valor inválido"
        prefixo = f"Item {item}: " if item and campo != "itens" else ""
        partes.append(f"{prefixo}{campo} {texto}".strip())
    return "Verifique os campos: " + "; ".join(dict.fromkeys(partes)) + "."


def criar_app() -> FastAPI:
    s = get_settings()
    if s.cookie_secure and (s.secret_key == "troque-esta-chave" or len(s.secret_key) < 32):
        raise RuntimeError("Defina SECRET_KEY com pelo menos 32 caracteres aleatórios antes de rodar em produção.")
    app = FastAPI(title="Cotações H3", docs_url="/api/docs", openapi_url="/api/openapi.json")

    # Comprime respostas (JS, CSS, SVG e JSON das listas): bem menos dados por acesso.
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    if s.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": _mensagem_validacao(exc)})

    for r in (auth, unidades, usuarios, registros, produtos, fornecedores, ia, admin):
        app.include_router(r.router, prefix="/api")

    @app.get("/api/saude", include_in_schema=False)
    def saude():
        return {"ok": True}

    # Em produção o próprio FastAPI serve o build do frontend (um único serviço para hospedar).
    dist = Path(s.frontend_dist) if s.frontend_dist else None
    if dist and (dist / "index.html").exists():
        if (dist / "assets").exists():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.middleware("http")
        async def _cache_assets(request: Request, call_next):
            resposta = await call_next(request)
            # Arquivos de /assets têm um código no nome que muda a cada versão: o navegador pode guardá-los
            # por 1 ano sem perguntar de novo ao servidor.
            if request.url.path.startswith("/assets/") and resposta.status_code == 200:
                resposta.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resposta

        @app.get("/{caminho:path}", include_in_schema=False)
        def spa(caminho: str):
            if caminho.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Rota não encontrada."})
            arquivo = (dist / caminho).resolve()
            if caminho and arquivo.is_file() and dist.resolve() in arquivo.parents:
                # Logos e ícone: guardados por 1 dia.
                return FileResponse(arquivo, headers={"Cache-Control": "public, max-age=86400"})
            # A página principal sempre é conferida, para pegar a versão nova logo após uma publicação.
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = criar_app()
