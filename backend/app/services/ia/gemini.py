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

# Erros temporários do lado do Google (instabilidade/sobrecarga): a leitura tenta outro modelo.
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
            # Sem novas tentativas no mesmo modelo: com "high demand" o que resolve é trocar de modelo.
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


# Modelo descoberto automaticamente quando o configurado em GEMINI_MODEL não existe mais.
_modelo_descoberto: str | None = None

_EXCLUIR = ("image", "tts", "audio", "live", "embedding", "vision", "learnlm", "robotics", "omni")


# Modelo reserva usado por sobrecarga do principal: vale por um tempo, depois o principal é tentado de novo.
_modelo_temporario: tuple[str, float] | None = None
LEMBRAR_RESERVA_SEGUNDOS = 30 * 60


def modelo_em_uso() -> str:
    if _modelo_temporario and time.monotonic() < _modelo_temporario[1]:
        return _modelo_temporario[0]
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
        cota = re.search(r"limit: *(\d+)", exc.message or "")
        extra = f" (cota informada pelo Google para o último modelo: {cota[1]})" if cota else ""
        return IAIndisponivel(
            "O limite de uso gratuito do Gemini foi atingido" + extra + ". "
            "Aguarde um minuto e tente de novo (se continuar, o limite do dia acabou e volta amanhã). " + detalhe,
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


CAMPOS_SEM_SCHEMA = (
    "\n\nFormato da resposta: um único objeto JSON com exatamente estas chaves: "
    + json.dumps({k: 0 if k == "valorFrete" else "" for k in SCHEMA["properties"] if k != "itens"}, ensure_ascii=False)[:-1]
    + ', "itens": [{"produto": "", "marca": "", "unidade": "", "qtd": 0, "valorUnit": 0}]}. '
    "Números como número JSON (ponto decimal), textos como string."
)


def _gerar(cliente, modelo: str, blocos: list[dict], com_schema: bool = True, segundos: float = TEMPO_POR_CHAMADA):
    """Pede a leitura ao Gemini. Sem schema (plano B), o formato vai só nas instruções."""
    extras = {"response_json_schema": SCHEMA} if com_schema else {}
    return cliente.models.generate_content(
        model=modelo,
        contents=_partes(blocos),
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCOES if com_schema else INSTRUCOES + CAMPOS_SEM_SCHEMA,
            response_mime_type="application/json",
            max_output_tokens=16000,
            http_options=types.HttpOptions(timeout=int(segundos * 1000)),
            **extras,
        ),
    )


def _temporario(exc: Exception) -> bool:
    """Vale tentar outro modelo: demora, instabilidade (5xx) ou cota gratuita esgotada (429).

    No Gemini gratuito cada modelo tem a própria cota, então outro modelo pode estar livre.
    """
    return isinstance(exc, httpx.TimeoutException) or (
        isinstance(exc, errors.APIError) and exc.code in (*ERROS_TEMPORARIOS, 429)
    )


def ler_com_gemini(blocos: list[dict]) -> ResultadoIA:
    """Tenta, em ordem e dentro do prazo: modelo atual com schema; se falhar por instabilidade, o mesmo
    modelo sem schema (plano B); depois outros modelos "Flash" da chave, também sem schema."""
    global _modelo_descoberto, _modelo_temporario
    cliente = obter_cliente()
    principal = modelo_em_uso()
    inicio = time.monotonic()

    def restante() -> float:
        return PRAZO_LEITURA - (time.monotonic() - inicio)

    fila: list[tuple[str, bool]] = [(principal, True)]
    tentados: list[str] = []
    reservas_na_fila = False
    primeiro_erro: Exception | None = None
    ultimo_erro: Exception | None = None
    resposta = None
    modelo = principal

    while fila and resposta is None:
        if ultimo_erro is not None and restante() < 10:
            break
        tentativa, com_schema = fila.pop(0)
        tentados.append(tentativa)
        try:
            resposta = _gerar(cliente, tentativa, blocos, com_schema, min(TEMPO_POR_CHAMADA, restante()))
            modelo = tentativa
        except (errors.APIError, httpx.TimeoutException) as exc:
            primeiro_erro = primeiro_erro or exc
            ultimo_erro = exc
            codigo = getattr(exc, "code", "timeout")
            log.warning(
                "Gemini %s (schema=%s) falhou: %s %s", tentativa, com_schema, codigo,
                (getattr(exc, "message", "") or "")[:300],
            )
            if codigo == 404:
                # O Google aposentou o modelo: escolhe sozinho o "Flash" disponível mais novo.
                if tentativa == principal:
                    try:
                        novo = descobrir_modelo(cliente)
                    except Exception:
                        novo = None
                    if novo and novo != tentativa:
                        fila.insert(0, (novo, True))
                continue
            if not _temporario(exc):
                break
            if com_schema and codigo not in (429, 503):
                # Plano B no mesmo modelo, sem schema (erro interno ou demora). Com 503 ("high demand")
                # ou 429 (cota) o problema é do modelo inteiro: vai direto para outro.
                fila.insert(0, (tentativa, False))
            if not reservas_na_fila:
                reservas_na_fila = True
                try:
                    outros = [m for m in modelos_disponiveis(cliente) if m != tentativa][:6]
                except Exception:  # sem lista de modelos: fica só com o que já está na fila
                    outros = []
                fila.extend((m, False) for m in outros)
        except httpx.HTTPError as exc:
            raise IAIndisponivel("Não foi possível falar com o serviço de IA. Tente novamente em instantes.") from exc

    if resposta is None:
        if isinstance(ultimo_erro, errors.APIError):
            erro = _erro_api(ultimo_erro)
            if len(set(tentados)) > 1:
                erro.args = (f"{erro.args[0]} Modelos tentados: {', '.join(dict.fromkeys(tentados))}.",)
            raise erro from ultimo_erro
        log.warning("Gemini não respondeu dentro do prazo (%s).", modelo)
        raise IAIndisponivel(
            "O Gemini (Google) não respondeu a tempo. Isso é do lado do Google; tente de novo daqui a pouco. "
            "Se continuar, use Admin → Uso da IA → Testar a IA.",
            504,
        ) from ultimo_erro

    if modelo != principal and isinstance(primeiro_erro, errors.APIError) and primeiro_erro.code in (404, 429):
        # Modelo principal aposentado ou sem cota: segue no que funcionou até o servidor reiniciar.
        _modelo_descoberto = modelo
    elif modelo != principal:
        # Principal sobrecarregado/lento: usa o que funcionou por 30 min antes de tentar o principal de novo.
        _modelo_temporario = (modelo, time.monotonic() + LEMBRAR_RESERVA_SEGUNDOS)

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
    texto = (resposta.text or "").strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto)
    try:
        dados = json.loads(texto)
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
    global _modelo_descoberto, _modelo_temporario
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
        _modelo_temporario = None
    return {
        "modelo_antes": atual,
        "modelo_em_uso": modelo_em_uso(),
        "erro_listagem": erro_lista,
        "resultados": resultados,
        "teste_leitura": _testar_leitura(cliente, modelo_em_uso()) if ok else None,
    }


def _testar_leitura(cliente, modelo: str) -> dict:
    """Uma leitura de verdade (curta), com e sem schema, para ver qual jeito o Google aceita."""
    blocos = [{"type": "text", "text": "Cotação: Dipirona 500mg cx 10 unidades R$ 12,50 - Distribuidora Alfa"}]
    resultado = {"modelo": modelo}
    for nome, com_schema in (("com_formato", True), ("sem_formato", False)):
        inicio = time.monotonic()
        try:
            _gerar(cliente, modelo, blocos, com_schema, 40)
            resultado[nome] = {"ok": True, "segundos": round(time.monotonic() - inicio, 1), "erro": ""}
        except errors.APIError as exc:
            resultado[nome] = {"ok": False, "segundos": round(time.monotonic() - inicio, 1),
                               "erro": f"{exc.code} {exc.status or ''}: {(exc.message or '')[:200]}"}
        except httpx.HTTPError as exc:
            resultado[nome] = {"ok": False, "segundos": round(time.monotonic() - inicio, 1),
                               "erro": f"sem resposta: {type(exc).__name__}"}
    return resultado
