"""Bring the Alma Spei stack up fresh for a test session, and tear it down.

Lifecycle (``up``):

  1. preflight the toolchain;
  2. ``bb init`` in the app repo so the ``.secrets`` files exist;
  3. ``docker compose down -v`` then ``up -d --wait db`` under a dedicated
     compose project + host port, giving a clean DB volume each session
     (the role-bootstrap init script only runs on a fresh volume);
  4. ``clojure -M:migrate up`` with migration credentials;
  5. ``clojure -M:ui ... release app`` to compile the frontend assets;
  6. start the backend (``clojure -M:run``) serving API + assets on loopback;
  7. poll ``/api/health/ready`` until it reports 200.

Teardown (``down``) stops the backend process and removes the DB volume.

All subprocesses inherit the current environment plus the Alma_* overrides so
the backend, migrator and compose all agree on ports and credentials. Backend
stdout/stderr is captured to ``reports/stack/backend.log`` for debugging.
"""

import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from alma_spei_tests.config import Settings
from alma_spei_tests.logging_setup import get_logger
from alma_spei_tests.orchestration import toolchain

log = get_logger("orchestration")


class StackError(RuntimeError):
    """Raised when the stack cannot be brought up or becomes unhealthy."""


class Stack:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._backend: subprocess.Popen | None = None
        self._backend_log: Path | None = None

    # --- environment ----------------------------------------------------------
    def _base_env(self) -> dict[str, str]:
        """App/migrator/compose env: ports + the single app secret source."""
        env = dict(os.environ)
        env["ALMA_DB_PORT"] = str(self.settings.db_port)
        env["ALMA_HTTP_PORT"] = str(self.settings.http_port)
        env["ALMA_HTTP_HOST"] = self.settings.http_host
        env["ALMA_DB_HOST"] = self.settings.db_host
        env["ALMA_DB_NAME"] = self.settings.db_name
        env["ALMA_DB_PASSWORD_FILE"] = str(self.settings.app_password_file)
        # Isolate from a dev stack sharing the app repo's compose file.
        env["COMPOSE_PROJECT_NAME"] = self.settings.compose_project
        return env

    def _migration_env(self) -> dict[str, str]:
        env = self._base_env()
        env["ALMA_MIGRATION_USER"] = self.settings.migration_user
        env["ALMA_MIGRATION_PASSWORD_FILE"] = str(self.settings.migration_password_file)
        return env

    # --- process helpers ------------------------------------------------------
    def _run(self, args: list[str], env: dict[str, str], step: str):
        log.info("stack: %s -> %s", step, " ".join(args))
        result = subprocess.run(
            args,
            cwd=self.settings.app_repo,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise StackError(
                f"Stack step failed: {step}\n"
                f"command: {' '.join(args)}\n"
                f"exit code: {result.returncode}\n"
                f"stderr (tail):\n{result.stderr[-2000:]}"
            )

    def _compose(self, *args: str) -> list[str]:
        s = self.settings
        return [
            s.docker_cmd, "compose",
            "-p", s.compose_project,
            "-f", str(s.compose_file),
            *args,
        ]

    # --- lifecycle ------------------------------------------------------------
    def up(self):
        if not self.settings.orchestrate:
            log.info("stack: ALMA_NO_ORCHESTRATION set; assuming app at %s", self.settings.base_url)
            self._wait_ready()
            return

        toolchain.check(self.settings)

        self._backend_log = self._prepare_log_file()

        # 2. secrets
        self._run([self.settings.bb_cmd, "init"], self._base_env(), "bb init (secrets)")

        # 3. fresh database
        self._run(self._compose("down", "-v", "--remove-orphans"), self._base_env(), "compose down -v")
        self._run(self._compose("up", "-d", "--wait", "db"), self._base_env(), "compose up db")

        # 4. migrations
        self._run(
            [self.settings.clojure_cmd, "-Srepro", "-M:migrate", "up"],
            self._migration_env(),
            "migrate up",
        )

        # 5. compiled frontend assets
        self._run(
            [self.settings.clojure_cmd, "-Srepro", "-M:ui",
             "-m", "shadow.cljs.devtools.cli", "release", "app"],
            self._base_env(),
            "frontend release build",
        )

        # 6. backend
        self._start_backend()

        # 7. readiness
        self._wait_ready()
        log.info("stack: ready at %s", self.settings.base_url)

    def _prepare_log_file(self) -> Path:
        stack_dir = _repo_reports_dir() / "stack"
        stack_dir.mkdir(parents=True, exist_ok=True)
        return stack_dir / "backend.log"

    def _start_backend(self):
        assert self._backend_log is not None
        log.info("stack: starting backend -> %s", self._backend_log)
        handle = self._backend_log.open("w", encoding="utf-8")
        self._backend = subprocess.Popen(
            [self.settings.clojure_cmd, "-Srepro", "-M:run"],
            cwd=self.settings.app_repo,
            env=self._base_env(),
            stdout=handle,
            stderr=subprocess.STDOUT,
        )

    def _wait_ready(self):
        url = f"{self.settings.base_url}/api/health/ready"
        deadline = time.monotonic() + self.settings.readiness_timeout_s
        last_error: str = "no attempt made"
        while time.monotonic() < deadline:
            if self._backend is not None and self._backend.poll() is not None:
                raise StackError(
                    f"Backend process exited early (code {self._backend.returncode}). "
                    f"See {self._backend_log}."
                )
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 (loopback only)
                    if resp.status == 200:
                        return
                    last_error = f"HTTP {resp.status}"
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                last_error = str(exc)
            time.sleep(1.0)
        raise StackError(
            f"App not ready at {url} within {self.settings.readiness_timeout_s}s "
            f"(last: {last_error}). See {self._backend_log}."
        )

    def restart_backend(self):
        """Stop and restart just the backend process, then wait for readiness.

        Used by disruptive tests. No-op's cleanly when orchestration is off
        (there is no process we own to restart).
        """
        if not self.settings.orchestrate:
            raise StackError("Cannot restart backend: orchestration is disabled (ALMA_NO_ORCHESTRATION).")
        log.info("stack: restarting backend")
        self._stop_backend()
        self._start_backend()
        self._wait_ready()

    def _stop_backend(self):
        if self._backend is None:
            return
        self._backend.terminate()
        try:
            self._backend.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self._backend.kill()
            self._backend.wait(timeout=10)
        self._backend = None

    def down(self):
        if not self.settings.orchestrate:
            return
        log.info("stack: tearing down")
        self._stop_backend()
        try:
            self._run(self._compose("down", "-v", "--remove-orphans"), self._base_env(), "compose down -v")
        except StackError as exc:  # teardown must not mask test results
            log.warning("stack: teardown issue (ignored): %s", exc)


def _repo_reports_dir() -> Path:
    from alma_spei_tests.config import REPO_ROOT

    return REPO_ROOT / "reports"
