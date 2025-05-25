"""
Asynchronous crawler used by main.py
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
    if page_url in visited or depth > max_depth:
        return
    visited.add(page_url)

    try:
    # ── download the page (follow redirects) ───────────────
    resp = await client.get(
        page_url,
        timeout=10.0,
        follow_redirects=True,
    )
    # Ignore pages that return 4xx or 5xx
    if resp.status_code >= 400:
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) grab file links (ignore ?query / #fragment)
    for tag in soup.find_all(["a", "img", "script"]):
        raw = tag.get("href") or tag.get("src")
        if not raw:
            continue
        full = urljoin(page_url, raw)
        path = urlsplit(full).path.lower()
        if any(path.endswith(f".{ext}") for ext in file_types):
            found.add(full)

    # 2) recurse into same-domain pages
    if depth < max_depth:
        for a in soup.find_all("a", href=True):
            child = urljoin(page_url, a["href"])
            if urlparse(child).netloc == base_domain:
                await _fetch_and_parse(
                    client, child, base_domain,
                    depth + 1, max_depth,
                    visited, found, file_types
                )

def _head_ok(url: str) -> bool:
    try:
        r = httpx.head(url, follow_redirects=True, timeout=5.0)
        if r.status_code in (405, 403):
            r = httpx.get(url, timeout=5.0)
        return r.status_code < 400
    except Exception:
        return False

# ── public API ────────────────────────────────────────────
async def crawl(
    base_url: str,
    max_depth: int,
    visited_list: List[str],
    file_types_list: List[str],
) -> Tuple[Set[str], Set[str]]:
    visited: Set[str] = set(visited_list or [])
    found:   Set[str] = set()
    file_types = {ext.lower().lstrip(".") for ext in (file_types_list or [])}
    base_domain = urlparse(base_url).netloc

    async with httpx.AsyncClient() as client:
        await _fetch_and_parse(
            client, base_url, base_domain,
            depth=1, max_depth=max_depth,
            visited=visited, found=found,
            file_types=file_types
        )

    # HEAD-check in a thread pool
    valid: Set[str] = set()
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=12) as pool:
        fut_to_url = {
            loop.run_in_executor(pool, _head_ok, url): url for url in found
        }
        for fut in asyncio.as_completed(fut_to_url):
            url = fut_to_url[fut]
            try:
                if await fut:
                    valid.add(url)
            except Exception:
                pass

    return visited, valid
