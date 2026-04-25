# Troubleshooting

## `/codex` says it only works in gateway sessions

That means Hermes could not detect `HERMES_SESSION_PLATFORM` and `HERMES_SESSION_CHAT_ID`.
Use it from Telegram, Discord, Slack, or another Hermes gateway chat.

## `/codex-projects` is empty

Edit:

- `<HERMES_HOME>/codex-dispatch/codex-projects.json`

## Workspace not allowed

Update:

- `<HERMES_HOME>/codex-dispatch/config.json`

and add the target path under `allowed_roots`.

## No final result message returned

Check logs under:

- `<HERMES_HOME>/codex-dispatch/jobs/`

Typical causes:

- `codex` command not found
- gateway platform is not configured for Hermes send_message delivery
- Codex timed out before producing a final result

