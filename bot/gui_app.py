#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
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


class MetricCard(QFrame):
    """A compact styled card displaying a metric value and label."""

    def __init__(self, label: str, value: str = "-", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setFixedHeight(50)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text_label = QLabel(label)
        self.text_label.setObjectName("MetricLabel")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.value_label)
        layout.addWidget(self.text_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class InsightCard(QFrame):
    """A compact styled card for displaying an insight/tip."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InsightCard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        icon = QLabel("\u2022")  # Bullet
        icon.setObjectName("InsightIcon")
        icon.setFixedWidth(12)

        text_label = QLabel(text)
        text_label.setObjectName("InsightText")
        text_label.setWordWrap(True)

        layout.addWidget(icon)
        layout.addWidget(text_label, stretch=1)


def apply_app_style(app: QApplication) -> None:
    app.setStyleSheet(
        f"""
        QMainWindow {{
            background: {COLORS["bg0"]};
            color: {COLORS["text"]};
            font-family: "Avenir Next", "Segoe UI", sans-serif;
            font-size: 12px;
        }}
        QMenuBar {{
            background: {COLORS["panel"]};
            color: {COLORS["text"]};
            border-bottom: 1px solid {COLORS["border"]};
            padding: 4px;
        }}
        QMenuBar::item {{
            padding: 4px 12px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background: {COLORS["panel_alt"]};
        }}
        QMenu {{
            background: {COLORS["panel"]};
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background: {COLORS["accent"]};
            color: {COLORS["bg0"]};
        }}
        QStatusBar {{
            background: {COLORS["panel"]};
            color: {COLORS["muted"]};
            border-top: 1px solid {COLORS["border"]};
        }}
        QTabWidget::pane {{
            border: 1px solid {COLORS["border"]};
            border-radius: 8px;
            background: rgba(15, 28, 56, 0.6);
            top: -1px;
        }}
        QTabBar::tab {{
            background: {COLORS["panel"]};
            color: {COLORS["muted"]};
            border: 1px solid {COLORS["border"]};
            border-bottom: none;
            padding: 8px 20px;
            margin-right: 2px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }}
        QTabBar::tab:selected {{
            background: {COLORS["panel_alt"]};
            color: {COLORS["accent"]};
            font-weight: 600;
        }}
        QTabBar::tab:hover:!selected {{
            background: {COLORS["panel_alt"]};
        }}
        QLabel {{
            color: {COLORS["text"]};
        }}
        QLabel#MutedLabel {{
            color: {COLORS["muted"]};
            font-size: 11px;
        }}
        QLabel#SectionTitle {{
            color: {COLORS["accent"]};
            font-weight: 600;
            font-size: 13px;
            padding: 4px 0;
        }}
        QLineEdit, QComboBox {{
            border: 1px solid {COLORS["border"]};
            border-radius: 6px;
            padding: 6px 8px;
            background: rgba(19, 35, 72, 0.96);
            color: {COLORS["text"]};
            selection-background-color: {COLORS["info"]};
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
            border-radius: 6px;
            padding: 6px 14px;
            background: rgba(19, 35, 72, 0.98);
            color: {COLORS["text"]};
            font-weight: 500;
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
        QPushButton#NavButton {{
            border: none;
            border-radius: 6px;
            padding: 10px 16px;
            background: transparent;
            color: {COLORS["muted"]};
            font-weight: 500;
            text-align: left;
        }}
        QPushButton#NavButton:hover {{
            background: rgba(245, 158, 11, 0.1);
            color: {COLORS["text"]};
        }}
        QPushButton#NavButton:checked {{
            background: rgba(245, 158, 11, 0.2);
            color: {COLORS["accent"]};
            font-weight: 600;
        }}
        QCheckBox {{
            color: {COLORS["muted"]};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {COLORS["border"]};
            background: rgba(19, 35, 72, 0.9);
        }}
        QCheckBox::indicator:checked {{
            background: {COLORS["accent"]};
            border-color: {COLORS["accent"]};
        }}
        QFrame#MetricCard {{
            border: 1px solid {COLORS["border"]};
            border-radius: 8px;
            background: rgba(19, 35, 72, 0.7);
        }}
        QLabel#MetricValue {{
            font-size: 18px;
            font-weight: 700;
            color: {COLORS["accent_strong"]};
        }}
        QLabel#MetricLabel {{
            font-size: 10px;
            color: {COLORS["muted"]};
        }}
        QFrame#InsightCard {{
            border: 1px solid {COLORS["border"]};
            border-radius: 6px;
            background: rgba(19, 35, 72, 0.5);
        }}
        QLabel#InsightText {{
            color: {COLORS["text"]};
            font-size: 11px;
        }}
        QLabel#InsightIcon {{
            color: {COLORS["info"]};
            font-size: 12px;
        }}
        QListWidget {{
            border: 1px solid {COLORS["border"]};
            border-radius: 8px;
            background: rgba(9, 18, 38, 0.96);
            color: {COLORS["text"]};
            padding: 4px;
            font-family: "JetBrains Mono", "Menlo", "Consolas", monospace;
            font-size: 11px;
            outline: none;
        }}
        QListWidget::item {{
            padding: 2px 6px;
            border-radius: 3px;
        }}
        QListWidget::item:hover {{
            background: rgba(245, 158, 11, 0.1);
        }}
        QSplitter::handle {{
            background: {COLORS["border"]};
        }}
        QSplitter::handle:vertical {{
            height: 3px;
        }}
        """
    )


class BotGui(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Signal Copier Control Room")
        self.resize(900, 650)

        self.env_inputs: dict[str, QLineEdit | QComboBox] = {}
        self.bot_process: QProcess | None = None
        self.analysis_process: QProcess | None = None
        self.analysis_queue: list[list[str]] = []
        self.analysis_label = "idle"

        self.write_env_on_start = QCheckBox("Write .env on start")
        self.prevent_sleep = QCheckBox("Prevent sleep (macOS)")
        self.prevent_sleep.setChecked(sys.platform == "darwin")

        self.analysis_total_input = QLineEdit(DEFAULT_ANALYSIS_TOTAL)
        self.analysis_total_input.setFixedWidth(60)
        self.analysis_batch_input = QLineEdit(DEFAULT_ANALYSIS_BATCH)
        self.analysis_batch_input.setFixedWidth(60)
        self.analysis_delay_input = QLineEdit(DEFAULT_ANALYSIS_DELAY)
        self.analysis_delay_input.setFixedWidth(40)

        # Metric cards for outcome summary (compact)
        self.metric_signals = MetricCard("Signals")
        self.metric_win_rate = MetricCard("Win Rate")
        self.metric_tp2 = MetricCard("TP2")
        self.metric_tp1 = MetricCard("TP1")
        self.metric_sl = MetricCard("SL")
        self.metric_conversion = MetricCard("TP1\u2192TP2")
        self.summary_date_label = QLabel("No data loaded")
        self.summary_date_label.setObjectName("MutedLabel")

        # Log view
        self.log_view = QListWidget()
        self.log_view.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.log_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self._show_log_context_menu)

        self._build_ui()
        self._build_menu()
        self._build_statusbar()
        self._load_initial_values()
        self.load_analysis_summary()

    # ---------- UI Construction ----------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Main splitter: tabs on top, log on bottom
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Tab widget for main content
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_config_tab(), "Configuration")
        self.tabs.addTab(self._build_bot_tab(), "Bot Control")
        self.tabs.addTab(self._build_analysis_tab(), "Analysis")
        splitter.addWidget(self.tabs)

        # Log panel at bottom
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.setSpacing(4)

        log_header = QHBoxLayout()
        log_title = QLabel("Output")
        log_title.setObjectName("SectionTitle")
        copy_selected_btn = QPushButton("Copy Selected")
        copy_selected_btn.setFixedWidth(100)
        copy_selected_btn.clicked.connect(self._copy_selected_logs)
        copy_all_btn = QPushButton("Copy All")
        copy_all_btn.setFixedWidth(70)
        copy_all_btn.clicked.connect(self._copy_all_logs)
        clear_log_btn = QPushButton("Clear")
        clear_log_btn.setFixedWidth(60)
        clear_log_btn.clicked.connect(lambda: self.log_view.clear())
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(copy_selected_btn)
        log_header.addWidget(copy_all_btn)
        log_header.addWidget(clear_log_btn)
        log_layout.addLayout(log_header)
        log_layout.addWidget(self.log_view)
        splitter.addWidget(log_widget)

        splitter.setSizes([400, 200])
        root.addWidget(splitter)

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        save_action = QAction("Save .env", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_env)
        file_menu.addAction(save_action)

        reload_action = QAction("Reload .env", self)
        reload_action.setShortcut("Ctrl+R")
        reload_action.triggered.connect(self.reload_env)
        file_menu.addAction(reload_action)

        file_menu.addSeparator()

        clear_cache_action = QAction("Clear Cache", self)
        clear_cache_action.triggered.connect(self.clear_cache)
        file_menu.addAction(clear_cache_action)

        # Edit menu (for log operations)
        edit_menu = menubar.addMenu("Edit")

        copy_selected_action = QAction("Copy Selected Logs", self)
        copy_selected_action.setShortcut("Ctrl+C")
        copy_selected_action.triggered.connect(self._copy_selected_logs)
        edit_menu.addAction(copy_selected_action)

        copy_all_action = QAction("Copy All Logs", self)
        copy_all_action.setShortcut("Ctrl+Shift+C")
        copy_all_action.triggered.connect(self._copy_all_logs)
        edit_menu.addAction(copy_all_action)

        edit_menu.addSeparator()

        clear_logs_action = QAction("Clear Logs", self)
        clear_logs_action.triggered.connect(lambda: self.log_view.clear())
        edit_menu.addAction(clear_logs_action)

        # Bot menu
        bot_menu = menubar.addMenu("Bot")

        start_action = QAction("Start Bot", self)
        start_action.setShortcut("Ctrl+B")
        start_action.triggered.connect(self.start_bot)
        bot_menu.addAction(start_action)

        stop_action = QAction("Stop Bot", self)
        stop_action.setShortcut("Ctrl+Shift+B")
        stop_action.triggered.connect(self.stop_bot)
        bot_menu.addAction(stop_action)

        # Analysis menu
        analysis_menu = menubar.addMenu("Analysis")

        fetch_action = QAction("Fetch Messages", self)
        fetch_action.triggered.connect(self.fetch_messages)
        analysis_menu.addAction(fetch_action)

        report_action = QAction("Generate Report", self)
        report_action.triggered.connect(self.generate_report)
        analysis_menu.addAction(report_action)

        analysis_menu.addSeparator()

        refresh_action = QAction("Refresh Summary", self)
        refresh_action.triggered.connect(self.load_analysis_summary)
        analysis_menu.addAction(refresh_action)

    def _build_statusbar(self) -> None:
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.bot_status_label = QLabel("Bot: stopped")
        self.analysis_status_label = QLabel("Analysis: idle")

        self.statusbar.addWidget(self.bot_status_label)
        self.statusbar.addWidget(QLabel(" | "))
        self.statusbar.addWidget(self.analysis_status_label)

    def _build_config_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(32)

        # Left column: Telegram + MT5
        left_col = QVBoxLayout()
        left_col.setSpacing(16)
        for section in ["Telegram", "MT5"]:
            fields = next(f for s, f in ENV_SECTIONS if s == section)
            left_col.addWidget(self._build_config_section(section, fields))
        left_col.addStretch()

        left_container = QWidget()
        left_container.setLayout(left_col)
        left_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(left_container)

        # Right column: Trading + Optional
        right_col = QVBoxLayout()
        right_col.setSpacing(16)
        for section in ["Trading", "Optional"]:
            fields = next(f for s, f in ENV_SECTIONS if s == section)
            right_col.addWidget(self._build_config_section(section, fields))
        right_col.addStretch()

        right_container = QWidget()
        right_container.setLayout(right_col)
        right_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(right_container)

        return widget

    def _build_config_section(self, title: str, fields: list[tuple[str, str, bool]]) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)

        form = QFormLayout()
        form.setSpacing(8)
        form.setHorizontalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        for key, label, is_secret in fields:
            if key == "TRADING_STRATEGY":
                widget = QComboBox()
                widget.addItems(STRATEGY_CHOICES)
                widget.setEditable(False)
                widget.setMinimumWidth(150)
                self.env_inputs[key] = widget
            else:
                widget = QLineEdit()
                widget.setEchoMode(QLineEdit.EchoMode.Password if is_secret else QLineEdit.EchoMode.Normal)
                widget.setPlaceholderText(label)
                widget.setMinimumWidth(150)
                self.env_inputs[key] = widget
            form.addRow(label, widget)

        layout.addLayout(form)
        return container

    def _build_bot_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # Bot controls
        controls = QHBoxLayout()
        controls.setSpacing(10)

        start_btn = QPushButton("Start Bot")
        start_btn.setObjectName("SuccessButton")
        start_btn.clicked.connect(self.start_bot)

        stop_btn = QPushButton("Stop Bot")
        stop_btn.setObjectName("DangerButton")
        stop_btn.clicked.connect(self.stop_bot)

        controls.addWidget(start_btn)
        controls.addWidget(stop_btn)
        controls.addStretch()
        layout.addLayout(controls)

        # Options
        options = QHBoxLayout()
        options.setSpacing(20)
        options.addWidget(self.write_env_on_start)
        options.addWidget(self.prevent_sleep)
        options.addStretch()
        layout.addLayout(options)

        # Tips
        tips = QLabel("Tip: Use Ctrl+B to start and Ctrl+Shift+B to stop the bot.")
        tips.setObjectName("MutedLabel")
        layout.addWidget(tips)

        layout.addStretch()
        return widget

    def _build_analysis_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Controls row
        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QLabel("Messages:"))
        controls.addWidget(self.analysis_total_input)
        controls.addWidget(QLabel("Batch:"))
        controls.addWidget(self.analysis_batch_input)
        controls.addWidget(QLabel("Delay:"))
        controls.addWidget(self.analysis_delay_input)
        controls.addSpacing(16)

        fetch_btn = QPushButton("Fetch")
        fetch_btn.clicked.connect(self.fetch_messages)
        report_btn = QPushButton("Report")
        report_btn.setObjectName("PrimaryButton")
        report_btn.clicked.connect(self.generate_report)
        both_btn = QPushButton("Fetch + Report")
        both_btn.clicked.connect(self.fetch_and_report)

        controls.addWidget(fetch_btn)
        controls.addWidget(report_btn)
        controls.addWidget(both_btn)
        controls.addStretch()
        layout.addLayout(controls)

        # Summary section
        summary_title = QLabel("Outcome Summary")
        summary_title.setObjectName("SectionTitle")
        layout.addWidget(summary_title)
        layout.addWidget(self.summary_date_label)

        # Metrics grid (compact, single row)
        metrics = QHBoxLayout()
        metrics.setSpacing(8)
        metrics.addWidget(self.metric_signals)
        metrics.addWidget(self.metric_win_rate)
        metrics.addWidget(self.metric_tp2)
        metrics.addWidget(self.metric_tp1)
        metrics.addWidget(self.metric_sl)
        metrics.addWidget(self.metric_conversion)
        metrics.addStretch()
        layout.addLayout(metrics)

        # Insights section
        insights_title = QLabel("Insights")
        insights_title.setObjectName("SectionTitle")
        layout.addWidget(insights_title)

        insights = [
            "TP1\u2192TP2 conversion shows runner quality",
            "If TP1-only dominates, consider earlier partials",
            "Avg time-to-TP helps tune session timing",
        ]
        for text in insights:
            layout.addWidget(InsightCard(text))

        layout.addStretch()
        return widget

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
        # Split text into lines and add each as a list item
        lines = text.splitlines()
        for line in lines:
            if line.strip():  # Skip empty lines
                item = QListWidgetItem(line)
                # Color code based on content
                if "[bot]" in line.lower():
                    item.setForeground(Qt.GlobalColor.cyan)
                elif "[analysis]" in line.lower():
                    item.setForeground(Qt.GlobalColor.yellow)
                elif "error" in line.lower():
                    item.setForeground(Qt.GlobalColor.red)
                elif "warning" in line.lower():
                    item.setForeground(Qt.GlobalColor.magenta)
                self.log_view.addItem(item)
        # Auto-scroll to bottom
        self.log_view.scrollToBottom()
        # Keep only last 1000 lines to prevent memory issues
        while self.log_view.count() > 1000:
            self.log_view.takeItem(0)

    def _copy_selected_logs(self) -> None:
        """Copy selected log lines to clipboard."""
        selected = self.log_view.selectedItems()
        if not selected:
            return
        text = "\n".join(item.text() for item in selected)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def _copy_all_logs(self) -> None:
        """Copy all log lines to clipboard."""
        lines = []
        for i in range(self.log_view.count()):
            item = self.log_view.item(i)
            if item:
                lines.append(item.text())
        text = "\n".join(lines)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def _show_log_context_menu(self, pos) -> None:  # type: ignore[no-untyped-def]
        """Show context menu for log view."""
        menu = QMenu(self)

        copy_selected_action = menu.addAction("Copy Selected")
        copy_selected_action.triggered.connect(self._copy_selected_logs)
        copy_selected_action.setEnabled(len(self.log_view.selectedItems()) > 0)

        copy_all_action = menu.addAction("Copy All")
        copy_all_action.triggered.connect(self._copy_all_logs)
        copy_all_action.setEnabled(self.log_view.count() > 0)

        menu.addSeparator()

        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.log_view.selectAll)

        menu.addSeparator()

        clear_action = menu.addAction("Clear")
        clear_action.triggered.connect(self.log_view.clear)

        menu.popup(self.log_view.mapToGlobal(pos))

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
    def _reset_summary_metrics(self, message: str = "No data") -> None:
        """Reset all metric cards to default state."""
        self.summary_date_label.setText(message)
        self.metric_signals.set_value("-")
        self.metric_win_rate.set_value("-")
        self.metric_tp2.set_value("-")
        self.metric_tp1.set_value("-")
        self.metric_sl.set_value("-")
        self.metric_conversion.set_value("-")

    def load_analysis_summary(self) -> None:
        if not OUTCOMES_PATH.exists():
            self._reset_summary_metrics("No outcomes yet. Run Generate Report after fetching signals.")
            return
        try:
            data = json.loads(OUTCOMES_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._reset_summary_metrics("signals_outcomes.json is not valid JSON.")
            return

        signals = data.get("signals", [])
        if not signals:
            self._reset_summary_metrics("signals_outcomes.json has no signals.")
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

        # Update metric cards
        self.summary_date_label.setText(f"Data: {date_range}")
        self.metric_signals.set_value(str(total))
        self.metric_win_rate.set_value(f"{win_rate:.1f}%")
        self.metric_tp2.set_value(str(tp2))
        self.metric_tp1.set_value(str(tp1))
        self.metric_sl.set_value(str(sl))
        self.metric_conversion.set_value(f"{conversion:.1f}%")

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
