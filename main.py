"""
FastAPI wrapper around the crawler
"""

# ── imports ───────────────────────────────────────────────
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from urllib.parse import urlparse
import logging, traceback

from crawler import crawl   # import our coroutine

# ── models ────────────────────────────────────────────────
class CrawlRequest(BaseModel):
    baseUrl:   HttpUrl
    depth:     Optional[int] = 2
    visited:   Optional[List[str]] = []
    fileTypes: List[str]

class CrawlResponse(BaseModel):
    visited:    List[str]
    foundFiles: List[str]

# ── app & CORS ────────────────────────────────────────────
app = FastAPI(title="Three Sixty Vue Crawler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://www.threesixtyvue.com",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

log = logging.getLogger("crawler")

# ── endpoints ─────────────────────────────────────────────
@app.post("/crawl", response_model=CrawlResponse)
async def crawl_endpoint(req: CrawlRequest):
    try:
        visited_set, files_set = await crawl(
            str(req.baseUrl),          # cast HttpUrl → str
            req.depth,
            req.visited,
            req.fileTypes,
        )
    except Exception:
        log.error("crawl failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal crawler error")

    return CrawlResponse(
        visited=[str(u) for u in visited_set],
        foundFiles=[str(u) for u in files_set],
    )

@app.get("/health")
def health():
    return {"status": "ok"}
