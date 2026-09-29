"""Leitura de cotações com o Google Gemini (saída em JSON com schema)."""

import base64
import copy
import json
import re

import httpx
from google import genai
from google.genai import errors, types

from ...config import get_settings
from .leitor import FERRAMENTA, PROMPT_SISTEMA, IAIndisponivel, ResultadoIA, com_uso, normalizar_resposta

INSTRUCOES = PROMPT_SISTEMA.replace(
    "Chame SEMPRE a ferramenta registrar_cotacao com o resultado.",
    "Responda SEMPRE com um único objeto JSON no formato pedido.",
)


def _schema() -> dict:
    """Mesmo schema da ferramenta do Claude, sem o que o Gemini não precisa."""
    schema = copy.deepcopy(FERRAMENTA["input_schema"])

    def limpar(no: dict) -> None:
        no.pop("additionalProperties", None)
        for filho in no.get("properties", {}).values():
            filho.pop("enum", None)  # frete é conferido depois em normalizar_resposta
            limpar(filho)
        if isinstance(no.get("items"), dict):
            limpar(no["items"])

    limpar(schema)
    return schema


SCHEMA = _schema()


def obter_cliente() -> genai.Client:
    chave = get_settings().gemini_api_key
    if not chave:
        raise IAIndisponivel("A leitura com IA não está configurada no servidor (falta a GEMINI_API_KEY).", 503)
    return genai.Client(api_key=chave, http_options=types.HttpOptions(timeout=180_000))


# Modelo descoberto automaticamente quando o configurado em GEMINI_MODEL não existe mais.
_modelo_descoberto: str | None = None

_EXCLUIR = ("image", "tts", "audio", "live", "embedding", "vision", "learnlm", "robotics")


def modelo_em_uso() -> str:
    return _modelo_descoberto or get_settings().gemini_model


def _prioridade(nome: str) -> tuple:
    """Maior = melhor. Alias "latest" > versão estável mais nova > preview; "lite" só como último recurso."""
    m = re.search(r"gemini-(\d+)(?:\.(\d+))?", nome)
    versao = (int(m[1]), int(m[2] or 0)) if m else ()
    return (
        "lite" not in nome,
        "latest" in nome,
        not any(p in nome for p in ("preview", "exp")),
        versao,
        nome,
    )


def descobrir_modelo(cliente) -> str | None:
    """Pergunta ao Google quais modelos "Flash" esta chave pode usar e escolhe o melhor."""
    candidatos = []
    for modelo in cliente.models.list():
        nome = (modelo.name or "").removeprefix("models/")
        acoes = modelo.supported_actions or []
        if "flash" in nome and "generateContent" in acoes and not any(x in nome for x in _EXCLUIR):
            candidatos.append(nome)
    return max(candidatos, key=_prioridade) if candidatos else None


def _partes(blocos: list[dict]) -> list:
    """Converte os blocos (formato da extração) em partes do Gemini."""
    partes: list = []
    for bloco in blocos:
        if bloco["type"] in ("document", "image"):
            fonte = bloco["source"]
            partes.append(types.Part.from_bytes(data=base64.standard_b64decode(fonte["data"]), mime_type=fonte["media_type"]))
        elif bloco["type"] == "text":
            partes.append(bloco["text"])
    partes.append("Extraia os dados desta cotação no formato JSON pedido.")
    return partes


def _erro_api(exc: errors.APIError) -> IAIndisponivel:
    codigo = exc.code or 0
    texto = f"{exc.status or ''} {exc.message or ''}".lower()
    if codigo in (401, 403) or "api key" in texto or "api_key" in texto:
        return IAIndisponivel("A chave do Gemini é inválida ou sem permissão. Avise o administrador.", 503)
    if codigo == 404:
        return IAIndisponivel(
            f"Nenhum modelo Gemini Flash disponível para esta chave (o modelo {modelo_em_uso()} não existe mais). "
            "Confira a chave no Google AI Studio.",
            503,
        )
    if codigo == 429:
        return IAIndisponivel(
            "O limite de uso gratuito do Gemini foi atingido. Aguarde um minuto e tente de novo "
            "(se continuar, o limite do dia acabou e volta amanhã).",
            429,
        )
    if codigo == 400:
        return IAIndisponivel(
            "A IA não conseguiu processar esse arquivo. Tente outro formato (PDF ou imagem) ou cole o texto.", 422
        )
    return IAIndisponivel("O serviço de IA está indisponível no momento. Tente novamente em instantes.")


def _gerar(cliente, modelo: str, blocos: list[dict]):
    return cliente.models.generate_content(
        model=modelo,
        contents=_partes(blocos),
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCOES,
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
            max_output_tokens=16000,
        ),
    )


def ler_com_gemini(blocos: list[dict]) -> ResultadoIA:
    global _modelo_descoberto
    cliente = obter_cliente()
    modelo = modelo_em_uso()
    try:
        try:
            resposta = _gerar(cliente, modelo, blocos)
        except errors.APIError as exc:
            if exc.code != 404:
                raise
            # O Google aposentou o modelo: escolhe sozinho o "Flash" disponível mais novo e tenta de novo.
            novo = descobrir_modelo(cliente)
            if not novo or novo == modelo:
                raise
            _modelo_descoberto = modelo = novo
            resposta = _gerar(cliente, modelo, blocos)
    except errors.APIError as exc:
        raise _erro_api(exc) from exc
    except httpx.TimeoutException as exc:
        raise IAIndisponivel("A leitura demorou demais. Tente de novo ou envie um arquivo menor.", 504) from exc
    except httpx.HTTPError as exc:
        raise IAIndisponivel("Não foi possível falar com o serviço de IA. Tente novamente em instantes.") from exc

    uso = resposta.usage_metadata
    entrada = int(getattr(uso, "prompt_token_count", 0) or 0)
    # Tokens de "raciocínio" também são cobrados como saída.
    saida = int(getattr(uso, "candidates_token_count", 0) or 0) + int(getattr(uso, "thoughts_token_count", 0) or 0)

    candidato = resposta.candidates[0] if resposta.candidates else None
    motivo = str(getattr(candidato, "finish_reason", "") or "")
    if "MAX_TOKENS" in motivo:
        raise com_uso(
            IAIndisponivel("A cotação é grande demais para ler de uma vez. Divida o arquivo e tente de novo.", 422),
            entrada, saida,
        )
    try:
        dados = json.loads(resposta.text or "")
    except (ValueError, TypeError):
        dados = None
    if not isinstance(dados, dict):
        raise com_uso(
            IAIndisponivel("A IA não conseguiu ler essa cotação. Confira o arquivo e tente de novo."), entrada, saida
        )
    return ResultadoIA(normalizar_resposta(dados), entrada, saida, modelo)
