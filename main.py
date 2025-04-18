from fastapi import FastAPI
# main app code
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from crawler import crawl

class CrawlRequest(BaseModel):
    baseUrl: str
    depth: Optional[int] = 2
    visited: Optional[List[str]] = []

class CrawlResponse(BaseModel):
    visited: List[str]
    foundFiles: List[str]

app = FastAPI(
    title="Three Sixty Vue Crawler",
    description="Given a base URL, depth, and list of visited URLs, returns new file URLs and updated visited list."
)

@app.post("/crawl", response_model=CrawlResponse)
def crawl_endpoint(req: CrawlRequest):
    try:
        visited_set, files_set = crawl(req.baseUrl, req.depth, set(req.visited), set())
        return CrawlResponse(
            visited=list(visited_set),
            foundFiles=list(files_set)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
