"""LLM chat with a web_search tool (OpenAI library via OpenRouter)."""

import json
import os
import sys
from datetime import datetime

import openai
from openai import OpenAI

import search

MAX_ROUNDS = 5

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Searches the web (DuckDuckGo, falling back to Finnish and English "
            "Wikipedia) and returns a list of results with title and url."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query, e.g. WSL2 docker",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}

SYSTEM_PROMPT = (
    "Olet avulias assistentti. Käytä web_search-työkalua, kun kysymys koskee "
    "ajankohtaista tietoa tai asioita, joista et ole varma. Kerro lähteet "
    "linkkeinä muodossa [otsikko](url). Vastaa käyttäjän kielellä."
)


def make_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("NEMOTRON_API_KEY")
    if not api_key:
        raise RuntimeError("Aseta ympäristömuuttuja OPENROUTER_API_KEY")
    return OpenAI(
        base_url=os.environ.get("NEMOTRON_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=api_key,
    )


def get_model() -> str:
    return os.environ["NEMOTRON_MODEL"]


def execute_tool_call(tool_call) -> tuple[str, dict]:
    """Run one tool call. Returns (content for the tool message, log entry)."""
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError:
        args = {}

    if name != "web_search" or not args.get("query"):
        log = {"tool": name, "arguments": args, "error": "invalid tool call"}
        print(f"[työkalu] virheellinen kutsu: {name}({tool_call.function.arguments})", file=sys.stderr)
        return json.dumps({"error": "unknown tool or missing query"}), log

    query = str(args["query"])
    max_results = args.get("max_results", 5)
    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = 5

    print(f"[työkalu] web_search(query={query!r}, max_results={max_results})", file=sys.stderr)
    source, results = search.web_search_with_source(query, max_results)
    print(f"[työkalu]   -> {len(results)} tulosta lähteestä {source or '-'}", file=sys.stderr)

    log = {"query": query, "max_results": max_results, "source": source, "count": len(results)}
    return json.dumps(results, ensure_ascii=False), log


def _assistant_message(msg) -> dict:
    """Convert an SDK message with tool calls into a plain dict for history."""
    return {
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ],
    }


def chat(messages: list[dict], client: OpenAI | None = None, model: str | None = None,
         max_rounds: int = MAX_ROUNDS) -> tuple[str, list[dict]]:
    """Run the tool-use loop.

    `messages` is the conversation history (user/assistant/tool dicts, without the
    system prompt). It is extended in place with the assistant/tool messages
    produced, so the caller can keep it for follow-up questions.
    Returns (final text reply, list of searches performed).
    """
    client = client or make_client()
    model = model or get_model()
    searches: list[dict] = []

    for round_no in range(max_rounds + 1):
        last_round = round_no == max_rounds
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            tools=[WEB_SEARCH_TOOL],
            # After max_rounds tool rounds, force a text answer.
            tool_choice="none" if last_round else "auto",
        )
        msg = response.choices[0].message

        if not msg.tool_calls or last_round:
            reply = msg.content or ""
            messages.append({"role": "assistant", "content": reply})
            return reply, searches

        messages.append(_assistant_message(msg))
        for tool_call in msg.tool_calls:
            content, log = execute_tool_call(tool_call)
            searches.append(log)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": content})

    raise AssertionError("unreachable")


def describe_api_error(exc: Exception) -> str:
    """Short, user-friendly description of an LLM API error."""
    if isinstance(exc, openai.RateLimitError):
        msg = "mallin käyttöraja täynnä (429)."
        reset = exc.response.headers.get("x-ratelimit-reset")
        if reset and reset.isdigit():
            when = datetime.fromtimestamp(int(reset) / 1000).strftime("%d.%m. klo %H:%M")
            msg += f" Raja nollautuu {when}."
        return msg
    if isinstance(exc, openai.AuthenticationError):
        return "API-avain ei kelpaa (401). Tarkista OPENROUTER_API_KEY."
    if isinstance(exc, openai.APIStatusError):
        return f"mallin API palautti virheen {exc.status_code}: {exc.message}"
    if isinstance(exc, openai.APIConnectionError):
        return "yhteys mallin API:in epäonnistui."
    return str(exc)


if __name__ == "__main__":
    # python chat_core.py "kysymys"   -> yksi kysymys
    # python chat_core.py             -> keskustelu (tyhjä rivi / Ctrl-D lopettaa)
    history: list[dict] = []
    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else None

    def ask(question: str) -> None:
        history.append({"role": "user", "content": question})
        try:
            reply, _ = chat(history)
        except Exception as exc:
            history.pop()
            sys.exit(f"Virhe: {describe_api_error(exc)}")
        print(f"\nMalli: {reply}\n")

    if questions:
        ask(questions[0])
    else:
        while True:
            try:
                q = input("Sinä: ").strip()
            except EOFError:
                break
            if not q:
                break
            ask(q)
