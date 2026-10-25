"""Central configuration for the test suite, resolved from environment variables.

Defaults isolate the test stack from a developer's running dev stack:
a dedicated compose project, its own DB host port and its own HTTP port. The
Alma Spei backend honours ALMA_DB_PORT / ALMA_HTTP_PORT / ALMA_DB_* overrides
(see src/api/alma_spei/api/config.clj in the app repo), so the orchestrator can
point everything at these ports.

Nothing here reads secrets into memory eagerly; the password is only read from
the app repo's .secrets files when a client actually connects.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Repo root = two levels up from src/alma_spei_tests/config.py
REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value is not None and value != "" else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Immutable, environment-derived settings shared by fixtures and clients."""

    # --- Application under test (the alma-spei repo) ---------------------------
    app_repo: Path = field(
        default_factory=lambda: Path(
            _env("ALMA_APP_REPO", str(REPO_ROOT.parent / "alma-spei"))
        ).resolve()
    )

    # --- Orchestration ---------------------------------------------------------
    # When False, fixtures assume the app is already running at base_url and do
    # not touch Docker / the backend (handy for fast local debugging).
    orchestrate: bool = field(default_factory=lambda: not _env_bool("ALMA_NO_ORCHESTRATION", False))
    compose_project: str = field(default_factory=lambda: _env("ALMA_COMPOSE_PROJECT", "alma-spei-tests"))
    readiness_timeout_s: int = field(default_factory=lambda: _env_int("ALMA_READINESS_TIMEOUT", 180))

    # External command names, overridable where the CLI is not plainly on PATH
    # (common for the Clojure CLI / Babashka on Windows).
    clojure_cmd: str = field(default_factory=lambda: _env("ALMA_CLOJURE_CMD", "clojure"))
    bb_cmd: str = field(default_factory=lambda: _env("ALMA_BB_CMD", "bb"))
    docker_cmd: str = field(default_factory=lambda: _env("ALMA_DOCKER_CMD", "docker"))

    # --- HTTP ------------------------------------------------------------------
    http_host: str = field(default_factory=lambda: _env("ALMA_HTTP_HOST", "127.0.0.1"))
    http_port: int = field(default_factory=lambda: _env_int("ALMA_TEST_HTTP_PORT", 3100))

    # --- Database --------------------------------------------------------------
    db_host: str = field(default_factory=lambda: _env("ALMA_DB_HOST", "127.0.0.1"))
    db_port: int = field(default_factory=lambda: _env_int("ALMA_TEST_DB_PORT", 55432))
    db_name: str = field(default_factory=lambda: _env("ALMA_DB_NAME", "alma_spei_dev"))
    db_app_user: str = field(default_factory=lambda: _env("ALMA_DB_USER", "alma_spei_app"))
    migration_user: str = field(default_factory=lambda: _env("ALMA_MIGRATION_USER", "alma_spei_migrator"))

    # --- Timeouts (seconds) ----------------------------------------------------
    http_timeout_s: float = field(default_factory=lambda: float(_env("ALMA_HTTP_TIMEOUT", "10")))

    @property
    def base_url(self) -> str:
        """Base URL of the app under test. BASE_URL overrides the derived value."""
        return _env("BASE_URL", f"http://{self.http_host}:{self.http_port}")

    @property
    def secrets_dir(self) -> Path:
        return self.app_repo / ".secrets"

    @property
    def app_password_file(self) -> Path:
        return self.secrets_dir / "app-password"

    @property
    def migration_password_file(self) -> Path:
        return self.secrets_dir / "migration-password"

    @property
    def compose_file(self) -> Path:
        return self.app_repo / "infra" / "compose.yaml"

    def read_app_password(self) -> str:
        """Read the app DB password written by `bb init` into the app repo."""
        return self.app_password_file.read_text(encoding="utf-8").strip()


def load_settings() -> Settings:
    """Build a fresh Settings snapshot from the current environment."""
    return Settings()
