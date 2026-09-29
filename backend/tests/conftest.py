import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://h3:h3@localhost:5432/cotacoes_test"
)
os.environ["IA_PROVEDOR"] = "anthropic"  # os testes do Gemini trocam o provedor explicitamente
os.environ["ANTHROPIC_API_KEY"] = "chave-de-teste"
os.environ["GEMINI_API_KEY"] = "chave-gemini-de-teste"
os.environ["SECRET_KEY"] = "chave-secreta-de-teste-com-mais-de-32-bytes"
os.environ["FRONTEND_DIST"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Unidade, Usuario  # noqa: E402
from app.security import gerar_hash  # noqa: E402

SENHA = "senha12345"


@pytest.fixture(scope="session", autouse=True)
def _banco():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _limpar():
    yield
    tabelas = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def unidades(db):
    matriz, filial = Unidade(nome="Matriz"), Unidade(nome="Filial Norte")
    db.add_all([matriz, filial])
    db.commit()
    return matriz, filial


@pytest.fixture
def usuarios(db, unidades):
    matriz, filial = unidades
    admin = Usuario(nome="Ana Admin", email="admin@h3.com.br", senha_hash=gerar_hash(SENHA), perfil="admin", unidade_id=matriz.id)
    comum = Usuario(nome="Bruno", email="bruno@h3.com.br", senha_hash=gerar_hash(SENHA), perfil="usuario", unidade_id=filial.id)
    db.add_all([admin, comum])
    db.commit()
    return admin, comum


def _logar(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "senha": SENHA})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def anonimo():
    return TestClient(app)


@pytest.fixture
def admin(usuarios):
    return _logar("admin@h3.com.br")


@pytest.fixture
def cliente(usuarios):
    return _logar("bruno@h3.com.br")


def novo_registro(**extra):
    base = {
        "fornecedor": "Distribuidora Alfa",
        "data_recebimento": "2026-09-01",
        "itens": [{"produto": "Dipirona 500mg", "marca": "EMS", "unidade_medida": "cx", "quantidade": 10, "valor_unitario": 12.3456}],
    }
    base.update(extra)
    return base


def pdf_com_texto(linhas: list[str]) -> bytes:
    """Gera um PDF simples (1 página, fonte Helvetica) com as linhas de texto dadas."""
    conteudo = "BT /F1 11 Tf 50 780 Td 14 TL " + " ".join(
        f"({l.replace('(', '[').replace(')', ']')}) Tj T*" for l in linhas
    ) + " ET"
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(conteudo.encode('latin-1'))} >>\nstream\n{conteudo}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    saida = b"%PDF-1.4\n"
    posicoes = []
    for i, obj in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    saida += "".join(f"{p:010d} 00000 n \n" for p in posicoes).encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return saida
