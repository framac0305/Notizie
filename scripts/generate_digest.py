"""Fetches RSS feeds for the configured topics and renders site/index.html."""
import html
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser

ROME = ZoneInfo("Europe/Rome")

FEEDS = {
    "Mercati finanziari": [
        "https://www.ilsole24ore.com/rss/finanza.xml",
        "https://it.investing.com/rss/news.rss",
    ],
    "Tecnologia / AI": [
        "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
    ],
    "Sport e motori": [
        "https://www.ansa.it/sito/notizie/sport/sport_rss.xml",
        "https://it.motorsport.com/rss/f1/news/",
    ],
}

ITEMS_PER_TOPIC = 6
SUMMARY_MAX_CHARS = 180

TAG_RE = re.compile(r"<[^>]+>")


def clean_summary(raw: str) -> str:
    text = html.unescape(TAG_RE.sub("", raw or "")).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > SUMMARY_MAX_CHARS:
        text = text[:SUMMARY_MAX_CHARS].rsplit(" ", 1)[0] + "…"
    return text


def fetch_topic_entries(urls: list[str]) -> list[dict]:
    entries = []
    for url in urls:
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        for e in parsed.entries:
            entries.append(
                {
                    "title": html.unescape(e.get("title", "").strip()),
                    "link": e.get("link", ""),
                    "summary": clean_summary(e.get("summary", e.get("description", ""))),
                    "published_parsed": e.get("published_parsed"),
                    "source": parsed.feed.get("title", ""),
                }
            )
    entries.sort(key=lambda x: x["published_parsed"] or 0, reverse=True)
    seen_titles = set()
    unique = []
    for e in entries:
        if e["title"] in seen_titles:
            continue
        seen_titles.add(e["title"])
        unique.append(e)
    return unique[:ITEMS_PER_TOPIC]


def render_html(digest: dict[str, list[dict]], generated_at: datetime) -> str:
    sections = []
    for topic, items in digest.items():
        cards = "\n".join(
            f"""<article class="card">
  <h3><a href="{html.escape(it['link'])}" target="_blank" rel="noopener">{html.escape(it['title'])}</a></h3>
  <p>{html.escape(it['summary'])}</p>
  <span class="source">{html.escape(it['source'])}</span>
</article>"""
            for it in items
        ) or "<p class=\"empty\">Nessuna notizia disponibile oggi.</p>"
        sections.append(f"""<section>
  <h2>{html.escape(topic)}</h2>
  {cards}
</section>""")

    body = "\n".join(sections)
    timestamp = generated_at.strftime("%d/%m/%Y %H:%M")

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Digest Notizie</title>
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#121417">
<link rel="apple-touch-icon" href="icons/icon-192.png">
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin: 0; font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: #121417; color: #eaeaea; }}
  header {{ padding: 20px 16px 8px; }}
  header h1 {{ margin: 0; font-size: 1.4rem; }}
  header time {{ color: #9aa0a6; font-size: 0.85rem; }}
  main {{ padding: 0 16px 32px; max-width: 720px; margin: 0 auto; }}
  section {{ margin-top: 24px; }}
  section h2 {{ font-size: 1.1rem; border-bottom: 1px solid #2a2d31; padding-bottom: 6px; }}
  .card {{ background: #1b1e22; border-radius: 10px; padding: 12px 14px; margin: 10px 0; }}
  .card h3 {{ margin: 0 0 6px; font-size: 1rem; }}
  .card h3 a {{ color: #8ab4f8; text-decoration: none; }}
  .card p {{ margin: 0; color: #c7c9cc; font-size: 0.9rem; line-height: 1.35; }}
  .card .source {{ display: block; margin-top: 6px; color: #777; font-size: 0.75rem; }}
  .empty {{ color: #777; font-style: italic; }}
</style>
</head>
<body>
<header>
  <h1>📰 Digest Notizie</h1>
  <time>Aggiornato il {timestamp}</time>
</header>
<main>
{body}
</main>
<script>
if ('serviceWorker' in navigator) {{
  navigator.serviceWorker.register('sw.js').catch(() => {{}});
}}
</script>
</body>
</html>
"""


def main() -> None:
    generated_at = datetime.now(ROME)
    digest = {topic: fetch_topic_entries(urls) for topic, urls in FEEDS.items()}

    site_dir = Path(__file__).resolve().parent.parent / "site"
    site_dir.mkdir(exist_ok=True)
    (site_dir / "index.html").write_text(render_html(digest, generated_at), encoding="utf-8")

    top_headlines = {
        topic: items[0]["title"] for topic, items in digest.items() if items
    }
    summary_path = site_dir / "latest_headlines.txt"
    summary_path.write_text(
        "\n".join(f"{topic}: {title}" for topic, title in top_headlines.items()),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
