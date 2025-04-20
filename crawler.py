from urllib.parse import urljoin

FILE_EXTS = (".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".webp")

def extract_files(soup, base_url):
    found = set()
    for tag in soup.find_all(True):
        for attr in ("src", "href"):
            if not tag.has_attr(attr):
                continue
            raw = tag[attr]                     # exactly what’s in the HTML
            # check extension (ignoring case, but *not* removing query‐string)
            if raw.lower().split("?", 1)[0].endswith(FILE_EXTS):
                # turn relative → absolute, but otherwise leave it alone
                absolute = urljoin(base_url, raw)
                found.add(absolute)
    return found
