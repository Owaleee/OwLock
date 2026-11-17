"""Servidor SÓ para desenvolvimento: serve a interface no navegador com a mesma Api.

Uso: python -m owlock.app.devserver --vault CAMINHO [--port 8765] [--seed]
Escuta apenas em 127.0.0.1. Não use em produção.
"""
from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from owlock.app.api import Api
from owlock.core import Entry, FileStore, Vault

HOST = "127.0.0.1"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
MAX_BODY = 1_000_000
SEED_PASSWORD = "senha-de-teste-123"


def dev_store(vault_path: Path) -> FileStore:
    """Guarda a Chave Secreta numa pasta ao lado do cofre (não usa o chaveiro do sistema)."""
    vault_path = Path(vault_path)
    return FileStore(vault_path.with_name(vault_path.name + ".keys"))


def make_save_dialog(directory: Path | None = None):
    """save_dialog de desenvolvimento: devolve /tmp/owlock-kit-<n>.html (n cresce a cada chamada)."""
    base = Path(directory) if directory is not None else Path("/tmp")
    counter = {"n": 0}

    def save_dialog(default_name: str) -> str:
        counter["n"] += 1
        return str(base / f"owlock-kit-{counter['n']}.html")

    return save_dialog


def _public_methods() -> set[str]:
    return {
        name
        for name, member in inspect.getmembers(Api, inspect.isfunction)
        if not name.startswith("_")
    }


def make_server(api: Api, port: int = 8765, web_dir: Path | None = None) -> ThreadingHTTPServer:
    """Cria o servidor (porta 0 escolhe uma porta livre)."""
    root = Path(web_dir) if web_dir is not None else WEB_DIR
    methods = _public_methods()

    class Handler(BaseHTTPRequestHandler):
        server_version = "OwLockDev"

        def log_message(self, fmt: str, *args: object) -> None:  # silencioso
            pass

        # ---- utilidades ----
        def _allowed_hosts(self) -> set[str]:
            p = self.server.server_address[1]
            return {f"127.0.0.1:{p}", f"localhost:{p}"}

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: object) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

        def _plain(self, status: int) -> None:
            self._send(status, HTTPStatus(status).phrase.encode(), "text/plain; charset=utf-8")

        def _origin_ok(self) -> bool:
            host = self.headers.get("Host")
            if host is not None and host not in self._allowed_hosts():
                return False
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            return origin in {f"http://{h}" for h in self._allowed_hosts()}

        # ---- métodos ----
        def do_GET(self) -> None:
            if not self._origin_ok():
                return self._plain(403)
            raw = unquote(urlsplit(self.path).path)
            if "\x00" in raw:
                return self._plain(404)
            rel = raw.lstrip("/") or "index.html"
            try:
                base = root.resolve()
                target = (base / rel).resolve()
                if not target.is_relative_to(base) or not target.is_file():
                    return self._plain(404)
                data = target.read_bytes()
            except (OSError, ValueError):
                return self._plain(404)
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            self._send(200, data, ctype)

        def do_POST(self) -> None:
            if not self._origin_ok():
                return self._plain(403)
            path = urlsplit(self.path).path
            prefix = "/api/"
            if not path.startswith(prefix):
                return self._plain(404)
            name = path[len(prefix):]
            if name.startswith("_") or name not in methods:
                return self._plain(404)
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if not 0 <= length <= MAX_BODY:
                    raise ValueError
                body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                if not isinstance(body, dict):
                    raise ValueError
                args = body.get("args", [])
                kwargs = body.get("kwargs", {})
                if not isinstance(args, list) or not isinstance(kwargs, dict):
                    raise ValueError
                if any(not isinstance(k, str) or k.startswith("_") for k in kwargs):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                return self._plain(400)
            try:
                result = getattr(api, name)(*args, **kwargs)
            except TypeError:
                return self._plain(400)
            self._json(200, result)

    return ThreadingHTTPServer((HOST, port), Handler)


def seed_vault(path: Path, store: FileStore | None = None) -> None:
    """Cria um cofre de teste com contas de exemplo."""
    vault = Vault.create(path, SEED_PASSWORD, store if store is not None else dev_store(path))
    cats = {c.name: c.id for c in vault.categories}
    samples = [
        Entry("Google", "seu.email@gmail.com", "Gx4!nP8s#Qd1vL2@", True, "Google Authenticator", "Conta principal", cats["Pessoal"], url="https://accounts.google.com"),
        Entry("Steam", "seu_usuario_steam", "T7#qLm9!vRz2@kWp", True, "Steam Guard", "", cats["Jogos"], url="https://store.steampowered.com"),
        Entry("GitHub", "seu-usuario", "Hk3$wTz9&pLq5!mB", True, "Authy", "Chave de acesso do trabalho", cats["Trabalho"], url="https://github.com"),
        Entry("Discord", "seu.email@gmail.com", "discord2021", False, "", "Trocar esta senha", cats["Jogos"], url="https://discord.com"),
        Entry("Netflix", "seu.email@gmail.com", "Nf!93kdPq", False, category_id=cats["Streaming"]),  # sem site: mostra o link da biblioteca
        Entry("Epic Games", "seu.email@gmail.com", "Zr8@cVn4#Yt6mJ1x", True, "Epic Authenticator", "", cats["Jogos"], url="https://store.epicgames.com", icon="none"),  # letra no lugar do ícone
    ]
    # Serviço personalizado na biblioteca de links.
    vault.update_services(
        [
            {
                "key": "custom-" + uuid4().hex,
                "name": "Portal da Faculdade",
                "aliases": ["faculdade"],
                "login_url": "https://portal.exemplo.edu.br",
                "icon": "",
            }
        ],
        {},
    )
    # Contas com versões antigas de senha (oldest -> atual), para o histórico aparecer.
    past = {"Discord": ("discord2019", "discord2020"), "GitHub": ("gh-antiga-2023",)}
    for entry in samples:
        olds = past.get(entry.service)
        if not olds:
            vault.add(entry)
            continue
        final = entry.password
        entry.password = olds[0]
        vault.add(entry)
        for password in (*olds[1:], final):
            vault.update(dataclasses.replace(entry, password=password))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Servidor de desenvolvimento do OwLock (só 127.0.0.1).")
    parser.add_argument("--vault", required=True, type=Path, help="caminho do arquivo do cofre")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seed", action="store_true", help="cria cofre de teste se não existir")
    args = parser.parse_args(argv)

    if args.seed and not args.vault.exists():
        seed_vault(args.vault)
        print(f"Cofre de TESTE criado em {args.vault} (senha mestra: {SEED_PASSWORD}). Não use dados reais.")
    api = Api(args.vault, store=dev_store(args.vault), save_dialog=make_save_dialog())
    server = make_server(api, args.port)
    print(f"Servidor de desenvolvimento em http://127.0.0.1:{server.server_address[1]}/ (Ctrl+C para sair)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
