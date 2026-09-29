from tests.conftest import novo_registro


def _item(produto, valor, un="CX", marca=None):
    return {"produto": produto, "valor_unitario": valor, "unidade_medida": un, "marca": marca}


def test_agrupamento_e_estatisticas(cliente):
    cliente.post("/api/registros", json=novo_registro(fornecedor="Alfa", data_recebimento="2026-01-10", itens=[_item("Dipirona 500mg", 10, marca="EMS")]))
    cliente.post("/api/registros", json=novo_registro(fornecedor="Beta", data_recebimento="2026-03-10", itens=[_item("DIPIRONA 500MG", 8, "cx", "Medley")]))
    cliente.post("/api/registros", json=novo_registro(fornecedor=None, data_recebimento="2026-02-10", itens=[_item("dipirona 500 mg", 12)]))
    cliente.post("/api/registros", json=novo_registro(data_recebimento="2026-02-10", itens=[_item("Dipirona 500mg", 20, "FR"), _item("Água destilada", 2, "FR")]))

    produtos = cliente.get("/api/produtos").json()
    chaves = [(p["chave"], p["unidade_medida"]) for p in produtos]
    assert chaves == [("agua destilada", "FR"), ("dipirona 500 mg", "CX"), ("dipirona 500mg", "CX"), ("dipirona 500mg", "FR")]
    dip = produtos[2]
    assert dip["qtd_valores"] == 2
    assert dip["marcas"] == ["EMS", "Medley"]
    assert dip["menor"] == {"valor": 8.0, "fornecedor": "Beta", "data": "2026-03-10"}
    assert dip["maior"]["valor"] == 10.0
    assert dip["ultimo"]["fornecedor"] == "Beta"

    assert [p["chave"] for p in cliente.get("/api/produtos", params={"ordem": "mais"}).json()][0] == "dipirona 500mg"
    assert cliente.get("/api/produtos", params={"ordem": "recente"}).json()[0]["ultimo"]["data"] == "2026-03-10"
    assert len(cliente.get("/api/produtos", params={"busca": "agua"}).json()) == 1
    assert len(cliente.get("/api/produtos", params={"busca": "medley"}).json()) == 1
    nao = cliente.get("/api/produtos/detalhe", params={"nome": "dipirona 500 mg", "un": "CX"}).json()
    assert nao["valores"][0]["fornecedor"] == "Não informado"


def test_detalhe_ordenado_com_diferenca(cliente):
    for data, valor in (("2026-01-01", 10), ("2026-02-01", 12.5), ("2026-03-01", 8)):
        cliente.post("/api/registros", json=novo_registro(data_recebimento=data, itens=[_item("Seringa 5ml", valor, "UN")]))
    d = cliente.get("/api/produtos/detalhe", params={"nome": "SERINGA 5ML", "un": "un"}).json()
    assert [v["valor"] for v in d["valores"]] == [8.0, 10.0, 12.5]
    assert [v["diferenca_pct"] for v in d["valores"]] == [0.0, 25.0, 56.25]
    assert d["ultimo"]["valor"] == 8.0
    assert cliente.get("/api/produtos/detalhe", params={"nome": "nada"}).status_code == 404


def test_apagar_produto_remove_registros_vazios(cliente):
    so_dip = cliente.post("/api/registros", json=novo_registro(itens=[_item("Dipirona", 1)])).json()["id"]
    misto = cliente.post("/api/registros", json=novo_registro(itens=[_item("Dipirona", 2), _item("Gaze", 3)])).json()["id"]
    r = cliente.delete("/api/produtos", params={"nome": "dipirona", "un": "CX"})
    assert r.json() == {"itens_apagados": 2, "registros_apagados": 1}
    assert cliente.get(f"/api/registros/{so_dip}").status_code == 404
    restante = cliente.get(f"/api/registros/{misto}").json()
    assert [i["produto"] for i in restante["itens"]] == ["Gaze"]
    assert cliente.get("/api/registros", params={"busca": "dipirona"}).json()["total"] == 0


def test_apagar_um_valor(cliente):
    rid = cliente.post("/api/registros", json=novo_registro(itens=[_item("Gaze", 3)])).json()["id"]
    item_id = cliente.get(f"/api/registros/{rid}").json()["itens"][0]["id"]
    assert cliente.delete(f"/api/itens/{item_id}").json()["registros_apagados"] == 1
    assert cliente.get(f"/api/registros/{rid}").status_code == 404
    assert cliente.delete(f"/api/itens/{item_id}").status_code == 404
