#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
CACHE_PATH = BASE_DIR / ".env.gui_cache.json"
ANALYSIS_DIR = BASE_DIR / "analysis"
REPORT_PATH = ANALYSIS_DIR / "report.md"
OUTCOMES_PATH = ANALYSIS_DIR / "signals_outcomes.json"

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
DEFAULT_ANALYSIS_TOTAL = "1000"
DEFAULT_ANALYSIS_BATCH = "100"
DEFAULT_ANALYSIS_DELAY = "2"

COLORS = {
    "bg0": "#060b18",
    "bg1": "#0b1630",
    "panel": "#0f1c38",
    "panel_alt": "#132348",
    "border": "#1f2f59",
    "text": "#e5e7eb",
    "muted": "#94a3b8",
    "accent": "#f59e0b",
    "accent_strong": "#fbbf24",
    "success": "#22c55e",
    "danger": "#ef4444",
    "info": "#22d3ee",
}


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


def build_bot_command(prevent_sleep: bool) -> list[str]:
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


def apply_app_style(app: QApplication) -> None:
    app.setStyleSheet(
        f"""
        QMainWindow {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {COLORS["bg0"]}, stop:1 {COLORS["bg1"]});
            color: {COLORS["text"]};
            font-family: "Fira Sans", "Avenir Next", "Segoe UI", sans-serif;
            font-size: 13px;
        }}
        QFrame#HeaderFrame {{
            border: 1px solid {COLORS["border"]};
            border-radius: 16px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {COLORS["panel"]}, stop:1 {COLORS["panel_alt"]});
        }}
        QLabel#HeaderTitle {{
            font-size: 28px;
            font-weight: 700;
            color: {COLORS["accent_strong"]};
        }}
        QLabel#HeaderSubtitle {{
            color: {COLORS["muted"]};
            font-size: 13px;
        }}
        QGroupBox {{
            border: 1px solid {COLORS["border"]};
            border-radius: 14px;
            margin-top: 16px;
            padding: 16px 14px 14px 14px;
            background: rgba(15, 28, 56, 0.94);
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
            color: {COLORS["accent"]};
            font-size: 13px;
        }}
        QLabel {{
            color: {COLORS["text"]};
        }}
        QLabel#MutedLabel {{
            color: {COLORS["muted"]};
            font-weight: 500;
        }}
        QLineEdit, QComboBox {{
            border: 1px solid {COLORS["border"]};
            border-radius: 10px;
            padding: 7px 10px;
            background: rgba(19, 35, 72, 0.96);
            color: {COLORS["text"]};
            selection-background-color: {COLORS["info"]};
            min-height: 30px;
        }}
        QLineEdit:focus, QComboBox:focus {{
            border: 1px solid {COLORS["accent"]};
        }}
        QComboBox QAbstractItemView {{
            background: {COLORS["panel_alt"]};
            border: 1px solid {COLORS["border"]};
            selection-background-color: {COLORS["accent"]};
            selection-color: {COLORS["bg0"]};
        }}
        QPushButton {{
            border: 1px solid {COLORS["border"]};
            border-radius: 12px;
            padding: 8px 12px;
            background: rgba(19, 35, 72, 0.98);
            color: {COLORS["text"]};
            font-weight: 600;
        }}
        QPushButton:hover {{
            border-color: {COLORS["accent"]};
        }}
        QPushButton#PrimaryButton {{
            background: {COLORS["accent"]};
            color: {COLORS["bg0"]};
            border-color: {COLORS["accent"]};
        }}
        QPushButton#PrimaryButton:hover {{
            background: {COLORS["accent_strong"]};
        }}
        QPushButton#SuccessButton {{
            background: {COLORS["success"]};
            color: {COLORS["bg0"]};
            border-color: {COLORS["success"]};
        }}
        QPushButton#SuccessButton:hover {{
            background: #34d399;
        }}
        QPushButton#DangerButton {{
            background: {COLORS["danger"]};
            color: {COLORS["text"]};
            border-color: {COLORS["danger"]};
        }}
        QPushButton#DangerButton:hover {{
            background: #f87171;
        }}
        QCheckBox {{
            color: {COLORS["muted"]};
            spacing: 8px;
            font-weight: 500;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 6px;
            border: 1px solid {COLORS["border"]};
            background: rgba(19, 35, 72, 0.9);
        }}
        QCheckBox::indicator:checked {{
            background: {COLORS["accent"]};
            border-color: {COLORS["accent"]};
        }}
        QPlainTextEdit {{
            border: 1px solid {COLORS["border"]};
            border-radius: 14px;
            background: rgba(9, 18, 38, 0.96);
            color: {COLORS["text"]};
            padding: 10px;
            selection-background-color: {COLORS["info"]};
            font-family: "JetBrains Mono", "Menlo", "Consolas", monospace;
            font-size: 12px;
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS["border"]};
            border-radius: 6px;
            min-height: 28px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {COLORS["accent"]};
        }}
        """
    )


class BotGui(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tania Signal Copier Control Room")
        self.resize(1200, 850)

        self.env_inputs: dict[str, QLineEdit | QComboBox] = {}
        self.bot_process: QProcess | None = None
        self.analysis_process: QProcess | None = None
        self.analysis_queue: list[list[str]] = []
        self.analysis_label = "idle"

        self.write_env_on_start = QCheckBox("Write .env on start")
        self.prevent_sleep = QCheckBox("Prevent sleep (macOS)")
        self.prevent_sleep.setChecked(sys.platform == "darwin")

        self.bot_status_label = QLabel("Bot: stopped")
        self.bot_status_label.setObjectName("MutedLabel")
        self.analysis_status_label = QLabel("Analysis: idle")
        self.analysis_status_label.setObjectName("MutedLabel")

        self.analysis_total_input = QLineEdit(DEFAULT_ANALYSIS_TOTAL)
        self.analysis_batch_input = QLineEdit(DEFAULT_ANALYSIS_BATCH)
        self.analysis_delay_input = QLineEdit(DEFAULT_ANALYSIS_DELAY)

        self.summary_view = QPlainTextEdit()
        self.summary_view.setReadOnly(True)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self._build_ui()
        self._load_initial_values()
        self.load_analysis_summary()

    # ---------- UI Construction ----------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        root.addWidget(self._build_header())

        content = QHBoxLayout()
        content.setSpacing(20)
        root.addLayout(content, stretch=1)

        content.addWidget(self._build_env_panel(), stretch=1)
        content.addWidget(self._build_analysis_panel(), stretch=1)

        log_group = QGroupBox("Live Output")
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_view)
        root.addWidget(log_group, stretch=1)

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("HeaderFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)

        title = QLabel("Signal Copier Control Room")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("Bold visibility into bot state, TP outcomes, and channel behavior.")
        subtitle.setObjectName("HeaderSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return frame

    def _build_env_panel(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        outer.addWidget(scroll)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(4, 4, 12, 4)
        inner_layout.setSpacing(14)

        for section, fields in ENV_SECTIONS:
            inner_layout.addWidget(self._build_env_group(section, fields))

        inner_layout.addWidget(self._build_bot_controls())
        inner_layout.addStretch(1)

        scroll.setWidget(inner)
        return container

    def _build_env_group(
        self, section: str, fields: list[tuple[str, str, bool]]
    ) -> QGroupBox:
        group = QGroupBox(section)
        form = QFormLayout(group)
        form.setSpacing(12)
        form.setHorizontalSpacing(16)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for key, label, is_secret in fields:
            label_widget = QLabel(label)
            label_widget.setMinimumWidth(120)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            if key == "TRADING_STRATEGY":
                widget = QComboBox()
                widget.addItems(STRATEGY_CHOICES)
                widget.setEditable(False)
                widget.setMinimumWidth(180)
                self.env_inputs[key] = widget
                form.addRow(label_widget, widget)
                continue

            entry = QLineEdit()
            entry.setEchoMode(QLineEdit.EchoMode.Password if is_secret else QLineEdit.EchoMode.Normal)
            entry.setPlaceholderText(label)
            entry.setMinimumWidth(180)
            self.env_inputs[key] = entry
            form.addRow(label_widget, entry)

        return group

    def _build_bot_controls(self) -> QGroupBox:
        group = QGroupBox("Bot Controls")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        # Main action buttons row
        main_btns = QHBoxLayout()
        main_btns.setSpacing(10)

        start_btn = QPushButton("Start Bot")
        start_btn.setObjectName("SuccessButton")
        start_btn.clicked.connect(self.start_bot)

        stop_btn = QPushButton("Stop Bot")
        stop_btn.setObjectName("DangerButton")
        stop_btn.clicked.connect(self.stop_bot)

        main_btns.addWidget(start_btn)
        main_btns.addWidget(stop_btn)
        layout.addLayout(main_btns)

        # Secondary buttons row
        secondary_btns = QHBoxLayout()
        secondary_btns.setSpacing(10)

        save_btn = QPushButton("Save .env")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_env)

        reload_btn = QPushButton("Reload .env")
        reload_btn.clicked.connect(self.reload_env)

        clear_btn = QPushButton("Clear Cache")
        clear_btn.clicked.connect(self.clear_cache)

        secondary_btns.addWidget(save_btn)
        secondary_btns.addWidget(reload_btn)
        secondary_btns.addWidget(clear_btn)
        layout.addLayout(secondary_btns)

        # Checkboxes row
        checkboxes = QHBoxLayout()
        checkboxes.setSpacing(20)
        checkboxes.addWidget(self.write_env_on_start)
        checkboxes.addWidget(self.prevent_sleep)
        checkboxes.addStretch(1)
        layout.addLayout(checkboxes)

        # Status
        layout.addWidget(self.bot_status_label)

        hint = QLabel("Tip: Save your .env before live trading sessions.")
        hint.setObjectName("MutedLabel")
        layout.addWidget(hint)
        return group

    def _build_analysis_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addWidget(self._build_analysis_controls())
        layout.addWidget(self._build_summary_group(), stretch=1)
        layout.addWidget(self._build_insights_group(), stretch=1)
        return panel

    def _build_analysis_controls(self) -> QGroupBox:
        group = QGroupBox("Signal Analysis")
        layout = QVBoxLayout(group)
        layout.setSpacing(14)

        # Input fields row with form layout for better alignment
        inputs_layout = QHBoxLayout()
        inputs_layout.setSpacing(16)

        for label_text, widget in [
            ("Messages", self.analysis_total_input),
            ("Batch", self.analysis_batch_input),
            ("Delay (s)", self.analysis_delay_input),
        ]:
            pair = QVBoxLayout()
            pair.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setObjectName("MutedLabel")
            widget.setFixedWidth(80)
            pair.addWidget(lbl)
            pair.addWidget(widget)
            inputs_layout.addLayout(pair)

        inputs_layout.addStretch(1)
        layout.addLayout(inputs_layout)

        # Buttons row 1
        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(10)

        fetch_btn = QPushButton("Fetch Messages")
        fetch_btn.clicked.connect(self.fetch_messages)
        report_btn = QPushButton("Generate Report")
        report_btn.setObjectName("PrimaryButton")
        report_btn.clicked.connect(self.generate_report)
        combo_btn = QPushButton("Fetch + Report")
        combo_btn.clicked.connect(self.fetch_and_report)

        btn_row1.addWidget(fetch_btn)
        btn_row1.addWidget(report_btn)
        btn_row1.addWidget(combo_btn)
        layout.addLayout(btn_row1)

        # Buttons row 2 with status
        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(10)

        refresh_btn = QPushButton("Refresh Summary")
        refresh_btn.clicked.connect(self.load_analysis_summary)
        btn_row2.addWidget(refresh_btn)
        btn_row2.addWidget(self.analysis_status_label)
        btn_row2.addStretch(1)
        layout.addLayout(btn_row2)

        return group

    def _build_summary_group(self) -> QGroupBox:
        group = QGroupBox("Outcome Summary")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        self.summary_view.setMinimumHeight(120)
        self.summary_view.setMaximumHeight(180)
        layout.addWidget(self.summary_view)
        return group

    def _build_insights_group(self) -> QGroupBox:
        group = QGroupBox("Actionable Insights")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        tips = QPlainTextEdit()
        tips.setReadOnly(True)
        tips.setMinimumHeight(100)
        tips.setMaximumHeight(140)
        tips.setPlainText(
            "\n".join(
                [
                    "- TP1 -> TP2 conversion shows runner quality; track it weekly.",
                    "- If TP1-only wins dominate, consider earlier partials on runners.",
                    "- Average time-to-TP helps tune news filters and session timing.",
                    "- Refresh Summary after any manual fetch to keep metrics aligned.",
                ]
            )
        )
        layout.addWidget(tips)
        return group

    # ---------- Env State ----------
    def _load_initial_values(self) -> None:
        env_values = read_env_file(ENV_PATH)
        cache_values = load_cache(CACHE_PATH)
        merged = {**env_values, **cache_values}
        for key, widget in self.env_inputs.items():
            value = merged.get(key, "")
            if key == "TRADING_STRATEGY":
                value = value.lower() if value else STRATEGY_CHOICES[0]
                combo = widget if isinstance(widget, QComboBox) else None
                if combo is not None:
                    idx = combo.findText(value)
                    combo.setCurrentIndex(idx if idx >= 0 else 0)
                continue
            if isinstance(widget, QLineEdit):
                widget.setText(value)

    def _current_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for key, widget in self.env_inputs.items():
            if isinstance(widget, QComboBox):
                values[key] = widget.currentText().strip().lower()
            else:
                values[key] = widget.text().strip()
        return values

    def save_env(self) -> None:
        values = self._current_values()
        write_env_file(ENV_PATH, values)
        save_cache(CACHE_PATH, values)
        QMessageBox.information(self, "Saved", "Saved values to .env and cache.")

    def reload_env(self) -> None:
        env_values = read_env_file(ENV_PATH)
        for key, widget in self.env_inputs.items():
            value = env_values.get(key, "")
            if isinstance(widget, QComboBox):
                value = value.lower() if value else STRATEGY_CHOICES[0]
                idx = widget.findText(value)
                widget.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                widget.setText(value)
        QMessageBox.information(self, "Reloaded", "Reloaded values from .env.")

    def clear_cache(self) -> None:
        if CACHE_PATH.exists():
            CACHE_PATH.unlink()
        QMessageBox.information(self, "Cache cleared", "Cache file removed.")

    # ---------- Logging ----------
    def _append_log(self, text: str) -> None:
        if not text:
            return
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)
        self.log_view.insertPlainText(text)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    # ---------- Process Helpers ----------
    def _qprocess_env(self, overrides: dict[str, str]) -> QProcessEnvironment:
        env = QProcessEnvironment.systemEnvironment()
        for key, value in overrides.items():
            env.insert(key, value)
        return env

    def _analysis_env_overrides(self) -> dict[str, str]:
        values = self._current_values()
        save_cache(CACHE_PATH, values)
        env = os.environ.copy()
        env.update(values)
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _analysis_command(self, script: str, args: list[str]) -> list[str]:
        uv_path = shutil.which("uv")
        if uv_path:
            return [uv_path, "run", "python", script, *args]
        return [sys.executable, script, *args]

    def _parse_int(self, raw: str, fallback: int) -> int:
        try:
            return max(1, int(raw.strip()))
        except (TypeError, ValueError):
            return fallback

    def _parse_float(self, raw: str, fallback: float) -> float:
        try:
            return max(0.0, float(raw.strip()))
        except (TypeError, ValueError):
            return fallback

    def _process_running(self, proc: QProcess | None) -> bool:
        return proc is not None and proc.state() != QProcess.ProcessState.NotRunning

    # ---------- Bot Control ----------
    def start_bot(self) -> None:
        if self._process_running(self.bot_process):
            QMessageBox.warning(self, "Already running", "Bot is already running.")
            return

        values = self._current_values()
        save_cache(CACHE_PATH, values)
        if self.write_env_on_start.isChecked():
            write_env_file(ENV_PATH, values)

        env_overrides = os.environ.copy()
        env_overrides.update(values)
        env_overrides["PYTHONUNBUFFERED"] = "1"
        cmd = build_bot_command(self.prevent_sleep.isChecked())

        self._append_log(f"\n[bot] Starting: {' '.join(cmd)}\n")

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setWorkingDirectory(str(BASE_DIR))
        process.setProcessEnvironment(self._qprocess_env(env_overrides))
        process.readyReadStandardOutput.connect(self._handle_bot_output)
        process.finished.connect(self._bot_finished)
        process.errorOccurred.connect(self._bot_error)
        process.start(cmd[0], cmd[1:])

        self.bot_process = process
        self.bot_status_label.setText("Bot: starting...")

    def stop_bot(self) -> None:
        if not self._process_running(self.bot_process):
            QMessageBox.information(self, "Not running", "Bot is not running.")
            return
        self._append_log("[bot] Stopping bot...\n")
        assert self.bot_process is not None
        self.bot_process.terminate()
        QTimer.singleShot(5000, self._kill_bot_if_needed)

    def _kill_bot_if_needed(self) -> None:
        if self._process_running(self.bot_process):
            assert self.bot_process is not None
            self._append_log("[bot] Terminate timed out; killing process.\n")
            self.bot_process.kill()

    def _handle_bot_output(self) -> None:
        if not self.bot_process:
            return
        data = self.bot_process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        self._append_log(text)
        if self._process_running(self.bot_process):
            self.bot_status_label.setText(f"Bot: running (pid {self.bot_process.processId()})")

    def _bot_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._append_log(f"[bot] Exited with code {exit_code}\n")
        self.bot_status_label.setText("Bot: stopped")
        self.bot_process = None

    def _bot_error(self, error: QProcess.ProcessError) -> None:
        self._append_log(f"[bot] Process error: {error}\n")
        self.bot_status_label.setText("Bot: error")
        if not self._process_running(self.bot_process):
            self.bot_process = None

    # ---------- Analysis Control ----------
    def fetch_messages(self) -> None:
        total = self._parse_int(self.analysis_total_input.text(), int(DEFAULT_ANALYSIS_TOTAL))
        batch = self._parse_int(self.analysis_batch_input.text(), int(DEFAULT_ANALYSIS_BATCH))
        delay = self._parse_float(self.analysis_delay_input.text(), float(DEFAULT_ANALYSIS_DELAY))
        cmd = self._analysis_command(
            "scripts/fetch_signals.py",
            ["--total", str(total), "--batch-size", str(batch), "--delay", str(delay)],
        )
        self._start_analysis_sequence("fetching messages", [cmd])

    def generate_report(self) -> None:
        cmd = self._analysis_command("scripts/report_signal_outcomes.py", [])
        self._start_analysis_sequence("generating report", [cmd])

    def fetch_and_report(self) -> None:
        total = self._parse_int(self.analysis_total_input.text(), int(DEFAULT_ANALYSIS_TOTAL))
        batch = self._parse_int(self.analysis_batch_input.text(), int(DEFAULT_ANALYSIS_BATCH))
        delay = self._parse_float(self.analysis_delay_input.text(), float(DEFAULT_ANALYSIS_DELAY))
        fetch_cmd = self._analysis_command(
            "scripts/fetch_signals.py",
            ["--total", str(total), "--batch-size", str(batch), "--delay", str(delay)],
        )
        report_cmd = self._analysis_command("scripts/report_signal_outcomes.py", [])
        self._start_analysis_sequence("fetch + report", [fetch_cmd, report_cmd])

    def _start_analysis_sequence(self, label: str, commands: list[list[str]]) -> None:
        if self._process_running(self.analysis_process):
            QMessageBox.warning(
                self,
                "Analysis running",
                "Wait for the current analysis to finish before starting another.",
            )
            return
        self.analysis_label = label
        self.analysis_queue = commands[:]
        self.analysis_status_label.setText(f"Analysis: {label}")
        self._run_next_analysis_command()

    def _run_next_analysis_command(self) -> None:
        if not self.analysis_queue:
            self._analysis_done()
            return

        cmd = self.analysis_queue.pop(0)
        env_overrides = self._analysis_env_overrides()

        self._append_log(f"\n[analysis] Running: {' '.join(cmd)}\n")

        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setWorkingDirectory(str(BASE_DIR))
        process.setProcessEnvironment(self._qprocess_env(env_overrides))
        process.readyReadStandardOutput.connect(self._handle_analysis_output)
        process.finished.connect(self._analysis_finished)
        process.errorOccurred.connect(self._analysis_error)
        process.start(cmd[0], cmd[1:])

        self.analysis_process = process

    def _handle_analysis_output(self) -> None:
        if not self.analysis_process:
            return
        data = self.analysis_process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        self._append_log(text)

    def _analysis_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._append_log(f"[analysis] Step finished with code {exit_code}\n")
        self.analysis_process = None
        if exit_code != 0:
            self.analysis_status_label.setText("Analysis: error")
            self.analysis_queue.clear()
            return
        self._run_next_analysis_command()

    def _analysis_error(self, error: QProcess.ProcessError) -> None:
        self._append_log(f"[analysis] Process error: {error}\n")
        self.analysis_status_label.setText("Analysis: error")
        self.analysis_queue.clear()
        if self.analysis_process is not None and not self._process_running(self.analysis_process):
            self.analysis_process = None

    def _analysis_done(self) -> None:
        self.analysis_status_label.setText("Analysis: idle")
        self.load_analysis_summary()

    # ---------- Analysis Summary ----------
    def load_analysis_summary(self) -> None:
        if not OUTCOMES_PATH.exists():
            self.summary_view.setPlainText(
                "No outcomes yet. Run Generate Report after fetching signals."
            )
            return
        try:
            data = json.loads(OUTCOMES_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.summary_view.setPlainText("signals_outcomes.json is not valid JSON.")
            return

        signals = data.get("signals", [])
        if not signals:
            self.summary_view.setPlainText("signals_outcomes.json has no signals.")
            return

        total = len(signals)
        tp2 = sum(1 for s in signals if s.get("outcome") == "tp2_hit")
        tp1 = sum(1 for s in signals if s.get("outcome") == "tp1_hit")
        sl = sum(1 for s in signals if s.get("outcome") == "sl_hit")
        tp_u = sum(1 for s in signals if s.get("outcome") == "tp_hit_unnumbered")
        tp_total = tp1 + tp2 + tp_u
        win_rate = (tp_total / total * 100) if total else 0.0
        tp1_reached = tp1 + tp2
        conversion = (tp2 / tp1_reached * 100) if tp1_reached else 0.0

        def _parse_dt(value: str | None) -> datetime | None:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None

        tp1_minutes: list[float] = []
        tp2_minutes: list[float] = []
        for signal in signals:
            signal_dt = _parse_dt(signal.get("date"))
            tp_hit_at = signal.get("tp_hit_at") or {}
            tp1_dt = _parse_dt(tp_hit_at.get("1") if isinstance(tp_hit_at, dict) else None)
            tp2_dt = _parse_dt(tp_hit_at.get("2") if isinstance(tp_hit_at, dict) else None)
            if signal_dt and tp1_dt and tp1_dt >= signal_dt:
                tp1_minutes.append((tp1_dt - signal_dt).total_seconds() / 60)
            if signal_dt and tp2_dt and tp2_dt >= signal_dt:
                tp2_minutes.append((tp2_dt - signal_dt).total_seconds() / 60)

        avg_tp1 = (sum(tp1_minutes) / len(tp1_minutes)) if tp1_minutes else None
        avg_tp2 = (sum(tp2_minutes) / len(tp2_minutes)) if tp2_minutes else None

        dates = sorted(d for d in (_parse_dt(s.get("date")) for s in signals) if d)
        date_range = f"{dates[0].date()} to {dates[-1].date()}" if dates else "unknown"

        lines = [
            f"Signals: {total} ({date_range})",
            f"TP2: {tp2} | TP1-only: {tp1} | SL (inferred): {sl}",
            f"Win rate: {win_rate:.1f}% | TP1 -> TP2 conversion: {conversion:.1f}%",
            f"Unnumbered TP hits: {tp_u}",
            f"Report: {REPORT_PATH}",
        ]
        if avg_tp1 is not None:
            lines.append(f"Avg time to TP1: {avg_tp1:.1f} minutes")
        if avg_tp2 is not None:
            lines.append(f"Avg time to TP2: {avg_tp2:.1f} minutes")

        self.summary_view.setPlainText("\n".join(lines))

    # ---------- Lifecycle ----------
    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._process_running(self.bot_process):
            reply = QMessageBox.question(
                self,
                "Quit",
                "Bot is running. Stop it and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.stop_bot()

        if self._process_running(self.analysis_process):
            self.analysis_process.kill()

        event.accept()


def main() -> None:
    app = QApplication(sys.argv)
    font = QFont("Fira Sans", 11)
    app.setFont(font)
    apply_app_style(app)
    window = BotGui()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
