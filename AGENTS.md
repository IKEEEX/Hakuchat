# AGENTS.md

Small Python LLM tooling proof-of-concept ("llm-websearch-poc").

## Environment

- Python 3.14 virtualenv at `.venv` (created with `python3.14 -m venv .venv`).
- Activate: `source .venv/bin/activate` (or use `.venv/bin/python` / `.venv/bin/pip` directly).
- Dependency: `openai` (declared in `pyproject.toml`, **not yet installed** in `.venv`).
  - Install: `.venv/bin/pip install openai` (or `pip install -e .`).

## Current state (verified)

- Root files: `pyproject.toml`, `weather.py`. No package structure, no `src/` layout.
- `weather.py`: calls OpenAI-compatible chat completions with a `get_current_temperature` tool; only prints the requested function name/arguments — does not implement the tool itself.
- Env vars used by `weather.py` (no defaults, raise `KeyError` if missing): `NEMOTRON_BASE_URL`, `NEMOTRON_API_KEY`, `NEMOTRON_MODEL`.
- No tests, no lint/format/typecheck config, no CI workflows, no pre-commit, no git commits yet (repo is empty on `master`).
- Do not hardcode secrets; all credentials come from env vars.

## Planned architecture (per requirements; not yet implemented)

- Background Python server (Flask or stdlib `http.server`) serving `index.html` and a `POST /api/chat` endpoint.
- LLM called via `openai` library through OpenRouter with the same Nemotron model as `weather.py`.
- API key read from env var `OPENROUTER_API_KEY` — never in code or git history.
- One tool `web_search`: params `query` (string, required) and `max_results` (int, default 5).
- Search done via `curl` in Python `subprocess.run`; search endpoint: `https://html.duckduckgo.com/html/?q=<haku>` (general web search; may block automated queries if too many). Fallback chain when a source returns nothing or fails (e.g. DDG CAPTCHA): Finnish Wikipedia, then English Wikipedia, both via full-text search API (`https://<lang>.wikipedia.org/w/api.php?action=query&list=search&srsearch=<haku>&format=json`).
- Result parsed into a list of `{title, url}` and returned to the model as JSON.
- Tool-use loop: execute tool calls and re-call the model until a text response; max 5 rounds.
- Conversation history persists per browser session (supports follow-ups like "Etsi vielä suomenkielisiä").
- UI: single `index.html`, no frameworks — message list, text field, Lähetä button, Enter sends.
- UI shows if/which search the model used; links in answers are clickable.
- `README.md` documents installation and startup.
