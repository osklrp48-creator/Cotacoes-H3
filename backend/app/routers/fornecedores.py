from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import usuario_atual
from ..models import Fornecedor, Item, Registro, Unidade, Usuario
from ..normalizacao import normalizar
from ..schemas import FornecedorIn
from ..services import fornecedores as svc

router = APIRouter(prefix="/fornecedores", tags=["fornecedores"])

CAMPOS = ("nome", "cnpj", "contato", "telefone", "email", "observacoes")


def _dados(f: Fornecedor) -> dict:
    return {"id": f.id, **{c: getattr(f, c) for c in CAMPOS}}


def _obter(db: Session, fornecedor_id: int) -> Fornecedor:
    fornecedor = db.get(Fornecedor, fornecedor_id)
    if not fornecedor:
        raise HTTPException(404, "Fornecedor não encontrado.")
    return fornecedor


@router.get("")
def listar(busca: str = "", db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    estatisticas = (
        select(
            Registro.fornecedor_id,
            func.count(Registro.id).label("qtd"),
            func.max(Registro.data_recebimento).label("ultimo"),
        )
        .where(Registro.fornecedor_id.is_not(None))
        .group_by(Registro.fornecedor_id)
        .subquery()
    )
    q = (
        select(Fornecedor, estatisticas.c.qtd, estatisticas.c.ultimo)
        .outerjoin(estatisticas, estatisticas.c.fornecedor_id == Fornecedor.id)
        .order_by(Fornecedor.nome_normalizado)
    )
    termo = normalizar(busca)
    if termo:
        q = q.where(Fornecedor.nome_normalizado.contains(termo, autoescape=True) | Fornecedor.cnpj.contains(busca.strip(), autoescape=True))
    return [
        {**_dados(f), "qtd_registros": qtd or 0, "ultimo_registro": ultimo}
        for f, qtd, ultimo in db.execute(q).all()
    ]


@router.post("", status_code=201)
def criar(dados: FornecedorIn, db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    if svc.buscar_por_nome(db, dados.nome):
        raise HTTPException(409, "Já existe um fornecedor com esse nome.")
    fornecedor = Fornecedor(**dados.model_dump(), nome_normalizado=normalizar(dados.nome))
    db.add(fornecedor)
    db.commit()
    return _dados(fornecedor)


@router.get("/{fornecedor_id}")
def obter(fornecedor_id: int, db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    fornecedor = _obter(db, fornecedor_id)
    linhas = db.execute(
        select(
            Item.id,
            Item.produto,
            Item.marca,
            Item.unidade_medida,
            Item.quantidade,
            Item.valor_unitario,
            Registro.id.label("registro_id"),
            Registro.data_recebimento,
            Registro.numero,
            Registro.status,
            Unidade.nome.label("unidade"),
        )
        .join(Registro, Registro.id == Item.registro_id)
        .join(Unidade, Unidade.id == Registro.unidade_id)
        .where(Registro.fornecedor_id == fornecedor_id)
        .order_by(Registro.data_recebimento.desc(), Registro.id.desc(), Item.id)
    ).all()
    return {
        **_dados(fornecedor),
        "qtd_registros": svc.contar_registros(db, fornecedor_id),
        "valores": [
            {
                "item_id": l.id,
                "registro_id": l.registro_id,
                "data": l.data_recebimento,
                "numero": l.numero,
                "status": l.status,
                "unidade": l.unidade,
                "produto": l.produto,
                "marca": l.marca,
                "unidade_medida": l.unidade_medida,
                "quantidade": float(l.quantidade) if l.quantidade is not None else None,
                "valor": float(l.valor_unitario),
            }
            for l in linhas
        ],
    }


@router.get("/{fornecedor_id}/previa")
def previa(fornecedor_id: int, nome: str, db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    """Quantos registros serão alterados ao renomear e se o nome novo já pertence a outro fornecedor."""
    fornecedor = _obter(db, fornecedor_id)
    if not nome.strip():
        raise HTTPException(422, "Informe o nome do fornecedor.")
    return svc.previa_renomear(db, fornecedor, nome.strip())


@router.put("/{fornecedor_id}")
def atualizar(
    fornecedor_id: int, dados: FornecedorIn, db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)
):
    fornecedor = _obter(db, fornecedor_id)
    resultado, alterados, juntou = svc.atualizar(db, fornecedor, dados.model_dump())
    db.commit()
    return {"fornecedor": _dados(resultado), "registros_alterados": alterados, "juntou": juntou}
