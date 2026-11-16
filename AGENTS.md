# AGENTS.md

Small Python LLM tooling proof-of-concept ("llm-websearch-poc"): a local web chat
where an LLM can call a `web_search` tool.

## Environment

- Python 3.14 virtualenv at `.venv` (created with `python3.14 -m venv .venv`).
- Activate: `source .venv/bin/activate` (or use `.venv/bin/python` / `.venv/bin/pip` directly).
- Dependencies (declared in `pyproject.toml`): `openai`, `flask`. Install: `pip install -e .`
  (`uv.lock` also exists).

## Files

- `search.py`: `web_search(query, max_results)` via `curl` in `subprocess.run`.
  Sources in order: DuckDuckGo HTML (`https://html.duckduckgo.com/html/?q=<haku>`),
  then Finnish Wikipedia, then English Wikipedia (full-text search API
  `https://<lang>.wikipedia.org/w/api.php?action=query&list=search&srsearch=<haku>&format=json`).
  Next source is tried when one fails or returns nothing (e.g. DDG CAPTCHA).
  Returns a list of `{title, url}`. Runnable: `python search.py "hakusana" [n]`.
- `chat_core.py`: OpenAI library via OpenRouter; tool `web_search` (`query` string
  required, `max_results` int default 5); tool-use loop max 5 rounds, then a text
  answer is forced. Runnable: `python chat_core.py ["kysymys"]`.
- `app.py`: Flask server — serves `index.html`, `POST /api/chat`
  (`{session_id, message}` → `{reply, searches}`), `POST /api/reset`.
  Conversation history kept in memory per browser session (`sessionStorage` id),
  so follow-ups like "Etsi vielä suomenkielisiä" work.
- `index.html`: no frameworks — message list, text field, Lähetä button, Enter sends,
  shows which search/source was used, links are clickable.
- `weather.py`: original tool-calling demo (prints requested tool call only).
- `README.md`: install and startup instructions (Finnish).
- `PROMPTS.md`: manual test prompts with expected results (Finnish).
- No tests, lint config or CI.

## Env vars

- `OPENROUTER_API_KEY` (required; `NEMOTRON_API_KEY` accepted as fallback).
- `NEMOTRON_MODEL` (required), `NEMOTRON_BASE_URL` (default `https://openrouter.ai/api/v1`).
- `PORT` (default 5000).

## Security requirements (must hold for all changes)

The model decides what is searched and results come from unknown web pages —
treat both as untrusted input.

| Risk | Required protection | Where |
|---|---|---|
| Command injection (e.g. query `x; rm -rf ~`) | `subprocess.run([...])` with a list, never `shell=True`; query URL-encoded (`urllib.parse.quote`/`quote_plus`) | `search.py` `_curl`, `search_*` |
| Prompt injection (result text instructs the model) | Return only title + URL (no snippets/page content); system prompt states results are data, not instructions | `search.py` `_sanitize`, `chat_core.py` `SYSTEM_PROMPT` |
| Hanging | curl `--max-time 10` (+ subprocess timeout); tool loop max 5 rounds; LLM client timeout | `search.py` `CURL_TIMEOUT`, `chat_core.py` `MAX_ROUNDS`, `LLM_TIMEOUT` |
| Oversized response | Result count capped (`MAX_RESULTS_LIMIT` = 10), title/URL length capped; user message max 4000 chars | `search.py`, `app.py` `MAX_MESSAGE_LEN` |
| API key leak | Key only in env var, never in code or git history; `.env`, `.venv`, `__pycache__` in `.gitignore` | `.gitignore` |
| Open server (others use your key) | Server binds only to `127.0.0.1`, `debug=False` | `app.py` |
| XSS via model/web text | UI builds DOM with `textContent`/`createElement`, never `innerHTML`; links only `http(s)`, `rel="noopener noreferrer"` | `index.html` `renderText` |
