"""API Configuration."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class MT5Config:
    """MT5 connection configuration."""

    login: int = field(default_factory=lambda: int(os.getenv("MT5_LOGIN", "0")))
    password: str = field(default_factory=lambda: os.getenv("MT5_PASSWORD", ""))
    server: str = field(default_factory=lambda: os.getenv("MT5_SERVER", ""))
    docker_host: str = field(default_factory=lambda: os.getenv("MT5_DOCKER_HOST", "localhost"))
    docker_port: int = field(default_factory=lambda: int(os.getenv("MT5_DOCKER_PORT", "8001")))


@dataclass
class APIConfig:
    """API server configuration."""

    host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    )
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")


@dataclass
class DatabaseConfig:
    """Database configuration."""

    url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{Path(__file__).parent.parent / 'trade_history.db'}",
        )
    )


@dataclass
class Config:
    """Main configuration combining all configs."""

    mt5: MT5Config = field(default_factory=MT5Config)
    api: APIConfig = field(default_factory=APIConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    # Path to bot state file
    bot_state_file: str = field(
        default_factory=lambda: os.getenv(
            "BOT_STATE_FILE",
            str(Path(__file__).parent.parent.parent / "bot" / "bot_state.json"),
        )
    )


# Global config instance
config = Config()
