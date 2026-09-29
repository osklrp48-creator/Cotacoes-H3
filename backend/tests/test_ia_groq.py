import json
from types import SimpleNamespace

import groq
import httpx
import pytest
from google.genai import errors

from app.config import get_settings
from app.models import UsoIA
from app.services.ia import gemini, groq_ia

RESPOSTA = {
    "fornecedor": "Distribuidora Alfa", "cnpj": "", "contato": "", "telefone": "", "email": "", "numero": "77",
    "data": "2026-09-29", "pagamento": "", "entrega": "", "frete": "CIF", "valorFrete": 0, "obs": "",
    "itens": [{"produto": "Dipirona 500mg", "marca": "EMS", "unidade": "cx", "qtd": 10, "valorUnit": 12.5}],
}


def _req():
    return httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


class GroqFalso:
    def __init__(self, conteudo=None, erro=None, modelos=("openai/gpt-oss-120b",)):
        self.chamadas = []
        self.conteudo = conteudo if conteudo is not None else json.dumps(RESPOSTA)
        self.erro = erro
        self.modelos = modelos
        self.chat = SimpleNamespace(completions=self)
        self.models = self

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        if callable(self.erro):
            self.erro(kwargs)
        elif self.erro:
            raise self.erro
        return SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=self.conteudo))],
            usage=SimpleNamespace(prompt_tokens=500, completion_tokens=120),
        )

    def list(self):
        return SimpleNamespace(data=[SimpleNamespace(id=m) for m in (*self.modelos, "whisper-large-v3")])


class GeminiSempreFalha:
    def __init__(self, codigo):
        self.codigo = codigo
        self.models = self

    def generate_content(self, **kwargs):
        raise errors.ServerError(self.codigo, {"error": {"code": self.codigo, "message": "high demand", "status": "UNAVAILABLE"}})

    def list(self, config=None):
        return []


@pytest.fixture(autouse=True)
def _estado_ia(monkeypatch):
    monkeypatch.setattr(gemini, "_modelo_descoberto", None)
    monkeypatch.setattr(gemini, "_modelo_temporario", None)
    monkeypatch.setattr(groq_ia, "_modelo_descoberto", None)
    monkeypatch.setattr(get_settings(), "ia_provedor", "gemini")
    monkeypatch.setattr(get_settings(), "groq_api_key", "chave-groq")


def test_gemini_sobrecarregado_usa_groq(cliente, monkeypatch, db):
    monkeypatch.setattr(gemini, "obter_cliente", lambda: GeminiSempreFalha(503))
    falso = GroqFalso()
    monkeypatch.setattr(groq_ia, "obter_cliente", lambda: falso)
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "Dipirona cx 12,50"})
    assert r.status_code == 200, r.text
    assert r.json()["fornecedor"] == "Distribuidora Alfa"
    chamada = falso.chamadas[0]
    assert chamada["model"] == "openai/gpt-oss-120b"
    assert chamada["response_format"] == {"type": "json_object"}
    assert "26.643.172/0001-77" in chamada["messages"][0]["content"]
    assert "Dipirona cx 12,50" in chamada["messages"][1]["content"]
    uso = db.query(UsoIA).one()
    assert (uso.modelo, uso.tokens_entrada, uso.sucesso) == ("groq/openai/gpt-oss-120b", 500, True)


def test_sem_chave_groq_mantem_erro_do_gemini(cliente, monkeypatch):
    monkeypatch.setattr(get_settings(), "groq_api_key", "")
    monkeypatch.setattr(gemini, "obter_cliente", lambda: GeminiSempreFalha(503))
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 502 and "sobrecarregado" in r.json()["detail"]


def test_imagem_nao_vai_para_o_groq(cliente, monkeypatch):
    monkeypatch.setattr(gemini, "obter_cliente", lambda: GeminiSempreFalha(503))
    falso = GroqFalso()
    monkeypatch.setattr(groq_ia, "obter_cliente", lambda: falso)
    r = cliente.post("/api/ia/ler-cotacao", files={"arquivo": ("f.jpg", b"\xff\xd8\xff img", "image/jpeg")})
    assert r.status_code == 502
    assert falso.chamadas == []


def test_groq_tambem_falha_explica_os_dois(cliente, monkeypatch):
    monkeypatch.setattr(gemini, "obter_cliente", lambda: GeminiSempreFalha(503))
    erro = groq.RateLimitError("limite", response=httpx.Response(429, request=_req()), body=None)
    monkeypatch.setattr(groq_ia, "obter_cliente", lambda: GroqFalso(erro=erro))
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 502
    detalhe = r.json()["detail"]
    assert "sobrecarregado" in detalhe and "IA reserva também falhou" in detalhe and "Groq" in detalhe


def test_groq_troca_modelo_aposentado(cliente, monkeypatch):
    monkeypatch.setattr(get_settings(), "ia_provedor", "groq")

    def recusa_antigo(kwargs):
        if kwargs["model"] == "openai/gpt-oss-120b":
            raise groq.BadRequestError(
                "The model `openai/gpt-oss-120b` has been decommissioned",
                response=httpx.Response(400, request=_req()), body=None,
            )

    falso = GroqFalso(erro=recusa_antigo, modelos=("qwen/qwen3-32b", "llama-3.3-70b-versatile"))
    monkeypatch.setattr(groq_ia, "obter_cliente", lambda: falso)
    r = cliente.post("/api/ia/ler-cotacao", data={"texto": "x"})
    assert r.status_code == 200, r.text
    assert [c["model"] for c in falso.chamadas] == ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"]


def test_provedor_groq_recusa_imagem(cliente, monkeypatch):
    monkeypatch.setattr(get_settings(), "ia_provedor", "groq")
    r = cliente.post("/api/ia/ler-cotacao", files={"arquivo": ("f.png", b"\x89PNG img", "image/png")})
    assert r.status_code == 422 and "só lê texto" in r.json()["detail"]
