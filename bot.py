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
from google import genai
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
    "wildberries", "wildberries card", "ozon", "карточк", "инфографик",
    "дизайн товара", "оформление товара", "маркетплейс", "товарная карточка"
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
        await private(update, "Бот почти настроен. Узнай свой Telegram ID командой /myid, затем впиши его в OWNER_TELEGRAM_ID в переменных окружения и перезапусти бота.")
        return
    if not is_owner(update):
        await private(update, "Этот бот приватный.")
        return
    await private(update,
        "Привет, Лёха! 🤖 Я ищу заказы на оформление карточек товаров и присылаю подходящие объявления.\n\n"
        "Команды:\n/status — состояние бота\n/scan — проверить источники сейчас\n/sources — список RSS-источников\n/myid — твой Telegram ID\n\n"
        "Поиск идёт по подключённым RSS-лентам. Добавь ссылки в feeds.txt и перезапусти бота.")


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await private(update, f"Твой Telegram ID: {update.effective_user.id if update.effective_user else 'не определён'}")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await private(update, "Доступ закрыт. Сначала настрой OWNER_TELEGRAM_ID в переменных окружения.")
        return
   await private(update, f"🟢 Бот запущен\nИнтервал проверки: {SCAN_MINUTES} мин.\nRSS-источников: {len(load_feeds())}\nИИ: {'подключён' if os.getenv('GEMINI_API_KEY', '').strip() else 'не подключён (работает фильтр по ключевым словам)'}")


async def sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await private(update, "Доступ закрыт.")
        return
    feeds = load_feeds()
    await private(update, "Подключённые RSS-источники:\n" + ("\n".join(f"• {x}" for x in feeds) if feeds else "Пока нет. Добавь RSS-ссылки в feeds.txt."))


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
    keyword_match = any(
        k in (title + " " + summary).lower()
        for k in KEYWORDS
    )

    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        return keyword_match, 0, "Совпадение по ключевым словам"

    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                "Ты фильтр заказов для фрилансера, "
                "который занимается дизайном карточек товаров "
                "и инфографикой для маркетплейсов.\n"
                "Определи, подходит ли объявление.\n"
                "Если подходит, ответь строго в формате:\n"
                "MATCH|число от 0 до 100|краткая причина\n"
                "Если не подходит, ответь SKIP.\n\n"
                f"Заголовок: {title}\n"
                f"Описание: {summary[:4000]}\n"
                f"Ссылка: {link}"
            )
        )

        result = (response.text or "").strip()
        match = re.match(
            r"MATCH\|(\d{1,3})\|(.*)",
            result,
            re.I | re.S
        )

        if match:
            return (
                True,
                min(100, int(match.group(1))),
                match.group(2).strip()[:300]
            )

        return False, 0, "Не подходит по оценке ИИ"

    except Exception:
        log.exception("Gemini review failed; using keyword filter")
        return (
            keyword_match,
            0,
            "Совпадение по ключевым словам (ИИ временно недоступен)"
        )


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
                title = entry.get("title", "Без названия") or "Без названия"
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
                text = (f"🆕 <b>Возможный заказ на карточки</b>\n\n"
                        f"<b>{escape_html(title[:300])}</b>\n"
                        f"{escape_html(summary[:900]) if summary else 'Описание не указано'}\n\n"
                        f"🤖 Оценка соответствия: {score}/100\n"
                        f"💡 {escape_html(reason)}\n"
                        f"🔗 {escape_html(link)}\n"
                        f"Источник: {escape_html(urlparse(source).netloc)}")
                await app.bot.send_message(chat_id=int(OWNER_ID), text=text, parse_mode="HTML",
                                           disable_web_page_preview=True)
            return {"found": len(jobs), "checked": checked, "errors": errors, "total": total}
        except Exception:
            log.exception("Scan failed")
            return None


def escape_html(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await private(update, "Доступ закрыт.")
        return
    if scan_lock.locked():
        await private(update, "⏳ Поиск уже выполняется. Дождись его завершения.")
        return
    await private(update, "🔎 Проверяю RSS-источники. Недоступные ленты будут пропущены…")
    result = await run_scan(context.application)
    if result is None:
        await private(update, "⚠️ Проверка завершилась с ошибкой. Посмотри журнал FadeHost.")
    elif result["total"] == 0:
        await private(update, "В feeds.txt пока нет RSS-источников.")
    else:
        await private(update, "✅ Проверка завершена.\n"
                             f"Успешно проверено источников: {result['checked']} из {result['total']}\n"
                             f"Источников с ошибками: {result['errors']}\n"
                             f"Новых подходящих объявлений: {result['found']}\n\n"
                             "Если заказов нет, это не обязательно ошибка: в новых публикациях могло не быть подходящих задач.")


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
        raise SystemExit("Не задан TELEGRAM_BOT_TOKEN в переменных окружения")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("sources", sources))
    app.add_handler(CommandHandler("scan", scan_command))
    app.run_polling()


if __name__ == "__main__":
    main()
