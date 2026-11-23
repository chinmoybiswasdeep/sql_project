"""Central configuration, resolved from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

DEMO_BASE_URL = "https://physionet.org/files/mimic-iv-demo/2.2"
DEMO_VERSION = "mimic-iv-demo-2.2"


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


@dataclass(frozen=True)
class PostgresConfig:
    host: str = field(default_factory=lambda: _env("HI_PG_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(_env("HI_PG_PORT", "5433")))
    user: str = field(default_factory=lambda: _env("HI_PG_USER", "hi_admin"))
    password: str = field(default_factory=lambda: os.getenv("HI_PG_PASSWORD", ""))
    dbname: str = field(default_factory=lambda: _env("HI_PG_DB", "hospital_intel"))

    @property
    def conninfo(self) -> str:
        parts = [f"host={self.host}", f"port={self.port}", f"user={self.user}",
                 f"dbname={self.dbname}"]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)

    @property
    def sqlalchemy_url(self) -> str:
        auth = self.user if not self.password else f"{self.user}:{self.password}"
        return f"postgresql+psycopg://{auth}@{self.host}:{self.port}/{self.dbname}"


@dataclass(frozen=True)
class Settings:
    dataset_mode: str = field(default_factory=lambda: _env("HI_DATASET_MODE", "demo"))
    demo_dir: Path = field(default_factory=lambda: PROJECT_ROOT / _env("HI_DEMO_DIR", "data/raw"))
    full_dir: Path = field(
        default_factory=lambda: PROJECT_ROOT / _env("HI_FULL_DIR", "data/full/mimiciv/3.1")
    )
    batch_rows: int = field(default_factory=lambda: int(_env("HI_BATCH_ROWS", "250000")))
    min_cell_size: int = field(default_factory=lambda: int(_env("HI_MIN_CELL_SIZE", "5")))
    pg: PostgresConfig = field(default_factory=PostgresConfig)

    def __post_init__(self) -> None:
        if self.dataset_mode not in {"demo", "full"}:
            raise ValueError(f"HI_DATASET_MODE must be 'demo' or 'full', got {self.dataset_mode!r}")
        if self.batch_rows <= 0:
            raise ValueError("HI_BATCH_ROWS must be positive")

    @property
    def data_dir(self) -> Path:
        return self.demo_dir if self.dataset_mode == "demo" else self.full_dir

    @property
    def dataset_label(self) -> str:
        return DEMO_VERSION if self.dataset_mode == "demo" else "mimic-iv-3.1"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def load_source_contract(path: str | None = None) -> dict[str, Any]:
    contract_path = Path(path) if path else PROJECT_ROOT / "config" / "sources.yaml"
    with contract_path.open() as fh:
        contract = yaml.safe_load(fh)
    missing = set(contract["load_order"]) ^ set(contract["tables"])
    if missing:
        raise ValueError(f"load_order and tables disagree on: {sorted(missing)}")
    return contract
