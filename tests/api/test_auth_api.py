from tests.api.conftest import TEST_EMAIL, TEST_PASSWORD


def test_login_with_correct_credentials_sets_cookie(client):
    resp = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert resp.status_code == 200
    assert resp.json() == {"email": TEST_EMAIL}
    assert "cubiapp_session" in resp.cookies


def test_login_with_wrong_password_is_rejected(client):
    resp = client.post("/auth/login", json={"email": TEST_EMAIL, "password": "incorrecta"})
    assert resp.status_code == 401


def test_login_with_unauthorized_email_is_rejected_with_same_message(client):
    resp_wrong_email = client.post("/auth/login", json={"email": "otro@example.com", "password": TEST_PASSWORD})
    resp_wrong_password = client.post("/auth/login", json={"email": TEST_EMAIL, "password": "incorrecta"})
    assert resp_wrong_email.status_code == 401
    assert resp_wrong_password.status_code == 401
    assert resp_wrong_email.json()["detail"] == resp_wrong_password.json()["detail"]


def test_protected_endpoint_without_cookie_is_401(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_returns_authenticated_email(authed_client):
    resp = authed_client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"email": TEST_EMAIL}


def test_logout_then_me_is_401_again(authed_client):
    resp = authed_client.post("/auth/logout")
    assert resp.status_code == 204

    resp_me = authed_client.get("/auth/me")
    assert resp_me.status_code == 401
