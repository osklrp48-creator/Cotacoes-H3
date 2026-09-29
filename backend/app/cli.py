"""Comandos de administração.

    python -m app.cli criar-admin --nome "Fulano" --email fulano@h3.com.br --unidade "Matriz"
    python -m app.cli importar cotacoes-export.json --unidade-id 1 [--usuario-id 1] [--simular]
"""

import argparse
import getpass
import sys

from sqlalchemy import func, select

from .db import SessionLocal
from .models import Unidade, Usuario
from .security import gerar_hash


def criar_admin(args) -> int:
    senha = args.senha or getpass.getpass("Senha (mín. 8 caracteres): ")
    if len(senha) < 8:
        print("Erro: a senha precisa ter pelo menos 8 caracteres.")
        return 1
    if not args.senha and getpass.getpass("Repita a senha: ") != senha:
        print("Erro: as senhas não conferem.")
        return 1
    with SessionLocal() as db:
        if db.scalar(select(Usuario).where(func.lower(Usuario.email) == args.email.lower())):
            print(f"Erro: já existe um usuário com o e-mail {args.email}.")
            return 1
        unidade = db.scalar(select(Unidade).where(func.lower(Unidade.nome) == args.unidade.strip().lower()))
        if unidade is None:
            unidade = Unidade(nome=args.unidade.strip())
            db.add(unidade)
            db.flush()
            print(f"Unidade criada: {unidade.nome} (id {unidade.id})")
        usuario = Usuario(
            nome=args.nome.strip(),
            email=args.email.strip().lower(),
            senha_hash=gerar_hash(senha),
            perfil="admin",
            unidade_id=unidade.id,
        )
        db.add(usuario)
        db.commit()
        print(f"Admin criado: {usuario.email} (id {usuario.id}), unidade {unidade.nome}.")
    return 0


def importar(args) -> int:
    from .importacao import importar_arquivo

    with SessionLocal() as db:
        try:
            resumo = importar_arquivo(db, args.arquivo, args.unidade_id, args.usuario_id, simular=args.simular)
        except ValueError as exc:
            print(f"Erro: {exc}")
            return 1
    print(resumo.texto())
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Comandos do Cotações H3")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("criar-admin", help="Cria um usuário administrador")
    p.add_argument("--nome", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--unidade", required=True, help="Nome da unidade (é criada se não existir)")
    p.add_argument("--senha", help="Se omitida, é pedida no terminal")
    p.set_defaults(func=criar_admin)

    p = sub.add_parser("importar", help="Importa o cotacoes-export.json")
    p.add_argument("arquivo", help='Caminho do JSON, ou "-" para ler da entrada padrão')
    p.add_argument("--unidade-id", type=int, required=True)
    p.add_argument("--usuario-id", type=int, help="Usuário registrado como autor (padrão: primeiro admin)")
    p.add_argument("--simular", action="store_true", help="Mostra o resultado sem gravar nada")
    p.set_defaults(func=importar)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
