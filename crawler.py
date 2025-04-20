import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def crawl(base_url: str, max_depth: int = 2):
    visited = set()
    found_files = set()
    base_domain = urlparse(base_url).netloc

    def _crawl(url: str, depth: int):
        if depth > max_depth or url in visited:
            return
        visited.add(url)
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
        except requests.RequestException:
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        # 1) Gather file links on this page
        for tag in soup.find_all(["a", "img", "script"], href=True, src=True):
            link = tag.get("href") or tag.get("src")
            full = urljoin(base_url, link)
            clean = full.split("?", 1)[0].lower()
            if clean.endswith((".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".webp")):
                found_files.add(full)

        # 2) Then recurse into *all* same‐domain <a> links
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            if urlparse(href).netloc == base_domain:
                _crawl(href, depth + 1)

    # Kick off the crawl
    _crawl(base_url, 0)
    return visited, found_files
