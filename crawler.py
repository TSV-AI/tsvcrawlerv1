import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

FILE_EXTS = (".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".webp")

def crawl(base_url: str, max_depth: int = 2, visited=None, found_files=None):
    if visited is None:
        visited = set()
    if found_files is None:
        found_files = set()

    base_domain = urlparse(base_url).netloc
    seen_paths  = set()   # track normalized paths to dedupe

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

        # Gather file links
        for tag in soup.find_all(["a", "img", "script"]):
            raw = tag.get("href") or tag.get("src")
            if not raw:
                continue

            full = urljoin(base_url, raw)
            parsed = urlparse(full)
            path   = parsed.path.lower()

            # 1) extension check
            if not path.endswith(FILE_EXTS):
                continue

            # 2) dedupe by path
            if path in seen_paths:
                continue

            # 3) quick HEAD-check to weed out 404s
            try:
                head = requests.head(full, allow_redirects=True, timeout=3)
                if head.status_code >= 400:
                    continue
            except requests.RequestException:
                continue

            # passed all filters!
            seen_paths.add(path)
            found_files.add(full)

        # Recurse into same-domain pages
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            if urlparse(href).netloc == base_domain:
                _crawl(href, depth + 1)

    # kick it off
    _crawl(base_url, 0)
    return visited, found_files
