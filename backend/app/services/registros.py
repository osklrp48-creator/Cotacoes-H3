from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import Item, Registro
from ..normalizacao import normalizar

NAO_INFORMADO = "Não informado"


def atualizar_busca(registro: Registro) -> None:
    partes = [registro.fornecedor_nome or ""]
    for item in registro.itens:
        partes.append(item.produto)
        partes.append(item.marca or "")
    registro.busca = normalizar(" ".join(p for p in partes if p))


def apagar_registros_vazios(db: Session, registro_ids: set[int]) -> int:
    """Apaga os registros (entre os informados) que ficaram sem itens. Retorna quantos foram apagados."""
    if not registro_ids:
        return 0
    com_itens = set(db.scalars(select(Item.registro_id).where(Item.registro_id.in_(registro_ids)).distinct()))
    vazios = registro_ids - com_itens
    if vazios:
        db.execute(delete(Registro).where(Registro.id.in_(vazios)))
    for registro in db.scalars(select(Registro).where(Registro.id.in_(com_itens))):
        db.refresh(registro, ["itens"])
        atualizar_busca(registro)
    return len(vazios)
