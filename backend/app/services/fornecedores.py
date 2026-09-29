from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import Fornecedor, Registro
from ..normalizacao import normalizar
from .registros import atualizar_busca

CAMPOS_CONTATO = ("cnpj", "contato", "telefone", "email")


def buscar_por_nome(db: Session, nome: str) -> Fornecedor | None:
    return db.scalar(select(Fornecedor).where(Fornecedor.nome_normalizado == normalizar(nome)))


def vincular(db: Session, registro: Registro, nome: str | None) -> None:
    """Liga o registro ao fornecedor com o mesmo nome normalizado (criando se não existir)."""
    if not nome:
        registro.fornecedor_id = None
        registro.fornecedor_nome = None
        registro.fornecedor = None
        return
    fornecedor = buscar_por_nome(db, nome)
    if fornecedor is None:
        fornecedor = Fornecedor(nome=nome, nome_normalizado=normalizar(nome))
        db.add(fornecedor)
    # Completa o cadastro com os dados de contato do registro, sem sobrescrever o que já existe.
    for campo in CAMPOS_CONTATO:
        if not getattr(fornecedor, campo) and getattr(registro, campo):
            setattr(fornecedor, campo, getattr(registro, campo))
    db.flush()
    registro.fornecedor = fornecedor
    registro.fornecedor_id = fornecedor.id
    registro.fornecedor_nome = fornecedor.nome


def contar_registros(db: Session, fornecedor_id: int) -> int:
    return db.scalar(select(func.count(Registro.id)).where(Registro.fornecedor_id == fornecedor_id)) or 0


def previa_renomear(db: Session, fornecedor: Fornecedor, novo_nome: str) -> dict:
    alvo = buscar_por_nome(db, novo_nome)
    juntar_com = alvo if alvo and alvo.id != fornecedor.id else None
    return {
        "registros_alterados": contar_registros(db, fornecedor.id),
        "juntar_com": {"id": juntar_com.id, "nome": juntar_com.nome} if juntar_com else None,
    }


def atualizar(db: Session, fornecedor: Fornecedor, dados: dict) -> tuple[Fornecedor, int, bool]:
    """Atualiza o cadastro. Se o nome mudar, propaga para os registros; se já existir, junta os dois.

    Retorna (fornecedor resultante, registros alterados, juntou).
    """
    novo_nome = dados["nome"]
    alvo = buscar_por_nome(db, novo_nome)
    alterados = 0

    if alvo and alvo.id != fornecedor.id:
        # Junta: o outro fornecedor passa a ser o cadastro principal.
        alvo.nome = novo_nome
        for campo in (*CAMPOS_CONTATO, "observacoes"):
            valor = dados.get(campo) or getattr(fornecedor, campo)
            if valor and not getattr(alvo, campo):
                setattr(alvo, campo, valor)
        alterados = db.execute(
            update(Registro)
            .where(Registro.fornecedor_id == fornecedor.id)
            .values(fornecedor_id=alvo.id, fornecedor_nome=novo_nome)
        ).rowcount
        db.execute(update(Registro).where(Registro.fornecedor_id == alvo.id).values(fornecedor_nome=novo_nome))
        db.delete(fornecedor)
        db.flush()
        _refazer_busca(db, alvo.id)
        return alvo, alterados, True

    nome_mudou = fornecedor.nome != novo_nome
    for campo, valor in dados.items():
        setattr(fornecedor, campo, valor)
    fornecedor.nome_normalizado = normalizar(novo_nome)
    if nome_mudou:
        alterados = db.execute(
            update(Registro).where(Registro.fornecedor_id == fornecedor.id).values(fornecedor_nome=novo_nome)
        ).rowcount
        db.flush()
        _refazer_busca(db, fornecedor.id)
    return fornecedor, alterados, False


def _refazer_busca(db: Session, fornecedor_id: int) -> None:
    db.expire_all()
    for registro in db.scalars(select(Registro).where(Registro.fornecedor_id == fornecedor_id)):
        atualizar_busca(registro)
