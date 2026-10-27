import re
import shutil
from pathlib import Path

import app

SITE = Path("site")
PAGES = {"index.html": "/", "about.html": "/about.html", "downloads.html": "/downloads.html"}


def fetch(client, url):
    response = client.get(url)
    if response.status_code != 200:
        raise RuntimeError(f"{url} returned {response.status_code}")
    return response.data


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "chart").mkdir(parents=True)
    client = app.app.test_client()

    for file, url in PAGES.items():
        (SITE / file).write_bytes(fetch(client, url))

    for name in app.CHARTS:
        for theme in app.THEMES:
            stem = f"{name}-{theme}"
            (SITE / "chart" / f"{stem}.svg").write_bytes(fetch(client, f"/chart/{stem}.svg"))
            print(f"chart/{stem}.svg")

    (SITE / "downloads").mkdir()
    for name in app.download_files():
        (SITE / "downloads" / name).write_bytes(fetch(client, f"/downloads/{name}"))

    shutil.copytree("static", SITE / "static")
    shutil.copytree(app.FIGURES_DIR, SITE / "figures")

    html = "".join((SITE / file).read_text(encoding="utf-8") for file in PAGES)
    linked = set(re.findall(r'(?:src|href)="((?:chart|static|downloads|figures)/[^"#?]+)"', html))
    if app.SITE_URL:
        linked |= {url.removeprefix(app.SITE_URL) for url in re.findall(r'content="(' + re.escape(app.SITE_URL) + r'[^"]+)"', html)}
    linked |= {f"{base}{theme}.svg" for base in re.findall(r'data-chart="([^"]+)"', html) for theme in app.THEMES}
    missing = sorted(path for path in linked if not (SITE / path).exists())
    if missing:
        raise RuntimeError(f"pages link to files that were not built: {missing}")
    print(f"built {len(PAGES)} pages and {len(linked)} linked files into {SITE}/")


if __name__ == "__main__":
    main()
