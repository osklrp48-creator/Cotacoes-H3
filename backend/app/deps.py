from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import Usuario
from .security import COOKIE_NAME, ler_token


def usuario_atual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    token = request.cookies.get(COOKIE_NAME)
    usuario_id = ler_token(token) if token else None
    usuario = db.get(Usuario, usuario_id) if usuario_id else None
    if not usuario or not usuario.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Entre novamente.")
    return usuario


def somente_admin(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    if usuario.perfil != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acesso restrito a administradores.")
    return usuario
