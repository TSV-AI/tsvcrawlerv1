# main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Set
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# ── Models ────────────────────────────────────────────────────────────────────

class CrawlRequest(BaseModel):
    baseUrl: HttpUrl
    depth: Optional[int] = 2
    visited: Optional[List[str]] = []

class CrawlResponse(BaseModel):
    visited: List[HttpUrl]
    foundFiles: List[HttpUrl]

# ── FastAPI App & CORS ────────────────────────────────────────────────────────

app = FastAPI(
    title="Three Sixty Vue Crawler",
    description="Given a base URL, depth, and list of visited URLs, returns new file URLs and updated visited list."
)

# Allow your frontend origin(s) here:
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",                # dev
        "http://localhost:5173",     # production
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Core Crawl Logic ─────────────────────────────────────────────────────────

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

    # 1) collect files by extension
    for a in soup.find_all("a", href=True):
        href = a["href"]
        for ext in file_types:
            if href.lower().endswith(f".{ext.lower()}"):
                file_url = urljoin(page_url, href)
                found.add(file_url)

    # 2) recurse into same-domain links
    if depth < max_depth:
        for a in soup.find_all("a", href=True):
            full = urljoin(page_url, a["href"])
            if urlparse(full).netloc == base_domain:
                await _fetch_and_parse(
                    client, full, base_domain, depth + 1,
                    max_depth, visited, found, file_types
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
    file_types = set(file_types_list or [])

    async with httpx.AsyncClient() as client:
        await _fetch_and_parse(
            client, base_url, base_domain, 1,
            max_depth, visited, found, file_types
        )

    return visited, found

# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/crawl", response_model=CrawlResponse)
async def crawl_endpoint(req: CrawlRequest):
    try:
        visited_set, files_set = await crawl(
            req.baseUrl,
            req.depth,
            req.visited,
            []  # you can extend CrawlRequest to include fileTypes if desired
        )
        return CrawlResponse(
            visited=list(visited_set),
            foundFiles=list(files_set)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
