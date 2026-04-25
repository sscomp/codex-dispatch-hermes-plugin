# codex-dispatch-hermes-plugin

Hermes 原生的 Codex 派工外掛，提供 `/codex` 與 `/codex-projects` 指令。

這個 repo 是給 Hermes-first 系統使用的版本，安裝後會以一般 Hermes plugin
方式掛到 `<HERMES_HOME>/plugins/codex-dispatch`，並透過 Hermes 自己的訊息
通道回傳開始與完成通知。

It installs as a normal Hermes plugin under `<HERMES_HOME>/plugins/codex-dispatch`
and exposes:

- `/codex`
- `/codex-projects`

Unlike the OpenClaw version, this package does not depend on `.openclaw`,
`openclaw.json`, or `openclaw message send`.

Version: `0.1.0`

## Recommended install

```bash
/Users/sscomp/codex-dispatch-hermes-plugin/scripts/install-profile.sh /Users/sscomp/.hermes/profiles/n2
```

With explicit Codex binary:

```bash
/Users/sscomp/codex-dispatch-hermes-plugin/scripts/install-profile.sh \
  /Users/sscomp/.hermes/profiles/n2 \
  --codex-path /Users/sscomp/.local/bin/codex
```

## What the installer does

- copies the plugin into `<HERMES_HOME>/plugins/codex-dispatch`
- creates `<HERMES_HOME>/codex-dispatch/config.json`
- creates `<HERMES_HOME>/codex-dispatch/codex-projects.json` if missing
- enables the plugin in `<HERMES_HOME>/config.yaml`

## Current scope

This version is optimized for Hermes gateway use.

- It captures the current Hermes gateway session target from Hermes session context.
- It starts a detached background runner.
- It sends start and finish messages back through Hermes' own platform delivery stack.

## Commands

### `/codex`

```text
/codex
/project MyRepo
/task 幫我修正登入 API timeout
/scope 只改 src/auth 與 tests/auth
/rules 不要 commit
/run pytest tests/auth -q
/report 摘要 + diff + 測試結果
```

You can also use `/workspace`:

```text
/codex
/workspace /Users/sscomp/my-repo
/task 幫我補上 release note
```

### `/codex-projects`

List configured `/project` aliases.

## Config files

- Plugin config: `<HERMES_HOME>/codex-dispatch/config.json`
- Project aliases: `<HERMES_HOME>/codex-dispatch/codex-projects.json`

Template:

- [templates/config.json](/Users/sscomp/codex-dispatch-hermes-plugin/templates/config.json)
- [templates/codex-projects.json](/Users/sscomp/codex-dispatch-hermes-plugin/templates/codex-projects.json)

## Notes

- This plugin currently targets gateway-backed Hermes sessions. If you use `/codex`
  from a plain terminal-only Hermes chat, the plugin will refuse background
  dispatch because there is no messaging target to send the final result to.
- The plugin is intentionally separate from the OpenClaw package so Hermes-first
  installs stay clean.

More details:

- [docs/quickstart.md](/Users/sscomp/codex-dispatch-hermes-plugin/docs/quickstart.md)
- [docs/troubleshooting.md](/Users/sscomp/codex-dispatch-hermes-plugin/docs/troubleshooting.md)
