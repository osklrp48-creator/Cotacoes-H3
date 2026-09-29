from tests.conftest import novo_registro


def test_ficha_com_valores(cliente):
    cliente.post("/api/registros", json=novo_registro(fornecedor="Alfa", numero="123"))
    f = cliente.get("/api/fornecedores").json()[0]
    ficha = cliente.get(f"/api/fornecedores/{f['id']}").json()
    assert ficha["nome"] == "Alfa"
    assert ficha["qtd_registros"] == 1
    assert ficha["valores"][0]["produto"] == "Dipirona 500mg"
    assert ficha["valores"][0]["numero"] == "123"


def test_renomear_atualiza_registros(cliente):
    for _ in range(2):
        cliente.post("/api/registros", json=novo_registro(fornecedor="Alfa Ltda"))
    fid = cliente.get("/api/fornecedores").json()[0]["id"]
    previa = cliente.get(f"/api/fornecedores/{fid}/previa", params={"nome": "Alfa Distribuidora"}).json()
    assert previa == {"registros_alterados": 2, "juntar_com": None}
    r = cliente.put(f"/api/fornecedores/{fid}", json={"nome": "Alfa Distribuidora", "cnpj": "11.111.111/0001-11"}).json()
    assert r["registros_alterados"] == 2 and r["juntou"] is False
    lista = cliente.get("/api/registros").json()["registros"]
    assert {x["fornecedor"] for x in lista} == {"Alfa Distribuidora"}
    assert cliente.get("/api/registros", params={"busca": "distribuidora"}).json()["total"] == 2


def test_renomear_para_existente_junta(cliente):
    cliente.post("/api/registros", json=novo_registro(fornecedor="Beta", telefone="1111"))
    cliente.post("/api/registros", json=novo_registro(fornecedor="Beta Comercio"))
    cliente.post("/api/registros", json=novo_registro(fornecedor="Beta Comercio"))
    fornecedores = {f["nome"]: f["id"] for f in cliente.get("/api/fornecedores").json()}
    origem, destino = fornecedores["Beta"], fornecedores["Beta Comercio"]

    previa = cliente.get(f"/api/fornecedores/{origem}/previa", params={"nome": "beta comércio"}).json()
    assert previa["registros_alterados"] == 1
    assert previa["juntar_com"] == {"id": destino, "nome": "Beta Comercio"}

    r = cliente.put(f"/api/fornecedores/{origem}", json={"nome": "Beta Comércio"}).json()
    assert r["juntou"] is True and r["registros_alterados"] == 1
    assert r["fornecedor"]["id"] == destino
    assert r["fornecedor"]["telefone"] == "1111"  # dados completados na junção
    lista = cliente.get("/api/fornecedores").json()
    assert len(lista) == 1 and lista[0]["qtd_registros"] == 3 and lista[0]["nome"] == "Beta Comércio"
    assert cliente.get(f"/api/fornecedores/{origem}").status_code == 404


def test_cadastro_manual(cliente):
    assert cliente.post("/api/fornecedores", json={"nome": "Gama"}).status_code == 201
    assert cliente.post("/api/fornecedores", json={"nome": "GAMA"}).status_code == 409
    assert cliente.get("/api/fornecedores").json()[0]["qtd_registros"] == 0
