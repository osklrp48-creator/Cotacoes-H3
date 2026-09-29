from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import somente_admin
from ..models import Unidade, Usuario
from ..schemas import UsuarioAtualizar, UsuarioCriar, UsuarioOut
from ..security import gerar_hash

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


def _email_em_uso(db: Session, email: str, ignorar_id: int | None = None) -> bool:
    q = select(Usuario.id).where(func.lower(Usuario.email) == email.lower())
    if ignorar_id:
        q = q.where(Usuario.id != ignorar_id)
    return db.scalar(q) is not None


def _checar_unidade(db: Session, unidade_id: int) -> None:
    if not db.get(Unidade, unidade_id):
        raise HTTPException(422, "Unidade não encontrada.")


@router.get("", response_model=list[UsuarioOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(somente_admin)):
    return db.scalars(select(Usuario).order_by(Usuario.nome)).all()


@router.post("", response_model=UsuarioOut, status_code=201)
def criar(dados: UsuarioCriar, db: Session = Depends(get_db), _: Usuario = Depends(somente_admin)):
    if _email_em_uso(db, dados.email):
        raise HTTPException(409, "Já existe um usuário com esse e-mail.")
    _checar_unidade(db, dados.unidade_id)
    usuario = Usuario(
        nome=dados.nome.strip(),
        email=dados.email.lower(),
        senha_hash=gerar_hash(dados.senha),
        perfil=dados.perfil,
        unidade_id=dados.unidade_id,
        ativo=dados.ativo,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.put("/{usuario_id}", response_model=UsuarioOut)
def atualizar(
    usuario_id: int,
    dados: UsuarioAtualizar,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(somente_admin),
):
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(404, "Usuário não encontrado.")
    if usuario.id == admin.id and (dados.ativo is False or dados.perfil == "usuario"):
        raise HTTPException(422, "Você não pode desativar nem tirar o perfil de admin da sua própria conta.")
    if dados.email and _email_em_uso(db, dados.email, usuario_id):
        raise HTTPException(409, "Já existe um usuário com esse e-mail.")
    if dados.unidade_id is not None:
        _checar_unidade(db, dados.unidade_id)
    if dados.nome is not None:
        usuario.nome = dados.nome.strip()
    if dados.email is not None:
        usuario.email = dados.email.lower()
    if dados.senha:
        usuario.senha_hash = gerar_hash(dados.senha)
    for campo in ("perfil", "unidade_id", "ativo"):
        valor = getattr(dados, campo)
        if valor is not None:
            setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario
