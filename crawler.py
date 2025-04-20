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
         for tag in soup.find_all(["a", "img", "script"]):
            raw = tag.get("href") or tag.get("src")
            if not raw:
                continue

            full = urljoin(base_url, raw)

            # 1) remove ?query and #fragment for the extension test
            clean = full.split('?', 1)[0].split('#', 1)[0].lower()

            # 2) test on the stripped path
            if clean.endswith((".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".webp")):
                # 3) add the original full URL (with query/fragment intact)
                found_files.add(full)

        # Recurse into same‑domain pages
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            if urlparse(href).netloc == base_domain:
                _crawl(href, depth + 1)

    _crawl(base_url, 0)
    return visited, found_files
