
import html
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()
TG_API_ID = os.getenv("TG_API_ID", "").strip()
TG_API_HASH = os.getenv("TG_API_HASH", "").strip()
TELETHON_SESSION = os.getenv("TELETHON_SESSION", "").strip()
SCAN_MINUTES = max(5, int(os.getenv("SCAN_MINUTES", "15")))
DB_PATH = os.getenv("DB_PATH", "jobs.sqlite3")
MAX_MESSAGES_PER_CHANNEL = max(1, int(os.getenv("MAX_MESSAGES_PER_CHANNEL", "30")))

# Начальный список. Доступность и активность каналов проверяются при запуске.
CHANNELS = [
    "@MPdesigns",
    "@free_design1",
    "@infograficdz",
    "@zakaz_design",
    "@designwork_vacansii",
    "@remotejobss",
    "@workmarketplaces",
    "@marketplacejob",
    "@design_vacancy",
    "@Designs_squad",
    "@freelancetaverna",
    "@FreelanceBay",
]

POSITIVE = [
    "ищу дизайнера", "нужен дизайнер", "нужна дизайнер", "требуется дизайнер",
    "ищем дизайнера", "ищу инфограф", "нужна инфограф", "инфографика",
    "карточк", "wildberries", "wildberries", "wb", "ozon", "озон",
    "маркетплейс", "дизайн товара", "оформление товара", "слайд для товара",
    "дизайн для товара", "карточек товара",
]
NEGATIVE = [
    "предлагаю услуги", "мои услуги", "портфолио дизайнера", "ищу работу",
    "ищу заказы", "возьму заказ", "обучение", "курс", "вебинар",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("freelance-bot")
scan_lock = asyncio.Lock()
user_client = None


def db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.execute(
        "CREATE TABLE IF NOT EXISTS seen "
        "(key TEXT PRIMARY KEY, seen_at TEXT NOT NULL)"
    )
    con.commit()
    return con


def is_owner(update: Update) -> bool:
    return (
        bool(OWNER_ID)
        and update.effective_user is not None
        and str(update.effective_user.id) == OWNER_ID
    )


async def reply(update: Update, text: str):
    if update.effective_chat:
        await update.effective_chat.send_message(
            text=text, disable_web_page_preview=True
        )


def is_relevant(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower())
    if any(word in normalized for word in NEGATIVE):
        return False
    return any(word in normalized for word in POSITIVE)


def was_seen(key: str) -> bool:
    with db() as con:
        return con.execute("SELECT 1 FROM seen WHERE key=?", (key,)).fetchone() is not None


def mark_seen(key: str):
    with db() as con:
        con.execute(
            "INSERT OR IGNORE INTO seen(key, seen_at) VALUES (?, ?)",
            (key, datetime.now(timezone.utc).isoformat()),
        )
        con.commit()


async def scan_channels(app: Application):
    global user_client
    if user_client is None or not user_client.is_connected():
        raise RuntimeError("Telegram user session is not connected")

    checked = errors = found = 0
    for channel in CHANNELS:
        try:
            entity = await user_client.get_entity(channel)
            checked += 1
            async for message in user_client.iter_messages(
                entity, limit=MAX_MESSAGES_PER_CHANNEL
            ):
                body = (message.message or "").strip()
                if not body:
                    continue
                key = f"{entity.id}:{message.id}"
                if was_seen(key):
                    continue
                # Помечаем просмотренным, чтобы не обрабатывать старые сообщения повторно.
                mark_seen(key)
                if not is_relevant(body):
                    continue

                link = f"https://t.me/{channel.lstrip('@')}/{message.id}"
                text = (
                    "🆕 <b>Возможный заказ на дизайн карточек</b>\n\n"
                    f"{html.escape(body[:3500])}\n\n"
                    f'📣 Источник: {html.escape(channel)}\n'
                    f'<a href="{html.escape(link, quote=True)}">Открыть сообщение</a>'
                )
                await app.bot.send_message(
                    chat_id=int(OWNER_ID),
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                found += 1
        except Exception as exc:
            errors += 1
            log.warning("Channel scan failed: %s (%s)", channel, type(exc).__name__)
    return {"checked": checked, "errors": errors, "found": found, "total": len(CHANNELS)}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "Доступ закрыт. Проверь OWNER_TELEGRAM_ID.")
        return
    await reply(
        update,
        "Привет! Я ищу объявления о заказах на дизайн карточек товаров.\n\n"
        "/status — состояние\n/scan — проверить каналы сейчас\n"
        "Поиск работает без нейросети.",
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(
        update,
        f"Твой Telegram ID: {update.effective_user.id if update.effective_user else 'не определён'}",
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "Доступ закрыт.")
        return
    connected = user_client is not None and user_client.is_connected()
    await reply(
        update,
        f"🟢 Бот запущен\n"
        f"Telegram-аккаунт подключён: {'да' if connected else 'нет'}\n"
        f"Каналов в списке: {len(CHANNELS)}\n"
        f"Интервал проверки: {SCAN_MINUTES} мин.",
    )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "Доступ закрыт.")
        return
    if scan_lock.locked():
        await reply(update, "⏳ Проверка уже выполняется.")
        return
    await reply(update, "🔎 Проверяю Telegram-каналы…")
    result = await run_scan(context.application)
    if result is None:
        await reply(update, "⚠️ Проверка не завершилась. Посмотри журнал FadeHost.")
    else:
        await reply(
            update,
            "✅ Проверка завершена.\n"
            f"Доступно каналов: {result['checked']} из {result['total']}\n"
            f"Ошибок: {result['errors']}\n"
            f"Новых подходящих объявлений: {result['found']}",
        )


async def run_scan(app: Application):
    if not OWNER_ID:
        log.warning("OWNER_TELEGRAM_ID is not set; notifications disabled")
        return None
    async with scan_lock:
        try:
            return await scan_channels(app)
        except Exception:
            log.exception("Scan failed")
            return None


async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    result = await run_scan(context.application)
    if result:
        log.info(
            "Scan complete: checked=%s/%s errors=%s found=%s",
            result["checked"], result["total"], result["errors"], result["found"],
        )


async def post_init(app: Application):
    global user_client
    if not all([TG_API_ID, TG_API_HASH, TELETHON_SESSION]):
        log.warning("Telegram user session settings are incomplete")
        return
    user_client = TelegramClient(
        StringSession(TELETHON_SESSION), int(TG_API_ID), TG_API_HASH
    )
    await user_client.connect()
    if not await user_client.is_user_authorized():
        raise RuntimeError("TELETHON_SESSION is not authorized")
    log.info("Telegram user session connected")
    if OWNER_ID:
        app.job_queue.run_repeating(
            scheduled_scan,
            interval=SCAN_MINUTES * 60,
            first=5,
            name="telegram-channel-search",
        )


async def post_shutdown(app: Application):
    global user_client
    if user_client is not None and user_client.is_connected():
        await user_client.disconnect()


def main():
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    if not OWNER_ID:
        log.warning("OWNER_TELEGRAM_ID is not set; notifications are disabled")
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("scan", scan_command))
    app.run_polling()


if __name__ == "__main__":
    main()
