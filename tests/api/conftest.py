import pytest
from fastapi.testclient import TestClient

from src.core.settings import Settings, hash_password

TEST_PASSWORD = "una-contrasena-de-test-segura"
TEST_EMAIL = "cayetanocanovas13@gmail.com"


@pytest.fixture
def api_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_api_test.db"))
    monkeypatch.setenv("CUBIAPP_CONFIG_DIR", str(tmp_path / "config"))
    Settings(config_dir=str(tmp_path / "config")).save_password_hash(hash_password(TEST_PASSWORD))
    return tmp_path


@pytest.fixture
def client(api_env):
    from src.api.app import create_app

    return TestClient(create_app())


@pytest.fixture
def authed_client(client):
    resp = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert resp.status_code == 200
    return client
