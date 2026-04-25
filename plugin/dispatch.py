from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

from .shared import (
    COMMAND_USAGE,
    format_projects,
    load_dispatch_config,
    load_registry,
    parse_structured_task,
    resolve_workspace,
    summarize_request,
)

logger = logging.getLogger(__name__)


def _current_target() -> dict[str, str]:
    try:
        from gateway.session_context import get_session_env
    except Exception as exc:
        raise RuntimeError(f"gateway session context unavailable: {exc}") from exc

    platform = get_session_env("HERMES_SESSION_PLATFORM", "").strip().lower()
    chat_id = get_session_env("HERMES_SESSION_CHAT_ID", "").strip()
    thread_id = get_session_env("HERMES_SESSION_THREAD_ID", "").strip()
    user_id = get_session_env("HERMES_SESSION_USER_ID", "").strip()
    user_name = get_session_env("HERMES_SESSION_USER_NAME", "").strip()

    if not platform or not chat_id:
        raise RuntimeError("this command currently works only in Hermes gateway sessions")

    return {
        "platform": platform,
        "chat_id": chat_id,
        "thread_id": thread_id,
        "user_id": user_id,
        "user_name": user_name,
    }


def _write_job_file(job_dir: Path, payload: dict) -> tuple[str, Path]:
    job_dir.mkdir(parents=True, exist_ok=True)
    job_id = f"codex-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}-{uuid.uuid4().hex[:8]}"
    path = job_dir / f"{job_id}.json"
    path.write_text(json.dumps({"job_id": job_id, **payload}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return job_id, path


def _spawn_runner(job_file: Path, hermes_home: Path) -> None:
    runner = Path(__file__).with_name("runner.py")
    env = os.environ.copy()
    env["HERMES_HOME"] = str(hermes_home)
    subprocess.Popen(
        [sys.executable, str(runner), str(job_file)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )


def _handle_codex_projects(_raw_args: str) -> str:
    cfg = load_dispatch_config()
    registry = load_registry(Path(cfg["registry_path"]))
    return format_projects(registry, cfg["registry_path"])


def _handle_codex(raw_args: str) -> str:
    raw = (raw_args or "").strip()
    if not raw:
        return COMMAND_USAGE

    spec = parse_structured_task(raw)
    if not spec["task"].strip():
        return f"缺少 /task\n\n{COMMAND_USAGE}"

    try:
        target = _current_target()
        cfg = load_dispatch_config()
        registry = load_registry(Path(cfg["registry_path"]))
        workspace_dir = resolve_workspace(spec, registry, cfg["allowed_roots"])
        hermes_home_raw = os.environ.get("HERMES_HOME", "").strip()
        if not hermes_home_raw:
            raise RuntimeError("missing HERMES_HOME")
        hermes_home = Path(hermes_home_raw).expanduser()

        payload = {
            "platform": target["platform"],
            "chat_id": target["chat_id"],
            "thread_id": target["thread_id"] or None,
            "user_id": target["user_id"],
            "user_name": target["user_name"],
            "workspace_dir": workspace_dir,
            "project": spec["project"].strip(),
            "task": spec["task"].strip(),
            "scope": spec["scope"].strip(),
            "rules": spec["rules"].strip(),
            "run": spec["run"].strip(),
            "report": spec["report"].strip(),
            "codex_path": cfg["codex_path"],
            "sandbox": cfg["default_sandbox"],
            "model": cfg["default_model"],
            "timeout_minutes": cfg["timeout_minutes"],
            "requested_at": datetime.now().isoformat(),
            "hermes_home": str(hermes_home),
        }
        job_id, job_file = _write_job_file(Path(cfg["job_dir"]), payload)
        _spawn_runner(job_file, hermes_home)
        return f"{summarize_request(spec, workspace_dir)}\n- job: {job_id}"
    except Exception as exc:
        logger.debug("codex dispatch creation failed", exc_info=True)
        return f"Codex 派工建立失敗：{exc}"


def register(ctx):
    ctx.register_command(
        "codex",
        handler=_handle_codex,
        description="Dispatch a structured coding task to a background Codex runner.",
    )
    ctx.register_command(
        "codex-projects",
        handler=_handle_codex_projects,
        description="List registered Codex project aliases.",
    )
    ctx.register_command(
        "codex_projects",
        handler=_handle_codex_projects,
        description="List registered Codex project aliases.",
    )
