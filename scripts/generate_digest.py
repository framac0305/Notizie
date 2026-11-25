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
        "https://www.repubblica.it/rss/economia/rss2.0.xml",
        "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
    ],
    "Tecnologia / AI": [
        "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://www.wired.it/feed/rss",
        "https://www.repubblica.it/rss/tecnologia/rss2.0.xml",
    ],
    "Sport e motori": [
        "https://www.ansa.it/sito/notizie/sport/sport_rss.xml",
        "https://it.motorsport.com/rss/f1/news/",
        "https://www.gazzetta.it/rss/home.xml",
        "https://www.gazzetta.it/rss/motori.xml",
        "https://sport.sky.it/rss/sport.xml",
    ],
}

SOURCE_NAMES = {
    "https://www.ilsole24ore.com/rss/finanza.xml": "Il Sole 24 Ore",
    "https://it.investing.com/rss/news.rss": "Investing.com",
    "https://www.repubblica.it/rss/economia/rss2.0.xml": "Repubblica Economia",
    "https://www.ansa.it/sito/notizie/economia/economia_rss.xml": "ANSA Economia",
    "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml": "ANSA Tecnologia",
    "https://techcrunch.com/category/artificial-intelligence/feed/": "TechCrunch",
    "https://www.wired.it/feed/rss": "Wired Italia",
    "https://www.repubblica.it/rss/tecnologia/rss2.0.xml": "Repubblica Italian Tech",
    "https://www.ansa.it/sito/notizie/sport/sport_rss.xml": "ANSA Sport",
    "https://it.motorsport.com/rss/f1/news/": "Motorsport.com",
    "https://www.gazzetta.it/rss/home.xml": "La Gazzetta dello Sport",
    "https://www.gazzetta.it/rss/motori.xml": "Gazzetta Motori",
    "https://sport.sky.it/rss/sport.xml": "Sky Sport",
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


IMG_SRC_RE = re.compile(r'<img[^>]+src="([^"]+)"')


def extract_image(e) -> str:
    media = e.get("media_content") or e.get("media_thumbnail")
    if media:
        url = media[0].get("url", "")
        if url:
            return url
    for link in e.get("links", []):
        if str(link.get("type", "")).startswith("image/"):
            return link.get("href", "")
    for enc in e.get("enclosures", []) if hasattr(e, "enclosures") else []:
        if str(enc.get("type", "")).startswith("image/"):
            return enc.get("href", "")
    raw = e.get("summary", "") or e.get("description", "") or ""
    match = IMG_SRC_RE.search(raw)
    if match:
        return match.group(1)
    return ""


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
                    "image": extract_image(e),
                    "published_parsed": e.get("published_parsed"),
                    "source": SOURCE_NAMES.get(url, parsed.feed.get("title", "")),
                }
            )
    import calendar

    entries.sort(
        key=lambda x: calendar.timegm(x["published_parsed"]) if x["published_parsed"] else 0,
        reverse=True,
    )
    seen_titles = set()
    unique = []
    for e in entries:
        if e["title"] in seen_titles:
            continue
        seen_titles.add(e["title"])
        unique.append(e)
    return unique[:ITEMS_PER_TOPIC]


def render_article(it: dict, lead: bool) -> str:
    image_html = (
        f'<div class="thumb"><img src="{html.escape(it["image"])}" alt="" loading="lazy" onerror="this.parentElement.remove()"></div>'
        if it["image"]
        else ""
    )
    headline_tag = "h3" if lead else "h4"
    dek_html = f'<p class="dek">{html.escape(it["summary"])}</p>' if it["summary"] else ""
    return f"""<article class="story{' lead' if lead else ''}">
  {image_html}
  <div class="story-text">
    <{headline_tag}><a href="{html.escape(it['link'])}" target="_blank" rel="noopener">{html.escape(it['title'])}</a></{headline_tag}>
    {dek_html}
    <p class="byline">{html.escape(it['source'])}</p>
  </div>
</article>"""


def render_html(digest: dict[str, list[dict]], generated_at: datetime) -> str:
    sections = []
    for topic, items in digest.items():
        if not items:
            articles = '<p class="empty">Nessuna notizia disponibile oggi.</p>'
        else:
            lead, rest = items[0], items[1:]
            articles = render_article(lead, lead=True) + "\n".join(
                render_article(it, lead=False) for it in rest
            )
        slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
        sections.append(f"""<section id="{slug}">
  <h2 class="section-title">{html.escape(topic)}</h2>
  <div class="stories">
  {articles}
  </div>
</section>""")

    body = "\n".join(sections)
    months_it = [
        "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    ]
    timestamp = f"{generated_at.day} {months_it[generated_at.month]} {generated_at.year} — {generated_at.strftime('%H:%M')}"

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Digest Notizie</title>
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#fbfaf7">
<link rel="apple-touch-icon" href="icons/icon-192.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700;900&family=PT+Serif:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #fbfaf7; --ink: #1a1a1a; --rule: #1a1a1a; --muted: #6b6b6b; --accent: #8a1f11;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: 'PT Serif', Georgia, serif; background: var(--bg); color: var(--ink); -webkit-font-smoothing: antialiased; }}
  .masthead {{ text-align: center; padding: 22px 16px 14px; border-bottom: 3px solid var(--rule); }}
  .masthead .kicker {{ font-family: 'PT Serif', serif; font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }}
  .masthead h1 {{ font-family: 'Playfair Display', serif; font-weight: 900; font-size: 2.4rem; margin: 6px 0; letter-spacing: -0.01em; }}
  .masthead time {{ font-size: 0.78rem; color: var(--muted); font-style: italic; }}
  nav.toc {{ display: flex; justify-content: center; gap: 18px; flex-wrap: wrap; padding: 10px 16px; border-bottom: 1px solid #ddd8ce; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; }}
  nav.toc a {{ color: var(--ink); text-decoration: none; }}
  main {{ max-width: 760px; margin: 0 auto; padding: 8px 16px 48px; }}
  section {{ margin-top: 34px; }}
  .section-title {{ font-family: 'Playfair Display', serif; font-size: 1.3rem; font-weight: 700; border-bottom: 2px solid var(--rule); padding-bottom: 6px; margin-bottom: 14px; }}
  .stories {{ display: block; }}
  .story {{ border-bottom: 1px solid #e3ddd0; padding: 16px 0; display: flex; gap: 14px; }}
  .story:last-child {{ border-bottom: none; }}
  .story.lead {{ flex-direction: column; gap: 10px; }}
  .story .thumb {{ flex: 0 0 110px; }}
  .story.lead .thumb {{ flex: none; width: 100%; }}
  .story .thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; border-radius: 2px; aspect-ratio: 1 / 1; }}
  .story.lead .thumb img {{ aspect-ratio: 16 / 9; }}
  .story-text {{ flex: 1; min-width: 0; }}
  .story h3, .story h4 {{ margin: 0 0 6px; line-height: 1.25; }}
  .story.lead h3 {{ font-family: 'Playfair Display', serif; font-size: 1.6rem; font-weight: 700; }}
  .story h4 {{ font-size: 1.02rem; font-weight: 700; }}
  .story a {{ color: var(--ink); text-decoration: none; }}
  .story a:hover {{ color: var(--accent); }}
  .dek {{ margin: 0 0 6px; color: #333; font-size: 0.92rem; line-height: 1.45; }}
  .byline {{ margin: 0; color: var(--muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; }}
  .empty {{ color: var(--muted); font-style: italic; }}
  footer {{ text-align: center; padding: 18px; color: var(--muted); font-size: 0.72rem; border-top: 3px solid var(--rule); }}
  @media (max-width: 480px) {{
    .masthead h1 {{ font-size: 1.9rem; }}
    .story.lead h3 {{ font-size: 1.3rem; }}
  }}
</style>
</head>
<body>
<header class="masthead">
  <div class="kicker">Il tuo digest personale</div>
  <h1>Digest Notizie</h1>
  <time>{timestamp}</time>
</header>
<nav class="toc">
  {' '.join(f'<a href="#{re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")}">{html.escape(t)}</a>' for t in digest)}
</nav>
<main>
{body}
</main>
<footer>
  Generato automaticamente da fonti pubbliche (ANSA, TechCrunch, Motorsport.com, Investing.com, Il Sole 24 Ore). Ogni articolo rimanda alla fonte originale.
</footer>
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
