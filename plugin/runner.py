from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path


def shorten(text: str, max_chars: int = 4000) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    if len(value) <= max_chars:
        return value
    return f"{value[: max_chars - 40]}\n\n[truncated {len(value) - max_chars + 40} chars]"


def append_log(file: Path, lines) -> None:
    text = "\n".join(lines) if isinstance(lines, list) else str(lines)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as fh:
        fh.write(text)
        fh.write("\n")


def build_prompt(job: dict) -> str:
    lines = [
        f"你正在處理 {job.get('project') or Path(job['workspace_dir']).name} 專案。",
        f"工作目錄：{job['workspace_dir']}",
        "",
        "請先閱讀相關檔案，再進行最小必要修改。",
        "Hermes 只是派工，你是實際執行修改的 Codex CLI。",
        "",
        f"任務：{job['task']}",
        job.get("scope") and f"修改範圍：{job['scope']}" or "修改範圍：只做完成任務所需的最小修改。",
        job.get("rules") and f"額外規則：{job['rules']}" or "額外規則：不要 commit，除非任務明確要求。",
        job.get("run") and f"完成後請執行：{job['run']}" or "完成後如有可行測試，請執行最相關的最小測試。",
        job.get("report") and f"回報格式偏好：{job['report']}" or "回報格式：摘要 + diff + 測試結果。",
        "",
        "最後請用繁體中文回報，而且一定要包含：",
        "1. 修改檔案",
        "2. 修改摘要",
        "3. 測試結果",
        "4. 風險與後續建議",
        "5. 是否有 commit（若沒有就明說未 commit）",
    ]
    return "\n".join(lines)


def run_capture(command: list[str], cwd: str | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def git_info(workspace_dir: str) -> dict:
    inside = run_capture(["git", "rev-parse", "--is-inside-work-tree"], cwd=workspace_dir)
    if inside.returncode != 0 or "true" not in inside.stdout:
        return {"tracked": False, "modified_files": "", "diff_stat": ""}
    status = run_capture(["git", "status", "--short"], cwd=workspace_dir)
    diff = run_capture(["git", "diff", "--stat"], cwd=workspace_dir)
    return {
        "tracked": True,
        "modified_files": status.stdout.strip(),
        "diff_stat": diff.stdout.strip(),
    }


async def send_message(job: dict, text: str, delivery_logs: dict[str, Path]) -> None:
    from gateway.config import Platform, load_gateway_config
    from tools.send_message_tool import _send_to_platform

    platform_map = {
        "telegram": Platform.TELEGRAM,
        "discord": Platform.DISCORD,
        "slack": Platform.SLACK,
        "whatsapp": Platform.WHATSAPP,
        "signal": Platform.SIGNAL,
        "bluebubbles": Platform.BLUEBUBBLES,
        "qqbot": Platform.QQBOT,
        "matrix": Platform.MATRIX,
        "mattermost": Platform.MATTERMOST,
        "homeassistant": Platform.HOMEASSISTANT,
        "dingtalk": Platform.DINGTALK,
        "feishu": Platform.FEISHU,
        "wecom": Platform.WECOM,
        "wecom_callback": Platform.WECOM_CALLBACK,
        "weixin": Platform.WEIXIN,
        "email": Platform.EMAIL,
        "sms": Platform.SMS,
    }

    platform_name = str(job["platform"]).strip().lower()
    platform = platform_map.get(platform_name)
    if platform is None:
        raise RuntimeError(f"unsupported platform: {platform_name}")

    config = load_gateway_config()
    pconfig = config.platforms.get(platform)
    if not pconfig or not pconfig.enabled:
        raise RuntimeError(f"platform not configured or disabled: {platform_name}")

    result = await _send_to_platform(
        platform,
        pconfig,
        str(job["chat_id"]),
        text,
        thread_id=job.get("thread_id") or None,
        media_files=None,
    )
    if isinstance(result, dict) and result.get("success"):
        append_log(delivery_logs["ok"], [json.dumps({"message": shorten(text, 500), "result": result}, ensure_ascii=False)])
        return
    append_log(delivery_logs["err"], [json.dumps({"message": shorten(text, 500), "result": result}, ensure_ascii=False)])
    raise RuntimeError(f"delivery failed: {result}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: runner.py <job-file>", file=sys.stderr)
        return 1

    job_file = Path(sys.argv[1]).resolve()
    job = json.loads(job_file.read_text(encoding="utf-8"))

    job_id = job.get("job_id") or job_file.stem
    job_dir = job_file.parent
    prompt_file = job_dir / f"{job_id}.prompt.txt"
    last_message_file = job_dir / f"{job_id}.last-message.txt"
    stdout_file = job_dir / f"{job_id}.stdout.log"
    stderr_file = job_dir / f"{job_id}.stderr.log"
    delivery_logs = {
        "ok": job_dir / f"{job_id}.delivery.ok.log",
        "err": job_dir / f"{job_id}.delivery.err.log",
    }

    prompt = build_prompt(job)
    prompt_file.write_text(prompt + "\n", encoding="utf-8")

    try:
        asyncio.run(
            send_message(
                job,
                "\n".join(
                    [
                        "Codex 派工已開始。",
                        f"- job: {job_id}",
                        f"- workspace: {job['workspace_dir']}",
                        job.get("project") and f"- project: {job['project']}" or "",
                        job.get("scope") and f"- scope: {job['scope']}" or "",
                        "完成後我會把摘要、diff 與測試結果回傳到這個對話。",
                    ]
                ).strip(),
                delivery_logs,
            )
        )
    except Exception as exc:
        append_log(stderr_file, f"[dispatch-start-send-failed] {exc}")

    args = [
        job.get("codex_path") or "codex",
        "exec",
        "-C",
        job["workspace_dir"],
        "-s",
        job.get("sandbox") or "workspace-write",
        "--skip-git-repo-check",
        "--color",
        "never",
        "-c",
        "shell_environment_policy.inherit=all",
        "-o",
        str(last_message_file),
    ]
    if job.get("model"):
        args.extend(["-m", job["model"]])
    args.append(prompt)

    timeout_seconds = max(5, int(job.get("timeout_minutes") or 25)) * 60
    proc = subprocess.run(
        args,
        cwd=job["workspace_dir"],
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        env=os.environ.copy(),
    )
    stdout_file.write_text(proc.stdout or "", encoding="utf-8")
    stderr_file.write_text(proc.stderr or "", encoding="utf-8")

    try:
        last_message = last_message_file.read_text(encoding="utf-8")
    except Exception:
        last_message = ""

    git = git_info(job["workspace_dir"])
    summary = "\n".join(
        [
            f"Codex 派工結果：{'完成' if proc.returncode == 0 else '失敗'}",
            f"- job: {job_id}",
            f"- workspace: {job['workspace_dir']}",
            f"- exit: {proc.returncode}",
            git["tracked"]
            and f"- git modified: {len(git['modified_files'].splitlines()) if git['modified_files'] else 0} files"
            or "- git modified: unavailable (not a git repo)",
            "",
            "【Codex 最終摘要】",
            shorten(last_message or "(no final message captured)", 5000),
            git["modified_files"] and f"\n【修改檔案】\n{shorten(git['modified_files'], 2500)}" or "",
            git["diff_stat"] and f"\n【Diff 摘要】\n{shorten(git['diff_stat'], 2500)}" or "",
            proc.stderr.strip() and f"\n【stderr】\n{shorten(proc.stderr, 2500)}" or "",
        ]
    ).strip()

    try:
        asyncio.run(send_message(job, summary, delivery_logs))
    except Exception as exc:
        append_log(stderr_file, f"[dispatch-final-send-failed] {exc}")
        return 1 if proc.returncode == 0 else proc.returncode

    return proc.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        job_file = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
        if job_file and job_file.exists():
            job = json.loads(job_file.read_text(encoding="utf-8"))
            job_dir = job_file.parent
            append_log(job_dir / f"{job.get('job_id', job_file.stem)}.stderr.log", f"[dispatch-timeout] {exc}")
            try:
                asyncio.run(send_message(job, f"Codex 派工失敗：執行逾時 ({exc.timeout} 秒)", {"ok": job_dir / "delivery.ok.log", "err": job_dir / "delivery.err.log"}))
            except Exception:
                pass
        raise
