# Codex Runtime Notes

These notes describe the environment Codex Desktop usually sees for this repository. They are
not project architecture rules; they are practical operating notes so future Codex sessions do
not waste time rediscovering the host boundary.

## Host / Shell

- Codex runs commands through **PowerShell on Windows**, with the repository mounted by UNC:
  `\\wsl.localhost\Debian\home\yasiu\story-forge`.
- The real development environment is **WSL Debian**. Claude Code may be running directly in
  WSL and can use normal Linux commands there; Codex Desktop may not have that same shell access.
- Do not assume a PowerShell command can execute inside WSL. If WSL access is needed, ask the
  user or use available GitHub/local connector evidence instead of guessing.

## Known Friction

- PowerShell sandbox setup can fail before any command starts on this UNC workspace. When that
  happens, local command output is unavailable even for simple reads.
- Windows/UNC views of a WSL checkout can report misleading filemode or symlink differences.
  Before treating those as review findings, verify canonical git state with `git ls-files -s`
  and `git status` from WSL, or avoid reporting them.
- The agent must never read, create, or edit `.env` or `backend/.env`; only `.env.example`
  templates are agent-editable.

## Review Fallback

When local shell access fails during a PR review:

- Use the GitHub connector to fetch PR metadata, changed files, diffs, comments, and branch files.
- Treat GitHub branch contents as review evidence, but say clearly if a check required local
  runtime state and could not be performed.
- For file/line findings, cite the PR branch path and line number from fetched files or diff
  hunks.

## Editing Guidance

- Prefer `apply_patch` for small repo edits.
- Keep Codex-specific runtime notes here; keep durable project/process rules in `AGENTS.md`,
  `docs/PLAN_*.md`, the spec, ADRs, or directory-level `AGENTS.md` as appropriate.
