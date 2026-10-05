from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import usuario_atual
from ..models import STATUS, Item, Registro, Unidade, Usuario
from ..normalizacao import normalizar, normalizar_unidade
from ..schemas import ListaRegistros, RegistroIn, RegistroOut, RegistroResumo
from ..services import fornecedores as svc_fornecedores
from ..services.registros import NAO_INFORMADO, atualizar_busca

router = APIRouter(prefix="/registros", tags=["registros"])

CAMPOS_SIMPLES = (
    "data_recebimento",
    "cnpj",
    "contato",
    "telefone",
    "email",
    "numero",
    "status",
    "condicao_pagamento",
    "prazo_entrega",
    "frete",
    "valor_frete",
    "referencia_interna",
    "observacoes",
)


def para_saida(r: Registro) -> RegistroOut:
    return RegistroOut.model_validate(
        {
            **{c: getattr(r, c) for c in CAMPOS_SIMPLES},
            "id": r.id,
            "fornecedor_id": r.fornecedor_id,
            "fornecedor": r.fornecedor_nome,
            "unidade": r.unidade,
            "usuario": r.usuario,
            "criado_em": r.criado_em,
            "atualizado_em": r.atualizado_em,
            "itens": r.itens,
        }
    )


def resumo_itens(r: Registro, limite: int = 3) -> str:
    nomes = [i.produto for i in r.itens[:limite]]
    extra = len(r.itens) - limite
    return ", ".join(nomes) + (f" e mais {extra}" if extra > 0 else "")


def aplicar_dados(db: Session, registro: Registro, dados: RegistroIn) -> None:
    for campo in CAMPOS_SIMPLES:
        setattr(registro, campo, getattr(dados, campo))
    registro.itens = [
        Item(
            produto=i.produto,
            produto_normalizado=normalizar(i.produto),
            marca=i.marca,
            descricao=i.descricao,
            unidade_medida=normalizar_unidade(i.unidade_medida),
            quantidade=i.quantidade,
            valor_unitario=i.valor_unitario,
        )
        for i in dados.itens
    ]
    svc_fornecedores.vincular(db, registro, dados.fornecedor)
    atualizar_busca(registro)


def _unidade_para(db: Session, usuario: Usuario, unidade_id: int | None, atual: int) -> int:
    if unidade_id is None or unidade_id == atual:
        return atual
    if usuario.perfil != "admin":
        raise HTTPException(403, "Só o administrador pode mudar a unidade de um registro.")
    if not db.get(Unidade, unidade_id):
        raise HTTPException(422, "Unidade não encontrada.")
    return unidade_id


def _obter(db: Session, registro_id: int) -> Registro:
    registro = db.get(Registro, registro_id)
    if not registro:
        raise HTTPException(404, "Registro não encontrado.")
    return registro


@router.get("", response_model=ListaRegistros)
def listar(
    busca: str = "",
    status: str = "",
    unidade_id: int | None = None,
    limite: int = Query(50, ge=1, le=200),
    deslocamento: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: Usuario = Depends(usuario_atual),
):
    filtros = []
    termo = normalizar(busca)
    if termo:
        for palavra in termo.split(" "):
            filtros.append(Registro.busca.contains(palavra, autoescape=True))
    if status:
        if status not in STATUS:
            raise HTTPException(422, "Status inválido.")
        filtros.append(Registro.status == status)
    if unidade_id:
        filtros.append(Registro.unidade_id == unidade_id)

    total = db.scalar(select(func.count(Registro.id)).where(*filtros)) or 0
    registros = db.scalars(
        select(Registro)
        .where(*filtros)
        .order_by(Registro.data_recebimento.desc(), Registro.id.desc())
        .limit(limite)
        .offset(deslocamento)
    ).unique()
    return ListaRegistros(
        total=total,
        registros=[
            RegistroResumo(
                id=r.id,
                data_recebimento=r.data_recebimento,
                fornecedor=r.fornecedor_nome or NAO_INFORMADO,
                unidade=r.unidade.nome,
                usuario=r.usuario.nome,
                numero=r.numero,
                status=r.status,
                qtd_itens=len(r.itens),
                itens_resumo=resumo_itens(r),
            )
            for r in registros
        ],
    )


@router.post("", response_model=RegistroOut, status_code=201)
def criar(dados: RegistroIn, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)):
    registro = Registro(
        usuario_id=usuario.id,
        unidade_id=_unidade_para(db, usuario, dados.unidade_id, usuario.unidade_id),
    )
    db.add(registro)
    aplicar_dados(db, registro, dados)
    db.commit()
    db.refresh(registro)
    return para_saida(registro)


@router.get("/{registro_id}", response_model=RegistroOut)
def obter(registro_id: int, db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    return para_saida(_obter(db, registro_id))


@router.put("/{registro_id}", response_model=RegistroOut)
def atualizar(
    registro_id: int, dados: RegistroIn, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_atual)
):
    registro = _obter(db, registro_id)
    registro.unidade_id = _unidade_para(db, usuario, dados.unidade_id, registro.unidade_id)
    registro.atualizado_por_id = usuario.id
    aplicar_dados(db, registro, dados)
    db.commit()
    db.refresh(registro)
    return para_saida(registro)


@router.delete("/{registro_id}", status_code=204)
def excluir(registro_id: int, db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    db.delete(_obter(db, registro_id))
    db.commit()
