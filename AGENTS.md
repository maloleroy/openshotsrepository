## Tools
- Use `uv add ...` to install Python packages.
- Use `uv run src/...` to run scripts.
- Run `uv run python` to execute Python code directly. Don't ever call the OS's Python.
- Run `uv run pytest` to run tests
- Run `uv run pyright src tests` to lint/check code
- You have access to the GitHub CLI `gh`

## Git and production

- Commit atomically: your work process should be easy to understand by readint commit titles.
- When handling a GitHub issue, use branch `<issue number>-<title>`; one issue = one branch = one PR = one merge to `main`, without squash or rebase. Use `gh issue view <number>` for issue details.
- Pushes to `main` deploy through GitHub Actions. Production host: `ssh debian@malo.cs-campus.fr`. Review `README.md` and `deploy/rollback.sh` before recovery work; preserve the live database.

## Code style

- Never use `getattr`, `hasattr`, `__dict__`, `dir`, or `try/except` (except `KeyboardInterrupt` while showing plots or awaiting text input).
- Keep imports out of `if` blocks. Imports at the top of functions are fine when used only there. Do not use `from __future__ import annotations`.
- Annotate variables whose types cannot be inferred by linting. Generally, prefer dataclasses and functions to OOP.
