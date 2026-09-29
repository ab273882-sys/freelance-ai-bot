import asyncio
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import feedparser
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip()
SCAN_MINUTES = max(5, int(os.getenv("SCAN_MINUTES", "15")))
DB_PATH = os.getenv("DB_PATH", "jobs.sqlite3")
FEEDS_FILE = os.getenv("FEEDS_FILE", "feeds.txt")
FEED_TIMEOUT = max(5, int(os.getenv("FEED_TIMEOUT_SECONDS", "12")))
AI_TIMEOUT = max(5, int(os.getenv("AI_TIMEOUT_SECONDS", "20")))
MAX_ENTRIES = max(1, int(os.getenv("MAX_ENTRIES_PER_FEED", "20")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("freelance-ai")
scan_lock = asyncio.Lock()

KEYWORDS = [
    "product listing", "product images", "amazon listing", "ecommerce",
    "e-commerce", "product card", "product infographic", "listing design",
    "wildberries", "wildberries card", "ozon", "ÐºÐ°ÑÑÐ¾ÑÐº", "Ð¸Ð½ÑÐ¾Ð³ÑÐ°ÑÐ¸Ðº",
    "Ð´Ð¸Ð·Ð°Ð¹Ð½ ÑÐ¾Ð²Ð°ÑÐ°", "Ð¾ÑÐ¾ÑÐ¼Ð»ÐµÐ½Ð¸Ðµ ÑÐ¾Ð²Ð°ÑÐ°", "Ð¼Ð°ÑÐºÐµÑÐ¿Ð»ÐµÐ¹Ñ", "ÑÐ¾Ð²Ð°ÑÐ½Ð°Ñ ÐºÐ°ÑÑÐ¾ÑÐºÐ°"
]


def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS seen (key TEXT PRIMARY KEY, seen_at TEXT)")
    con.commit()
    return con


def is_owner(update: Update) -> bool:
    return bool(OWNER_ID) and update.effective_user and str(update.effective_user.id) == OWNER_ID


async def private(update: Update, text: str):
    if update.effective_chat:
        await update.effective_chat.send_message(text, disable_web_page_preview=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not OWNER_ID:
        await private(update, "ÐÐ¾Ñ Ð¿Ð¾ÑÑÐ¸ Ð½Ð°ÑÑÑÐ¾ÐµÐ½. Ð£Ð·Ð½Ð°Ð¹ ÑÐ²Ð¾Ð¹ Telegram ID ÐºÐ¾Ð¼Ð°Ð½Ð´Ð¾Ð¹ /myid, Ð·Ð°ÑÐµÐ¼ Ð²Ð¿Ð¸ÑÐ¸ ÐµÐ³Ð¾ Ð² OWNER_TELEGRAM_ID Ð² Ð¿ÐµÑÐµÐ¼ÐµÐ½Ð½ÑÑ Ð¾ÐºÑÑÐ¶ÐµÐ½Ð¸Ñ Ð¸ Ð¿ÐµÑÐµÐ·Ð°Ð¿ÑÑÑÐ¸ Ð±Ð¾ÑÐ°.")
        return
    if not is_owner(update):
        await private(update, "Ð­ÑÐ¾Ñ Ð±Ð¾Ñ Ð¿ÑÐ¸Ð²Ð°ÑÐ½ÑÐ¹.")
        return
    await private(update,
        "ÐÑÐ¸Ð²ÐµÑ, ÐÑÑÐ°! ð¤ Ð¯ Ð¸ÑÑ Ð·Ð°ÐºÐ°Ð·Ñ Ð½Ð° Ð¾ÑÐ¾ÑÐ¼Ð»ÐµÐ½Ð¸Ðµ ÐºÐ°ÑÑÐ¾ÑÐµÐº ÑÐ¾Ð²Ð°ÑÐ¾Ð² Ð¸ Ð¿ÑÐ¸ÑÑÐ»Ð°Ñ Ð¿Ð¾Ð´ÑÐ¾Ð´ÑÑÐ¸Ðµ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ.\n\n"
        "ÐÐ¾Ð¼Ð°Ð½Ð´Ñ:\n/status â ÑÐ¾ÑÑÐ¾ÑÐ½Ð¸Ðµ Ð±Ð¾ÑÐ°\n/scan â Ð¿ÑÐ¾Ð²ÐµÑÐ¸ÑÑ Ð¸ÑÑÐ¾ÑÐ½Ð¸ÐºÐ¸ ÑÐµÐ¹ÑÐ°Ñ\n/sources â ÑÐ¿Ð¸ÑÐ¾Ðº RSS-Ð¸ÑÑÐ¾ÑÐ½Ð¸ÐºÐ¾Ð²\n/myid â ÑÐ²Ð¾Ð¹ Telegram ID\n\n"
        "ÐÐ¾Ð¸ÑÐº Ð¸Ð´ÑÑ Ð¿Ð¾ Ð¿Ð¾Ð´ÐºÐ»ÑÑÑÐ½Ð½ÑÐ¼ RSS-Ð»ÐµÐ½ÑÐ°Ð¼. ÐÐ¾Ð±Ð°Ð²Ñ ÑÑÑÐ»ÐºÐ¸ Ð² feeds.txt Ð¸ Ð¿ÐµÑÐµÐ·Ð°Ð¿ÑÑÑÐ¸ Ð±Ð¾ÑÐ°.")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await private(update, f"Ð¢Ð²Ð¾Ð¹ Telegram ID: {update.effective_user.id if update.effective_user else 'Ð½Ðµ Ð¾Ð¿ÑÐµÐ´ÐµÐ»ÑÐ½'}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await private(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ. Ð¡Ð½Ð°ÑÐ°Ð»Ð° Ð½Ð°ÑÑÑÐ¾Ð¹ OWNER_TELEGRAM_ID Ð² Ð¿ÐµÑÐµÐ¼ÐµÐ½Ð½ÑÑ Ð¾ÐºÑÑÐ¶ÐµÐ½Ð¸Ñ.")
        return
    await private(update, f"ð¢ ÐÐ¾Ñ Ð·Ð°Ð¿ÑÑÐµÐ½\nÐÐ½ÑÐµÑÐ²Ð°Ð» Ð¿ÑÐ¾Ð²ÐµÑÐºÐ¸: {SCAN_MINUTES} Ð¼Ð¸Ð½.\nRSS-Ð¸ÑÑÐ¾ÑÐ½Ð¸ÐºÐ¾Ð²: {len(load_feeds())}\nÐÐ: {'Ð¿Ð¾Ð´ÐºÐ»ÑÑÑÐ½' if OPENAI_API_KEY else 'Ð½Ðµ Ð¿Ð¾Ð´ÐºÐ»ÑÑÑÐ½ (ÑÐ°Ð±Ð¾ÑÐ°ÐµÑ ÑÐ¸Ð»ÑÑÑ Ð¿Ð¾ ÐºÐ»ÑÑÐµÐ²ÑÐ¼ ÑÐ»Ð¾Ð²Ð°Ð¼)'}")


async def sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await private(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    feeds = load_feeds()
    await private(update, "ÐÐ¾Ð´ÐºÐ»ÑÑÑÐ½Ð½ÑÐµ RSS-Ð¸ÑÑÐ¾ÑÐ½Ð¸ÐºÐ¸:\n" + ("\n".join(f"â¢ {x}" for x in feeds) if feeds else "ÐÐ¾ÐºÐ° Ð½ÐµÑ. ÐÐ¾Ð±Ð°Ð²Ñ RSS-ÑÑÑÐ»ÐºÐ¸ Ð² feeds.txt."))


def load_feeds():
    p = Path(FEEDS_FILE)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
            and urlparse(line.strip()).scheme in ("http", "https")]


def already_seen(key):
    with db() as con:
        return con.execute("SELECT 1 FROM seen WHERE key=?", (key,)).fetchone() is not None


def mark_seen(key):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO seen(key, seen_at) VALUES (?, ?)",
                    (key, datetime.now(timezone.utc).isoformat()))
        con.commit()


def fetch_feed(feed_url):
    request = Request(feed_url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; FreelanceJobBot/1.0)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    with urlopen(request, timeout=FEED_TIMEOUT) as response:
        return feedparser.parse(response.read())


def ai_review(title, summary, link):
    keyword_match = any(k in (title + " " + summary).lower() for k in KEYWORDS)
    if not OPENAI_API_KEY:
        return keyword_match, 0, "Ð¡Ð¾Ð²Ð¿Ð°Ð´ÐµÐ½Ð¸Ðµ Ð¿Ð¾ ÐºÐ»ÑÑÐµÐ²ÑÐ¼ ÑÐ»Ð¾Ð²Ð°Ð¼"
    try:
        client = OpenAI(api_key=OPENAI_API_KEY, timeout=AI_TIMEOUT, max_retries=0)
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=(
                "Ð¢Ñ ÑÐ¸Ð»ÑÑÑ Ð·Ð°ÐºÐ°Ð·Ð¾Ð² Ð´Ð»Ñ ÑÑÐ¸Ð»Ð°Ð½ÑÐµÑÐ°, ÐºÐ¾ÑÐ¾ÑÑÐ¹ Ð´ÐµÐ»Ð°ÐµÑ Ð´Ð¸Ð·Ð°Ð¹Ð½ Ð¸ Ð¸Ð½ÑÐ¾Ð³ÑÐ°ÑÐ¸ÐºÑ "
                "ÐºÐ°ÑÑÐ¾ÑÐµÐº ÑÐ¾Ð²Ð°ÑÐ¾Ð² Ð´Ð»Ñ Ð¼Ð°ÑÐºÐµÑÐ¿Ð»ÐµÐ¹ÑÐ¾Ð². ÐÑÐµÐ½Ð¸ ÑÐ¾Ð»ÑÐºÐ¾ ÑÐ¾Ð¾ÑÐ²ÐµÑÑÑÐ²Ð¸Ðµ Ð·Ð°Ð´Ð°ÑÐ¸. "
                "ÐÐµ Ð²ÑÐ´ÑÐ¼ÑÐ²Ð°Ð¹ Ð±ÑÐ´Ð¶ÐµÑ Ð¸Ð»Ð¸ Ð´ÐµÑÐ°Ð»Ð¸. ÐÑÐ»Ð¸ ÑÑÐ¾ Ð·Ð°ÐºÐ°Ð· Ð½Ð° Ð¾ÑÐ¾ÑÐ¼Ð»ÐµÐ½Ð¸Ðµ ÐºÐ°ÑÑÐ¾ÑÐµÐº ÑÐ¾Ð²Ð°ÑÐ°, "
                "Ð¸Ð·Ð¾Ð±ÑÐ°Ð¶ÐµÐ½Ð¸Ñ ÑÐ¾Ð²Ð°ÑÐ°, Ð¸Ð½ÑÐ¾Ð³ÑÐ°ÑÐ¸ÐºÑ Ð¸Ð»Ð¸ Ð´Ð¸Ð·Ð°Ð¹Ð½ Ð»Ð¸ÑÑÐ¸Ð½Ð³Ð° â Ð¾ÑÐ²ÐµÑÑ MATCH; Ð¸Ð½Ð°ÑÐµ SKIP. "
                "Ð¤Ð¾ÑÐ¼Ð°Ñ ÑÑÑÐ¾Ð³Ð¾: MATCH|ÑÐ¸ÑÐ»Ð¾ Ð¾Ñ 0 Ð´Ð¾ 100|ÐºÑÐ°ÑÐºÐ°Ñ Ð¿ÑÐ¸ÑÐ¸Ð½Ð° ÐÐÐ SKIP.\n\n"
                f"ÐÐ°Ð³Ð¾Ð»Ð¾Ð²Ð¾Ðº: {title}\nÐÐ¿Ð¸ÑÐ°Ð½Ð¸Ðµ: {summary[:4000]}\nÐ¡ÑÑÐ»ÐºÐ°: {link}"
            ))
        result = response.output_text.strip()
        m = re.match(r"MATCH\|(\d{1,3})\|(.*)", result, re.I | re.S)
        if m:
            return True, min(100, int(m.group(1))), m.group(2).strip()[:300]
        return False, 0, "ÐÐµ Ð¿Ð¾Ð´ÑÐ¾Ð´Ð¸Ñ Ð¿Ð¾ Ð¾ÑÐµÐ½ÐºÐµ ÐÐ"
    except Exception:
        log.exception("AI review failed; using keyword filter")
        return keyword_match, 0, "Ð¡Ð¾Ð²Ð¿Ð°Ð´ÐµÐ½Ð¸Ðµ Ð¿Ð¾ ÐºÐ»ÑÑÐµÐ²ÑÐ¼ ÑÐ»Ð¾Ð²Ð°Ð¼ (ÐÐ Ð²ÑÐµÐ¼ÐµÐ½Ð½Ð¾ Ð½ÐµÐ´Ð¾ÑÑÑÐ¿ÐµÐ½)"


def scan():
    found, checked, errors = [], 0, 0
    feeds = load_feeds()
    for feed_url in feeds:
        try:
            parsed = fetch_feed(feed_url)
            if parsed.bozo and not parsed.entries:
                errors += 1
                log.warning("Feed parse error: %s: %s", feed_url, parsed.bozo_exception)
                continue
            checked += 1
            for entry in parsed.entries[:MAX_ENTRIES]:
                link = entry.get("link", "") or ""
                title = entry.get("title", "ÐÐµÐ· Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ñ") or "ÐÐµÐ· Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ñ"
                summary = re.sub(r"<[^>]+>", " ", entry.get("summary", "") or "")
                summary = re.sub(r"\s+", " ", summary).strip()
                key = entry.get("id") or link or (title + summary)
                if not key or already_seen(key):
                    continue
                mark_seen(key)
                match, score, reason = ai_review(title, summary, link)
                if match:
                    found.append((title, summary, link, score, reason, feed_url))
        except Exception as exc:
            errors += 1
            log.warning("Feed error: %s (%s)", feed_url, type(exc).__name__)
            log.debug("Feed exception details", exc_info=True)
    return found, checked, errors, len(feeds)


async def run_scan(app: Application):
    if not OWNER_ID:
        log.warning("OWNER_TELEGRAM_ID is not set; scan notifications are disabled")
        return None
    async with scan_lock:
        try:
            jobs, checked, errors, total = await asyncio.to_thread(scan)
            for title, summary, link, score, reason, source in jobs:
                text = (f"ð <b>ÐÐ¾Ð·Ð¼Ð¾Ð¶Ð½ÑÐ¹ Ð·Ð°ÐºÐ°Ð· Ð½Ð° ÐºÐ°ÑÑÐ¾ÑÐºÐ¸</b>\n\n"
                        f"<b>{escape_html(title[:300])}</b>\n"
                        f"{escape_html(summary[:900]) if summary else 'ÐÐ¿Ð¸ÑÐ°Ð½Ð¸Ðµ Ð½Ðµ ÑÐºÐ°Ð·Ð°Ð½Ð¾'}\n\n"
                        f"ð¤ ÐÑÐµÐ½ÐºÐ° ÑÐ¾Ð¾ÑÐ²ÐµÑÑÑÐ²Ð¸Ñ: {score}/100\n"
                        f"ð¡ {escape_html(reason)}\n"
                        f"ð {escape_html(link)}\n"
                        f"ÐÑÑÐ¾ÑÐ½Ð¸Ðº: {escape_html(urlparse(source).netloc)}")
                await app.bot.send_message(chat=int(OWNER_ID), text=text, parse_mode="HTML",
                                           disable_web_page_preview=True)
            return {"found": len(jobs), "checked": checked, "errors": errors, "total": total}
        except Exception:
            log.exception("Scan failed")
            return None


def escape_html(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await private(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    if scan_lock.locked():
        await private(update, "â³ ÐÐ¾Ð¸ÑÐº ÑÐ¶Ðµ Ð²ÑÐ¿Ð¾Ð»Ð½ÑÐµÑÑÑ. ÐÐ¾Ð¶Ð´Ð¸ÑÑ ÐµÐ³Ð¾ Ð·Ð°Ð²ÐµÑÑÐµÐ½Ð¸Ñ.")
        return
    await private(update, "ð ÐÑÐ¾Ð²ÐµÑÑÑ RSS-Ð¸ÑÑÐ¾ÑÐ½Ð¸ÐºÐ¸. ÐÐµÐ´Ð¾ÑÑÑÐ¿Ð½ÑÐµ Ð»ÐµÐ½ÑÑ Ð±ÑÐ´ÑÑ Ð¿ÑÐ¾Ð¿ÑÑÐµÐ½Ñâ¦")
    result = await run_scan(context.application)
    if result is None:
        await private(update, "â ï¸ ÐÑÐ¾Ð²ÐµÑÐºÐ° Ð·Ð°Ð²ÐµÑÑÐ¸Ð»Ð°ÑÑ Ñ Ð¾ÑÐ¸Ð±ÐºÐ¾Ð¹. ÐÐ¾ÑÐ¼Ð¾ÑÑÐ¸ Ð¶ÑÑÐ½Ð°Ð» FadeHost.")
    elif result["total"] == 0:
        await private(update, "Ð feeds.txt Ð¿Ð¾ÐºÐ° Ð½ÐµÑ RSS-Ð¸ÑÑÐ¾ÑÐ½Ð¸ÐºÐ¾Ð².")
    else:
        await private(update, "â ÐÑÐ¾Ð²ÐµÑÐºÐ° Ð·Ð°Ð²ÐµÑÑÐµÐ½Ð°.\n"
                             f"Ð£ÑÐ¿ÐµÑÐ½Ð¾ Ð¿ÑÐ¾Ð²ÐµÑÐµÐ½Ð¾ Ð¸ÑÑÐ¾ÑÐ½Ð¸ÐºÐ¾Ð²: {result['checked']} Ð¸Ð· {result['total']}\n"
                             f"ÐÑÑÐ¾ÑÐ½Ð¸ÐºÐ¾Ð² Ñ Ð¾ÑÐ¸Ð±ÐºÐ°Ð¼Ð¸: {result['errors']}\n"
                             f"ÐÐ¾Ð²ÑÑ Ð¿Ð¾Ð´ÑÐ¾Ð´ÑÑÐ¸Ñ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ð¹: {result['found']}\n\n"
                             "ÐÑÐ»Ð¸ Ð·Ð°ÐºÐ°Ð·Ð¾Ð² Ð½ÐµÑ, ÑÑÐ¾ Ð½Ðµ Ð¾Ð±ÑÐ·Ð°ÑÐµÐ»ÑÐ½Ð¾ Ð¾ÑÐ¸Ð±ÐºÐ°: Ð² Ð½Ð¾Ð²ÑÑ Ð¿ÑÐ±Ð»Ð¸ÐºÐ°ÑÐ¸ÑÑ Ð¼Ð¾Ð³Ð»Ð¾ Ð½Ðµ Ð±ÑÑÑ Ð¿Ð¾Ð´ÑÐ¾Ð´ÑÑÐ¸Ñ Ð·Ð°Ð´Ð°Ñ.")


async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    result = await run_scan(context.application)
    if result:
        log.info("Scheduled scan complete: checked=%s/%s errors=%s found=%s",
                 result["checked"], result["total"], result["errors"], result["found"])


async def post_init(app: Application):
    if OWNER_ID:
        app.job_queue.run_repeating(scheduled_scan, interval=SCAN_MINUTES * 60,
                                    first=5, name="job-search")


def main():
    if not BOT_TOKEN:
        raise SystemExit("ÐÐµ Ð·Ð°Ð´Ð°Ð½ TELEGRAM_BOT_TOKEN Ð² Ð¿ÐµÑÐµÐ¼ÐµÐ½Ð½ÑÑ Ð¾ÐºÑÑÐ¶ÐµÐ½Ð¸Ñ")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("sources", sources))
    app.add_handler(CommandHandler("scan", scan_command))
    app.run_polling()


if __name__ == "__main__":
    main()
