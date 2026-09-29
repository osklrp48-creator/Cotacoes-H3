def test_usuario_comum_nao_acessa_admin(cliente):
    assert cliente.get("/api/usuarios").status_code == 403
    assert cliente.post("/api/unidades", json={"nome": "X"}).status_code == 403
    assert cliente.get("/api/admin/uso-ia").status_code == 403
    assert cliente.get("/api/unidades").status_code == 200  # todos veem as unidades (filtro)


def test_crud_unidades_e_usuarios(admin):
    r = admin.post("/api/unidades", json={"nome": "Filial Sul"})
    assert r.status_code == 201
    uid = r.json()["id"]
    assert admin.post("/api/unidades", json={"nome": "filial sul"}).status_code == 409

    r = admin.post("/api/usuarios", json={"nome": "Carla", "email": "carla@h3.com.br", "senha": "12345678", "unidade_id": uid})
    assert r.status_code == 201
    assert r.json()["perfil"] == "usuario"
    assert "senha_hash" not in r.json()

    r = admin.post("/api/usuarios", json={"nome": "X", "email": "x@h3.com.br", "senha": "123", "unidade_id": uid})
    assert r.status_code == 422
    assert "senha" in r.json()["detail"]

    assert admin.delete(f"/api/unidades/{uid}").status_code == 409  # tem usuário


def test_admin_nao_se_rebaixa(admin, usuarios):
    adm, _ = usuarios
    r = admin.put(f"/api/usuarios/{adm.id}", json={"perfil": "usuario"})
    assert r.status_code == 422
