import http.client
import json
import threading
from pathlib import Path

import pytest

from owlock.app.api import Api
from owlock.app.devserver import make_server
from owlock.core import Vault

FAST = {"time_cost": 1, "memory_cost": 8192, "parallelism": 1}
from tests._store import STORE  # noqa: E402
PW = "senha-mestra-1"


class Clip:
    text = ""

    def copy(self, t):
        self.text = t

    def paste(self):
        return self.text


@pytest.fixture
def server(tmp_path):
    path = tmp_path / "c.vault"
    Vault.create(path, PW, STORE, kdf_params=FAST)
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>oi</h1>")
    (tmp_path / "segredo.txt").write_text("segredo")
    srv = make_server(Api(path, clipboard=Clip(), store=STORE), 0, web_dir=web)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def request(srv, method, path, body=None, headers=None):
    port = srv.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    hdrs = dict(headers or {})
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    conn.request(method, path, body=data, headers=hdrs)
    r = conn.getresponse()
    payload = r.read()
    conn.close()
    return r.status, payload


def test_binds_loopback_only(server):
    assert server.server_address[0] == "127.0.0.1"


def test_status_and_unlock(server):
    code, raw = request(server, "POST", "/api/status", {"args": [], "kwargs": {}})
    assert code == 200 and json.loads(raw)["unlocked"] is False
    code, raw = request(server, "POST", "/api/unlock", {"args": ["errada-errada"]})
    assert json.loads(raw)["error"] == "wrong_password"
    code, raw = request(server, "POST", "/api/unlock", {"kwargs": {"password": PW}})
    assert json.loads(raw) == {"ok": True, "migrated": False}
    code, raw = request(server, "POST", "/api/status", {})
    assert json.loads(raw)["unlocked"] is True


def test_private_and_unknown_methods_404(server):
    for name in ("_vault", "__init__", "_require", "nao_existe"):
        assert request(server, "POST", f"/api/{name}", {})[0] == 404


def test_bad_body_400(server):
    assert request(server, "POST", "/api/status", b"{nao json")[0] == 400
    assert request(server, "POST", "/api/status", b"[1,2]")[0] == 400
    assert request(server, "POST", "/api/status", {"args": "x"})[0] == 400
    assert request(server, "POST", "/api/unlock", {"args": [1, 2, 3]})[0] == 400


def test_static_served(server):
    code, raw = request(server, "GET", "/")
    assert code == 200 and b"oi" in raw
    assert request(server, "GET", "/nao-existe.js")[0] == 404


@pytest.mark.parametrize(
    "path",
    ["/../segredo.txt", "/../../pyproject.toml", "/%2e%2e/segredo.txt",
     "/%2e%2e%2fsegredo.txt", "/..%2fsegredo.txt", "/%2E%2E/%2E%2E/etc/passwd",
     "/....//segredo.txt", "/..\\segredo.txt"],
)
def test_path_traversal_404(server, path):
    code, raw = request(server, "GET", path)
    assert code == 404
    assert b"segredo" not in raw.lower().replace(b"not found", b"")


def test_missing_web_dir_404(tmp_path):
    srv = make_server(Api(tmp_path / "c.vault", clipboard=Clip(), store=STORE), 0, web_dir=tmp_path / "nada")
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        assert request(srv, "GET", "/")[0] == 404
        assert request(srv, "GET", "/app.js")[0] == 404
    finally:
        srv.shutdown()
        srv.server_close()


def test_foreign_origin_403(server):
    code, _ = request(server, "POST", "/api/status", {}, {"Origin": "http://evil.example"})
    assert code == 403
    code, _ = request(server, "GET", "/", headers={"Origin": "http://evil.example"})
    assert code == 403


def test_same_origin_allowed(server):
    port = server.server_address[1]
    for origin in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
        code, _ = request(server, "POST", "/api/status", {}, {"Origin": origin})
        assert code == 200
    code, _ = request(server, "POST", "/api/status", {}, {"Origin": f"http://127.0.0.1:{port + 1}"})
    assert code == 403


def test_foreign_host_header_403(server):
    code, _ = request(server, "POST", "/api/status", {}, {"Host": "evil.example"})
    assert code == 403


def test_dev_store_is_a_folder_next_to_the_vault(tmp_path):
    from owlock.app.devserver import dev_store

    store = dev_store(tmp_path / "c.vault")
    assert store.directory == tmp_path / "c.vault.keys"


def test_dev_save_dialog_numbers_files_in_given_dir(tmp_path):
    from owlock.app.devserver import make_save_dialog

    dialog = make_save_dialog(tmp_path)
    assert dialog("a.html") == str(tmp_path / "owlock-kit-1.html")
    assert dialog("a.html") == str(tmp_path / "owlock-kit-2.html")
    import tempfile
    assert make_save_dialog().__call__("x").startswith(str(Path(tempfile.gettempdir()) / "owlock-kit-"))


def test_seed_vault_uses_file_store_next_to_it(tmp_path):
    from owlock.app.devserver import dev_store, seed_vault
    from owlock.core import crypto

    path = tmp_path / "seed.vault"
    orig = crypto.DEFAULT_KDF_PARAMS.copy()
    crypto.DEFAULT_KDF_PARAMS.update(FAST)
    try:
        seed_vault(path)
    finally:
        crypto.DEFAULT_KDF_PARAMS.update(orig)
    assert len(list((tmp_path / "seed.vault.keys").glob("*.key"))) == 1
    assert len(Vault.open(path, "senha-de-teste-123", dev_store(path)).entries) == 6
