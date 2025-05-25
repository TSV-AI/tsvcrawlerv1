"""
crawler.py  –  Async site crawler used by main.py
"""

# ── imports ───────────────────────────────────────────────
import asyncio
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse, urlsplit
from concurrent.futures import ThreadPoolExecutor

import httpx
from bs4 import BeautifulSoup

# ── helpers ───────────────────────────────────────────────
async def _fetch_and_parse(
    client: httpx.AsyncClient,
    page_url: str,
    base_domain: str,
    depth: int,
    max_depth: int,
    visited: Set[str],
    found: Set[str],
    file_types: Set[str],
):
    """Recursively crawl pages and collect file URLs."""
    if page_url in visited or depth > max_depth:
        return
    visited.add(page_url)

    # --- download page, follow redirects ---
    try:
        resp = await client.get(
            page_url,
            timeout=10.0,
            follow_redirects=True,
        )
    except httpx.RequestError:
        return        # network error → skip page

    if resp.status_code >= 400:
        return        # 404 / 403 / 5xx → skip page

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- 1) collect file URLs (strip ?query / #fragment) ---
    for tag in soup.find_all(["a", "img", "script"]):
        raw = tag.get("href") or tag.get("src")
        if not raw:
            continue
        full = urljoin(page_url, raw)
        path = urlsplit(full).path.lower()
        if any(path.endswith(f".{ext}") for ext in file_types):
            found.add(full)

    # --- 2) recurse into same-domain links ---
    if depth < max_depth:
        for a in soup.find_all("a", href=True):
            child = urljoin(page_url, a["href"])
            if urlparse(child).netloc == base_domain:
                await _fetch_and_parse(
                    client,
                    child,
                    base_domain,
                    depth + 1,
                    max_depth,
                    visited,
                    found,
                    file_types,
                )

def _head_ok(url: str) -> bool:
    """Return True if URL responds <400 to HEAD (or fallback GET)."""
    try:
        r = httpx.head(url, follow_redirects=True, timeout=5.0)
        if r.status_code in (405, 403):
            r = httpx.get(url, timeout=5.0)
        return r.status_code < 400
    except Exception:
        return False

# ── public coroutine ─────────────────────────────────────
async def crawl(
    base_url: str,
    max_depth: int,
    visited_list: List[str],
    file_types_list: List[str],
) -> Tuple[Set[str], Set[str]]:
    """
    Crawl `base_url` up to `max_depth` and return (visited_set, valid_file_set).
    `file_types_list` should contain extensions like ["pdf","png","zip"].
    """
    visited: Set[str] = set(visited_list or [])
    found:   Set[str] = set()
    file_types = {ext.lower().lstrip(".") for ext in (file_types_list or [])}
    base_domain = urlparse(base_url).netloc

    async with httpx.AsyncClient() as client:
        await _fetch_and_parse(
            client,
            base_url,
            base_domain,
            depth=1,
            max_depth=max_depth,
            visited=visited,
            found=found,
            file_types=file_types,
        )

 # Skip HEAD validation – just return what was found
 return visited, found
