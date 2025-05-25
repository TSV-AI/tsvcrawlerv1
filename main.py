from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Set
from urllib.parse import urlparse            # ← add this line
import httpx 
import logging, traceback

# ── Request & Response Models ────────────────────────────────────────────────

class CrawlRequest(BaseModel):
    baseUrl: HttpUrl               # validated input URL
    depth: Optional[int] = 2       # 1=light, 2=normal, 3=deep
    visited: Optional[List[str]] = []  
    fileTypes: List[str]           # e.g. ["pdf","png","zip"]

class CrawlResponse(BaseModel):
    visited: List[str]             # return as plain strings
    foundFiles: List[str]

# ── FastAPI App & CORS ────────────────────────────────────────────────────────

app = FastAPI(
    title="Three Sixty Vue Crawler",
    description="Crawls a site to specified depth, finds files, returns CSV-ready data."
)

# Allow your frontend origins here:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ── Core Crawling Logic ───────────────────────────────────────────────────────

async def _fetch_and_parse(
    client: httpx.AsyncClient,
    page_url: str,
    base_domain: str,
    depth: int,
    max_depth: int,
    visited: Set[str],
    found: Set[str],
    file_types: Set[str]
):
    if page_url in visited or depth > max_depth:
        return
    visited.add(page_url)

    try:
        resp = await client.get(page_url, timeout=10.0)
        resp.raise_for_status()
    except Exception:
        return

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) collect files matching extensions
    for tag in soup.find_all(["a", "img", "script"]):
        raw_href = tag.get("href") or tag.get("src")
        if not raw_href:
            continue

        full_url = urljoin(page_url, raw_href)

        # ⬇️ strip query-strings / fragments before extension check
        path = urlsplit(full_url).path.lower()

        if any(path.endswith(f".{ext}") for ext in file_types):
            found.add(full_url)

    # 2) recurse into same-domain links
    if depth < max_depth:
        for a in soup.find_all("a", href=True):
            full = urljoin(page_url, a["href"])
            if urlparse(full).netloc == base_domain:
                await _fetch_and_parse(
                    client, full, base_domain,
                    depth + 1, max_depth,
                    visited, found, file_types
                )

async def crawl(
    base_url: str,
    max_depth: int,
    visited_list: List[str],
    file_types_list: List[str]
):
    visited: Set[str] = set(visited_list or [])
    found: Set[str] = set()
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
            file_types=set(file_types_list)
        )

    return visited, found

# ── API Endpoints ────────────────────────────────────────────────────────────

import traceback, logging
log = logging.getLogger("crawler")

# main.py  ───── only the endpoint needs to change
@app.post("/crawl", response_model=CrawlResponse)
async def crawl_endpoint(req: CrawlRequest):
    try:
        visited_set, files_set = await crawl(
            str(req.baseUrl),             # ← plain str, no .decode() issue
            req.depth,
            req.visited,
            req.fileTypes,
        )
    except Exception as e:
        # log / re-raise
        log.error("Crawl failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

    return CrawlResponse(
        visited=[str(u) for u in visited_set],
        foundFiles=[str(u) for u in files_set],
    )

@app.get("/health")
def health_check():
    return {"status": "ok"}
