"""Web search via curl: DuckDuckGo -> Finnish Wikipedia -> English Wikipedia."""

import json
import subprocess
import sys
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, quote_plus, urlparse

CURL_TIMEOUT = 10  # seconds
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) llm-websearch-poc/0.1"


def _curl(url: str, timeout: int = CURL_TIMEOUT) -> str:
    """Fetch url with curl and return the body. Raises RuntimeError on failure."""
    cmd = [
        "curl",
        "--silent",
        "--show-error",
        "--location",
        "--max-time", str(timeout),
        "--user-agent", USER_AGENT,
        url,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout + 5,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


# --- DuckDuckGo ---------------------------------------------------------------

class _DuckDuckGoParser(HTMLParser):
    """Collects <a class="result__a" href="...">title</a> links."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        if "result__a" in (attrs.get("class") or "").split():
            self._href = attrs.get("href") or ""
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            title = " ".join("".join(self._text).split())
            url = _unwrap_ddg_url(self._href)
            if title and url:
                self.results.append({"title": title, "url": url})
            self._href = None
            self._text = []


def _unwrap_ddg_url(href: str) -> str:
    """DuckDuckGo wraps links as //duckduckgo.com/l/?uddg=<real url>."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return target[0]
    return href if parsed.scheme in ("http", "https") else ""


def parse_duckduckgo(html: str, max_results: int) -> list[dict]:
    parser = _DuckDuckGoParser()
    parser.feed(html)
    results = [r for r in parser.results if "duckduckgo.com/y.js" not in r["url"]]  # skip ads
    return results[:max_results]


def search_duckduckgo(query: str, max_results: int) -> list[dict]:
    html = _curl("https://html.duckduckgo.com/html/?q=" + quote_plus(query))
    if "anomaly-modal" in html:
        raise RuntimeError("DuckDuckGo blocked the automated query (CAPTCHA)")
    return parse_duckduckgo(html, max_results)


# --- Wikipedia ----------------------------------------------------------------

def parse_wikipedia(json_text: str, max_results: int, lang: str = "fi") -> list[dict]:
    """Full-text search format: {"query": {"search": [{"title": ...}, ...]}}."""
    hits = json.loads(json_text).get("query", {}).get("search", [])
    return [
        {
            "title": hit["title"],
            "url": f"https://{lang}.wikipedia.org/wiki/"
            + quote(hit["title"].replace(" ", "_")),
        }
        for hit in hits[:max_results]
    ]


def search_wikipedia(query: str, max_results: int, lang: str = "fi") -> list[dict]:
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={quote_plus(query)}&srlimit={max_results}&srprop=&format=json"
    )
    return parse_wikipedia(_curl(url), max_results, lang)


# --- Public API ---------------------------------------------------------------

SOURCES = [
    ("duckduckgo", search_duckduckgo),
    ("wikipedia-fi", lambda q, n: search_wikipedia(q, n, "fi")),
    ("wikipedia-en", lambda q, n: search_wikipedia(q, n, "en")),
]


def web_search_with_source(query: str, max_results: int = 5) -> tuple[str | None, list[dict]]:
    """Try each source in order; return (source_name, results) from the first non-empty one."""
    max_results = max(1, min(int(max_results), 20))
    for name, fn in SOURCES:
        try:
            results = fn(query, max_results)
        except Exception as exc:  # network/parse errors -> try next source
            print(f"[search] {name} failed: {exc}", file=sys.stderr)
            continue
        if results:
            return name, results
    return None, []


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Return a list of {"title": ..., "url": ...} dicts."""
    return web_search_with_source(query, max_results)[1]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Käyttö: python search.py "hakusana" [max_results]')
    q = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    source, results = web_search_with_source(q, n)
    print(f"Lähde: {source or '-'}", file=sys.stderr)
    print(json.dumps(results, ensure_ascii=False, indent=2))
