from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import requests

# (your extract_files here)

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

        # — replace your old loop with this —
        found_files |= extract_files(soup, url)

        # now recurse into same‑domain links
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            if urlparse(href).netloc == base_domain:
                _crawl(href, depth + 1)

    _crawl(base_url, 0)
    return visited, found_files
