"""
crawler.py – async site crawler used by main.py
Implements three crawl modes:
  • standard     – direct requests, small delay, desktop UA pool
  • stealth      – cheap datacentre proxies, larger delay, mixed UA pool
  • residential  – residential proxies, largest delay, mixed UA pool
"""

# ── imports ───────────────────────────────────────────────
import asyncio, random, httpx
from typing import List, Set, Tuple
from urllib.parse import urljoin, urlparse, urlsplit
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup

# ── header / proxy helpers ────────────────────────────────
DESKTOP_UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.3 Safari/605.1.15",
]
MOBILE_UA = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
]

PROXY_POOLS = {
    "stealth": [
        # fill with datacentre proxy URLs or leave empty
        # "http://USER:PASS@datacentre-proxy1:8000",
    ],
    "residential": [
        # fill with residential proxy URLs or leave empty
        # "http://USER:PASS@residential-gw1:9000",
    ],
}

def make_headers(mode: str) -> dict:
    pool = DESKTOP_UA if mode == "standard" else DESKTOP_UA + MOBILE_UA
    return {
        "User-Agent": random.choice(pool),
        "Accept-Language": "en-US,en;q=0.9",
    }

def crawl_delay(mode: str) -> float:
    if mode == "standard":
        return random.uniform(1, 2)
    if mode == "stealth":
        return random.uniform(2, 5)
    return random.uniform(5, 10)  # residential

# ── recursive fetch/parsing ───────────────────────────────
async def _fetch_and_parse(
    client: httpx.AsyncClient,
    page_url: str,
    base_domain: str,
    depth: int,
    max_depth: int,
    visited: Set[str],
    found: Set[str],
    file_types: Set[str],
    mode: str,
):
    if page_url in visited or depth > max_depth:
        return
    visited.add(page_url)

    # polite delay per mode
    await asyncio.sleep(crawl_delay(mode))

    try:
        resp = await client.get(page_url, timeout=10.0, follow_redirects=True)
    except httpx.RequestError:
        return
    if resp.status_code >= 400:
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) collect file URLs
    for tag in soup.find_all(["a", "img", "script"]):
        raw = tag.get("href") or tag.get("src")
        if not raw:
            continue
        full = urljoin(page_url, raw)
        path = urlsplit(full).path.lower()
        if any(path.endswith(f".{ext}") for ext in file_types):
            found.add(full)

    # 2) recurse into same-domain links
    if depth < max_depth:
        for a in soup.find_all("a", href=True):
            child = urljoin(page_url, a["href"])
            if urlparse(child).netloc == base_domain:
                await _fetch_and_parse(
                    client, child, base_domain,
                    depth + 1, max_depth,
                    visited, found, file_types, mode
                )

# ── public coroutine ─────────────────────────────────────
async def crawl(
    base_url: str,
    max_depth: int,
    visited_list: List[str],
    file_types_list: List[str],
    mode: str = "standard",
) -> Tuple[Set[str], Set[str]]:

    visited: Set[str] = set(visited_list or [])
    found:   Set[str] = set()
    file_types = {ext.lower().lstrip(".") for ext in (file_types_list or [])}
    base_domain = urlparse(base_url).netloc

    proxy_url = None
    if mode in PROXY_POOLS and PROXY_POOLS[mode]:
        proxy_url = random.choice(PROXY_POOLS[mode])

    async with httpx.AsyncClient(
        proxies=proxy_url,
        headers=make_headers(mode),
        follow_redirects=True,
    ) as client:
        await _fetch_and_parse(
            client, base_url, base_domain,
            depth=1, max_depth=max_depth,
            visited=visited, found=found,
            file_types=file_types, mode=mode
        )

    return visited, found  # no HEAD-check for maximum reliability
