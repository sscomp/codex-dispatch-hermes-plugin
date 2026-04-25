#!/usr/bin/env bash
set -euo pipefail

PROFILE_HOME="${1:-}"
if [ -z "$PROFILE_HOME" ]; then
  echo "Usage: install-profile.sh <hermes-profile-home> [options]" >&2
  exit 2
fi
if [ ! -d "$PROFILE_HOME" ]; then
  echo "Profile path not found: $PROFILE_HOME" >&2
  exit 2
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_DST="$PROFILE_HOME/plugins/codex-dispatch"
PLUGIN_SRC="$REPO_DIR/plugin"
CONFIG_DIR="$PROFILE_HOME/codex-dispatch"
CONFIG_FILE="$CONFIG_DIR/config.json"
REGISTRY_FILE="$CONFIG_DIR/codex-projects.json"
CODEX_PATH="$(command -v codex || true)"
if [ -z "$CODEX_PATH" ]; then
  CODEX_PATH="codex"
fi
DEFAULT_MODEL=""
DEFAULT_SANDBOX="workspace-write"
TIMEOUT_MINUTES="25"
ALLOWED_ROOTS=("$HOME")

shift
while [ "$#" -gt 0 ]; do
  case "$1" in
    --codex-path)
      CODEX_PATH="${2:-}"
      shift 2
      ;;
    --allowed-root)
      ALLOWED_ROOTS+=("${2:-}")
      shift 2
      ;;
    --default-model)
      DEFAULT_MODEL="${2:-}"
      shift 2
      ;;
    --default-sandbox)
      DEFAULT_SANDBOX="${2:-}"
      shift 2
      ;;
    --timeout-minutes)
      TIMEOUT_MINUTES="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$PROFILE_HOME/plugins" "$CONFIG_DIR"
rm -rf "$PLUGIN_DST"
cp -R "$PLUGIN_SRC" "$PLUGIN_DST"

python3 - "$PROFILE_HOME" "$CONFIG_FILE" "$REGISTRY_FILE" "$CODEX_PATH" "$DEFAULT_SANDBOX" "$DEFAULT_MODEL" "$TIMEOUT_MINUTES" "${ALLOWED_ROOTS[@]}" <<'PY'
import json
import sys
from pathlib import Path

profile_home = Path(sys.argv[1])
config_file = Path(sys.argv[2])
registry_file = Path(sys.argv[3])
codex_path = sys.argv[4]
default_sandbox = sys.argv[5]
default_model = sys.argv[6]
timeout_minutes = int(float(sys.argv[7]))
allowed_roots = list(dict.fromkeys(p for p in sys.argv[8:] if p))

config_payload = {
    "registry_path": str(registry_file),
    "job_dir": str(profile_home / "codex-dispatch" / "jobs"),
    "allowed_roots": allowed_roots,
    "codex_path": codex_path,
    "default_sandbox": default_sandbox,
    "default_model": default_model,
    "timeout_minutes": timeout_minutes,
}
config_file.write_text(json.dumps(config_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if not registry_file.exists():
    registry_file.write_text(
        json.dumps({"projects": {"ExampleRepo": "/Users/your-name/example-repo"}}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

yaml_path = profile_home / "config.yaml"
content = yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else ""
lines = content.splitlines()

def is_top_level(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not line.startswith((" ", "\t")) and ":" in stripped and not stripped.startswith("#")

plugins_idx = None
for idx, line in enumerate(lines):
    if line.strip() == "plugins:" and not line.startswith((" ", "\t")):
        plugins_idx = idx
        break

if plugins_idx is None:
    block = [
        "plugins:",
        "  enabled:",
        "    - codex-dispatch",
    ]
    new_content = content.rstrip()
    if new_content:
        new_content += "\n"
    new_content += "\n".join(block) + "\n"
    yaml_path.write_text(new_content, encoding="utf-8")
    raise SystemExit(0)

plugins_end = len(lines)
for idx in range(plugins_idx + 1, len(lines)):
    if is_top_level(lines[idx]):
        plugins_end = idx
        break

plugin_block = lines[plugins_idx:plugins_end]
if any(line.strip() == "- codex-dispatch" for line in plugin_block):
    yaml_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    raise SystemExit(0)

enabled_idx = None
for idx, line in enumerate(plugin_block):
    if line.strip() == "enabled:" and line.startswith("  "):
        enabled_idx = idx
        break

if enabled_idx is None:
    insertion = ["  enabled:", "    - codex-dispatch"]
    updated_block = plugin_block + insertion
else:
    insert_at = len(plugin_block)
    for idx in range(enabled_idx + 1, len(plugin_block)):
        line = plugin_block[idx]
        if line.startswith("  ") and not line.startswith("    "):
            insert_at = idx
            break
    updated_block = plugin_block[:insert_at] + ["    - codex-dispatch"] + plugin_block[insert_at:]

updated_lines = lines[:plugins_idx] + updated_block + lines[plugins_end:]
yaml_path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")
PY

echo "Installed Hermes Codex Dispatch into: $PROFILE_HOME"
echo "  plugin: $PLUGIN_DST"
echo "  config: $CONFIG_FILE"
echo "  projects: $REGISTRY_FILE"
echo "Next step: restart the Hermes gateway, then test /codex-projects."
