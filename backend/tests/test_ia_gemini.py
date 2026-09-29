import io
import json

import pytest
from google.genai import errors, types
from openpyxl import Workbook

from app.config import get_settings
from app.models import UsoIA
from app.services.ia import gemini

RESPOSTA = {
    "fornecedor": "João (WhatsApp)",
    "cnpj": "",
    "contato": "",
    "telefone": "11 98888-7777",
    "email": "",
    "numero": "",
    "data": "2026-09-22",
    "pagamento": "à vista",
    "entrega": "",
    "frete": "fob",
    "valorFrete": 0,
    "obs": "",
    "itens": [{"produto": "Luva M", "marca": "Supermax", "unidade": "cx", "qtd": 3, "valorUnit": "24,50"}],
}


def _resposta(texto: str, motivo=types.FinishReason.STOP):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part(text=texto)]), finish_reason=motivo)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=1800, candidates_token_count=250, thoughts_token_count=100
        ),
    )


class GeminiFalso:
    def __init__(self, resposta=None, erro=None):
        self.chamadas = []
        self.resposta = resposta or _resposta(json.dumps(RESPOSTA))
        self.erro = erro
        self.models = self

    def generate_content(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.erro:
            raise self.erro
        return self.resposta


@pytest.fixture
def usar_gemini(monkeypatch):
    monkeypatch.setattr(get_settings(), "ia_provedor", "gemini")


@pytest.fixture
def falso(monkeypatch, usar_gemini):
    f = GeminiFalso()
    monkeypatch.setattr(gemini, "obter_cliente", lambda: f)
    return f


def test_texto_com_gemini(cliente, falso, db):
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "luva 24,50 cx"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["fornecedor"] == "João (WhatsApp)"
    assert d["frete"] == "FOB"
    assert d["itens"] == [{"produto": "Luva M", "marca": "Supermax", "unidade": "CX", "qtd": 3.0, "valorUnit": 24.5}]

    chamada = falso.chamadas[0]
    assert chamada["model"] == "gemini-flash-latest"
    config = chamada["config"]
    assert config.response_mime_type == "application/json"
    assert "26.643.172/0001-77" in config.system_instruction
    assert "additionalProperties" not in json.dumps(config.response_json_schema)
    assert any("luva 24,50 cx" in p for p in chamada["contents"] if isinstance(p, str))

    uso = db.query(UsoIA).one()
    assert (uso.modelo, uso.tokens_entrada, uso.tokens_saida, uso.sucesso) == ("gemini-flash-latest", 1800, 350, True)
    assert cliente.get("/api/registros").json()["total"] == 0


def test_pdf_vai_como_bytes(cliente, falso):
    r = cliente.post("/api/ia/ler-cotacao", files={"arquivo": ("c.pdf", b"%PDF-1.4 x", "application/pdf")})
    assert r.status_code == 200
    parte = falso.chamadas[0]["contents"][0]
    assert isinstance(parte, types.Part)
    assert parte.inline_data.mime_type == "application/pdf"
    assert parte.inline_data.data == b"%PDF-1.4 x"


def test_planilha_vai_como_texto(cliente, falso):
    wb = Workbook()
    wb.active.append(["Soro 500ml", 4.5])
    buf = io.BytesIO()
    wb.save(buf)
    assert cliente.post("/api/ia/ler-cotacao", files={"arquivo": ("c.xlsx", buf.getvalue(), "application/octet-stream")}).status_code == 200
    assert "Soro 500ml,4.5" in falso.chamadas[0]["contents"][0]


def test_limite_gratuito(cliente, monkeypatch, usar_gemini, db):
    erro = errors.ClientError(429, {"error": {"code": 429, "message": "Resource has been exhausted", "status": "RESOURCE_EXHAUSTED"}})
    monkeypatch.setattr(gemini, "obter_cliente", lambda: GeminiFalso(erro=erro))
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 429
    assert "limite de uso gratuito" in r.json()["detail"]
    assert db.query(UsoIA).one().sucesso is False


def test_chave_invalida(cliente, monkeypatch, usar_gemini):
    erro = errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}})
    monkeypatch.setattr(gemini, "obter_cliente", lambda: GeminiFalso(erro=erro))
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 503
    assert "chave do Gemini" in r.json()["detail"]


def test_resposta_cortada_e_json_invalido(cliente, monkeypatch, usar_gemini):
    monkeypatch.setattr(gemini, "obter_cliente", lambda: GeminiFalso(resposta=_resposta('{"itens": [', types.FinishReason.MAX_TOKENS)))
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 422 and "grande demais" in r.json()["detail"]

    monkeypatch.setattr(gemini, "obter_cliente", lambda: GeminiFalso(resposta=_resposta("não é json")))
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 502 and "não conseguiu ler" in r.json()["detail"]


def test_sem_chave_gemini(cliente, monkeypatch, usar_gemini):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.json()["detail"]


def test_custo_gemini_gratuito(admin, falso):
    admin.post("/api/ia/ler-cotacao", data={"texto": "a"})
    d = admin.get("/api/admin/uso-ia").json()
    assert d["provedor"] == "gemini" and d["modelo"] == "gemini-flash-latest"
    assert d["total"]["tokens_entrada"] == 1800
    assert d["total"]["custo_estimado_usd"] == 0


@pytest.fixture(autouse=True)
def _sem_modelo_descoberto(monkeypatch):
    monkeypatch.setattr(gemini, "_modelo_descoberto", None)


class GeminiComModeloAposentado(GeminiFalso):
    """Recusa (404) qualquer modelo fora da lista e lista os modelos disponíveis."""

    def __init__(self, disponiveis):
        super().__init__()
        self.disponiveis = disponiveis

    def generate_content(self, **kwargs):
        if kwargs["model"] not in self.disponiveis:
            self.chamadas.append(kwargs)
            raise errors.ClientError(404, {"error": {"code": 404, "message": "models/x is not found", "status": "NOT_FOUND"}})
        return super().generate_content(**kwargs)

    def list(self, config=None):
        todos = [*self.disponiveis, "gemini-embedding-001", "gemini-2.5-flash-image"]
        return [
            types.Model(name=f"models/{n}", supported_actions=["embedContent"] if "embedding" in n else ["generateContent"])
            for n in todos
        ]


def test_modelo_aposentado_troca_sozinho(cliente, monkeypatch, usar_gemini, db):
    monkeypatch.setattr(get_settings(), "gemini_model", "gemini-2.5-flash")
    falso = GeminiComModeloAposentado(["gemini-3-flash", "gemini-3.1-flash-lite", "gemini-3.1-flash-preview"])
    monkeypatch.setattr(gemini, "obter_cliente", lambda: falso)

    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 200, r.text
    assert [c["model"] for c in falso.chamadas] == ["gemini-2.5-flash", "gemini-3-flash"]
    assert db.query(UsoIA).one().modelo == "gemini-3-flash"

    # A escolha fica guardada: a próxima leitura já vai direto no modelo novo.
    cliente.post("/api/ia/ler-cotacao", data={"texto": "y"})
    assert falso.chamadas[-1]["model"] == "gemini-3-flash"


def test_modelo_aposentado_sem_alternativa(cliente, monkeypatch, usar_gemini):
    monkeypatch.setattr(get_settings(), "gemini_model", "gemini-2.5-flash")
    monkeypatch.setattr(gemini, "obter_cliente", lambda: GeminiComModeloAposentado([]))
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 503
    assert "Nenhum modelo Gemini Flash disponível" in r.json()["detail"]
