"""Fail-fast preflight checks for the tools the orchestrator needs.

"Always fresh" orchestration builds and runs the real app, so the Clojure CLI,
Babashka, Docker (with Compose v2) and a JDK/Node toolchain must be present.
We check early and raise one clear, actionable message rather than failing with
an obscure error halfway through bring-up.
"""

import shutil
import subprocess
from dataclasses import dataclass

from alma_spei_tests.config import Settings


@dataclass(frozen=True)
class Tool:
    name: str
    command: str
    hint: str


class ToolchainError(RuntimeError):
    """Raised when a required external tool is missing or unusable."""


def _resolvable(command: str) -> bool:
    return shutil.which(command) is not None


def check(settings: Settings):
    """Verify required tools exist and the app repo is present. Raise otherwise."""
    tools = [
        Tool("Docker", settings.docker_cmd, "Install Docker Desktop/Engine with Compose v2 and start it."),
        Tool("Clojure CLI", settings.clojure_cmd, "Install the Clojure CLI, or set ALMA_CLOJURE_CMD."),
        Tool("Babashka", settings.bb_cmd, "Install Babashka (bb), or set ALMA_BB_CMD."),
    ]
    missing = [t for t in tools if not _resolvable(t.command)]
    problems = [f"  - {t.name} (`{t.command}`): {t.hint}" for t in missing]

    # Docker must not only exist but be running.
    if settings.docker_cmd not in {t.command for t in missing}:
        try:
            subprocess.run(
                [settings.docker_cmd, "info"],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            problems.append("  - Docker daemon does not appear to be running. Start Docker and retry.")

    if not settings.compose_file.exists():
        problems.append(
            f"  - App repo not found at {settings.app_repo} "
            f"(expected {settings.compose_file}). Clone alma-spei next to this repo "
            f"or set ALMA_APP_REPO."
        )

    if problems:
        raise ToolchainError(
            "Cannot orchestrate the Alma Spei stack. Fix the following and retry "
            "(or set ALMA_NO_ORCHESTRATION=1 to test an already-running app):\n"
            + "\n".join(problems)
        )
