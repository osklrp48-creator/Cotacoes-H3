def test_login_errado(anonimo, usuarios):
    r = anonimo.post("/api/auth/login", json={"email": "admin@h3.com.br", "senha": "errada"})
    assert r.status_code == 401
    assert r.json()["detail"] == "E-mail ou senha incorretos."


def test_login_me_logout(admin):
    r = admin.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["perfil"] == "admin"
    assert r.json()["unidade"]["nome"] == "Matriz"
    admin.post("/api/auth/logout")
    assert admin.get("/api/auth/me").status_code == 401


def test_cookie_httponly(anonimo, usuarios):
    r = anonimo.post("/api/auth/login", json={"email": "ADMIN@h3.com.br", "senha": "senha12345"})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()


def test_rotas_protegidas(anonimo):
    for metodo, rota in [
        ("get", "/api/registros"),
        ("get", "/api/produtos"),
        ("get", "/api/fornecedores"),
        ("get", "/api/unidades"),
        ("post", "/api/ia/ler-cotacao"),
        ("get", "/api/admin/uso-ia"),
    ]:
        assert getattr(anonimo, metodo)(rota).status_code == 401, rota


def test_usuario_desativado_nao_entra(admin, usuarios, anonimo):
    _, comum = usuarios
    assert admin.put(f"/api/usuarios/{comum.id}", json={"ativo": False}).status_code == 200
    r = anonimo.post("/api/auth/login", json={"email": "bruno@h3.com.br", "senha": "senha12345"})
    assert r.status_code == 403
