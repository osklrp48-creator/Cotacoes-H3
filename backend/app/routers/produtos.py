from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import usuario_atual
from ..models import Item, Registro, Unidade, Usuario
from ..normalizacao import normalizar, normalizar_unidade
from ..services.registros import NAO_INFORMADO, apagar_registros_vazios

router = APIRouter(tags=["produtos"])


def _linhas(db: Session, *filtros):
    q = (
        select(
            Item.id,
            Item.registro_id,
            Item.produto,
            Item.produto_normalizado,
            Item.marca,
            Item.unidade_medida,
            Item.quantidade,
            Item.valor_unitario,
            Registro.data_recebimento,
            Registro.fornecedor_nome,
            Registro.fornecedor_id,
            Unidade.nome.label("unidade"),
        )
        .join(Registro, Registro.id == Item.registro_id)
        .join(Unidade, Unidade.id == Registro.unidade_id)
        .where(*filtros)
    )
    return db.execute(q).all()


def _ponto(linha) -> dict:
    return {
        "valor": float(linha.valor_unitario),
        "fornecedor": linha.fornecedor_nome or NAO_INFORMADO,
        "data": linha.data_recebimento,
    }


def _por_data(linha):
    return (linha.data_recebimento, linha.id)


def _por_valor(linha):
    return (linha.valor_unitario, linha.data_recebimento, linha.id)


def _marcas(linhas) -> list[str]:
    vistas: dict[str, str] = {}
    for linha in linhas:
        if linha.marca:
            vistas.setdefault(normalizar(linha.marca), linha.marca)
    return sorted(vistas.values(), key=normalizar)


@router.get("/produtos")
def listar(
    busca: str = "",
    ordem: Literal["alfa", "recente", "mais"] = "alfa",
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_atual),
):
    grupos: dict[tuple[str, str], list] = defaultdict(list)
    for linha in _linhas(db):
        grupos[(linha.produto_normalizado, linha.unidade_medida)].append(linha)

    termo = normalizar(busca)
    produtos = []
    for (chave, un), linhas in grupos.items():
        if termo and termo not in chave and not any(termo in normalizar(l.marca) for l in linhas):
            continue
        ultimo = max(linhas, key=_por_data)
        produtos.append(
            {
                "nome": ultimo.produto,
                "chave": chave,
                "unidade_medida": un,
                "marcas": _marcas(linhas),
                "qtd_valores": len(linhas),
                "menor": _ponto(min(linhas, key=_por_valor)),
                "ultimo": _ponto(ultimo),
                "maior": _ponto(max(linhas, key=_por_valor)),
            }
        )

    if ordem == "recente":
        produtos.sort(key=lambda p: (p["ultimo"]["data"], normalizar(p["nome"])), reverse=True)
    elif ordem == "mais":
        produtos.sort(key=lambda p: (-p["qtd_valores"], normalizar(p["nome"])))
    else:
        produtos.sort(key=lambda p: (p["chave"], p["unidade_medida"]))
    return produtos


def _filtro_produto(nome: str, un: str):
    return (Item.produto_normalizado == normalizar(nome), Item.unidade_medida == normalizar_unidade(un))


@router.get("/produtos/detalhe")
def detalhe(nome: str, un: str = "", db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    linhas = _linhas(db, *_filtro_produto(nome, un))
    if not linhas:
        raise HTTPException(404, "Produto não encontrado.")
    por_valor = sorted(linhas, key=_por_valor)
    menor = float(por_valor[0].valor_unitario)
    ultimo = max(linhas, key=_por_data)
    return {
        "nome": ultimo.produto,
        "chave": ultimo.produto_normalizado,
        "unidade_medida": ultimo.unidade_medida,
        "marcas": _marcas(linhas),
        "qtd_valores": len(linhas),
        "menor": _ponto(por_valor[0]),
        "ultimo": _ponto(ultimo),
        "maior": _ponto(por_valor[-1]),
        "valores": [
            {
                "item_id": l.id,
                "registro_id": l.registro_id,
                "data": l.data_recebimento,
                "fornecedor": l.fornecedor_nome or NAO_INFORMADO,
                "fornecedor_id": l.fornecedor_id,
                "produto": l.produto,
                "marca": l.marca,
                "quantidade": float(l.quantidade) if l.quantidade is not None else None,
                "valor": float(l.valor_unitario),
                "unidade": l.unidade,
                "diferenca_pct": round((float(l.valor_unitario) - menor) / menor * 100, 2) if menor else None,
            }
            for l in por_valor
        ],
    }


@router.delete("/produtos")
def apagar_produto(nome: str, un: str = "", db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    filtros = _filtro_produto(nome, un)
    registro_ids = set(db.scalars(select(Item.registro_id).where(*filtros)))
    if not registro_ids:
        raise HTTPException(404, "Produto não encontrado.")
    itens = db.execute(delete(Item).where(*filtros)).rowcount
    registros = apagar_registros_vazios(db, registro_ids)
    db.commit()
    return {"itens_apagados": itens, "registros_apagados": registros}


@router.delete("/itens/{item_id}")
def apagar_item(item_id: int, db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Valor não encontrado.")
    registro_id = item.registro_id
    db.execute(delete(Item).where(Item.id == item_id))
    registros = apagar_registros_vazios(db, {registro_id})
    db.commit()
    return {"itens_apagados": 1, "registros_apagados": registros}
