import requests
# crawler code
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def crawl(base_url: str, max_depth: int = 2, visited=None, found_files=None):
    if visited is None:
        visited = set()
    if found_files is None:
        found_files = set()

    base_domain = urlparse(base_url).netloc

    def _crawl(url: str, depth: int):
        if depth > max_depth or url in visited:
            return
        visited.add(url)
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
        except Exception:
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        # Gather file links
from urllib.parse import urlparse

for tag in soup.find_all(["a", "img", "script"]):
    link = tag.get("href") or tag.get("src")
    if not link:
        continue

    full = urljoin(base_url, link)
    p = urlparse(full)
    if p.path.lower().endswith((".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".webp")):
        found_files.add(full)

        # Recurse into same‑domain pages
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            if urlparse(href).netloc == base_domain:
                _crawl(href, depth + 1)

    _crawl(base_url, 0)
    return visited, found_files
