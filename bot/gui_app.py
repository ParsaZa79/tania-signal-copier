#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
import tkinter as tk

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CACHE_PATH = BASE_DIR / ".env.gui_cache.json"
INSERT_COLOR = "#1a1a1a"

ENV_SECTIONS: list[tuple[str, list[tuple[str, str, bool]]]] = [
    (
        "Telegram",
        [
            ("TELEGRAM_API_ID", "API ID", False),
            ("TELEGRAM_API_HASH", "API Hash", False),
            ("TELEGRAM_CHANNEL", "Channel", False),
        ],
    ),
    (
        "MT5",
        [
            ("MT5_LOGIN", "Login", False),
            ("MT5_PASSWORD", "Password", True),
            ("MT5_SERVER", "Server", False),
            ("MT5_DOCKER_HOST", "Docker Host", False),
            ("MT5_DOCKER_PORT", "Docker Port", False),
        ],
    ),
    (
        "Trading",
        [
            ("DEFAULT_LOT_SIZE", "Default Lot Size", False),
            ("MAX_RISK_PERCENT", "Max Risk Percent", False),
            ("SCALP_LOT_SIZE", "Scalp Lot Size (dual_tp)", False),
            ("RUNNER_LOT_SIZE", "Runner Lot Size (dual_tp)", False),
            ("TRADING_STRATEGY", "Strategy (dual_tp|single)", False),
            ("EDIT_WINDOW_SECONDS", "Edit Window Seconds", False),
        ],
    ),
    (
        "Optional",
        [
            ("TEST_SYMBOL", "Test Symbol", False),
        ],
    ),
]

STRATEGY_CHOICES = ("dual_tp", "single")


def parse_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        return value[1:-1]
    return value


def format_env_value(value: str) -> str:
    if value == "":
        return ""
    if any(ch.isspace() for ch in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        env[key.strip()] = parse_env_value(raw_value)
    return env


def write_env_file(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out_lines: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in updates:
            out_lines.append(f"{key}={format_env_value(updates[key])}")
            seen.add(key)
        else:
            out_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            out_lines.append(f"{key}={format_env_value(value)}")
    content = "\n".join(out_lines).rstrip() + "\n"
    path.write_text(content, encoding="utf-8")


def load_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    return {}


def save_cache(path: Path, values: dict[str, str]) -> None:
    payload = {k: v for k, v in values.items()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def build_command(prevent_sleep: bool) -> list[str]:
    uv_path = shutil.which("uv")
    if uv_path:
        cmd = [uv_path, "run", "python", "-m", "tania_signal_copier.bot"]
    else:
        cmd = [sys.executable, "-m", "tania_signal_copier.bot"]
    if prevent_sleep and sys.platform == "darwin":
        caffeinate = shutil.which("caffeinate")
        if caffeinate:
            return [caffeinate, "-dims", *cmd]
    return cmd


class BotGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Tania Signal Copier GUI")
        self.root.geometry("980x720")

        self.process: subprocess.Popen[str] | None = None
        self.queue: queue.Queue[str] = queue.Queue()

        self.env_vars: dict[str, tk.StringVar] = {}
        for _, fields in ENV_SECTIONS:
            for key, _, _ in fields:
                self.env_vars[key] = tk.StringVar()

        self.write_env_on_start = tk.BooleanVar(value=False)
        self.prevent_sleep = tk.BooleanVar(value=sys.platform == "darwin")

        self.status_var = tk.StringVar(value="Status: stopped")

        self._build_ui()
        self._load_initial_values()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._drain_queue)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        top = ttk.Frame(main)
        top.pack(fill="x")

        for idx, (section, fields) in enumerate(ENV_SECTIONS):
            frame = ttk.LabelFrame(top, text=section, padding=10)
            frame.grid(row=idx // 2, column=idx % 2, padx=6, pady=6, sticky="nsew")
            for row, (key, label, is_secret) in enumerate(fields):
                ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
                if key == "TRADING_STRATEGY":
                    widget = ttk.Combobox(
                        frame,
                        textvariable=self.env_vars[key],
                        values=STRATEGY_CHOICES,
                        state="readonly",
                        width=30,
                    )
                else:
                    widget = tk.Entry(
                        frame,
                        textvariable=self.env_vars[key],
                        width=32,
                        show="*" if is_secret else "",
                        insertbackground=INSERT_COLOR,
                    )
                widget.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=2)
            frame.columnconfigure(1, weight=1)

        for col in range(2):
            top.columnconfigure(col, weight=1)

        controls = ttk.Frame(main)
        controls.pack(fill="x", pady=(8, 6))

        ttk.Button(controls, text="Start Bot", command=self.start_bot).grid(
            row=0, column=0, padx=4
        )
        ttk.Button(controls, text="Stop Bot", command=self.stop_bot).grid(
            row=0, column=1, padx=4
        )
        ttk.Button(controls, text="Save .env", command=self.save_env).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(controls, text="Reload .env", command=self.reload_env).grid(
            row=0, column=3, padx=4
        )
        ttk.Button(controls, text="Clear Cache", command=self.clear_cache).grid(
            row=0, column=4, padx=4
        )

        ttk.Checkbutton(
            controls,
            text="Write .env on start",
            variable=self.write_env_on_start,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        ttk.Checkbutton(
            controls,
            text="Prevent sleep (macOS)",
            variable=self.prevent_sleep,
        ).grid(row=1, column=2, columnspan=2, sticky="w", padx=4, pady=4)

        ttk.Label(controls, textvariable=self.status_var).grid(
            row=1, column=4, sticky="e", padx=4
        )
        controls.columnconfigure(4, weight=1)

        log_frame = ttk.LabelFrame(main, text="Bot Output", padding=10)
        log_frame.pack(fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=18, wrap="word", state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

    def _load_initial_values(self) -> None:
        env_values = read_env_file(ENV_PATH)
        cache_values = load_cache(CACHE_PATH)
        merged = {**env_values, **cache_values}
        for key, var in self.env_vars.items():
            if key in merged:
                value = merged[key]
                if key == "TRADING_STRATEGY":
                    value = value.lower()
                var.set(value)
        if not self.env_vars["TRADING_STRATEGY"].get():
            self.env_vars["TRADING_STRATEGY"].set(STRATEGY_CHOICES[0])

    def _current_values(self) -> dict[str, str]:
        values = {key: var.get().strip() for key, var in self.env_vars.items()}
        if "TRADING_STRATEGY" in values:
            values["TRADING_STRATEGY"] = values["TRADING_STRATEGY"].lower()
        return values

    def save_env(self) -> None:
        values = self._current_values()
        write_env_file(ENV_PATH, values)
        save_cache(CACHE_PATH, values)
        messagebox.showinfo("Saved", "Saved values to .env and cache.")

    def reload_env(self) -> None:
        env_values = read_env_file(ENV_PATH)
        for key, var in self.env_vars.items():
            var.set(env_values.get(key, ""))
        messagebox.showinfo("Reloaded", "Reloaded values from .env.")

    def clear_cache(self) -> None:
        if CACHE_PATH.exists():
            CACHE_PATH.unlink()
        messagebox.showinfo("Cache cleared", "Cache file removed.")

    def start_bot(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showwarning("Already running", "Bot is already running.")
            return

        values = self._current_values()
        save_cache(CACHE_PATH, values)
        if self.write_env_on_start.get():
            write_env_file(ENV_PATH, values)

        env = os.environ.copy()
        env.update(values)
        env["PYTHONUNBUFFERED"] = "1"

        cmd = build_command(self.prevent_sleep.get())
        self._append_log(f"Starting bot: {' '.join(cmd)}\n")
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            self._append_log(f"Failed to start bot: {exc}\n")
            messagebox.showerror("Start failed", f"Failed to start bot:\n{exc}")
            return

        threading.Thread(target=self._read_output, args=(self.process,), daemon=True).start()
        self.status_var.set(f"Status: running (pid {self.process.pid})")

    def _read_output(self, proc: subprocess.Popen[str]) -> None:
        if not proc.stdout:
            return
        for line in proc.stdout:
            self.queue.put(line)

    def stop_bot(self) -> None:
        if not self.process or self.process.poll() is not None:
            messagebox.showinfo("Not running", "Bot is not running.")
            return
        self._append_log("Stopping bot...\n")
        proc = self.process

        def _stop() -> None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        threading.Thread(target=_stop, daemon=True).start()

    def _drain_queue(self) -> None:
        while True:
            try:
                line = self.queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(line)

        if self.process and self.process.poll() is not None:
            exit_code = self.process.poll()
            self._append_log(f"Bot exited with code {exit_code}\n")
            self.status_var.set("Status: stopped")
            self.process = None

        self.root.after(100, self._drain_queue)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Quit", "Bot is running. Stop it and exit?"):
                return
            self.stop_bot()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ttk.Style().theme_use("default")
    BotGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
