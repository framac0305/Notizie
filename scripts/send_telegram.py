"""Sends a 'digest ready' notification to Telegram with a link to the PWA."""
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    pages_url = os.environ["PAGES_URL"]

    headlines_path = Path(__file__).resolve().parent.parent / "site" / "latest_headlines.txt"
    headlines = headlines_path.read_text(encoding="utf-8") if headlines_path.exists() else ""

    text = f"📰 *Digest pronto*\n\n{headlines}\n\n[Apri il digest]({pages_url})"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "false",
        }
    ).encode()

    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode()
        if resp.status != 200:
            print(body, file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
