from __future__ import annotations

import json
import os
from pathlib import Path

COMMAND_USAGE = "\n".join(
    [
        "用法：",
        "/codex",
        "/project <專案名稱>",
        "/workspace </Users/...>",
        "/task <要做的事>",
        "/scope <限制修改範圍>",
        "/rules <額外規則>",
        "/run <要跑的測試或命令>",
        "/report <回報格式>",
        "",
        "至少需要：",
        "- /task",
        "- 以及 /project 或 /workspace 其中之一",
    ]
)


def _default_config_path() -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
    return hermes_home / "codex-dispatch" / "config.json"


def load_dispatch_config() -> dict:
    config_path = _default_config_path()
    if not config_path.exists():
        raise RuntimeError(f"dispatch config not found: {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    data.setdefault("registry_path", str(config_path.parent / "codex-projects.json"))
    data.setdefault("job_dir", str(config_path.parent / "jobs"))
    data.setdefault("allowed_roots", [str(Path.home())])
    data.setdefault("codex_path", "codex")
    data.setdefault("default_sandbox", "workspace-write")
    data.setdefault("default_model", "")
    data.setdefault("timeout_minutes", 25)
    return data


def parse_structured_task(raw: str) -> dict[str, str]:
    lines = str(raw or "").replace("\r\n", "\n").split("\n")
    fields: dict[str, str] = {}
    current_key: str | None = None

    for line in lines:
        trimmed = line.strip()
        if trimmed.startswith("/"):
            parts = trimmed.split(None, 1)
            current_key = parts[0].lstrip("/").lower()
            fields[current_key] = parts[1].strip() if len(parts) > 1 else ""
            continue
        if current_key and trimmed:
            fields[current_key] = f"{fields[current_key]}\n{trimmed}".strip()

    return {
        "project": fields.get("project", ""),
        "workspace": fields.get("workspace", ""),
        "task": fields.get("task", ""),
        "scope": fields.get("scope", ""),
        "rules": fields.get("rules", ""),
        "run": fields.get("run", ""),
        "report": fields.get("report", ""),
    }


def load_registry(file: Path) -> dict:
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    projects = payload.get("projects")
    return projects if isinstance(projects, dict) else {}


def _is_under_allowed_roots(candidate: Path, allowed_roots: list[str]) -> bool:
    resolved_candidate = candidate.resolve()
    for root in allowed_roots:
        resolved_root = Path(root).expanduser().resolve()
        if resolved_candidate == resolved_root or str(resolved_candidate).startswith(f"{resolved_root}{os.sep}"):
            return True
    return False


def resolve_workspace(spec: dict[str, str], registry: dict, allowed_roots: list[str]) -> str:
    explicit_workspace = spec["workspace"].strip()
    if explicit_workspace:
        resolved = Path(explicit_workspace).expanduser().resolve()
        if not _is_under_allowed_roots(resolved, allowed_roots):
            raise RuntimeError(f"workspace 不在允許範圍內：{resolved}")
        if not resolved.is_dir():
            raise RuntimeError(f"workspace 不存在：{resolved}")
        return str(resolved)

    project_name = spec["project"].strip()
    if not project_name:
        raise RuntimeError("需要提供 /project 或 /workspace")

    mapped = registry.get(project_name)
    if not isinstance(mapped, str) or not mapped.strip():
        raise RuntimeError(f"找不到 project 映射：{project_name}")

    resolved = Path(mapped).expanduser().resolve()
    if not _is_under_allowed_roots(resolved, allowed_roots):
        raise RuntimeError(f"project 映射超出允許範圍：{resolved}")
    if not resolved.is_dir():
        raise RuntimeError(f"project 路徑不存在：{resolved}")
    return str(resolved)


def summarize_request(spec: dict[str, str], workspace_dir: str) -> str:
    lines = [
        "已建立 Codex 派工。",
        f"- workspace: {workspace_dir}",
    ]
    for key in ("project", "task", "scope", "rules", "run", "report"):
        value = spec.get(key, "").strip()
        if value:
            lines.append(f"- {key}: {value}")
    lines.extend(["", "Codex 會在背景執行，完成後把摘要、diff 與測試結果回傳到這個對話。"])
    return "\n".join(lines)


def format_projects(registry: dict, registry_path: str) -> str:
    entries = sorted(registry.items(), key=lambda item: item[0].lower())
    if not entries:
        return "\n".join(
            [
                "目前 project registry 是空的。",
                "可直接改用：/workspace /Users/...",
                f"若要建立 project 別名，請編輯：{registry_path}",
            ]
        )
    return "\n".join(["目前可用的 project 映射：", *[f"- {name} -> {target}" for name, target in entries]])

