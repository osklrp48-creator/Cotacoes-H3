from datetime import date, datetime, time, timedelta, timezone

import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import somente_admin
from ..models import Unidade, UsoIA, Usuario
from ..importacao import importar_dados
from ..services.ia import leitor

router = APIRouter(prefix="/admin", tags=["admin"])


def _custo(entrada: int, saida: int) -> float:
    preco_entrada, preco_saida = get_settings().precos_ia()
    return round(entrada / 1_000_000 * preco_entrada + saida / 1_000_000 * preco_saida, 4)


@router.get("/uso-ia")
def uso_ia(
    de: date | None = None,
    ate: date | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(somente_admin),
):
    hoje = date.today()
    de = de or hoje.replace(day=1)
    ate = ate or hoje
    filtros = (
        UsoIA.criado_em >= datetime.combine(de, time.min, tzinfo=timezone.utc),
        UsoIA.criado_em < datetime.combine(ate + timedelta(days=1), time.min, tzinfo=timezone.utc),
    )
    colunas = (
        func.count(UsoIA.id).label("leituras"),
        func.count(UsoIA.id).filter(UsoIA.sucesso.is_(False)).label("falhas"),
        func.coalesce(func.sum(UsoIA.tokens_entrada), 0).label("entrada"),
        func.coalesce(func.sum(UsoIA.tokens_saida), 0).label("saida"),
    )

    def linha(nome, r):
        return {
            "nome": nome,
            "leituras": r.leituras,
            "falhas": r.falhas,
            "tokens_entrada": int(r.entrada),
            "tokens_saida": int(r.saida),
            "custo_estimado_usd": _custo(int(r.entrada), int(r.saida)),
        }

    total = db.execute(select(*colunas).where(*filtros)).one()
    por_usuario = db.execute(
        select(func.coalesce(Usuario.nome, "(usuário removido)").label("nome"), *colunas)
        .select_from(UsoIA)
        .outerjoin(Usuario, Usuario.id == UsoIA.usuario_id)
        .where(*filtros)
        .group_by(Usuario.id, Usuario.nome)
        .order_by(func.count(UsoIA.id).desc())
    ).all()
    por_unidade = db.execute(
        select(func.coalesce(Unidade.nome, "(unidade removida)").label("nome"), *colunas)
        .select_from(UsoIA)
        .outerjoin(Unidade, Unidade.id == UsoIA.unidade_id)
        .where(*filtros)
        .group_by(Unidade.id, Unidade.nome)
        .order_by(func.count(UsoIA.id).desc())
    ).all()
    return {
        "de": de,
        "ate": ate,
        "provedor": get_settings().ia_provedor,
        "modelo": leitor.modelo_atual(),
        "preco_entrada_mtok": get_settings().precos_ia()[0],
        "preco_saida_mtok": get_settings().precos_ia()[1],
        "total": linha("Total", total),
        "por_usuario": [linha(r.nome, r) for r in por_usuario],
        "por_unidade": [linha(r.nome, r) for r in por_unidade],
    }


LIMITE_IMPORTACAO_MB = 50


@router.post("/importar")
def importar(
    arquivo: UploadFile = File(...),
    unidade_id: int = Form(...),
    simular: bool = Form(True),
    db: Session = Depends(get_db),
    admin: Usuario = Depends(somente_admin),
):
    """Importa o cotacoes-export.json pela tela Admin (os registros ficam no nome do admin que importou)."""
    dados = arquivo.file.read(LIMITE_IMPORTACAO_MB * 1024 * 1024 + 1)
    if len(dados) > LIMITE_IMPORTACAO_MB * 1024 * 1024:
        raise HTTPException(422, f"O arquivo passa do limite de {LIMITE_IMPORTACAO_MB} MB.")
    try:
        conteudo = json.loads(dados.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(422, "O arquivo não é um JSON válido. Envie o cotacoes-export.json original.") from exc
    try:
        resumo = importar_dados(db, conteudo, unidade_id, admin.id, simular=simular)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return asdict(resumo)
