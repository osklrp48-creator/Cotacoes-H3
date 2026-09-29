from app.importacao import importar_dados
from app.models import Fornecedor, Registro

EXPORT = {
    "cotacoes": [
        {
            "id": "abc1",
            "fornecedor": "Distribuidora Alfa",
            "data": "2026-05-02",
            "cnpj": "11.222.333/0001-44",
            "numero": "77",
            "status": "Em análise",
            "pagamento": "30 dias",
            "entrega": "7 dias",
            "frete": "fob",
            "valorFrete": "25,90",
            "obs": "ok",
            "criadoEm": "2026-05-02T10:00:00Z",
            "itens": [
                {"produto": "Dipirona", "marca": "EMS", "unidade": "cx", "qtd": "10", "valorUnit": "1.234,5678"},
                {"produto": "", "valorUnit": 3},
            ],
        },
        {"fornecedor": "", "data": "10/06/2026", "itens": [{"produto": "Gaze", "valorUnit": 2}]},
        {"fornecedor": "Sem data", "itens": [{"produto": "X", "valorUnit": 1}]},
    ],
    "fornecedores": [{"nome": "Distribuidora ALFA", "telefone": "1199"}, {"nome": "Só cadastro"}],
}


def test_importacao(db, usuarios, unidades):
    _, filial = unidades
    resumo = importar_dados(db, EXPORT, filial.id)
    assert (resumo.importados, resumo.ignorados, resumo.itens, resumo.fornecedores) == (2, 1, 2, 2)
    assert any("sem data" in a for a in resumo.avisos)

    registros = db.query(Registro).order_by(Registro.data_recebimento).all()
    alfa = registros[0]
    assert alfa.unidade_id == filial.id
    assert alfa.status == "em_analise" and alfa.frete == "FOB" and float(alfa.valor_frete) == 25.9
    assert float(alfa.itens[0].valor_unitario) == 1234.5678 and alfa.itens[0].unidade_medida == "CX"
    assert alfa.fornecedor.telefone == "1199"
    assert alfa.criado_em.year == 2026 and alfa.criado_em.month == 5
    assert registros[1].fornecedor_id is None
    assert db.query(Fornecedor).count() == 2

    # Rodar de novo não duplica.
    resumo2 = importar_dados(db, EXPORT, filial.id)
    assert resumo2.importados == 0 and resumo2.ja_existentes == 2
    assert db.query(Registro).count() == 2


def test_simulacao_nao_grava(db, usuarios, unidades):
    matriz, _ = unidades
    resumo = importar_dados(db, EXPORT, matriz.id, simular=True)
    assert resumo.importados == 2
    assert db.query(Registro).count() == 0


def test_importar_pela_tela_admin(admin, cliente, unidades, db):
    import json as _json

    _, filial = unidades
    arquivo = ("cotacoes-export.json", _json.dumps(EXPORT).encode(), "application/json")
    r = admin.post("/api/admin/importar", files={"arquivo": arquivo}, data={"unidade_id": filial.id, "simular": "true"})
    assert r.status_code == 200, r.text
    assert r.json()["importados"] == 2 and r.json()["simulado"] is True
    assert db.query(Registro).count() == 0

    r = admin.post("/api/admin/importar", files={"arquivo": arquivo}, data={"unidade_id": filial.id, "simular": "false"})
    assert r.json()["importados"] == 2
    assert db.query(Registro).count() == 2
    assert {x.usuario.nome for x in db.query(Registro)} == {"Ana Admin"}

    r = admin.post("/api/admin/importar", files={"arquivo": ("x.json", b"nao e json", "application/json")}, data={"unidade_id": filial.id})
    assert r.status_code == 422 and "JSON" in r.json()["detail"]
    assert cliente.post("/api/admin/importar", files={"arquivo": arquivo}, data={"unidade_id": filial.id}).status_code == 403


def test_admin_inicial_por_variaveis(db, monkeypatch):
    from app.cli import criar_admin_inicial
    from app.models import Usuario

    monkeypatch.setenv("ADMIN_EMAIL", "Chefe@H3.com.br")
    monkeypatch.setenv("ADMIN_SENHA", "senha-forte-123")
    monkeypatch.setenv("ADMIN_UNIDADE", "Matriz")
    assert criar_admin_inicial() == 0
    admin = db.query(Usuario).one()
    assert (admin.email, admin.perfil, admin.unidade.nome) == ("chefe@h3.com.br", "admin", "Matriz")
    # Rodar de novo (a cada reinício do servidor) não cria outro.
    monkeypatch.setenv("ADMIN_EMAIL", "outro@h3.com.br")
    criar_admin_inicial()
    assert db.query(Usuario).count() == 1
