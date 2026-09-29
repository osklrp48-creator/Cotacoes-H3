"""Leitura de cotações com a API da Anthropic (saída estruturada via tool use)."""

import re
from dataclasses import dataclass
from datetime import date

import anthropic

from ...config import get_settings

CNPJ_H3 = "26643172000177"
NOME_FERRAMENTA = "registrar_cotacao"


class IAIndisponivel(Exception):
    """Erro com mensagem pronta para o usuário."""

    def __init__(self, mensagem: str, status: int = 502):
        super().__init__(mensagem)
        self.status = status


PROMPT_SISTEMA = """Você lê cotações/orçamentos de preços recebidos pela H3 Pharma Comércio e Serviços Ltda. \
e extrai os dados para um formulário. Chame SEMPRE a ferramenta registrar_cotacao com o resultado.

Regras:
1. A H3 Pharma Comércio e Serviços Ltda. (CNPJ 26.643.172/0001-77) é a COMPRADORA. Nunca use a H3, \
seu nome, CNPJ, endereço ou contatos como dados do fornecedor.
2. O fornecedor é quem está vendendo/passando o preço. Pode ser empresa, loja ou pessoa física sem CNPJ \
(ex.: "João (WhatsApp)").
3. Não invente dados. Se uma informação não aparece, use "" para textos e 0 para números.
4. Números: use ponto como separador decimal e sem separador de milhar (ex.: "1.234,50" vira 1234.5; \
"R$ 12,3456" vira 12.3456).
5. valorUnit é o preço de UMA unidade do item. Se só houver o valor total da linha, divida pela quantidade.
6. Inclua TODOS os itens da cotação, na ordem em que aparecem, mesmo que sejam muitos.
7. data: data da cotação/recebimento no formato AAAA-MM-DD; se não houver, use "".
8. frete: "CIF" (frete pago pelo fornecedor/incluso) ou "FOB" (pago pelo comprador); se não estiver claro, "".
9. unidade: unidade de medida abreviada em maiúsculas (UN, CX, FR, PCT, KG, L, AMP, CP, ...).
10. obs: só observações relevantes da cotação (validade, condições especiais); sem repetir outros campos."""

_TEXTO = {"type": "string"}
_NUMERO = {"type": "number"}

FERRAMENTA = {
    "name": NOME_FERRAMENTA,
    "description": "Registra os dados extraídos da cotação para pré-preencher o formulário.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "fornecedor": {**_TEXTO, "description": "Nome de quem passou o valor (empresa, loja ou pessoa)"},
            "cnpj": _TEXTO,
            "contato": {**_TEXTO, "description": "Nome da pessoa de contato do fornecedor"},
            "telefone": _TEXTO,
            "email": _TEXTO,
            "numero": {**_TEXTO, "description": "Número da cotação/orçamento/proposta"},
            "data": {**_TEXTO, "description": "AAAA-MM-DD ou vazio"},
            "pagamento": {**_TEXTO, "description": "Condição de pagamento"},
            "entrega": {**_TEXTO, "description": "Prazo de entrega"},
            "frete": {"type": "string", "enum": ["CIF", "FOB", ""]},
            "valorFrete": _NUMERO,
            "obs": _TEXTO,
            "itens": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "produto": _TEXTO,
                        "marca": _TEXTO,
                        "unidade": _TEXTO,
                        "qtd": _NUMERO,
                        "valorUnit": _NUMERO,
                    },
                    "required": ["produto", "marca", "unidade", "qtd", "valorUnit"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "fornecedor", "cnpj", "contato", "telefone", "email", "numero", "data",
            "pagamento", "entrega", "frete", "valorFrete", "obs", "itens",
        ],
        "additionalProperties": False,
    },
}


@dataclass
class ResultadoIA:
    dados: dict
    tokens_entrada: int
    tokens_saida: int
    modelo: str = ""


def obter_cliente() -> anthropic.Anthropic:
    chave = get_settings().anthropic_api_key
    if not chave:
        raise IAIndisponivel("A leitura com IA não está configurada no servidor (falta a ANTHROPIC_API_KEY).", 503)
    return anthropic.Anthropic(api_key=chave, timeout=180, max_retries=2)


def _texto(v) -> str:
    return str(v).strip() if v is not None else ""


def _numero(v) -> float:
    if isinstance(v, bool):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v) if v == v and v >= 0 else 0.0  # descarta NaN e negativos
    t = re.sub(r"[^\d,.\-]", "", _texto(v))
    if not t:
        return 0.0
    if "," in t:  # formato brasileiro
        t = t.replace(".", "").replace(",", ".")
    try:
        return max(float(t), 0.0)
    except ValueError:
        return 0.0


def _digitos(v: str) -> str:
    return re.sub(r"\D", "", v)


def normalizar_resposta(bruto: dict) -> dict:
    """Garante tipos e formatos esperados pelo formulário, mesmo se a IA fugir do padrão."""
    dados = {c: _texto(bruto.get(c)) for c in (
        "fornecedor", "cnpj", "contato", "telefone", "email", "numero", "data", "pagamento", "entrega", "obs",
    )}
    try:
        date.fromisoformat(dados["data"])
    except ValueError:
        dados["data"] = ""
    frete = _texto(bruto.get("frete")).upper()
    dados["frete"] = frete if frete in ("CIF", "FOB") else ""
    dados["valorFrete"] = round(_numero(bruto.get("valorFrete")), 2)

    # Proteção extra: a H3 é a compradora, nunca o fornecedor.
    if _digitos(dados["cnpj"]) == CNPJ_H3:
        dados["cnpj"] = ""
    if "h3 pharma" in dados["fornecedor"].lower():
        dados["fornecedor"] = ""

    itens = []
    for item in bruto.get("itens") or []:
        if not isinstance(item, dict):
            continue
        produto = _texto(item.get("produto"))
        if not produto:
            continue
        itens.append(
            {
                "produto": produto,
                "marca": _texto(item.get("marca")),
                "unidade": _texto(item.get("unidade")).upper(),
                "qtd": _numero(item.get("qtd")),
                "valorUnit": round(_numero(item.get("valorUnit")), 4),
            }
        )
    dados["itens"] = itens
    return dados


def modelo_atual() -> str:
    s = get_settings()
    if s.ia_provedor == "gemini":
        from . import gemini

        return gemini.modelo_em_uso()
    return s.anthropic_model


def ler_cotacao(blocos: list[dict]) -> ResultadoIA:
    """Lê a cotação com o provedor configurado em IA_PROVEDOR (gemini ou anthropic)."""
    if get_settings().ia_provedor == "gemini":
        from . import gemini

        return gemini.ler_com_gemini(blocos)
    return ler_com_anthropic(blocos)


def ler_com_anthropic(blocos: list[dict]) -> ResultadoIA:
    cliente = obter_cliente()
    s = get_settings()
    try:
        resposta = cliente.messages.create(
            model=s.anthropic_model,
            max_tokens=16000,
            system=PROMPT_SISTEMA,
            tools=[FERRAMENTA],
            # Os modelos atuais não aceitam tool_choice forçado; "auto" + instrução no prompt + strict.
            tool_choice={"type": "auto"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        *blocos,
                        {"type": "text", "text": "Extraia os dados desta cotação com a ferramenta registrar_cotacao."},
                    ],
                }
            ],
        )
    except anthropic.AuthenticationError as exc:
        raise IAIndisponivel("A chave da API de IA é inválida. Avise o administrador.", 503) from exc
    except anthropic.RateLimitError as exc:
        raise IAIndisponivel("Muitas leituras ao mesmo tempo. Aguarde um minuto e tente de novo.", 429) from exc
    except anthropic.APITimeoutError as exc:
        raise IAIndisponivel("A leitura demorou demais. Tente de novo ou envie um arquivo menor.", 504) from exc
    except anthropic.BadRequestError as exc:
        raise IAIndisponivel(
            "A IA não conseguiu processar esse arquivo. Tente outro formato (PDF ou imagem) ou cole o texto.", 422
        ) from exc
    except anthropic.APIError as exc:
        raise IAIndisponivel("O serviço de IA está indisponível no momento. Tente novamente em instantes.") from exc

    uso = getattr(resposta, "usage", None)
    entrada = int(getattr(uso, "input_tokens", 0) or 0)
    saida = int(getattr(uso, "output_tokens", 0) or 0)

    bloco = next(
        (b for b in resposta.content if getattr(b, "type", None) == "tool_use" and b.name == NOME_FERRAMENTA), None
    )
    if bloco is None or not isinstance(bloco.input, dict):
        raise com_uso(IAIndisponivel("A IA não conseguiu ler essa cotação. Confira o arquivo e tente de novo."),
                       entrada, saida)
    if resposta.stop_reason == "max_tokens":
        raise com_uso(
            IAIndisponivel("A cotação é grande demais para ler de uma vez. Divida o arquivo e tente de novo.", 422),
            entrada, saida,
        )
    return ResultadoIA(normalizar_resposta(bloco.input), entrada, saida, s.anthropic_model)


def com_uso(erro: IAIndisponivel, entrada: int, saida: int) -> IAIndisponivel:
    erro.tokens_entrada = entrada  # type: ignore[attr-defined]
    erro.tokens_saida = saida  # type: ignore[attr-defined]
    return erro
