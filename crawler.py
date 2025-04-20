import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

FILE_EXTS = (".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".webp")

def crawl(base_url: str, max_depth: int = 2, visited=None, found_files=None):
    if visited is None:
        visited = set()
    if found_files is None:
        found_files = set()

    base_domain = urlparse(base_url).netloc
    seen_paths  = set()

    # Use a single Session for connection pooling
    session = requests.Session()

    def _crawl(url: str, depth: int):
        if depth > max_depth or url in visited:
            return
        visited.add(url)

        try:
            resp = session.get(url, timeout=5)
            resp.raise_for_status()
        except requests.RequestException:
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        # 1) Collect candidates
        for tag in soup.find_all(["a", "img", "script"]):
            raw = tag.get("href") or tag.get("src")
            if not raw:
                continue

            full = urljoin(base_url, raw)
            path = urlparse(full).path.lower()

            if not path.endswith(FILE_EXTS):
                continue
            if path in seen_paths:
                continue

            seen_paths.add(path)
            found_files.add(full)

        # 2) Recurse same‑domain links
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            if urlparse(href).netloc == base_domain:
                _crawl(href, depth + 1)

    # Kick off the crawl
    _crawl(base_url, 0)

    # 3) Parallel HEAD‑check to weed out 404s
    def is_live(url):
        try:
            r = session.head(url, allow_redirects=True, timeout=1)
            return r.status_code < 400
        except:
            return False

    valid_files = set()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(is_live, url): url for url in found_files}
        for fut in as_completed(futures):
            url = futures[fut]
            if fut.result():
                valid_files.add(url)

    return visited, valid_files
