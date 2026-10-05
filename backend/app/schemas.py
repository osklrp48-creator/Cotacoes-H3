from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .normalizacao import limpar

Status = Literal["recebida", "em_analise", "aprovada", "recusada"]
Perfil = Literal["admin", "usuario"]


class ModeloSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class LoginIn(BaseModel):
    email: str
    senha: str


class UnidadeOut(ModeloSaida):
    id: int
    nome: str
    ativo: bool


class UsuarioOut(ModeloSaida):
    id: int
    nome: str
    email: str
    perfil: Perfil
    ativo: bool
    unidade: UnidadeOut


# ---------- Unidades / usuários ----------
class UnidadeIn(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    ativo: bool = True

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Informe o nome da unidade.")
        return v


class UsuarioCriar(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=128)
    perfil: Perfil = "usuario"
    unidade_id: int
    ativo: bool = True


class UsuarioAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    senha: str | None = Field(default=None, min_length=8, max_length=128)
    perfil: Perfil | None = None
    unidade_id: int | None = None
    ativo: bool | None = None


# ---------- Registros ----------
class TextoOpcional(BaseModel):
    """Converte strings vazias em None em todos os campos de texto."""

    @field_validator("*", mode="before")
    @classmethod
    def _vazio(cls, v):
        if isinstance(v, str):
            return limpar(v)
        return v


class ItemIn(TextoOpcional):
    produto: str = Field(max_length=300)
    marca: str | None = Field(default=None, max_length=120)
    descricao: str | None = Field(default=None, max_length=4000)
    unidade_medida: str | None = Field(default=None, max_length=20)
    quantidade: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    valor_unitario: Decimal = Field(ge=0, max_digits=14, decimal_places=4)


class RegistroIn(TextoOpcional):
    fornecedor: str | None = Field(default=None, max_length=200)
    data_recebimento: date
    unidade_id: int | None = None  # só o admin pode escolher; usuário comum usa a própria unidade
    cnpj: str | None = Field(default=None, max_length=30)
    contato: str | None = Field(default=None, max_length=200)
    telefone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=254)
    numero: str | None = Field(default=None, max_length=60)
    status: Status = "recebida"
    condicao_pagamento: str | None = Field(default=None, max_length=200)
    prazo_entrega: str | None = Field(default=None, max_length=200)
    frete: Literal["CIF", "FOB"] | None = None
    valor_frete: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    referencia_interna: str | None = Field(default=None, max_length=120)
    observacoes: str | None = None
    itens: list[ItemIn] = Field(min_length=1)


class ItemOut(ModeloSaida):
    id: int
    produto: str
    marca: str | None
    descricao: str | None
    unidade_medida: str
    quantidade: float | None
    valor_unitario: float


class Pessoa(ModeloSaida):
    id: int
    nome: str


class RegistroOut(ModeloSaida):
    id: int
    fornecedor_id: int | None
    fornecedor: str | None
    data_recebimento: date
    unidade: Pessoa
    usuario: Pessoa
    cnpj: str | None
    contato: str | None
    telefone: str | None
    email: str | None
    numero: str | None
    status: Status
    condicao_pagamento: str | None
    prazo_entrega: str | None
    frete: str | None
    valor_frete: float | None
    referencia_interna: str | None
    observacoes: str | None
    criado_em: datetime
    atualizado_em: datetime
    itens: list[ItemOut]


class RegistroResumo(BaseModel):
    id: int
    data_recebimento: date
    fornecedor: str
    unidade: str
    usuario: str
    numero: str | None
    status: Status
    qtd_itens: int
    itens_resumo: str


class ListaRegistros(BaseModel):
    total: int
    registros: list[RegistroResumo]


# ---------- Fornecedores ----------
class FornecedorIn(TextoOpcional):
    nome: str = Field(max_length=200)
    cnpj: str | None = Field(default=None, max_length=30)
    contato: str | None = Field(default=None, max_length=200)
    telefone: str | None = Field(default=None, max_length=60)
    email: str | None = Field(default=None, max_length=254)
    observacoes: str | None = None

    @field_validator("nome")
    @classmethod
    def _nome(cls, v):
        if not v:
            raise ValueError("Informe o nome do fornecedor.")
        return v
