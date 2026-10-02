import asyncio
import html
from html.parser import HTMLParser
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

# ÐÐ°ÑÑÐ±ÐµÐ¶Ð½ÑÐµ ÑÐ°Ð¹ÑÑ Ñ Ð¿ÑÐ±Ð»Ð¸ÑÐ½ÑÐ¼Ð¸ API. ÐÑÐ¾Ð²ÐµÑÑÑÑÑÑ Ð¾ÑÐ´ÐµÐ»ÑÐ½Ð¾ Ð¾Ñ Telegram.
# ÐÐ½ÑÐµÑÐ²Ð°Ð» 6 ÑÐ°ÑÐ¾Ð²: Remotive ÑÐµÐºÐ¾Ð¼ÐµÐ½Ð´ÑÐµÑ Ð½Ðµ Ð±Ð¾Ð»ÐµÐµ 4 Ð·Ð°Ð¿ÑÐ¾ÑÐ¾Ð² Ð² ÑÑÑÐºÐ¸.
WEB_SCAN_HOURS = max(6, int(os.getenv("WEB_SCAN_HOURS", "6")))
WEB_MAX_AGE_HOURS = max(1, int(os.getenv("WEB_MAX_AGE_HOURS", "72")))

WEB_SOURCES = {
    "Remote OK": "https://remoteok.com/api",
    "Himalayas": "https://himalayas.app/jobs/api?limit=20",
    "Remotive": "https://remotive.com/api/remote-jobs?limit=100",
    "Jobicy": "https://jobicy.com/api/v2/remote-jobs?count=50",
    # ÐÐ¾Ð¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»ÑÐ½ÑÐµ Ð¾ÑÐºÑÑÑÑÐµ Ð»ÐµÐ½ÑÑ ÑÐ´Ð°Ð»ÑÐ½Ð½ÑÑ Ð²Ð°ÐºÐ°Ð½ÑÐ¸Ð¹
    "RemoteJobs.org": "https://remotejobs.org/api/v1/jobs?limit=50",
    "Career Nest": "https://careernest.cloud/api/feed?limit=100",
    "Arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
    "Remote First Jobs": "https://remotefirstjobs.com/api/search-jobs",
}

# Ð¦ÐµÐ»ÐµÐ²ÑÐµ Ð½Ð°Ð¿ÑÐ°Ð²Ð»ÐµÐ½Ð¸Ñ: Ð°Ð½Ð¸Ð¼Ð°ÑÐ¸Ñ Ð»Ð¾Ð³Ð¾ÑÐ¸Ð¿Ð¾Ð², ÐºÐ°ÑÑÐ¾ÑÐºÐ¸ ÑÐ¾Ð²Ð°ÑÐ¾Ð² Ð¸ Ð»ÑÐ±ÑÐµ AI-ÑÐ¾Ð»Ð¸.
WEB_KEYWORDS = [
    "logo animation", "animated logo", "animate logo", "motion graphics",
    "motion designer", "logo animator", "brand animation",
    "product listing", "ecommerce product", "e-commerce product",
    "amazon listing", "amazon product", "product images",
    "product image", "product infographic", "ecommerce designer",
    "e-commerce designer", "marketplace listing", "product card",
    "ai", "artificial intelligence", "generative ai", "machine learning",
    "llm", "prompt engineer", "ai trainer", "ai data", "ai evaluator",
    "ai annotator", "ai content", "ai artist", "ai designer",
]

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
    # ÐÐ°ÑÑÐ±ÐµÐ¶Ð½ÑÐµ ÐºÐ°Ð½Ð°Ð»Ñ (Ð°Ð½Ð³Ð»Ð¸Ð¹ÑÐºÐ¸Ð¹/Ð¸ÑÐ¿Ð°Ð½ÑÐºÐ¸Ð¹)
    '@remotegraphicdesignjobs',
    '@findmyremote_design',
]
# Ð¡ÑÑÐ¾Ð³Ð¸Ð¹ ÑÐ¸Ð»ÑÑÑ: Ð¿ÑÐ¾Ð¿ÑÑÐºÐ°ÐµÐ¼ ÑÐ¾Ð»ÑÐºÐ¾ ÑÐ²Ð½ÑÐ¹ Ð¿Ð¾Ð¸ÑÐº Ð¸ÑÐ¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»Ñ/Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ°.
# ÐÐ±ÑÐ¸Ðµ ÑÐ»Ð¾Ð²Ð° Ð²ÑÐ¾Ð´Ðµ Â«Ð¸Ð½ÑÐ¾Ð³ÑÐ°ÑÐ¸ÐºÐ°Â», Â«WBÂ» Ð¸ Â«ÐºÐ°ÑÑÐ¾ÑÐºÐ¸Â» ÑÐ°Ð¼Ð¸ Ð¿Ð¾ ÑÐµÐ±Ðµ Ð½Ðµ Ð¿Ð¾Ð´ÑÐ¾Ð´ÑÑ.
POSITIVE = [
    "Ð¸ÑÑ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ°",
    "Ð¸ÑÐµÐ¼ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ°",
    "Ð½ÑÐ¶ÐµÐ½ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ",
    "Ð½ÑÐ¶Ð½Ð° Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ",
    "Ð½ÑÐ¶ÐµÐ½ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ ÐºÐ°ÑÑÐ¾ÑÐµÐº",
    "ÑÑÐµÐ±ÑÐµÑÑÑ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ",
    "ÑÑÐµÐ±ÑÐµÑÑÑ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ ÐºÐ°ÑÑÐ¾ÑÐµÐº",
    "Ð¸ÑÑ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ° ÐºÐ°ÑÑÐ¾ÑÐµÐº",
    "Ð¸ÑÐµÐ¼ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ° ÐºÐ°ÑÑÐ¾ÑÐµÐº",
    "Ð¸ÑÑ Ð¸Ð½ÑÐ¾Ð³ÑÐ°ÑÐ¸ÑÑÐ°",
    "Ð¸ÑÐµÐ¼ Ð¸Ð½ÑÐ¾Ð³ÑÐ°ÑÐ¸ÑÑÐ°",
    "Ð½ÑÐ¶ÐµÐ½ Ð¸Ð½ÑÐ¾Ð³ÑÐ°ÑÐ¸ÑÑ",
    "Ð½ÑÐ¶Ð½Ð° Ð¸Ð½ÑÐ¾Ð³ÑÐ°ÑÐ¸ÑÑ",
    "ÑÑÐµÐ±ÑÐµÑÑÑ Ð¸Ð½ÑÐ¾Ð³ÑÐ°ÑÐ¸ÑÑ",
    "Ð¸ÑÑ Ð¸ÑÐ¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»Ñ",
    "Ð¸ÑÐµÐ¼ Ð¸ÑÐ¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»Ñ",
    "Ð½ÑÐ¶ÐµÐ½ Ð¸ÑÐ¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»Ñ",
    "Ð½ÑÐ¶Ð½Ð° Ð¸ÑÐ¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»Ñ",
    "ÑÑÐµÐ±ÑÐµÑÑÑ Ð¸ÑÐ¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»Ñ",
    "Ð¸ÑÑ ÑÐ¿ÐµÑÐ¸Ð°Ð»Ð¸ÑÑÐ° Ð¿Ð¾ Ð´Ð¸Ð·Ð°Ð¹Ð½Ñ",
    "Ð¸ÑÐµÐ¼ ÑÐ¿ÐµÑÐ¸Ð°Ð»Ð¸ÑÑÐ° Ð¿Ð¾ Ð´Ð¸Ð·Ð°Ð¹Ð½Ñ",
    "Ð½ÑÐ¶ÐµÐ½ ÑÐ¿ÐµÑÐ¸Ð°Ð»Ð¸ÑÑ Ð¿Ð¾ Ð´Ð¸Ð·Ð°Ð¹Ð½Ñ",
    "Ð½ÑÐ¶ÐµÐ½ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ Ð´Ð»Ñ",
    "Ð½ÑÐ¶Ð½Ð° Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ Ð´Ð»Ñ",
    "Ð·Ð°ÐºÐ°Ð· Ð½Ð° Ð´Ð¸Ð·Ð°Ð¹Ð½",
    "ÐµÑÑÑ Ð·Ð°ÐºÐ°Ð· Ð½Ð° Ð´Ð¸Ð·Ð°Ð¹Ð½",
    "Ð¸ÑÑ ÑÐµÐ»Ð¾Ð²ÐµÐºÐ° Ð´Ð»Ñ Ð´Ð¸Ð·Ð°Ð¹Ð½Ð°",
    # ÐÐ¾Ð³Ð¾ÑÐ¸Ð¿Ñ, Ð±Ð°Ð½Ð½ÐµÑÑ Ð¸ ÑÐ¸ÑÐ¼ÐµÐ½Ð½ÑÐ¹ ÑÑÐ¸Ð»Ñ (ÑÑÑÑÐºÐ¸Ð¹)
    "Ð¸ÑÑ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ° Ð»Ð¾Ð³Ð¾ÑÐ¸Ð¿Ð°",
    "Ð¸ÑÐµÐ¼ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ° Ð»Ð¾Ð³Ð¾ÑÐ¸Ð¿Ð°",
    "Ð½ÑÐ¶ÐµÐ½ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ Ð»Ð¾Ð³Ð¾ÑÐ¸Ð¿Ð°",
    "Ð½ÑÐ¶ÐµÐ½ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ Ð´Ð»Ñ Ð»Ð¾Ð³Ð¾ÑÐ¸Ð¿Ð°",
    "Ð·Ð°ÐºÐ°Ð·Ð°ÑÑ Ð»Ð¾Ð³Ð¾ÑÐ¸Ð¿",
    "Ð·Ð°ÐºÐ°Ð· Ð½Ð° Ð»Ð¾Ð³Ð¾ÑÐ¸Ð¿",
    "Ð¸ÑÑ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ° Ð±Ð°Ð½Ð½ÐµÑÐ¾Ð²",
    "Ð¸ÑÐµÐ¼ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ° Ð±Ð°Ð½Ð½ÐµÑÐ¾Ð²",
    "Ð½ÑÐ¶ÐµÐ½ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ Ð±Ð°Ð½Ð½ÐµÑÐ¾Ð²",
    "Ð½ÑÐ¶ÐµÐ½ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ Ð´Ð»Ñ Ð±Ð°Ð½Ð½ÐµÑÐ°",
    "Ð·Ð°ÐºÐ°Ð·Ð°ÑÑ Ð±Ð°Ð½Ð½ÐµÑ",
    "Ð·Ð°ÐºÐ°Ð· Ð½Ð° Ð±Ð°Ð½Ð½ÐµÑ",
    "Ð¸ÑÑ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ° ÑÐ¸ÑÐ¼ÐµÐ½Ð½Ð¾Ð³Ð¾ ÑÑÐ¸Ð»Ñ",
    "Ð½ÑÐ¶ÐµÐ½ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ ÑÐ¸ÑÐ¼ÐµÐ½Ð½Ð¾Ð³Ð¾ ÑÑÐ¸Ð»Ñ",
    # ÐÐ½Ð³Ð»Ð¸Ð¹ÑÐºÐ¸Ðµ ÑÐ¾ÑÐ¼ÑÐ»Ð¸ÑÐ¾Ð²ÐºÐ¸ Ð·Ð°ÐºÐ°Ð·Ð¾Ð² Ð² Ð·Ð°ÑÑÐ±ÐµÐ¶Ð½ÑÑ ÐºÐ°Ð½Ð°Ð»Ð°Ñ
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
    "Ð¿ÑÐµÐ´Ð»Ð°Ð³Ð°Ñ ÑÑÐ»ÑÐ³Ð¸",
    "Ð¾ÐºÐ°Ð·ÑÐ²Ð°Ñ ÑÑÐ»ÑÐ³Ð¸",
    "Ð¼Ð¾Ð¸ ÑÑÐ»ÑÐ³Ð¸",
    "ÑÑÐ»ÑÐ³Ð¸ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑÐ°",
    "Ñ Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ",
    "Ð´Ð¸Ð·Ð°Ð¹Ð½ÐµÑ Ð½Ð° ÑÐ²ÑÐ·Ð¸",
    "Ð¸ÑÑ ÑÐ°Ð±Ð¾ÑÑ",
    "Ð¸ÑÑ Ð·Ð°ÐºÐ°Ð·Ñ",
    "Ð¸ÑÑ Ð·Ð°ÐºÐ°Ð·ÑÐ¸ÐºÐ¾Ð²",
    "Ð¸ÑÑ ÐºÐ»Ð¸ÐµÐ½ÑÐ¾Ð²",
    "Ð¸ÑÑ Ð¿ÑÐ¾ÐµÐºÑÑ",
    "Ð²Ð¾Ð·ÑÐ¼Ñ Ð·Ð°ÐºÐ°Ð·",
    "Ð²Ð¾Ð·ÑÐ¼Ñ Ð·Ð°ÐºÐ°Ð·Ñ",
    "ÑÐ²Ð¾Ð±Ð¾Ð´ÐµÐ½ Ð´Ð»Ñ Ð·Ð°ÐºÐ°Ð·Ð¾Ð²",
    "ÑÐ²Ð¾Ð±Ð¾Ð´Ð½Ð° Ð´Ð»Ñ Ð·Ð°ÐºÐ°Ð·Ð¾Ð²",
    "Ð¿Ð¾ÑÑÑÐ¾Ð»Ð¸Ð¾",
    "Ð¾Ð±ÑÑÐµÐ½Ð¸Ðµ",
    "ÐºÑÑÑ",
    "Ð²ÐµÐ±Ð¸Ð½Ð°Ñ",
    # ÐÐ½Ð³Ð»Ð¾ÑÐ·ÑÑÐ½Ð°Ñ ÑÐ°Ð¼Ð¾ÑÐµÐºÐ»Ð°Ð¼Ð° Ð¸ Ð¿Ð¾Ð¸ÑÐº Ð·Ð°ÐºÐ°Ð·Ð¾Ð² ÑÐ°Ð¼Ð¸Ð¼ Ð¸ÑÐ¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»ÐµÐ¼
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
    normalized = re.sub(r"\s+", " ", text.lower().replace("Ñ", "Ðµ"))
    # Ð¡Ð½Ð°ÑÐ°Ð»Ð° Ð¾ÑÑÐµÐºÐ°ÐµÐ¼ ÑÐ°Ð¼Ð¾ÑÐµÐºÐ»Ð°Ð¼Ñ Ð¸ Ð¿ÑÐµÐ´Ð»Ð¾Ð¶ÐµÐ½Ð¸Ñ ÑÑÐ»ÑÐ³.
    if any(word in normalized for word in NEGATIVE):
        return False
    # Ð¢ÑÐµÐ±ÑÐµÐ¼ ÑÐ²Ð½ÑÑ ÑÐ¾ÑÐ¼ÑÐ»Ð¸ÑÐ¾Ð²ÐºÑ, ÑÑÐ¾ Ð°Ð²ÑÐ¾Ñ Ð¸ÑÐµÑ Ð¸ÑÐ¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»Ñ.
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
                        text=f"ð ÐÐ°Ð¹Ð´ÐµÐ½Ð¾ Ð½Ð¾Ð²ÑÑ Ð·Ð°ÐºÐ°Ð·Ð¾Ð²: {found}\nð Ð£ ÑÐµÐ±Ñ Ð¾Ð¶Ð¸Ð´Ð°ÑÑ Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÐ°: {count}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ð Ð¡Ð¼Ð¾ÑÑÐµÑÑ Ð·Ð°ÐºÐ°Ð·Ñ", callback_data="queue:open")]]),
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



class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data and data.strip():
            self.parts.append(data.strip())


def _repair_mojibake(value):
    """ÐÐ¾Ð¿ÑÑÐ°ÑÑÑÑ Ð¸ÑÐ¿ÑÐ°Ð²Ð¸ÑÑ ÑÐµÐºÑÑ, ÐµÑÐ»Ð¸ UTF-8 Ð¾ÑÐ¸Ð±Ð¾ÑÐ½Ð¾ Ð¿ÑÐ¾ÑÐ¸ÑÐ°Ð»Ð¸ ÐºÐ°Ðº cp1252/latin-1."""
    if not isinstance(value, str):
        return value
    markers = ("\u00c3", "\u00c2", "\u00d0", "\u00d1", "\u00f0", "\u00de", "\u00e2\u20ac", "\u0420\u045f", "\u0421\u045f")
    if not any(marker in value for marker in markers):
        return value

    original_score = sum(value.count(marker) for marker in markers)
    for encoding in ("cp1252", "latin-1"):
        try:
            candidate = value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        candidate_score = sum(candidate.count(marker) for marker in markers)
        if candidate_score < original_score:
            return candidate
    return value


def _plain_text(value):
    parser = _HTMLText()
    try:
        parser.feed(value or "")
        return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    except Exception:
        return re.sub(r"<[^>]+>", " ", value or "").strip()


def _fetch_json(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "FreelanceOpportunityBot/1.0"}
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def _web_job_is_relevant(title, description):
    combined = (str(title or "") + " " + _plain_text(str(description or ""))).casefold()
    return any(term.casefold() in combined for term in WEB_KEYWORDS)


def _web_job_date(value):
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc)
        raw = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _extract_web_jobs(source, data):
    if source == "Remote OK":
        items = data if isinstance(data, list) else []
        result = []
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            result.append({
                "id": str(item["id"]),
                "title": item.get("position") or item.get("title") or "",
                "company": item.get("company") or "",
                "description": item.get("description") or "",
                "url": item.get("url") or "",
                "date": item.get("date") or item.get("epoch"),
            })
        return result

    if source == "Himalayas":
        items = data.get("jobs", []) if isinstance(data, dict) else []
        result = []
        for item in items:
            result.append({
                "id": str(item.get("guid") or item.get("id") or item.get("applicationLink") or ""),
                "title": item.get("title") or "",
                "company": item.get("companyName") or "",
                "description": item.get("description") or "",
                "url": item.get("applicationLink") or item.get("guid") or "",
                "date": item.get("pubDate") or item.get("pubDateISO"),
            })
        return result

    if source == "Remotive":
        items = data.get("jobs", []) if isinstance(data, dict) else []
        return [{
            "id": str(item.get("id") or item.get("url") or ""),
            "title": item.get("title") or "",
            "company": item.get("company_name") or "",
            "description": item.get("description") or "",
            "url": item.get("url") or "",
            "date": item.get("publication_date") or "",
        } for item in items]

    if source == "Jobicy":
        items = data.get("jobs", []) if isinstance(data, dict) else []
        return [{
            "id": str(item.get("id") or item.get("url") or ""),
            "title": item.get("jobTitle") or "",
            "company": item.get("companyName") or "",
            "description": item.get("jobDescription") or "",
            "url": item.get("url") or "",
            "date": item.get("pubDate") or item.get("datePosted") or "",
        } for item in items]

    if source == "RemoteJobs.org":
        items = data.get("data", data.get("jobs", [])) if isinstance(data, dict) else []
        return [{
            "id": str(item.get("id") or item.get("job_url") or item.get("url") or ""),
            "title": item.get("title") or item.get("name") or "",
            "company": item.get("company") or item.get("company_name") or "",
            "description": item.get("description") or "",
            "url": item.get("job_url") or item.get("url") or "",
            "date": item.get("posted_at") or item.get("created_at") or "",
        } for item in items if isinstance(item, dict)]

    if source == "Career Nest":
        items = data.get("jobs", data.get("data", [])) if isinstance(data, dict) else []
        return [{
            "id": str(item.get("id") or item.get("job_url") or item.get("url") or ""),
            "title": item.get("title") or item.get("job_title") or "",
            "company": item.get("company") or item.get("company_name") or "",
            "description": item.get("description") or "",
            "url": item.get("job_url") or item.get("url") or "",
            "date": item.get("posted_at") or item.get("published_at") or "",
        } for item in items if isinstance(item, dict)]

    if source == "Arbeitnow":
        items = data.get("data", []) if isinstance(data, dict) else []
        return [{
            "id": str(item.get("slug") or item.get("url") or ""),
            "title": item.get("title") or "",
            "company": item.get("company_name") or "",
            "description": item.get("description") or "",
            "url": item.get("url") or "",
            "date": item.get("created_at") or "",
        } for item in items if isinstance(item, dict)]

    if source == "Remote First Jobs":
        items = data.get("jobs", []) if isinstance(data, dict) else []
        return [{
            "id": str(item.get("id") or item.get("url") or ""),
            "title": item.get("title") or "",
            "company": item.get("company_name") or "",
            "description": item.get("description") or "",
            "url": item.get("url") or "",
            "date": item.get("published_at") or "",
        } for item in items if isinstance(item, dict)]

    return []


async def scan_websites(app: Application):
    """Ð§Ð¸ÑÐ°ÐµÑ ÑÐ¾Ð»ÑÐºÐ¾ Ð¿ÑÐ±Ð»Ð¸ÑÐ½ÑÐµ JSON API, Ð±ÐµÐ· Ð²ÑÐ¾Ð´Ð° Ð¸ Ð¾Ð±ÑÐ¾Ð´Ð° Ð¾Ð³ÑÐ°Ð½Ð¸ÑÐµÐ½Ð¸Ð¹ ÑÐ°Ð¹ÑÐ¾Ð²."""
    checked = errors = found = 0
    for source, url in WEB_SOURCES.items():
        try:
            data = await asyncio.to_thread(_fetch_json, url)
            checked += 1
            for item in _extract_web_jobs(source, data):
                title = _repair_mojibake(str(item.get("title") or "")).strip()
                description = _repair_mojibake(str(item.get("description") or "")).strip()
                link = str(item.get("url") or "").strip()
                job_id = str(item.get("id") or link).strip()
                if not title or not link or not job_id:
                    continue
                if not link.startswith(("https://", "http://")):
                    continue
                published = _web_job_date(item.get("date"))
                if published:
                    age = datetime.now(timezone.utc) - published
                    if age < timedelta(0) or age > timedelta(hours=WEB_MAX_AGE_HOURS):
                        continue
                if not _web_job_is_relevant(title, description):
                    continue

                key = f"web:{source}:{job_id}"
                if was_seen(key):
                    continue
                body = (
                    f"ð <b>ÐÐ°ÑÑÐ±ÐµÐ¶Ð½ÑÐ¹ ÑÐ°Ð¹Ñ: {html.escape(source)}</b>\n"
                    f"ð¼ <b>{html.escape(title[:300])}</b>\n"
                    f"ð¢ {html.escape(_repair_mojibake(str(item.get('company') or 'ÐÐ¾Ð¼Ð¿Ð°Ð½Ð¸Ñ Ð½Ðµ ÑÐºÐ°Ð·Ð°Ð½Ð°'))[:200])}\n\n"
                    f"{html.escape(_plain_text(description)[:2200])}\n\n"
                    f"ð Ð¢ÐµÐ¼Ð°ÑÐ¸ÐºÐ°: {html.escape(', '.join(k for k in WEB_KEYWORDS if k.casefold() in (title + ' ' + _plain_text(description)).casefold())[:500])}"
                )
                with db() as con:
                    con.execute(
                        "INSERT OR IGNORE INTO jobs(key, body, channel, link, created_at) VALUES (?, ?, ?, ?, ?)",
                        (key, body[:3500], source, link, (published or datetime.now(timezone.utc)).isoformat()),
                    )
                    con.commit()
                mark_seen(key)
                found += 1
        except Exception as exc:
            errors += 1
            log.warning("Website scan failed: %s (%s)", source, type(exc).__name__)

    if found:
        for user_id in sorted(ALLOWED_USER_IDS):
            if is_paused(user_id):
                continue
            count = pending_count(user_id)
            if count:
                try:
                    await app.bot.send_message(
                        chat_id=int(user_id),
                        text=f"ð ÐÐ°Ð¹Ð´ÐµÐ½Ñ Ð½Ð¾Ð²ÑÐµ Ð²Ð°ÐºÐ°Ð½ÑÐ¸Ð¸ Ð½Ð° Ð·Ð°ÑÑÐ±ÐµÐ¶Ð½ÑÑ ÑÐ°Ð¹ÑÐ°Ñ: {found}\nð ÐÐ¶Ð¸Ð´Ð°ÑÑ Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÐ°: {count}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ð Ð¡Ð¼Ð¾ÑÑÐµÑÑ Ð·Ð°ÐºÐ°Ð·Ñ", callback_data="queue:open")]]),
                    )
                except TelegramError as exc:
                    log.warning("Website queue notice failed for %s: %s", user_id, type(exc).__name__)

    return {"checked": checked, "errors": errors, "found": found, "total": len(WEB_SOURCES)}


async def scheduled_web_scan(context: ContextTypes.DEFAULT_TYPE):
    result = await scan_websites(context.application)
    log.info(
        "Website scan complete: checked=%s/%s errors=%s found=%s",
        result["checked"], result["total"], result["errors"], result["found"],
    )


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
            f"ð ÐÑÐµ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÐµÐ½Ñ!\nâ­ Ð¡Ð¾ÑÑÐ°Ð½ÐµÐ½Ð¾: {saved_count(user_id)}",
            reply_markup=None,
        )
        return
    key, body, channel, link = jobs[0]
    total = len(jobs)
    # ÐÐ¾Ð¼ÐµÑ ÑÐµÐºÑÑÐµÐ³Ð¾ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ Ð¾ÑÐ½Ð¾ÑÐ¸ÑÐµÐ»ÑÐ½Ð¾ ÑÐ¶Ðµ Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÐµÐ½Ð½ÑÑ Ð² ÑÑÐ¾Ð¹ Ð¾ÑÐµÑÐµÐ´Ð¸.
    with db() as con:
        reviewed = con.execute(
            "SELECT COUNT(*) FROM decisions WHERE user_id=?", (str(user_id),)
        ).fetchone()[0]
    number = reviewed + 1
    text = (
        f"ð <b>ÐÐ°ÐºÐ°Ð· {number} Ð¸Ð· {number + total - 1}</b>\n"
        f"â­ Ð¡Ð¾ÑÑÐ°Ð½ÐµÐ½Ð¾: {saved_count(user_id)}\n\n"
        f"{html.escape(body)}\n\n"
        f"ð£ ÐÑÑÐ¾ÑÐ½Ð¸Ðº: {html.escape(channel)}\n"
        f'<a href="{html.escape(link, quote=True)}">ÐÑÐºÑÑÑÑ Ð¾ÑÐ¸Ð³Ð¸Ð½Ð°Ð»</a>'
    )
    # ÐÐ¾ÑÐ¾ÑÐºÐ¸Ðµ callback_data: Telegram Ð´Ð¾Ð¿ÑÑÐºÐ°ÐµÑ Ð½Ðµ Ð±Ð¾Ð»ÐµÐµ 64 Ð±Ð°Ð¹Ñ.
    # Ð¢ÐµÐºÑÑÐ¸Ð¹ Ð·Ð°ÐºÐ°Ð· Ð±ÐµÑÑÑÑÑ Ð¸Ð· Ð¾ÑÐµÑÐµÐ´Ð¸ Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ Ð² queue_callback.
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("â ÐÑÐ¾Ð¿ÑÑÑÐ¸ÑÑ", callback_data="queue:skip"),
         InlineKeyboardButton("â ÐÑÑÐ°Ð²Ð¸ÑÑ", callback_data="queue:keep")],
        [InlineKeyboardButton("ð·ðº ÐÐµÑÐµÐ²ÐµÑÑÐ¸", callback_data="queue:translate")],
        [InlineKeyboardButton("â¬ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="queue:back")],
    ])
    text = _repair_mojibake(text)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)


def translate_to_russian(text: str) -> str:
    """ÐÐµÑÐµÐ²Ð¾Ð´Ð¸Ñ ÑÐµÐºÑÑ ÑÐµÑÐµÐ· Ð¿ÑÐ±Ð»Ð¸ÑÐ½ÑÐ¹ Google Translate endpoint."""
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
        await query.answer("ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.", show_alert=True)
        return
    data = query.data or ""
    if data == "queue:translate":
        await query.answer("ÐÐµÑÐµÐ²Ð¾Ð¶Ñâ¦")
        jobs = pending_jobs(user_id)
        if not jobs:
            await query.answer("ÐÑÐµÑÐµÐ´Ñ Ð¿ÑÑÑÐ°.", show_alert=True)
            return
        key, body, channel, link = jobs[0]
        try:
            translated = await asyncio.to_thread(translate_to_russian, body)
            translated = translated[:3500]
            await query.message.reply_text(
                "ð·ðº <b>ÐÐµÑÐµÐ²Ð¾Ð´ Ð½Ð° ÑÑÑÑÐºÐ¸Ð¹</b>\n\n" + html.escape(translated),
                parse_mode="HTML", disable_web_page_preview=True,
            )
        except Exception as exc:
            log.warning("Translation failed: %s", type(exc).__name__)
            await query.message.reply_text(
                "â ï¸ ÐÐµ ÑÐ´Ð°Ð»Ð¾ÑÑ Ð¿ÐµÑÐµÐ²ÐµÑÑÐ¸. ÐÐ¾Ð¿ÑÐ¾Ð±ÑÐ¹ Ð¿Ð¾Ð·Ð¶Ðµ."
            )
        return
    if data == "queue:open":
        await query.answer()
        await show_next(query, user_id)
        return
    if data == "queue:back":
        await query.answer()
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
    if data in ("queue:skip", "queue:keep"):
        await query.answer()
        jobs = pending_jobs(user_id)
        if not jobs:
            await query.edit_message_text("ð­ ÐÑÐµÑÐµÐ´Ñ Ð¿ÑÑÑÐ°.", reply_markup=None)
            return
        key = jobs[0][0]
        decision = "keep" if data == "queue:keep" else "skip"
        with db() as con:
            con.execute(
                "INSERT OR IGNORE INTO decisions(user_id, job_key, decision, decided_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, key, decision, datetime.now(timezone.utc).isoformat()),
            )
            con.commit()
        await show_next(query, user_id)


async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    user_id = str(update.effective_user.id)
    with db() as con:
        rows = con.execute(
            "SELECT j.body, j.link FROM jobs j JOIN decisions d ON d.job_key=j.key "
            "WHERE d.user_id=? AND d.decision='keep' ORDER BY d.decided_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
    if not rows:
        await reply(update, "â­ ÐÐ¾ÐºÐ° Ð½ÐµÑ ÑÐ¾ÑÑÐ°Ð½ÑÐ½Ð½ÑÑ Ð·Ð°ÐºÐ°Ð·Ð¾Ð².")
        return
    text = "â­ <b>Ð¡Ð¾ÑÑÐ°Ð½ÑÐ½Ð½ÑÐµ Ð·Ð°ÐºÐ°Ð·Ñ</b>\n\n" + "\n\n".join(
        f"{i}. {html.escape(body[:700])}\n<a href=\"{html.escape(link, quote=True)}\">ÐÑÐºÑÑÑÑ Ð¾ÑÐ¸Ð³Ð¸Ð½Ð°Ð»</a>"
        for i, (body, link) in enumerate(rows, 1)
    )
    await update.effective_chat.send_message(text=text, parse_mode="HTML", disable_web_page_preview=True)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    user_id = str(update.effective_user.id)
    with db() as con:
        total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        kept = con.execute("SELECT COUNT(*) FROM decisions WHERE user_id=? AND decision='keep'", (user_id,)).fetchone()[0]
        skipped = con.execute("SELECT COUNT(*) FROM decisions WHERE user_id=? AND decision='skip'", (user_id,)).fetchone()[0]
    paused, keyword = get_pref(user_id)
    await reply(update, f"ð Ð¢Ð²Ð¾Ñ ÑÑÐ°ÑÐ¸ÑÑÐ¸ÐºÐ°\nÐÑÐµÐ³Ð¾ Ð½Ð°Ð¹Ð´ÐµÐ½Ð¾: {total}\nâ­ Ð¡Ð¾ÑÑÐ°Ð½ÐµÐ½Ð¾: {kept}\nâ ÐÑÐ¾Ð¿ÑÑÐµÐ½Ð¾: {skipped}\nâ³ ÐÐ¶Ð¸Ð´Ð°ÑÑ Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÐ°: {pending_count(user_id)}\nÐ£Ð²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ: {'Ð¿Ð°ÑÐ·Ð°' if paused else 'Ð²ÐºÐ»ÑÑÐµÐ½Ñ'}\nÐ¤Ð¸Ð»ÑÑÑ: {html.escape(keyword) if keyword else 'Ð½Ðµ Ð·Ð°Ð´Ð°Ð½'}")


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    user_id = str(update.effective_user.id)
    paused, _ = get_pref(user_id)
    set_paused(user_id, not paused)
    await reply(update, "â¸ï¸ Ð£Ð²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ Ð¿ÑÐ¸Ð¾ÑÑÐ°Ð½Ð¾Ð²Ð»ÐµÐ½Ñ. ÐÑÐµÑÐµÐ´Ñ Ð´Ð¾ÑÑÑÐ¿Ð½Ð° ÐºÐ¾Ð¼Ð°Ð½Ð´Ð¾Ð¹ /queue." if not paused else "â¶ï¸ Ð£Ð²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ñ ÑÐ½Ð¾Ð²Ð° Ð²ÐºÐ»ÑÑÐµÐ½Ñ.")


async def filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    user_id = str(update.effective_user.id)
    keyword = " ".join(context.args).strip()
    if keyword.lower() == "clear":
        keyword = ""
    set_keyword(user_id, keyword)
    await reply(update, (f"ð Ð¤Ð¸Ð»ÑÑÑ ÑÑÑÐ°Ð½Ð¾Ð²Ð»ÐµÐ½: {html.escape(keyword)}\nÐ Ð¾ÑÐµÑÐµÐ´Ð¸: {pending_count(user_id)}" if keyword else "ð Ð¤Ð¸Ð»ÑÑÑ Ð¾ÑÐ¸ÑÐµÐ½. ÐÐ¾ÐºÐ°Ð·ÑÐ²Ð°Ñ Ð²ÑÐµ Ð¿Ð¾Ð´ÑÐ¾Ð´ÑÑÐ¸Ðµ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ."))


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    user_id = str(update.effective_user.id)
    jobs = pending_jobs(user_id)
    if not jobs:
        await reply(update, "ð­ ÐÐµÑ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ð¹ Ð´Ð»Ñ Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÐ°. ÐÐ¾Ð¿ÑÐ¾Ð±ÑÐ¹ /scan Ð¸Ð»Ð¸ Ð¾ÑÐ¸ÑÑÐ¸ ÑÐ¸Ð»ÑÑÑ ÐºÐ¾Ð¼Ð°Ð½Ð´Ð¾Ð¹ /filter clear.")
        return
    await update.effective_chat.send_message(
        text=f"ð ÐÐ°Ð¹Ð´ÐµÐ½Ð¾ Ð´Ð»Ñ Ð¿ÑÐ¾ÑÐ¼Ð¾ÑÑÐ°: {len(jobs)}\nÐÐ°Ð¶Ð¼Ð¸ ÐºÐ½Ð¾Ð¿ÐºÑ, ÑÑÐ¾Ð±Ñ Ð½Ð°ÑÐ°ÑÑ.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("ð Ð¡Ð¼Ð¾ÑÑÐµÑÑ Ð·Ð°ÐºÐ°Ð·Ñ", callback_data="queue:open")]]),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    await reply(
        update,
        "ÐÑÐ¸Ð²ÐµÑ! Ð¯ Ð¸ÑÑ ÑÐ²ÐµÐ¶Ð¸Ðµ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ñ Ð¾ Ð·Ð°ÐºÐ°Ð·Ð°Ñ Ð½Ð° Ð´Ð¸Ð·Ð°Ð¹Ð½ ÐºÐ°ÑÑÐ¾ÑÐµÐº ÑÐ¾Ð²Ð°ÑÐ¾Ð².\n\n"
        f"ÐÐ¾Ð·ÑÐ°ÑÑ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ð¹: Ð´Ð¾ {MAX_AGE_HOURS} Ñ.\n"
        f"ÐÐ½ÑÐµÑÐ²Ð°Ð» Ð¿ÑÐ¾Ð²ÐµÑÐºÐ¸: {SCAN_MINUTES} Ð¼Ð¸Ð½.\n\n"
        "/status â ÑÐ¾ÑÑÐ¾ÑÐ½Ð¸Ðµ\n"
        "/scan â Ð¿ÑÐ¾Ð²ÐµÑÐ¸ÑÑ Telegram-ÐºÐ°Ð½Ð°Ð»Ñ ÑÐµÐ¹ÑÐ°Ñ\n"
        "/webscan â Ð¿ÑÐ¾Ð²ÐµÑÐ¸ÑÑ Ð·Ð°ÑÑÐ±ÐµÐ¶Ð½ÑÐµ ÑÐ°Ð¹ÑÑ ÑÐµÐ¹ÑÐ°Ñ\n"
        "/saved â ÑÐ¾ÑÑÐ°Ð½ÑÐ½Ð½ÑÐµ Ð·Ð°ÐºÐ°Ð·Ñ\n"
        "/stats â ÑÑÐ°ÑÐ¸ÑÑÐ¸ÐºÐ°\n"
        "/queue â Ð¾ÑÐºÑÑÑÑ Ð¾ÑÐµÑÐµÐ´Ñ\n"
        "/pause â Ð¿Ð°ÑÐ·Ð°/Ð²Ð¾Ð·Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ðµ ÑÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½Ð¸Ð¹\n"
        "/filter ÑÐ»Ð¾Ð²Ð¾ â ÑÐ¸Ð»ÑÑÑ Ð¿Ð¾ ÑÐ»Ð¾Ð²Ð°Ð¼; /filter clear â ÑÐ±ÑÐ¾Ñ\n"
        "/myid â ÑÐ·Ð½Ð°ÑÑ Telegram ID\n"
        "ÐÐ¾Ð¸ÑÐº ÑÐ°Ð±Ð¾ÑÐ°ÐµÑ Ð±ÐµÐ· Ð½ÐµÐ¹ÑÐ¾ÑÐµÑÐ¸.",
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(
        update,
        f"Ð¢Ð²Ð¾Ð¹ Telegram ID: "
        f"{update.effective_user.id if update.effective_user else 'Ð½Ðµ Ð¾Ð¿ÑÐµÐ´ÐµÐ»ÑÐ½'}",
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    connected = user_client is not None and user_client.is_connected()
    await reply(
        update,
        f"ð¢ ÐÐ¾Ñ Ð·Ð°Ð¿ÑÑÐµÐ½\n"
        f"Telegram-Ð°ÐºÐºÐ°ÑÐ½Ñ Ð¿Ð¾Ð´ÐºÐ»ÑÑÑÐ½: {'Ð´Ð°' if connected else 'Ð½ÐµÑ'}\n"
        f"ÐÐ¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»ÐµÐ¹: {len(ALLOWED_USER_IDS)}\n"
        f"ÐÐ°Ð½Ð°Ð»Ð¾Ð² Ð² ÑÐ¿Ð¸ÑÐºÐµ: {len(CHANNELS)}\n"
        f"Ð¡Ð°Ð¹ÑÐ¾Ð² Ð²Ð°ÐºÐ°Ð½ÑÐ¸Ð¹: {len(WEB_SOURCES)}\n"
        f"ÐÑÐ¾Ð²ÐµÑÐºÐ° ÑÐ°Ð¹ÑÐ¾Ð²: ÐºÐ°Ð¶Ð´ÑÐµ {WEB_SCAN_HOURS} Ñ.\n"
        f"ÐÐ½ÑÐµÑÐ²Ð°Ð» Ð¿ÑÐ¾Ð²ÐµÑÐºÐ¸: {SCAN_MINUTES} Ð¼Ð¸Ð½.\n"
        f"ÐÐ°ÐºÑÐ¸Ð¼Ð°Ð»ÑÐ½ÑÐ¹ Ð²Ð¾Ð·ÑÐ°ÑÑ Ð·Ð°ÑÐ²ÐºÐ¸: {MAX_AGE_HOURS} Ñ.",
    )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    if scan_lock.locked():
        await reply(update, "â³ ÐÑÐ¾Ð²ÐµÑÐºÐ° ÑÐ¶Ðµ Ð²ÑÐ¿Ð¾Ð»Ð½ÑÐµÑÑÑ.")
        return
    await reply(update, "ð ÐÑÐ¾Ð²ÐµÑÑÑ Telegram-ÐºÐ°Ð½Ð°Ð»Ñâ¦")
    result = await run_scan(context.application)
    if result is None:
        await reply(update, "â ï¸ ÐÑÐ¾Ð²ÐµÑÐºÐ° Ð½Ðµ Ð·Ð°Ð²ÐµÑÑÐ¸Ð»Ð°ÑÑ. ÐÐ¾ÑÐ¼Ð¾ÑÑÐ¸ Ð¶ÑÑÐ½Ð°Ð» FadeHost.")
    else:
        await reply(
            update,
            "â ÐÑÐ¾Ð²ÐµÑÐºÐ° Ð·Ð°Ð²ÐµÑÑÐµÐ½Ð°.\n"
            f"ÐÐ¾ÑÑÑÐ¿Ð½Ð¾ ÐºÐ°Ð½Ð°Ð»Ð¾Ð²: {result['checked']} Ð¸Ð· {result['total']}\n"
            f"ÐÑÐ¸Ð±Ð¾Ðº: {result['errors']}\n"
            f"ÐÐ¾Ð²ÑÑ Ð¿Ð¾Ð´ÑÐ¾Ð´ÑÑÐ¸Ñ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ð¹: {result['found']}\n"
            f"Ð¡ÑÐ°ÑÑÑ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ð¹ Ð¿ÑÐ¾Ð¿ÑÑÐµÐ½Ð¾: {result['old']}",
        )



async def webscan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "ÐÐ¾ÑÑÑÐ¿ Ð·Ð°ÐºÑÑÑ.")
        return
    await reply(update, "ð ÐÑÐ¾Ð²ÐµÑÑÑ Ð·Ð°ÑÑÐ±ÐµÐ¶Ð½ÑÐµ ÑÐ°Ð¹ÑÑ Ñ Ð²Ð°ÐºÐ°Ð½ÑÐ¸ÑÐ¼Ð¸â¦")
    result = await scan_websites(context.application)
    await reply(
        update,
        "â ÐÑÐ¾Ð²ÐµÑÐºÐ° ÑÐ°Ð¹ÑÐ¾Ð² Ð·Ð°Ð²ÐµÑÑÐµÐ½Ð°.\n"
        f"ÐÑÑÐ¾ÑÐ½Ð¸ÐºÐ¾Ð² Ð¿ÑÐ¾Ð²ÐµÑÐµÐ½Ð¾: {result['checked']} Ð¸Ð· {result['total']}\n"
        f"ÐÑÐ¸Ð±Ð¾Ðº: {result['errors']}\n"
        f"ÐÐ¾Ð²ÑÑ Ð¿Ð¾Ð´ÑÐ¾Ð´ÑÑÐ¸Ñ Ð¾Ð±ÑÑÐ²Ð»ÐµÐ½Ð¸Ð¹: {result['found']}",
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
        app.job_queue.run_repeating(
            scheduled_web_scan,
            interval=WEB_SCAN_HOURS * 60 * 60,
            first=30,
            name="foreign-freelance-sites",
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
    app.add_handler(CommandHandler("webscan", webscan_command))
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
