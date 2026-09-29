"""Leitura de cotações com o Groq (plano gratuito), usada como reserva quando o Gemini falha.

O Groq só recebe texto: serve para texto colado, Word, planilhas e PDFs com texto (que já chegam
aqui como texto extraído). PDF escaneado e fotos continuam dependendo do Gemini.
"""

import json
import logging
import re
import time

import groq

from ...config import get_settings
from .leitor import PROMPT_SISTEMA, IAIndisponivel, ResultadoIA, com_uso, normalizar_resposta

log = logging.getLogger("cotacoes.ia")

INSTRUCOES = PROMPT_SISTEMA.replace(
    "Chame SEMPRE a ferramenta registrar_cotacao com o resultado.",
    "Responda SEMPRE com um único objeto JSON, sem texto antes ou depois, com exatamente estas chaves: "
    '{"fornecedor": "", "cnpj": "", "contato": "", "telefone": "", "email": "", "numero": "", "data": "", '
    '"pagamento": "", "entrega": "", "frete": "", "valorFrete": 0, "obs": "", '
    '"itens": [{"produto": "", "marca": "", "unidade": "", "qtd": 0, "valorUnit": 0}]}. '
    "Números como número JSON (ponto decimal), textos como string.",
)

# Preferência quando o modelo configurado não existe mais (o Groq troca modelos com frequência).
PREFERIDOS = ("gpt-oss-120b", "llama-4-maverick", "llama-3.3-70b", "qwen3-32b", "kimi-k2", "gpt-oss-20b")
_EXCLUIR = ("whisper", "tts", "guard", "playai", "orpheus", "compound", "allam", "distil")

TEMPO_POR_CHAMADA = 60

_modelo_descoberto: str | None = None


def configurado() -> bool:
    return bool(get_settings().groq_api_key)


def modelo_em_uso() -> str:
    return _modelo_descoberto or get_settings().groq_model


def obter_cliente() -> groq.Groq:
    chave = get_settings().groq_api_key
    if not chave:
        raise IAIndisponivel("A IA reserva (Groq) não está configurada (falta a GROQ_API_KEY).", 503)
    return groq.Groq(api_key=chave, timeout=TEMPO_POR_CHAMADA, max_retries=0)


def aceita(blocos: list[dict]) -> bool:
    """O Groq só lê texto."""
    return all(b.get("type") == "text" for b in blocos)


def descobrir_modelo(cliente) -> str | None:
    nomes = [m.id for m in cliente.models.list().data if not any(x in m.id for x in _EXCLUIR)]
    for preferido in PREFERIDOS:
        for nome in nomes:
            if preferido in nome:
                return nome
    return nomes[0] if nomes else None


def _chamar(cliente, modelo: str, blocos: list[dict]):
    texto = "\n\n".join(b["text"] for b in blocos)
    return cliente.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": INSTRUCOES},
            {"role": "user", "content": texto + "\n\nExtraia os dados desta cotação e responda só com o JSON."},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_completion_tokens=16000,
    )


def _modelo_sumiu(exc: groq.APIStatusError) -> bool:
    texto = str(exc).lower()
    return exc.status_code == 404 or "decommissioned" in texto or "model_not_found" in texto or "does not exist" in texto


def ler_com_groq(blocos: list[dict]) -> ResultadoIA:
    global _modelo_descoberto
    cliente = obter_cliente()
    modelo = modelo_em_uso()
    inicio = time.monotonic()
    try:
        try:
            resposta = _chamar(cliente, modelo, blocos)
        except groq.APIStatusError as exc:
            if not _modelo_sumiu(exc):
                raise
            novo = descobrir_modelo(cliente)
            if not novo or novo == modelo:
                raise
            _modelo_descoberto = modelo = novo
            resposta = _chamar(cliente, modelo, blocos)
    except groq.AuthenticationError as exc:
        raise IAIndisponivel("A chave do Groq é inválida. Confira a GROQ_API_KEY no Render.", 503) from exc
    except groq.RateLimitError as exc:
        raise IAIndisponivel("O limite gratuito do Groq também foi atingido. Tente de novo mais tarde.", 429) from exc
    except groq.APITimeoutError as exc:
        raise IAIndisponivel("O Groq não respondeu a tempo. Tente de novo daqui a pouco.", 504) from exc
    except groq.APIStatusError as exc:
        log.warning("Erro do Groq com o modelo %s: %s %s", modelo, exc.status_code, str(exc)[:300])
        raise IAIndisponivel(f"O Groq também falhou (detalhe técnico: {exc.status_code}).") from exc
    except groq.APIConnectionError as exc:
        raise IAIndisponivel("Não foi possível falar com o Groq. Tente novamente em instantes.") from exc
    log.info("Groq %s respondeu em %.1f s", modelo, time.monotonic() - inicio)

    uso = resposta.usage
    entrada = int(getattr(uso, "prompt_tokens", 0) or 0)
    saida = int(getattr(uso, "completion_tokens", 0) or 0)
    escolha = resposta.choices[0] if resposta.choices else None
    if escolha is not None and escolha.finish_reason == "length":
        raise com_uso(
            IAIndisponivel("A cotação é grande demais para ler de uma vez. Divida o arquivo e tente de novo.", 422),
            entrada, saida,
        )
    texto = ((escolha.message.content if escolha else "") or "").strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto)
    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        dados = None
    if not isinstance(dados, dict):
        raise com_uso(
            IAIndisponivel("A IA não conseguiu ler essa cotação. Confira o arquivo e tente de novo."), entrada, saida
        )
    return ResultadoIA(normalizar_resposta(dados), entrada, saida, f"groq/{modelo}")
