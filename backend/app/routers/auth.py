from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import usuario_atual
from ..models import Usuario
from ..schemas import LoginIn, UsuarioOut
from ..security import COOKIE_NAME, criar_token, verificar_senha

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UsuarioOut)
def login(dados: LoginIn, response: Response, db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(func.lower(Usuario.email) == dados.email.strip().lower()))
    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    if not usuario.ativo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuário desativado. Fale com o administrador.")
    s = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        criar_token(usuario.id),
        max_age=s.jwt_expire_hours * 3600,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path="/",
    )
    return usuario


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(usuario_atual)):
    return usuario
