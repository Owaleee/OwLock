"""Interface gráfica do Cofre (CustomTkinter)."""

from __future__ import annotations

import dataclasses
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from cofre.core.errors import VaultCorruptedError, VaultExistsError, WrongPasswordError
from cofre.core.generator import generate_password
from cofre.core.models import Entry
from cofre.core.vault import DEFAULT_VAULT_PATH, MIN_MASTER_PASSWORD_LENGTH, Vault

AUTO_LOCK_MS = 5 * 60 * 1000
CLIPBOARD_CLEAR_MS = 30 * 1000
ERROR_COLOR = "#ff5555"


class UnlockFrame(ctk.CTkFrame):
    """Tela de desbloqueio ou de criação do cofre."""

    def __init__(self, app: "CofreApp") -> None:
        super().__init__(app, fg_color="transparent")
        self.app = app
        self.creating = not app.vault_path.exists()
        self._results: queue.Queue = queue.Queue()

        box = ctk.CTkFrame(self, width=420)
        box.place(relx=0.5, rely=0.5, anchor="center")
        pad = {"padx": 30}

        ctk.CTkLabel(box, text="Cofre", font=ctk.CTkFont(size=28, weight="bold")).pack(pady=(30, 5), **pad)
        subtitle = "Criar cofre" if self.creating else "Desbloquear"
        ctk.CTkLabel(box, text=subtitle, font=ctk.CTkFont(size=16)).pack(pady=(0, 15), **pad)

        self.password_entry = ctk.CTkEntry(box, show="•", width=300, placeholder_text="Senha mestra")
        self.password_entry.pack(pady=5, **pad)
        self.password_entry.bind("<Return>", lambda _e: self._submit())

        self.confirm_entry: ctk.CTkEntry | None = None
        if self.creating:
            self.confirm_entry = ctk.CTkEntry(box, show="•", width=300, placeholder_text="Confirmar senha mestra")
            self.confirm_entry.pack(pady=5, **pad)
            self.confirm_entry.bind("<Return>", lambda _e: self._submit())
            ctk.CTkLabel(
                box,
                text=(
                    f"Mínimo de {MIN_MASTER_PASSWORD_LENGTH} caracteres.\n"
                    "Atenção: a senha mestra NÃO pode ser recuperada.\n"
                    "Se você esquecê-la, perderá o acesso às contas."
                ),
                text_color="#ffb347",
                justify="center",
                wraplength=320,
            ).pack(pady=8, **pad)

        self.error_label = ctk.CTkLabel(box, text="", text_color=ERROR_COLOR, wraplength=320, justify="center")
        self.error_label.pack(pady=4, **pad)

        self.button = ctk.CTkButton(box, text="Criar cofre" if self.creating else "Desbloquear", command=self._submit)
        self.button.pack(pady=(5, 30), **pad)
        self.password_entry.focus_set()

    def _show_error(self, text: str) -> None:
        self.error_label.configure(text=text)

    def _submit(self) -> None:
        if str(self.button.cget("state")) == "disabled":
            return
        password = self.password_entry.get()
        if self.creating:
            assert self.confirm_entry is not None
            if len(password) < MIN_MASTER_PASSWORD_LENGTH:
                self._show_error(f"A senha mestra deve ter pelo menos {MIN_MASTER_PASSWORD_LENGTH} caracteres.")
                return
            if password != self.confirm_entry.get():
                self._show_error("As senhas não coincidem.")
                return
        elif not password:
            self._show_error("Digite a senha mestra.")
            return

        self._show_error("")
        self.button.configure(state="disabled", text="Abrindo...")
        self.password_entry.delete(0, "end")
        if self.confirm_entry is not None:
            self.confirm_entry.delete(0, "end")

        path = self.app.vault_path
        creating = self.creating

        def work() -> None:
            try:
                vault = Vault.create(path, password) if creating else Vault.open(path, password)
                self._results.put(("ok", vault))
            except Exception as exc:  # noqa: BLE001 - repassado à thread principal
                self._results.put(("err", exc))

        threading.Thread(target=work, daemon=True).start()
        self._poll()

    def _poll(self) -> None:
        """Verifica (na thread principal) o resultado da thread de derivação."""
        try:
            kind, payload = self._results.get_nowait()
        except queue.Empty:
            self.after(50, self._poll)
            return
        if not self.winfo_exists():
            return
        if kind == "ok":
            self.app.show_main(payload)
            return
        self.button.configure(state="normal", text="Criar cofre" if self.creating else "Desbloquear")
        self._show_error(self._describe(payload))
        self.password_entry.focus_set()

    def _describe(self, exc: Exception) -> str:
        if isinstance(exc, WrongPasswordError):
            return "Senha mestra incorreta ou arquivo alterado."
        if isinstance(exc, VaultCorruptedError):
            bak = self.app.vault_path.with_name(self.app.vault_path.name + ".bak")
            return f"O arquivo do cofre está corrompido. Dica: tente restaurar a cópia de segurança em {bak}"
        if isinstance(exc, VaultExistsError):
            return "Já existe um cofre neste caminho."
        if isinstance(exc, FileNotFoundError):
            return "Arquivo do cofre não encontrado."
        if isinstance(exc, ValueError):
            return str(exc)
        return f"Erro inesperado: {exc}"


class EntryDialog(ctk.CTkToplevel):
    """Formulário modal para criar ou editar uma conta."""

    def __init__(self, app: "CofreApp", entry: Entry | None, on_save: Callable[[Entry], None]) -> None:
        super().__init__(app)
        self.entry = entry
        self.on_save = on_save
        self.title("Editar conta" if entry else "Nova conta")
        self.geometry("460x560")
        self.resizable(False, False)
        self.transient(app)
        self.columnconfigure(0, weight=1)

        def label(text: str) -> None:
            ctk.CTkLabel(self, text=text, anchor="w").pack(fill="x", padx=20, pady=(10, 0))

        label("Serviço *")
        self.service = ctk.CTkEntry(self)
        self.service.pack(fill="x", padx=20)

        label("Login / e-mail")
        self.username = ctk.CTkEntry(self)
        self.username.pack(fill="x", padx=20)

        label("Senha")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20)
        self.password = ctk.CTkEntry(row, show="•")
        self.password.pack(side="left", fill="x", expand=True)
        self.show_btn = ctk.CTkButton(row, text="Mostrar", width=70, command=self._toggle_show)
        self.show_btn.pack(side="left", padx=(6, 0))
        ctk.CTkButton(row, text="Gerar", width=60, command=self._generate).pack(side="left", padx=(6, 0))

        self.has_2fa = ctk.CTkCheckBox(self, text="Tem verificação em duas etapas (2FA)", command=self._sync_2fa)
        self.has_2fa.pack(anchor="w", padx=20, pady=(14, 0))
        label("App autenticador")
        self.twofa_app = ctk.CTkEntry(self, placeholder_text="ex.: Google Authenticator")
        self.twofa_app.pack(fill="x", padx=20)

        label("Notas")
        self.notes = ctk.CTkTextbox(self, height=90)
        self.notes.pack(fill="x", padx=20)

        self.error_label = ctk.CTkLabel(self, text="", text_color=ERROR_COLOR)
        self.error_label.pack(pady=(8, 0))
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(pady=8)
        ctk.CTkButton(buttons, text="Salvar", command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(buttons, text="Cancelar", fg_color="gray40", hover_color="gray30", command=self.destroy).pack(
            side="left", padx=6
        )

        if entry:
            self.service.insert(0, entry.service)
            self.username.insert(0, entry.username)
            self.password.insert(0, entry.password)
            if entry.has_2fa:
                self.has_2fa.select()
            self.twofa_app.insert(0, entry.twofa_app)
            self.notes.insert("1.0", entry.notes)
        self._sync_2fa()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(150, self._grab)
        self.service.focus_set()

    def _grab(self) -> None:
        """Torna o diálogo modal quando a janela já estiver visível."""
        try:
            if self.winfo_exists():
                self.grab_set()
                self.focus_force()
        except tk.TclError:
            pass

    def _toggle_show(self) -> None:
        hidden = self.password.cget("show") == "•"
        self.password.configure(show="" if hidden else "•")
        self.show_btn.configure(text="Ocultar" if hidden else "Mostrar")

    def _generate(self) -> None:
        self.password.delete(0, "end")
        self.password.insert(0, generate_password(20))

    def _sync_2fa(self) -> None:
        enabled = bool(self.has_2fa.get())
        self.twofa_app.configure(state="normal" if enabled else "disabled")

    def _save(self) -> None:
        service = self.service.get().strip()
        if not service:
            self.error_label.configure(text="O serviço é obrigatório.")
            return
        has_2fa = bool(self.has_2fa.get())
        data = {
            "service": service,
            "username": self.username.get().strip(),
            "password": self.password.get(),
            "has_2fa": has_2fa,
            "twofa_app": self.twofa_app.get().strip() if has_2fa else "",
            "notes": self.notes.get("1.0", "end-1c"),
        }
        if self.entry:
            # cópia: o objeto original só muda se o cofre salvar com sucesso
            result = dataclasses.replace(self.entry, **data)
        else:
            result = Entry(**data)
        self.on_save(result)  # o callback fecha o diálogo se salvar


class MainFrame(ctk.CTkFrame):
    """Tela principal: busca e lista de contas."""

    def __init__(self, app: "CofreApp") -> None:
        super().__init__(app, fg_color="transparent")
        self.app = app
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(12, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        ctk.CTkEntry(bar, textvariable=self.search_var, placeholder_text="Buscar...").pack(
            side="left", fill="x", expand=True
        )
        ctk.CTkButton(bar, text="+ Nova conta", width=110, command=app.new_entry).pack(side="left", padx=(8, 0))
        ctk.CTkButton(bar, text="Bloquear", width=90, fg_color="gray40", hover_color="gray30", command=app.lock).pack(
            side="left", padx=(8, 0)
        )
        self.list_frame = ctk.CTkScrollableFrame(self)
        self.list_frame.pack(fill="both", expand=True, padx=12, pady=6)
        self.status = ctk.CTkLabel(self, text="", text_color="gray70", anchor="w")
        self.status.pack(fill="x", padx=14, pady=(0, 8))
        self._status_job: str | None = None
        self.refresh()

    def set_status(self, text: str, ms: int = 4000) -> None:
        """Mostra um aviso discreto por alguns segundos."""
        if self._status_job:
            self.after_cancel(self._status_job)
        self.status.configure(text=text)
        self._status_job = self.after(ms, lambda: self.status.configure(text=""))

    def refresh(self) -> None:
        """Recarrega a lista conforme a busca atual."""
        vault = self.app.vault
        for child in self.list_frame.winfo_children():
            child.destroy()
        if vault is None:
            return
        text = self.search_var.get().strip()
        entries = vault.search(text) if text else list(vault.entries)
        entries.sort(key=lambda e: e.service.casefold())
        if not entries:
            msg = "Nenhuma conta encontrada." if text else "Nenhuma conta ainda.\nClique em \"+ Nova conta\" para começar."
            ctk.CTkLabel(self.list_frame, text=msg, text_color="gray70", justify="center").pack(pady=40)
            return
        for entry in entries:
            self._row(entry)

    def _row(self, entry: Entry) -> None:
        row = ctk.CTkFrame(self.list_frame)
        row.pack(fill="x", pady=3, padx=2)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=8, pady=6)
        ctk.CTkLabel(info, text=entry.service, font=ctk.CTkFont(size=15, weight="bold"), anchor="w").pack(fill="x")
        ctk.CTkLabel(info, text=entry.username or "(sem login)", text_color="gray70", anchor="w").pack(fill="x")
        if entry.has_2fa:
            badge = f"2FA: {entry.twofa_app}" if entry.twofa_app else "2FA"
            ctk.CTkLabel(
                info, text=badge, text_color="#7ee787", fg_color="#1f3a28", corner_radius=6, anchor="w"
            ).pack(anchor="w", pady=(2, 0))
        btns = ctk.CTkFrame(row, fg_color="transparent")
        btns.pack(side="right", padx=6)
        ctk.CTkButton(btns, text="Copiar login", width=90, command=lambda: self.app.copy_text(entry.username, "Login")).pack(
            side="left", padx=2
        )
        ctk.CTkButton(btns, text="Copiar senha", width=95, command=lambda: self.app.copy_text(entry.password, "Senha")).pack(
            side="left", padx=2
        )
        ctk.CTkButton(btns, text="Editar", width=60, command=lambda: self.app.edit_entry(entry)).pack(side="left", padx=2)
        ctk.CTkButton(
            btns, text="Excluir", width=65, fg_color="#a33", hover_color="#822", command=lambda: self.app.delete_entry(entry)
        ).pack(side="left", padx=2)


class CofreApp(ctk.CTk):
    """Janela principal do aplicativo."""

    def __init__(self, vault_path: Path = DEFAULT_VAULT_PATH) -> None:
        ctk.set_appearance_mode("dark")
        super().__init__()
        self.title("Cofre")
        self.geometry("900x600")
        self.minsize(700, 450)
        self.vault_path = Path(vault_path)
        self.vault: Vault | None = None
        self.frame: ctk.CTkFrame | None = None
        self._dialog: EntryDialog | None = None
        self._lock_job: str | None = None
        self._clip_job: str | None = None
        self._copied_text: str | None = None

        for seq in ("<Any-KeyPress>", "<Any-Button>", "<Motion>"):
            self.bind_all(seq, self._reset_idle, add="+")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show_unlock()

    # --- troca de telas -------------------------------------------------
    def _swap(self, frame: ctk.CTkFrame) -> None:
        if self.frame is not None:
            self.frame.destroy()
        self.frame = frame
        frame.pack(fill="both", expand=True)

    def show_unlock(self) -> None:
        """Mostra a tela de desbloqueio/criação."""
        self._swap(UnlockFrame(self))

    def show_main(self, vault: Vault) -> None:
        """Guarda o cofre aberto e mostra a tela principal."""
        self.vault = vault
        self._swap(MainFrame(self))
        self._reset_idle()

    def _unlock_sync(self, password: str) -> None:
        """Abre o cofre de forma síncrona e mostra a tela principal (usado em testes)."""
        self.show_main(Vault.open(self.vault_path, password))

    # --- bloqueio -------------------------------------------------------
    def _reset_idle(self, _event: object = None) -> None:
        if self._lock_job:
            self.after_cancel(self._lock_job)
            self._lock_job = None
        if self.vault is not None:
            self._lock_job = self.after(AUTO_LOCK_MS, self.lock)

    def lock(self) -> None:
        """Descarta o cofre da memória e volta à tela de desbloqueio."""
        if self._lock_job:
            self.after_cancel(self._lock_job)
            self._lock_job = None
        if self._dialog is not None:
            try:
                self._dialog.destroy()
            except tk.TclError:
                pass
            self._dialog = None
        self.vault = None
        if isinstance(self.frame, MainFrame):
            for child in self.frame.list_frame.winfo_children():
                child.destroy()
        self.show_unlock()

    # --- ações ----------------------------------------------------------
    def new_entry(self) -> None:
        self._open_dialog(None)

    def edit_entry(self, entry: Entry) -> None:
        self._open_dialog(entry)

    def _open_dialog(self, entry: Entry | None) -> None:
        if self.vault is None or (self._dialog is not None and self._dialog.winfo_exists()):
            return

        def save(result: Entry) -> None:
            if self.vault is None:
                return
            try:
                if entry is None:
                    self.vault.add(result)
                else:
                    self.vault.update(result)
            except OSError as exc:
                messagebox.showerror("Erro ao salvar", f"Não foi possível salvar o cofre:\n{exc}", parent=self._dialog)
                return
            except KeyError:
                messagebox.showerror("Erro ao salvar", "A conta não existe mais no cofre.", parent=self._dialog)
                return
            if self._dialog is not None:
                self._dialog.destroy()
                self._dialog = None
            if isinstance(self.frame, MainFrame):
                self.frame.refresh()

        self._dialog = EntryDialog(self, entry, save)

    def delete_entry(self, entry: Entry) -> None:
        if self.vault is None:
            return
        if not messagebox.askyesno("Excluir conta", f"Excluir a conta \"{entry.service}\"? Isso não pode ser desfeito.", parent=self):
            return
        try:
            self.vault.delete(entry.id)
        except OSError as exc:
            messagebox.showerror("Erro ao salvar", f"Não foi possível salvar o cofre:\n{exc}", parent=self)
            return
        except KeyError:
            pass
        if isinstance(self.frame, MainFrame):
            self.frame.refresh()

    # --- área de transferência -----------------------------------------
    def copy_text(self, text: str, what: str) -> None:
        """Copia o texto e agenda a limpeza da área de transferência."""
        if not text:
            if isinstance(self.frame, MainFrame):
                self.frame.set_status(f"{what} vazio, nada copiado.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._copied_text = text
        if self._clip_job:
            self.after_cancel(self._clip_job)
        self._clip_job = self.after(CLIPBOARD_CLEAR_MS, self._clear_clipboard)
        if isinstance(self.frame, MainFrame):
            if what == "Senha":
                self.frame.set_status("Senha copiada — será apagada em 30 s", 5000)
            else:
                self.frame.set_status(f"{what} copiado — será apagado em 30 s", 5000)

    def _clear_clipboard(self) -> None:
        """Limpa a área de transferência só se ainda tiver o texto copiado pelo app."""
        self._clip_job = None
        if self._copied_text is None:
            return
        try:
            current = self.clipboard_get()
        except tk.TclError:
            current = None
        if current == self._copied_text:
            self.clipboard_clear()
        self._copied_text = None

    def _on_close(self) -> None:
        if self._clip_job:
            self.after_cancel(self._clip_job)
        self._clear_clipboard()
        self.vault = None
        self.destroy()
