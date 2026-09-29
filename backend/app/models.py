from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

PERFIS = ("admin", "usuario")
STATUS = ("recebida", "em_analise", "aprovada", "recusada")
FRETES = ("CIF", "FOB")


class Unidade(Base):
    __tablename__ = "unidades"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    perfil: Mapped[str] = mapped_column(Enum(*PERFIS, name="perfil_usuario"), default="usuario")
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades.id", ondelete="RESTRICT"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    unidade: Mapped[Unidade] = relationship(lazy="joined")


class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    nome_normalizado: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    cnpj: Mapped[str | None] = mapped_column(String(30))
    contato: Mapped[str | None] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(254))
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Registro(Base):
    __tablename__ = "registros"

    id: Mapped[int] = mapped_column(primary_key=True)
    fornecedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("fornecedores.id", ondelete="SET NULL"), index=True
    )
    fornecedor_nome: Mapped[str | None] = mapped_column(String(200))
    data_recebimento: Mapped[date] = mapped_column(Date, index=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades.id", ondelete="RESTRICT"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    atualizado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    cnpj: Mapped[str | None] = mapped_column(String(30))
    contato: Mapped[str | None] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(254))
    numero: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(
        Enum(*STATUS, name="status_registro"), default="recebida", server_default="recebida", index=True
    )
    condicao_pagamento: Mapped[str | None] = mapped_column(String(200))
    prazo_entrega: Mapped[str | None] = mapped_column(String(200))
    frete: Mapped[str | None] = mapped_column(Enum(*FRETES, name="tipo_frete"))
    valor_frete: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    referencia_interna: Mapped[str | None] = mapped_column(String(120))
    observacoes: Mapped[str | None] = mapped_column(Text)
    # Texto normalizado (fornecedor + produtos + marcas) usado na busca.
    busca: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Identificador de origem para a importação não duplicar registros se for rodada de novo.
    importacao_ref: Mapped[str | None] = mapped_column(String(120), unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    unidade: Mapped[Unidade] = relationship(lazy="joined")
    usuario: Mapped[Usuario] = relationship(foreign_keys=[usuario_id], lazy="joined")
    fornecedor: Mapped[Fornecedor | None] = relationship(lazy="joined")
    itens: Mapped[list["Item"]] = relationship(
        back_populates="registro", cascade="all, delete-orphan", order_by="Item.id", lazy="selectin"
    )


class Item(Base):
    __tablename__ = "itens"

    id: Mapped[int] = mapped_column(primary_key=True)
    registro_id: Mapped[int] = mapped_column(ForeignKey("registros.id", ondelete="CASCADE"), index=True)
    produto: Mapped[str] = mapped_column(String(300))
    produto_normalizado: Mapped[str] = mapped_column(String(300), index=True)
    marca: Mapped[str | None] = mapped_column(String(120))
    unidade_medida: Mapped[str] = mapped_column(String(20), default="", server_default="")
    quantidade: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4))

    registro: Mapped[Registro] = relationship(back_populates="itens")


class UsoIA(Base):
    __tablename__ = "uso_ia"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    unidade_id: Mapped[int | None] = mapped_column(ForeignKey("unidades.id", ondelete="SET NULL"), index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    tipo_entrada: Mapped[str] = mapped_column(String(20))
    modelo: Mapped[str] = mapped_column(String(80))
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0)
    tokens_saida: Mapped[int] = mapped_column(Integer, default=0)
    sucesso: Mapped[bool] = mapped_column(Boolean, default=True)
