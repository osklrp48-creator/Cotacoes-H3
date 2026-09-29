from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import somente_admin, usuario_atual
from ..models import Registro, Unidade, Usuario
from ..schemas import UnidadeIn, UnidadeOut

router = APIRouter(prefix="/unidades", tags=["unidades"])


def _nome_em_uso(db: Session, nome: str, ignorar_id: int | None = None) -> bool:
    q = select(Unidade.id).where(func.lower(Unidade.nome) == nome.lower())
    if ignorar_id:
        q = q.where(Unidade.id != ignorar_id)
    return db.scalar(q) is not None


@router.get("", response_model=list[UnidadeOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(usuario_atual)):
    return db.scalars(select(Unidade).order_by(Unidade.nome)).all()


@router.post("", response_model=UnidadeOut, status_code=201)
def criar(dados: UnidadeIn, db: Session = Depends(get_db), _: Usuario = Depends(somente_admin)):
    if _nome_em_uso(db, dados.nome):
        raise HTTPException(409, "Já existe uma unidade com esse nome.")
    unidade = Unidade(nome=dados.nome, ativo=dados.ativo)
    db.add(unidade)
    db.commit()
    return unidade


@router.put("/{unidade_id}", response_model=UnidadeOut)
def atualizar(unidade_id: int, dados: UnidadeIn, db: Session = Depends(get_db), _: Usuario = Depends(somente_admin)):
    unidade = db.get(Unidade, unidade_id)
    if not unidade:
        raise HTTPException(404, "Unidade não encontrada.")
    if _nome_em_uso(db, dados.nome, unidade_id):
        raise HTTPException(409, "Já existe uma unidade com esse nome.")
    unidade.nome = dados.nome
    unidade.ativo = dados.ativo
    db.commit()
    return unidade


@router.delete("/{unidade_id}", status_code=204)
def excluir(unidade_id: int, db: Session = Depends(get_db), _: Usuario = Depends(somente_admin)):
    unidade = db.get(Unidade, unidade_id)
    if not unidade:
        raise HTTPException(404, "Unidade não encontrada.")
    em_uso = db.scalar(select(exists().where(Usuario.unidade_id == unidade_id))) or db.scalar(
        select(exists().where(Registro.unidade_id == unidade_id))
    )
    if em_uso:
        raise HTTPException(409, "Esta unidade tem usuários ou registros. Desative-a em vez de excluir.")
    db.delete(unidade)
    db.commit()
