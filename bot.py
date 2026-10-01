import asyncio
import html
import logging
import os
import re
import sqlite3
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter, TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OWNER_ID = os.getenv("OWNER_TELEGRAM_ID", "").strip()
FRIEND_ID = "8476118466"
ALLOWED_USER_IDS = {x for x in (OWNER_ID, FRIEND_ID) if x.isdigit()}

TG_API_ID = os.getenv("TG_API_ID", "").strip()
TG_API_HASH = os.getenv("TG_API_HASH", "").strip()
TELETHON_SESSION = os.getenv("TELETHON_SESSION", "").strip()

SCAN_MINUTES = max(5, int(os.getenv("SCAN_MINUTES", "15")))
DB_PATH = os.getenv("DB_PATH", "jobs.sqlite3")
MAX_MESSAGES_PER_CHANNEL = max(
    1, int(os.getenv("MAX_MESSAGES_PER_CHANNEL", "30"))
)
MAX_AGE_HOURS = max(1, int(os.getenv("MAX_AGE_HOURS", "24")))
SEND_DELAY = max(1, int(os.getenv("SEND_DELAY", "2")))

CHANNELS = [
    '@MPdesigns',
    '@free_design1',
    '@infograficdz',
    '@zakaz_design',
    '@designwork_vacansii',
    '@remotejobss',
    '@workmarketplaces',
    '@marketplacejob',
    '@design_vacancy',
    '@Designs_squad',
    '@freelancetaverna',
    '@FreelanceBay',
    '@dizain_wb_ozon',
    '@dizainer_wb',
    '@wb_ozon_designers',
    '@designers_wb_ozon',
    '@dizainerplace',
    '@infografikamptop',
    '@dizainery_wildberries_ozon',
    '@Designs_job',
    '@designer_jobs',
    '@design_freevacancies',
    '@designer_vacancies',
    '@vakansii_design',
    '@vakansii_dizaynerov',
    '@dsgn_vacancies',
    '@vakansi_rus',
    '@workfordesigner',
    '@designer_work',
    '@design_profii',
    '@design_crate',
    '@fordesigner',
    '@junior_designers',
    '@motionhunter',
    '@designhunters',
    '@FrWork3',
    '@rueventjob',
    '@frilans_na_legke',
    '@digital_rabota',
    '@proffreelancee',
    '@TRemoters',
    '@udafrii',
    '@FreeWorkFeed',
    '@workk_on',
    # Зарубежные каналы (английский/испанский)
    '@remotegraphicdesignjobs',
    '@findmyremote_design',
]
# Строгий фильтр: пропускаем только явный поиск исполнителя/дизайнера.
# Общие слова вроде «инфографика», «WB» и «карточки» сами по себе не подходят.
POSITIVE = [
    "ищу дизайнера",
    "ищем дизайнера",
    "нужен дизайнер",
    "нужна дизайнер",
    "нужен дизайнер карточек",
    "требуется дизайнер",
    "требуется дизайнер карточек",
    "ищу дизайнера карточек",
    "ищем дизайнера карточек",
    "ищу инфографиста",
    "ищем инфографиста",
    "нужен инфографист",
    "нужна инфографист",
    "требуется инфографист",
    "ищу исполнителя",
    "ищем исполнителя",
    "нужен исполнитель",
    "нужна исполнитель",
    "требуется исполнитель",
    "ищу специалиста по дизайну",
    "ищем специалиста по дизайну",
    "нужен специалист по дизайну",
    "нужен дизайнер для",
    "нужна дизайнер для",
    "заказ на дизайн",
    "есть заказ на дизайн",
    "ищу человека для дизайна",
    # Логотипы, баннеры и фирменный стиль (русский)
    "ищу дизайнера логотипа",
    "ищем дизайнера логотипа",
    "нужен дизайнер логотипа",
    "нужен дизайнер для логотипа",
    "заказать логотип",
    "заказ на логотип",
    "ищу дизайнера баннеров",
    "ищем дизайнера баннеров",
    "нужен дизайнер баннеров",
    "нужен дизайнер для баннера",
    "заказать баннер",
    "заказ на баннер",
    "ищу дизайнера фирменного стиля",
    "нужен дизайнер фирменного стиля",
    # Английские формулировки заказов в зарубежных каналах
    "looking for a designer",
    "looking for graphic designer",
    "looking for a graphic designer",
    "hiring a designer",
    "we are hiring a designer",
    "need a designer",
    "need graphic designer",
    "need a graphic designer",
    "looking for logo designer",
    "looking for a logo designer",
    "need a logo designer",
    "logo design job",
    "logo design project",
    "looking for a banner designer",
    "need a banner designer",
    "banner design job",
    "banner design project",
    "designer wanted",
    "graphic designer wanted",
]

NEGATIVE = [
    "предлагаю услуги",
    "оказываю услуги",
    "мои услуги",
    "услуги дизайнера",
    "я дизайнер",
    "дизайнер на связи",
    "ищу работу",
    "ищу заказы",
    "ищу заказчиков",
    "ищу клиентов",
    "ищу проекты",
    "возьму заказ",
    "возьму заказы",
    "свободен для заказов",
    "свободна для заказов",
    "портфолио",
    "обучение",
    "курс",
    "вебинар",
    # Англоязычная самореклама и поиск заказов самим исполнителем
    "i am a designer",
    "i'm a designer",
    "my portfolio",
    "my services",
    "offering design services",
    "designer for hire",
    "available for freelance work",
    "looking for clients",
    "looking for freelance projects",
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
    con.execute(
        "CREATE TABLE IF NOT EXISTS jobs "
        "(key TEXT PRIMARY KEY, body TEXT NOT NULL, channel TEXT NOT NULL, "
        "link TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS user_prefs "
        "(user_id TEXT PRIMARY KEY, paused INTEGER NOT NULL DEFAULT 0, keyword TEXT NOT NULL DEFAULT '')"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS decisions "
        "(user_id TEXT NOT NULL, job_key TEXT NOT NULL, decision TEXT NOT NULL, "
        "decided_at TEXT NOT NULL, PRIMARY KEY(user_id, job_key))"
    )
    con.commit()
    return con


def is_owner(update: Update) -> bool:
    return (
        update.effective_user is not None
        and str(update.effective_user.id) in ALLOWED_USER_IDS
    )


async def reply(update: Update, text: str):
    if update.effective_chat:
        await update.effective_chat.send_message(
            text=text,
            disable_web_page_preview=True,
        )


def is_relevant(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower().replace("ё", "е"))
    # Сначала отсекаем саморекламу и предложения услуг.
    if any(word in normalized for word in NEGATIVE):
        return False
    # Требуем явную формулировку, что автор ищет исполнителя.
    return any(word in normalized for word in POSITIVE)


def was_seen(key: str) -> bool:
    with db() as con:
        return con.execute(
            "SELECT 1 FROM seen WHERE key=?", (key,)
        ).fetchone() is not None


def mark_seen(key: str):
    with db() as con:
        con.execute(
            "INSERT OR IGNORE INTO seen(key, seen_at) VALUES (?, ?)",
            (key, datetime.now(timezone.utc).isoformat()),
        )
        con.commit()


def is_recent(message) -> bool:
    if not message.date:
        return False
    message_date = message.date
    if message_date.tzinfo is None:
        message_date = message_date.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - message_date
    return timedelta(0) <= age <= timedelta(hours=MAX_AGE_HOURS)


async def send_notification(app: Application, text: str):
    sent_to_all = True
    for user_id in sorted(ALLOWED_USER_IDS):
        try:
            await app.bot.send_message(
                chat_id=int(user_id),
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            await asyncio.sleep(SEND_DELAY)
        except RetryAfter as exc:
            wait_time = exc.retry_after
            if hasattr(wait_time, "total_seconds"):
                wait_time = wait_time.total_seconds()
            log.warning("Telegram rate limit. Waiting %s seconds", wait_time)
            await asyncio.sleep(float(wait_time) + 1)
            try:
                await app.bot.send_message(
                    chat_id=int(user_id),
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(SEND_DELAY)
            except TelegramError as retry_exc:
                sent_to_all = False
                log.warning(
                    "Notification failed for user %s after retry: %s",
                    user_id, type(retry_exc).__name__,
                )
        except TelegramError as exc:
            sent_to_all = False
            log.warning(
                "Notification failed for user %s: %s",
                user_id, type(exc).__name__,
            )
    return sent_to_all


async def scan_channels(app: Application):
    global user_client
    if user_client is None or not user_client.is_connected():
        raise RuntimeError("Telegram user session is not connected")

    checked = errors = found = old = 0

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

                if not is_recent(message):
                    mark_seen(key)
                    old += 1
                    continue

                if not is_relevant(body):
                    mark_seen(key)
                    continue

                link = f"https://t.me/{channel.lstrip('@')}/{message.id}"
                with db() as con:
                    con.execute(
                        "INSERT OR IGNORE INTO jobs(key, body, channel, link, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (key, body[:3500], channel, link, message.date.isoformat()),
                    )
                    con.commit()
                found += 1
                mark_seen(key)

        except Exception as exc:
            errors += 1
            log.warning(
                "Channel scan failed: %s (%s)",
                channel, type(exc).__name__,
            )

    if found:
        for user_id in sorted(ALLOWED_USER_IDS):
            if is_paused(user_id):
                continue
            count = pending_count(user_id)
            if count:
                try:
                    await app.bot.send_message(
                        chat_id=int(user_id),
                        text=f"🆕 Найдено новых заказов: {found}\n📋 У тебя ожидают просмотра: {count}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👀 Смотреть заказы", callback_data="queue:open")]]),
                    )
                except TelegramError as exc:
                    log.warning("Queue notice failed for %s: %s", user_id, type(exc).__name__)

    return {
        "checked": checked,
        "errors": errors,
        "found": found,
        "old": old,
        "total": len(CHANNELS),
    }


def get_pref(user_id: str):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO user_prefs(user_id) VALUES (?)", (str(user_id),))
        row = con.execute("SELECT paused, keyword FROM user_prefs WHERE user_id=?", (str(user_id),)).fetchone()
        con.commit()
    return bool(row[0]), row[1] or ""


def is_paused(user_id: str) -> bool:
    return get_pref(user_id)[0]


def set_paused(user_id: str, paused: bool):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO user_prefs(user_id) VALUES (?)", (str(user_id),))
        con.execute("UPDATE user_prefs SET paused=? WHERE user_id=?", (int(paused), str(user_id)))
        con.commit()


def set_keyword(user_id: str, keyword: str):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO user_prefs(user_id) VALUES (?)", (str(user_id),))
        con.execute("UPDATE user_prefs SET keyword=? WHERE user_id=?", (keyword, str(user_id)))
        con.commit()


def pending_jobs(user_id: str):
    _, keyword = get_pref(user_id)
    with db() as con:
        rows = con.execute(
            "SELECT j.key, j.body, j.channel, j.link FROM jobs j "
            "LEFT JOIN decisions d ON d.job_key=j.key AND d.user_id=? "
            "WHERE d.job_key IS NULL ORDER BY j.created_at DESC, j.key DESC",
            (str(user_id),),
        ).fetchall()
    if keyword:
        needle = keyword.casefold()
        rows = [row for row in rows if needle in row[1].casefold()]
    return rows


def pending_count(user_id: str) -> int:
    return len(pending_jobs(user_id))


def saved_count(user_id: str) -> int:
    with db() as con:
        return con.execute(
            "SELECT COUNT(*) FROM decisions WHERE user_id=? AND decision='keep'",
            (str(user_id),),
        ).fetchone()[0]


async def show_next(query, user_id: str):
    jobs = pending_jobs(user_id)
    if not jobs:
        await query.edit_message_text(
            f"🎉 Все объявления просмотрены!\n⭐ Сохранено: {saved_count(user_id)}",
            reply_markup=None,
        )
        return
    key, body, channel, link = jobs[0]
    total = len(jobs)
    # Номер текущего объявления относительно уже просмотренных в этой очереди.
    with db() as con:
        reviewed = con.execute(
            "SELECT COUNT(*) FROM decisions WHERE user_id=?", (str(user_id),)
        ).fetchone()[0]
    number = reviewed + 1
    text = (
        f"📋 <b>Заказ {number} из {number + total - 1}</b>\n"
        f"⭐ Сохранено: {saved_count(user_id)}\n\n"
        f"{html.escape(body)}\n\n"
        f"📣 Источник: {html.escape(channel)}\n"
        f'<a href="{html.escape(link, quote=True)}">Открыть оригинал</a>'
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Пропустить", callback_data=f"queue:skip:{key}"),
         InlineKeyboardButton("✅ Оставить", callback_data=f"queue:keep:{key}")],
        [InlineKeyboardButton("🇷🇺 Перевести", callback_data=f"queue:translate:{key}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="queue:back")],
    ])
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)


def translate_to_russian(text: str) -> str:
    """Переводит текст через публичный Google Translate endpoint."""
    params = urllib.parse.urlencode({
        "client": "gtx", "sl": "auto", "tl": "ru", "dt": "t", "q": text[:4000]
    })
    request = urllib.request.Request(
        "https://translate.googleapis.com/translate_a/single?" + params,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in data[0] if part and part[0])


async def queue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    if user_id not in ALLOWED_USER_IDS:
        await query.answer("Доступ закрыт.", show_alert=True)
        return
    await query.answer()
    data = query.data or ""
    if data.startswith("queue:translate:"):
        key = data.split(":", 2)[2]
        with db() as con:
            row = con.execute("SELECT body FROM jobs WHERE key=?", (key,)).fetchone()
        if not row:
            await query.answer("Объявление не найдено.", show_alert=True)
            return
        await query.answer("Перевожу…")
        try:
            translated = await asyncio.to_thread(translate_to_russian, row[0])
            # Ограничение Telegram на длину сообщения; кнопки остаются доступными.
            translated = translated[:3500]
            await query.message.reply_text(
                "🇷🇺 <b>Перевод на русский</b>\\n\\n" + html.escape(translated),
                parse_mode="HTML", disable_web_page_preview=True,
            )
        except Exception as exc:
            log.warning("Translation failed: %s", type(exc).__name__)
            await query.message.reply_text(
                "⚠️ Не удалось перевести. Попробуй позже."
            )
        return
    if data == "queue:open":
        await show_next(query, user_id)
        return
    if data == "queue:back":
        with db() as con:
            row = con.execute(
                "SELECT job_key FROM decisions WHERE user_id=? ORDER BY decided_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if row:
                con.execute("DELETE FROM decisions WHERE user_id=? AND job_key=?", (user_id, row[0]))
                con.commit()
        await show_next(query, user_id)
        return
    parts = data.split(":", 2)
    if len(parts) == 3 and parts[1] in ("skip", "keep"):
        decision = "keep" if parts[1] == "keep" else "skip"
        with db() as con:
            con.execute(
                "INSERT OR IGNORE INTO decisions(user_id, job_key, decision, decided_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, parts[2], decision, datetime.now(timezone.utc).isoformat()),
            )
            con.commit()
        await show_next(query, user_id)


async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "Доступ закрыт.")
        return
    user_id = str(update.effective_user.id)
    with db() as con:
        rows = con.execute(
            "SELECT j.body, j.link FROM jobs j JOIN decisions d ON d.job_key=j.key "
            "WHERE d.user_id=? AND d.decision='keep' ORDER BY d.decided_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
    if not rows:
        await reply(update, "⭐ Пока нет сохранённых заказов.")
        return
    text = "⭐ <b>Сохранённые заказы</b>\n\n" + "\n\n".join(
        f"{i}. {html.escape(body[:700])}\n<a href=\"{html.escape(link, quote=True)}\">Открыть оригинал</a>"
        for i, (body, link) in enumerate(rows, 1)
    )
    await update.effective_chat.send_message(text=text, parse_mode="HTML", disable_web_page_preview=True)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "Доступ закрыт.")
        return
    user_id = str(update.effective_user.id)
    with db() as con:
        total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        kept = con.execute("SELECT COUNT(*) FROM decisions WHERE user_id=? AND decision='keep'", (user_id,)).fetchone()[0]
        skipped = con.execute("SELECT COUNT(*) FROM decisions WHERE user_id=? AND decision='skip'", (user_id,)).fetchone()[0]
    paused, keyword = get_pref(user_id)
    await reply(update, f"📊 Твоя статистика\nВсего найдено: {total}\n⭐ Сохранено: {kept}\n❌ Пропущено: {skipped}\n⏳ Ожидают просмотра: {pending_count(user_id)}\nУведомления: {'пауза' if paused else 'включены'}\nФильтр: {html.escape(keyword) if keyword else 'не задан'}")


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "Доступ закрыт.")
        return
    user_id = str(update.effective_user.id)
    paused, _ = get_pref(user_id)
    set_paused(user_id, not paused)
    await reply(update, "⏸️ Уведомления приостановлены. Очередь доступна командой /queue." if not paused else "▶️ Уведомления снова включены.")


async def filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "Доступ закрыт.")
        return
    user_id = str(update.effective_user.id)
    keyword = " ".join(context.args).strip()
    if keyword.lower() == "clear":
        keyword = ""
    set_keyword(user_id, keyword)
    await reply(update, (f"🔍 Фильтр установлен: {html.escape(keyword)}\nВ очереди: {pending_count(user_id)}" if keyword else "🔍 Фильтр очищен. Показываю все подходящие объявления."))


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "Доступ закрыт.")
        return
    user_id = str(update.effective_user.id)
    jobs = pending_jobs(user_id)
    if not jobs:
        await reply(update, "📭 Нет объявлений для просмотра. Попробуй /scan или очисти фильтр командой /filter clear.")
        return
    await update.effective_chat.send_message(
        text=f"📋 Найдено для просмотра: {len(jobs)}\nНажми кнопку, чтобы начать.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👀 Смотреть заказы", callback_data="queue:open")]]),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "Доступ закрыт.")
        return
    await reply(
        update,
        "Привет! Я ищу свежие объявления о заказах на дизайн карточек товаров.\n\n"
        f"Возраст объявлений: до {MAX_AGE_HOURS} ч.\n"
        f"Интервал проверки: {SCAN_MINUTES} мин.\n\n"
        "/status — состояние\n"
        "/scan — проверить каналы сейчас\n"
        "/saved — сохранённые заказы\n"
        "/stats — статистика\n"
        "/queue — открыть очередь\n"
        "/pause — пауза/возобновление уведомлений\n"
        "/filter слово — фильтр по словам; /filter clear — сброс\n"
        "/myid — узнать Telegram ID\n"
        "Поиск работает без нейросети.",
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(
        update,
        f"Твой Telegram ID: "
        f"{update.effective_user.id if update.effective_user else 'не определён'}",
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
        f"Пользователей: {len(ALLOWED_USER_IDS)}\n"
        f"Каналов в списке: {len(CHANNELS)}\n"
        f"Интервал проверки: {SCAN_MINUTES} мин.\n"
        f"Максимальный возраст заявки: {MAX_AGE_HOURS} ч.",
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
            f"Новых подходящих объявлений: {result['found']}\n"
            f"Старых объявлений пропущено: {result['old']}",
        )


async def run_scan(app: Application):
    if not ALLOWED_USER_IDS:
        log.warning("No allowed Telegram user IDs are configured")
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
            "Scan complete: checked=%s/%s errors=%s found=%s old=%s",
            result["checked"], result["total"], result["errors"],
            result["found"], result["old"],
        )


async def post_init(app: Application):
    global user_client
    if not all([TG_API_ID, TG_API_HASH, TELETHON_SESSION]):
        log.warning("Telegram user session settings are incomplete")
        return

    user_client = TelegramClient(
        StringSession(TELETHON_SESSION),
        int(TG_API_ID),
        TG_API_HASH,
    )
    await user_client.connect()
    me = await user_client.get_me()
    log.info("Telegram session is_bot=%s", me.bot)

    if not await user_client.is_user_authorized():
        raise RuntimeError("TELETHON_SESSION is not authorized")

    log.info("Telegram user session connected")
    if ALLOWED_USER_IDS:
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
        log.warning("OWNER_TELEGRAM_ID is not set")

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
    app.add_handler(CommandHandler("saved", saved_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("filter", filter_command))
    app.add_handler(CommandHandler("queue", queue_command))
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(queue_callback, pattern=r"^queue:"))
    app.run_polling()


if __name__ == "__main__":
    main()
