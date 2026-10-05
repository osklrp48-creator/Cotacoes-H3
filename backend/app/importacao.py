"""Importação única do cotacoes-export.json ({"cotacoes": [...], "fornecedores": [...]})."""

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Fornecedor, Registro, Unidade, Usuario
from .normalizacao import limpar, normalizar
from .routers.registros import aplicar_dados
from .schemas import RegistroIn
from .services.fornecedores import buscar_por_nome

ALIASES = {
    "fornecedor": ("fornecedor", "quemPassou", "quem_passou", "fornecedorNome", "fornecedor_nome"),
    "data": ("data", "dataRecebimento", "data_recebimento", "recebidoEm", "dataCotacao"),
    "cnpj": ("cnpj",),
    "contato": ("contato",),
    "telefone": ("telefone", "fone", "whatsapp"),
    "email": ("email", "e-mail"),
    "numero": ("numero", "numeroCotacao", "numero_cotacao", "nCotacao", "num"),
    "status": ("status",),
    "pagamento": ("pagamento", "condicaoPagamento", "condicao_pagamento", "condPagamento"),
    "entrega": ("entrega", "prazoEntrega", "prazo_entrega"),
    "frete": ("frete", "tipoFrete"),
    "valorFrete": ("valorFrete", "valor_frete"),
    "referencia": ("referencia", "ref", "referenciaInterna", "referencia_interna"),
    "obs": ("obs", "observacoes", "observacao"),
    "criadoEm": ("criadoEm", "criado_em", "createdAt"),
    "atualizadoEm": ("atualizadoEm", "atualizado_em", "updatedAt"),
    "id": ("id", "_id", "uuid"),
}
ALIASES_ITEM = {
    "produto": ("produto", "nome"),
    "descricao": ("descricao", "descrição", "detalhes", "especificacao"),
    "marca": ("marca", "fabricante"),
    "unidade": ("unidade", "un", "unidadeMedida", "unidade_medida"),
    "qtd": ("qtd", "quantidade", "qtde"),
    "valorUnit": ("valorUnit", "valor_unitario", "valorUnitario", "valor", "preco"),
}
STATUS = {
    "recebida": "recebida",
    "em analise": "em_analise",
    "em_analise": "em_analise",
    "analise": "em_analise",
    "aprovada": "aprovada",
    "recusada": "recusada",
}


def _pegar(d: dict, aliases: tuple[str, ...]):
    for a in aliases:
        if a in d and d[a] not in (None, ""):
            return d[a]
    return None


def _texto(v) -> str | None:
    return limpar(str(v)) if v is not None else None


def _numero(v, casas: int) -> Decimal | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        d = Decimal(str(v))
    else:
        t = re.sub(r"[^\d,.\-]", "", str(v))
        if not t:
            return None
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        try:
            d = Decimal(t)
        except InvalidOperation:
            return None
    if d < 0:
        return None
    return d.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)


def _data(v) -> date | None:
    if not v:
        return None
    t = str(v).strip()
    try:
        return date.fromisoformat(t[:10])
    except ValueError:
        pass
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", t)
    if m:
        dia, mes, ano = (int(x) for x in m.groups())
        ano += 2000 if ano < 100 else 0
        try:
            return date(ano, mes, dia)
        except ValueError:
            return None
    return None


def _data_hora(v) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _referencia(c: dict) -> str:
    ident = _pegar(c, ALIASES["id"])
    if ident is not None:
        return f"export:{ident}"[:120]
    conteudo = json.dumps(c, sort_keys=True, ensure_ascii=False, default=str)
    return "export-hash:" + hashlib.sha1(conteudo.encode()).hexdigest()


@dataclass
class Resumo:
    simulado: bool = False
    importados: int = 0
    ja_existentes: int = 0
    ignorados: int = 0
    itens: int = 0
    fornecedores: int = 0
    avisos: list[str] = field(default_factory=list)

    def texto(self) -> str:
        linhas = [
            "SIMULAÇÃO (nada foi gravado)" if self.simulado else "Importação concluída",
            f"  Registros importados: {self.importados}",
            f"  Itens importados: {self.itens}",
            f"  Já importados antes (pulados): {self.ja_existentes}",
            f"  Ignorados por erro: {self.ignorados}",
            f"  Fornecedores do cadastro processados: {self.fornecedores}",
        ]
        if self.avisos:
            linhas.append("Avisos:")
            linhas += [f"  - {a}" for a in self.avisos]
        return "\n".join(linhas)


def converter_cotacao(c: dict, avisos: list[str], rotulo: str) -> dict | None:
    data = _data(_pegar(c, ALIASES["data"])) or _data(_pegar(c, ALIASES["criadoEm"]))
    if data is None:
        avisos.append(f"{rotulo}: sem data de recebimento válida, ignorado.")
        return None

    itens = []
    for n, i in enumerate(c.get("itens") or [], start=1):
        if not isinstance(i, dict):
            continue
        produto = _texto(_pegar(i, ALIASES_ITEM["produto"]))
        descricao = _texto(_pegar(i, ALIASES_ITEM["descricao"]))
        if not produto and descricao:
            # Exportações antigas que só têm "descricao": ela é o nome do produto.
            produto, descricao = descricao, None
        valor = _numero(_pegar(i, ALIASES_ITEM["valorUnit"]), 4)
        if not produto or valor is None:
            avisos.append(f"{rotulo}, item {n}: sem produto ou valor unitário, item ignorado.")
            continue
        itens.append(
            {
                "produto": produto,
                "descricao": descricao,
                "marca": _texto(_pegar(i, ALIASES_ITEM["marca"])),
                "unidade_medida": _texto(_pegar(i, ALIASES_ITEM["unidade"])),
                "quantidade": _numero(_pegar(i, ALIASES_ITEM["qtd"]), 3),
                "valor_unitario": valor,
            }
        )
    if not itens:
        avisos.append(f"{rotulo}: nenhum item válido, ignorado.")
        return None

    status = STATUS.get(normalizar(_texto(_pegar(c, ALIASES["status"])) or "recebida"), "recebida")
    frete = (_texto(_pegar(c, ALIASES["frete"])) or "").upper()
    valor_frete = _numero(_pegar(c, ALIASES["valorFrete"]), 2)
    return {
        "fornecedor": _texto(_pegar(c, ALIASES["fornecedor"])),
        "data_recebimento": data,
        "cnpj": _texto(_pegar(c, ALIASES["cnpj"])),
        "contato": _texto(_pegar(c, ALIASES["contato"])),
        "telefone": _texto(_pegar(c, ALIASES["telefone"])),
        "email": _texto(_pegar(c, ALIASES["email"])),
        "numero": _texto(_pegar(c, ALIASES["numero"])),
        "status": status,
        "condicao_pagamento": _texto(_pegar(c, ALIASES["pagamento"])),
        "prazo_entrega": _texto(_pegar(c, ALIASES["entrega"])),
        "frete": frete if frete in ("CIF", "FOB") else None,
        "valor_frete": valor_frete if valor_frete else None,
        "referencia_interna": _texto(_pegar(c, ALIASES["referencia"])),
        "observacoes": _texto(_pegar(c, ALIASES["obs"])),
        "itens": itens,
    }


def importar_dados(
    db: Session, conteudo: dict, unidade_id: int, usuario_id: int | None = None, simular: bool = False
) -> Resumo:
    if not isinstance(conteudo, dict) or not isinstance(conteudo.get("cotacoes"), list):
        raise ValueError('O arquivo precisa ter o formato {"cotacoes": [...], "fornecedores": [...]}.')
    if not db.get(Unidade, unidade_id):
        raise ValueError(f"Unidade {unidade_id} não encontrada. Crie a unidade no painel admin antes.")
    if usuario_id is None:
        usuario_id = db.scalar(select(Usuario.id).where(Usuario.perfil == "admin").order_by(Usuario.id))
        if usuario_id is None:
            raise ValueError("Nenhum admin encontrado. Rode primeiro o comando criar-admin.")
    elif not db.get(Usuario, usuario_id):
        raise ValueError(f"Usuário {usuario_id} não encontrado.")

    resumo = Resumo(simulado=simular)

    for f in conteudo.get("fornecedores") or []:
        nome = _texto(_pegar(f, ("nome", "fornecedor", "razaoSocial"))) if isinstance(f, dict) else None
        if not nome:
            continue
        fornecedor = buscar_por_nome(db, nome)
        if fornecedor is None:
            fornecedor = Fornecedor(nome=nome[:200], nome_normalizado=normalizar(nome)[:200])
            db.add(fornecedor)
        for campo, aliases in (
            ("cnpj", ("cnpj",)),
            ("contato", ("contato",)),
            ("telefone", ("telefone", "fone")),
            ("email", ("email",)),
            ("observacoes", ("observacoes", "obs")),
        ):
            valor = _texto(_pegar(f, aliases))
            if valor and not getattr(fornecedor, campo):
                setattr(fornecedor, campo, valor)
        db.flush()
        resumo.fornecedores += 1

    referencias_existentes = set(db.scalars(select(Registro.importacao_ref).where(Registro.importacao_ref.is_not(None))))
    for n, c in enumerate(conteudo["cotacoes"], start=1):
        rotulo = f"Cotação {n}"
        if not isinstance(c, dict):
            resumo.ignorados += 1
            resumo.avisos.append(f"{rotulo}: formato inválido, ignorada.")
            continue
        ref = _referencia(c)
        if ref in referencias_existentes:
            resumo.ja_existentes += 1
            continue
        dados = converter_cotacao(c, resumo.avisos, rotulo)
        if dados is None:
            resumo.ignorados += 1
            continue
        try:
            entrada = RegistroIn.model_validate(dados)
        except ValidationError as exc:
            resumo.ignorados += 1
            resumo.avisos.append(f"{rotulo}: dados inválidos ({exc.error_count()} erro(s)), ignorada.")
            continue

        registro = Registro(unidade_id=unidade_id, usuario_id=usuario_id, importacao_ref=ref)
        db.add(registro)
        aplicar_dados(db, registro, entrada)
        criado = _data_hora(_pegar(c, ALIASES["criadoEm"]))
        if criado:
            registro.criado_em = criado
        atualizado = _data_hora(_pegar(c, ALIASES["atualizadoEm"]))
        if atualizado or criado:
            registro.atualizado_em = atualizado or criado
        referencias_existentes.add(ref)
        resumo.importados += 1
        resumo.itens += len(entrada.itens)

    if simular:
        db.rollback()
    else:
        db.commit()
    return resumo


def importar_arquivo(
    db: Session, caminho: str, unidade_id: int, usuario_id: int | None = None, simular: bool = False
) -> Resumo:
    try:
        if caminho == "-":  # lê da entrada padrão (útil com docker compose exec)
            texto = sys.stdin.buffer.read().decode("utf-8-sig")
        else:
            arquivo = Path(caminho)
            if not arquivo.exists():
                raise ValueError(f"Arquivo não encontrado: {caminho}")
            texto = arquivo.read_text(encoding="utf-8-sig")
        conteudo = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ValueError(f"O arquivo não é um JSON válido: {exc}") from exc
    return importar_dados(db, conteudo, unidade_id, usuario_id, simular)
