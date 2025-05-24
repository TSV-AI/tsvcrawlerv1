"""
crawler.py
~~~~~~~~~~
Asynchronous site crawler that:

1. Recursively visits pages up to `max_depth`, **same-domain only**.
2. Collects file URLs whose paths end with any extension in `file_types_list`.
3. HEAD-checks each found file (in parallel) to confirm it exists (status < 400).

The function signature is designed to plug directly into the FastAPI
endpoint in `main.py`.
"""

from typing import List, Set, Tuple
import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Internal helper ──────────────────────────────────────────────────────────


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
    """Recursive async crawler."""
    if page_url in visited or depth > max_depth:
        return
    visited.add(page_url)

    try:
        resp = await client.get(page_url, timeout=10.0)
        resp.raise_for_status()
    except httpx.RequestError:
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) collect files
    for tag in soup.find_all(["a", "img", "script"]):
        raw_href = tag.get("href") or tag.get("src")
        if not raw_href:
            continue
        full_url = urljoin(page_url, raw_href)
        path = urlparse(full_url).path.lower()
        if any(path.endswith(f".{ext}") for ext in file_types):
            found.add(full_url)

    # 2) recurse into same-domain links
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


def _head_check(url: str) -> bool:
    """Synchronously verify the file actually exists."""
    try:
        r = httpx.head(url, follow_redirects=True, timeout=5.0)
        return r.status_code < 400
    except Exception:
        return False


# ── Public API ───────────────────────────────────────────────────────────────


async def crawl(
    base_url: str,
    max_depth: int,
    visited_list: List[str],
    file_types_list: List[str],
) -> Tuple[Set[str], Set[str]]:
    """
    Asynchronously crawl `base_url` up to `max_depth`, return:
        visited_set, valid_file_urls
    `file_types_list` is a list like ["pdf", "png", "zip"] (case-insensitive).
    """
    visited: Set[str] = set(visited_list or [])
    found: Set[str] = set()
    file_types: Set[str] = {ext.lower().lstrip(".") for ext in file_types_list or []}
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

    # HEAD-check in parallel (thread pool → non-blocking for event loop)
    valid: Set[str] = set()
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=12) as pool:
        tasks = [
            loop.run_in_executor(pool, _head_check, url) for url in found
        ]
        for idx, coro in enumerate(asyncio.as_completed(tasks)):
            if await coro:
                valid.add(list(found)[idx])

    return visited, valid
