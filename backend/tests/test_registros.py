from tests.conftest import novo_registro


def test_criar_registro_minimo(cliente, usuarios):
    r = cliente.post("/api/registros", json={"data_recebimento": "2026-09-10", "itens": [{"produto": "Luva", "valor_unitario": "0.5"}]})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["fornecedor"] is None
    assert d["status"] == "recebida"
    assert d["unidade"]["nome"] == "Filial Norte"  # unidade do usuário
    assert d["usuario"]["nome"] == "Bruno"

    lista = cliente.get("/api/registros").json()
    assert lista["total"] == 1
    assert lista["registros"][0]["fornecedor"] == "Não informado"


def test_validacoes(cliente):
    r = cliente.post("/api/registros", json={"data_recebimento": "2026-09-10", "itens": []})
    assert r.status_code == 422
    assert "item" in r.json()["detail"]
    r = cliente.post("/api/registros", json={"itens": [{"produto": "A", "valor_unitario": 1}]})
    assert r.status_code == 422
    assert "data" in r.json()["detail"]
    r = cliente.post("/api/registros", json={"data_recebimento": "2026-09-10", "itens": [{"produto": " ", "valor_unitario": 1}]})
    assert r.status_code == 422
    assert "Item 1: produto" in r.json()["detail"]
    r = cliente.post("/api/registros", json=novo_registro(itens=[{"produto": "A", "valor_unitario": 1.23456}]))
    assert r.status_code == 422


def test_valor_4_casas_e_unidade_maiuscula(cliente):
    d = cliente.post("/api/registros", json=novo_registro()).json()
    assert d["itens"][0]["valor_unitario"] == 12.3456
    assert d["itens"][0]["unidade_medida"] == "CX"


def test_fornecedor_vinculado_automaticamente(cliente):
    a = cliente.post("/api/registros", json=novo_registro(fornecedor="João (WhatsApp)", telefone="11 99999-0000")).json()
    b = cliente.post("/api/registros", json=novo_registro(fornecedor="joao (whatsapp)")).json()
    assert a["fornecedor_id"] == b["fornecedor_id"]
    assert b["fornecedor"] == "João (WhatsApp)"
    fornecedores = cliente.get("/api/fornecedores").json()
    assert len(fornecedores) == 1
    assert fornecedores[0]["telefone"] == "11 99999-0000"
    assert fornecedores[0]["qtd_registros"] == 2


def test_busca_e_filtros(cliente, admin, unidades):
    cliente.post("/api/registros", json=novo_registro(status="aprovada"))
    admin.post("/api/registros", json=novo_registro(fornecedor="Loja Beta", itens=[{"produto": "Álcool Gel", "marca": "Asseptgel", "valor_unitario": 9}]))
    assert cliente.get("/api/registros", params={"busca": "alcool"}).json()["total"] == 1
    assert cliente.get("/api/registros", params={"busca": "ASSEPT"}).json()["total"] == 1
    assert cliente.get("/api/registros", params={"busca": "beta"}).json()["total"] == 1
    assert cliente.get("/api/registros", params={"busca": "ems"}).json()["total"] == 1
    assert cliente.get("/api/registros", params={"status": "aprovada"}).json()["total"] == 1
    matriz, _ = unidades
    r = cliente.get("/api/registros", params={"unidade_id": matriz.id}).json()
    assert r["total"] == 1 and r["registros"][0]["unidade"] == "Matriz"


def test_editar_e_excluir(cliente, admin):
    rid = cliente.post("/api/registros", json=novo_registro()).json()["id"]
    r = admin.put(f"/api/registros/{rid}", json=novo_registro(fornecedor=None, status="em_analise", itens=[{"produto": "Soro", "valor_unitario": 3}, {"produto": "Gaze", "valor_unitario": 1}]))
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "em_analise" and len(d["itens"]) == 2 and d["fornecedor"] is None
    assert d["usuario"]["nome"] == "Bruno"  # autor original é mantido
    assert admin.delete(f"/api/registros/{rid}").status_code == 204
    assert admin.get(f"/api/registros/{rid}").status_code == 404


def test_usuario_comum_nao_troca_unidade(cliente, unidades):
    matriz, _ = unidades
    r = cliente.post("/api/registros", json=novo_registro(unidade_id=matriz.id))
    assert r.status_code == 403


def test_admin_escolhe_unidade(admin, unidades):
    _, filial = unidades
    r = admin.post("/api/registros", json=novo_registro(unidade_id=filial.id))
    assert r.json()["unidade"]["id"] == filial.id
