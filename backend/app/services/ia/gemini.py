"""Leitura de cotações com o Google Gemini (saída em JSON com schema)."""

import base64
import copy
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

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

log = logging.getLogger("cotacoes.ia")

# Erros temporários do lado do Google (instabilidade/sobrecarga): o SDK tenta de novo sozinho.
ERROS_TEMPORARIOS = (500, 502, 503, 504)

# Tempo máximo de uma leitura inteira (incluindo novas tentativas e modelos reserva), em segundos.
PRAZO_LEITURA = 100
TEMPO_POR_CHAMADA = 60


def obter_cliente() -> genai.Client:
    chave = get_settings().gemini_api_key
    if not chave:
        raise IAIndisponivel("A leitura com IA não está configurada no servidor (falta a GEMINI_API_KEY).", 503)
    return genai.Client(
        api_key=chave,
        http_options=types.HttpOptions(
            timeout=TEMPO_POR_CHAMADA * 1000,
            retry_options=types.HttpRetryOptions(
                attempts=2, initial_delay=2, max_delay=5, http_status_codes=list(ERROS_TEMPORARIOS)
            ),
        ),
    )


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


def modelos_disponiveis(cliente) -> list[str]:
    """Modelos "Flash" que esta chave pode usar, do melhor para o pior."""
    candidatos = []
    for modelo in cliente.models.list():
        nome = (modelo.name or "").removeprefix("models/")
        acoes = modelo.supported_actions or []
        if "flash" in nome and "generateContent" in acoes and not any(x in nome for x in _EXCLUIR):
            candidatos.append(nome)
    return sorted(candidatos, key=_prioridade, reverse=True)


def descobrir_modelo(cliente) -> str | None:
    """Pergunta ao Google quais modelos "Flash" esta chave pode usar e escolhe o melhor."""
    disponiveis = modelos_disponiveis(cliente)
    return disponiveis[0] if disponiveis else None


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
    detalhe = f"(detalhe técnico: {codigo} {exc.status or ''})".replace(" )", ")")
    log.warning("Erro do Gemini com o modelo %s: %s %s - %s", modelo_em_uso(), codigo, exc.status, exc.message)
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
            "A IA não conseguiu processar esse arquivo. Tente outro formato (PDF ou imagem) ou cole o texto. "
            + detalhe,
            422,
        )
    if codigo in ERROS_TEMPORARIOS:
        return IAIndisponivel(
            "O Gemini (Google) está sobrecarregado ou instável agora. Isso é do lado do Google e costuma passar "
            "em poucos minutos: tente de novo daqui a pouco. " + detalhe
        )
    return IAIndisponivel("O serviço de IA está indisponível no momento. Tente novamente em instantes. " + detalhe)


def _gerar(cliente, modelo: str, blocos: list[dict], segundos: float = TEMPO_POR_CHAMADA):
    return cliente.models.generate_content(
        model=modelo,
        contents=_partes(blocos),
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCOES,
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
            max_output_tokens=16000,
            http_options=types.HttpOptions(timeout=int(segundos * 1000)),
        ),
    )


def _temporario(exc: Exception) -> bool:
    return isinstance(exc, httpx.TimeoutException) or (
        isinstance(exc, errors.APIError) and exc.code in ERROS_TEMPORARIOS
    )


def ler_com_gemini(blocos: list[dict]) -> ResultadoIA:
    global _modelo_descoberto
    cliente = obter_cliente()
    modelo = modelo_em_uso()
    inicio = time.monotonic()

    def restante() -> float:
        return PRAZO_LEITURA - (time.monotonic() - inicio)

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
            resposta = _gerar(cliente, modelo, blocos, min(TEMPO_POR_CHAMADA, restante()))
    except (errors.APIError, httpx.TimeoutException) as exc:
        if not _temporario(exc):
            if isinstance(exc, errors.APIError):
                raise _erro_api(exc) from exc
            raise
        # Modelo sobrecarregado ou lento: tenta outros "Flash" da chave enquanto houver tempo.
        log.warning("Gemini %s sem resposta (%s); tentando outro modelo.", modelo, getattr(exc, "code", "timeout"))
        resposta = None
        ultimo_erro: Exception = exc
        try:
            reservas = [m for m in modelos_disponiveis(cliente) if m != modelo][:2]
        except (errors.APIError, httpx.HTTPError):
            reservas = []
        for reserva in reservas:
            if restante() < 15:
                break
            try:
                resposta = _gerar(cliente, reserva, blocos, min(TEMPO_POR_CHAMADA, restante()))
                modelo = reserva
                break
            except (errors.APIError, httpx.TimeoutException) as exc_reserva:
                if not _temporario(exc_reserva):
                    ultimo_erro = exc_reserva
                    break
                ultimo_erro = exc_reserva
        if resposta is None:
            if isinstance(ultimo_erro, errors.APIError):
                raise _erro_api(ultimo_erro) from ultimo_erro
            log.warning("Gemini não respondeu dentro do prazo (%s).", modelo)
            raise IAIndisponivel(
                "O Gemini (Google) não respondeu a tempo. Isso é do lado do Google; tente de novo daqui a pouco. "
                "Se continuar, use Admin → Uso da IA → Testar a IA.",
                504,
            ) from ultimo_erro
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


def _testar_modelo(cliente, modelo: str) -> dict:
    inicio = time.monotonic()
    try:
        cliente.models.generate_content(
            model=modelo,
            contents="Responda apenas com a palavra OK.",
            config=types.GenerateContentConfig(
                max_output_tokens=300,
                http_options=types.HttpOptions(timeout=25_000, retry_options=types.HttpRetryOptions(attempts=1)),
            ),
        )
        return {"modelo": modelo, "ok": True, "segundos": round(time.monotonic() - inicio, 1), "erro": ""}
    except errors.APIError as exc:
        erro = f"{exc.code} {exc.status or ''}: {(exc.message or '')[:200]}"
    except httpx.TimeoutException:
        erro = "não respondeu em 25 segundos"
    except httpx.HTTPError as exc:
        erro = f"falha de conexão: {exc}"[:200]
    return {"modelo": modelo, "ok": False, "segundos": round(time.monotonic() - inicio, 1), "erro": erro}


def diagnosticar() -> dict:
    """Testa rapidamente os modelos "Flash" da chave e passa a usar o melhor que responder."""
    global _modelo_descoberto
    cliente = obter_cliente()
    atual = modelo_em_uso()
    try:
        disponiveis = modelos_disponiveis(cliente)
        erro_lista = ""
    except (errors.APIError, httpx.HTTPError) as exc:
        disponiveis, erro_lista = [], f"Não foi possível listar os modelos: {exc}"[:300]
    testar = list(dict.fromkeys([atual, *disponiveis]))[:6]
    with ThreadPoolExecutor(max_workers=len(testar)) as pool:
        resultados = list(pool.map(lambda m: _testar_modelo(cliente, m), testar))
    ok = [r["modelo"] for r in resultados if r["ok"]]
    if ok and atual not in ok:
        _modelo_descoberto = max(ok, key=_prioridade)
    return {
        "modelo_antes": atual,
        "modelo_em_uso": modelo_em_uso(),
        "erro_listagem": erro_lista,
        "resultados": resultados,
    }
