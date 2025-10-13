# ai/tools/web_tools.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import json, re, time, os, random
import httpx
from bs4 import BeautifulSoup

# A rotating UA pool to reduce heuristics/rate limiting from free providers.
_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]
def _ua() -> str:
    return random.choice(_UA_POOL)

def _clean_text(txt: str, limit: int = 1800) -> str:
    return re.sub(r"\s+", " ", (txt or "")).strip()[:limit]

# ---------------------------
# SEARCH PROVIDERS (free)
# ---------------------------

def _wikipedia_best_guess(q: str) -> List[Dict[str, str]]:
    """
    1) Try Wikipedia "best match" redirect:
       https://en.wikipedia.org/wiki/Special:Search?search=<q>&go=1&ns0=1
       If it resolves to /wiki/<Title>, return that as a single result.
    """
    url = "https://en.wikipedia.org/wiki/Special:Search"
    headers = {"User-Agent": _ua(), "Accept": "text/html,application/xhtml+xml"}
    params = {"search": q, "go": "1", "ns0": "1"}  # ns0=main article namespace
    with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        # If we were redirected to a concrete article, take it
        final = str(r.url)
        if "/wiki/" in final and "Special:Search" not in final:
            title = final.rsplit("/wiki/", 1)[-1].replace("_", " ")
            return [{"title": title, "url": final, "snippet": ""}]
    return []

def _wikipedia_rest_search(q: str, k: int = 5) -> List[Dict[str, str]]:
    """
    2) Wikipedia REST page search (good relevance, stable).
       https://en.wikipedia.org/w/rest.php/v1/search/page?q=<q>&limit=<k>
    """
    url = "https://en.wikipedia.org/w/rest.php/v1/search/page"
    headers = {"User-Agent": _ua(), "Accept": "application/json"}
    with httpx.Client(headers=headers, timeout=10.0) as client:
        r = client.get(url, params={"q": q, "limit": max(1, k)})
        r.raise_for_status()
        data = r.json()
        pages = data.get("pages", []) if isinstance(data, dict) else []
        out: List[Dict[str, str]] = []
        for it in pages[:k]:
            key = it.get("key") or it.get("title") or ""
            if not key:
                continue
            title = it.get("title", key)
            snippet = ""
            # REST often provides a 'description' or 'excerpt'
            if "description" in it and isinstance(it["description"], str):
                snippet = it["description"]
            elif "excerpt" in it and isinstance(it["excerpt"], str):
                snippet = BeautifulSoup(it["excerpt"], "html.parser").get_text(" ")
            out.append({
                "title": title,
                "url": f"https://en.wikipedia.org/wiki/{key}",
                "snippet": snippet,
            })
        return out

def _duckduckgo_html_search(q: str, k: int = 5, backoff_base: float = 1.1) -> List[Dict[str, str]]:
    """
    3) Fallback: light HTML DuckDuckGo search endpoint (no external lib).
       Endpoint: https://duckduckgo.com/html/
       We parse result links and return top-k.
       Gentle backoff to reduce "202 Ratelimit".
    """
    headers = {"User-Agent": _ua(), "Accept": "text/html"}
    last_err: Optional[str] = None
    for attempt in range(4):  # a few polite retries
        try:
            with httpx.Client(headers=headers, timeout=10.0) as client:
                r = client.get("https://duckduckgo.com/html/", params={"q": q})
                if r.status_code == 202:
                    last_err = "202 Ratelimit"
                    time.sleep(backoff_base ** (attempt + 1))
                    continue
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                links: List[Dict[str, str]] = []
                # Two common patterns for result links on /html:
                for a in soup.select("a.result__a, a.result__url"):
                    href = a.get("href") or ""
                    title = a.get_text(strip=True)
                    if not href.startswith(("http://", "https://")):
                        continue
                    if title and href:
                        links.append({"title": title, "url": href, "snippet": ""})
                    if len(links) >= k:
                        break
                if links:
                    return links
                # No links -> treat as failure to try backoff
                last_err = "no_results"
                time.sleep(backoff_base ** (attempt + 1))
        except Exception as e:
            last_err = str(e)
            time.sleep(backoff_base ** (attempt + 1))
    raise RuntimeError(f"duckduckgo_failed:{last_err or 'unknown'}")

# ---------------------------
# TOOLS
# ---------------------------

def tool_web_search(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    web.search:
      1) Wikipedia best-guess redirect (usually jumps to the exact article)
      2) Wikipedia REST page search
      3) DDG HTML fallback (reduced rate-limit issues vs API)
    args:
      q: str (query)
      k: int (top-k, default 5)
    """
    q = (args or {}).get("q") or ""
    k = int((args or {}).get("k") or 5)
    if not q:
        return {"ok": False, "error": "missing_query", "hint": "Provide args.q"}

    # Provider 1: Wikipedia best-guess (fast path to exact page)
    try:
        links = _wikipedia_best_guess(q)
        if links:
            return {"ok": True, "query": q, "k": len(links), "links": links, "provider": "wikipedia_best_guess"}
    except Exception as e:
        wiki_best_err = f"wikipedia_best_guess_failed:{e}"
    else:
        wiki_best_err = None

    # Provider 2: Wikipedia REST page search
    try:
        links = _wikipedia_rest_search(q, k)
        if links:
            return {"ok": True, "query": q, "k": min(k, len(links)), "links": links, "provider": "wikipedia_rest"}
    except Exception as e:
        wiki_rest_err = f"wikipedia_rest_failed:{e}"
    else:
        wiki_rest_err = None

    # Provider 3: DuckDuckGo HTML (reduced rate-limit issues)
    try:
        links = _duckduckgo_html_search(q, k)
        if links:
            return {"ok": True, "query": q, "k": min(k, len(links)), "links": links, "provider": "duckduckgo_html"}
    except Exception as e:
        ddg_err = str(e)

    return {
        "ok": False,
        "error": "all_free_providers_failed",
        "query": q,
        "k": k,
        "wikipedia_best_guess": {"ok": wiki_best_err is None, "error": wiki_best_err},
        "wikipedia_rest": {"ok": wiki_rest_err is None, "error": wiki_rest_err},
        "duckduckgo_html": {"ok": False, "error": ddg_err},
    }

def tool_web_get(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    web.get: fetch a URL and extract readable text (title + main content).
    args:
      url: str
      timeout: float (seconds, default 15)
    """
    url = (args or {}).get("url") or ""
    timeout = float((args or {}).get("timeout") or 15)
    if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "invalid_url", "hint": "Provide args.url starting with http(s)://", "url": url}

    headers = {
        "User-Agent": _ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(follow_redirects=True, headers=headers, timeout=timeout) as client:
            resp = client.get(url)
            if resp.status_code >= 400:
                return {"ok": False, "error": f"http_{resp.status_code}", "url": url}

            soup = BeautifulSoup(resp.text, "html.parser")
            title = (soup.title.string.strip() if soup.title and soup.title.string else "")[:140]
            for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form"]):
                tag.decompose()
            text = _clean_text(soup.get_text(separator=" "))
            return {"ok": True, "url": str(resp.url), "title": title, "text": text}
    except Exception as e:
        return {"ok": False, "error": f"fetch_failed:{e}", "url": url}

# ---------------------------
# Tool specs for registry
# ---------------------------

def spec_web_search() -> Dict[str, Any]:
    return {
        "description": "Free web search with minimal rate limits: Wikipedia best-guess, Wikipedia REST, DuckDuckGo HTML fallback.",
        "schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "k": {"type": "integer"},
            },
            "required": ["q"],
            "additionalProperties": False,
        },
        "runner": tool_web_search,
    }

def spec_web_get() -> Dict[str, Any]:
    return {
        "description": "Fetch a web page and extract readable text (title + content).",
        "schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "timeout": {"type": "number"},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "runner": tool_web_get,
    }
