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

# \u0417\u0430\u0440\u0443\u0431\u0435\u0436\u043d\u044b\u0435 \u0441\u0430\u0439\u0442\u044b \u0441 \u043f\u0443\u0431\u043b\u0438\u0447\u043d\u044b\u043c\u0438 API. \u041f\u0440\u043e\u0432\u0435\u0440\u044f\u044e\u0442\u0441\u044f \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u043e \u043e\u0442 Telegram.
# \u0418\u043d\u0442\u0435\u0440\u0432\u0430\u043b 6 \u0447\u0430\u0441\u043e\u0432: Remotive \u0440\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u0435\u0442 \u043d\u0435 \u0431\u043e\u043b\u0435\u0435 4 \u0437\u0430\u043f\u0440\u043e\u0441\u043e\u0432 \u0432 \u0441\u0443\u0442\u043a\u0438.
WEB_SCAN_HOURS = max(6, int(os.getenv("WEB_SCAN_HOURS", "6")))
WEB_MAX_AGE_HOURS = max(1, int(os.getenv("WEB_MAX_AGE_HOURS", "72")))

WEB_SOURCES = {
    "Remote OK": "https://remoteok.com/api",
    "Himalayas": "https://himalayas.app/jobs/api?limit=20",
    "Remotive": "https://remotive.com/api/remote-jobs?limit=100",
    "Jobicy": "https://jobicy.com/api/v2/remote-jobs?count=50",
    # \u0414\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0435 \u043e\u0442\u043a\u0440\u044b\u0442\u044b\u0435 \u043b\u0435\u043d\u0442\u044b \u0443\u0434\u0430\u043b\u0451\u043d\u043d\u044b\u0445 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u0439
    "RemoteJobs.org": "https://remotejobs.org/api/v1/jobs?limit=50",
    "Career Nest": "https://careernest.cloud/api/feed?limit=100",
    "Arbeitnow": "https://www.arbeitnow.com/api/job-board-api",
    "Remote First Jobs": "https://remotefirstjobs.com/api/search-jobs",
}

# \u0426\u0435\u043b\u0435\u0432\u044b\u0435 \u043d\u0430\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f: \u0430\u043d\u0438\u043c\u0430\u0446\u0438\u044f \u043b\u043e\u0433\u043e\u0442\u0438\u043f\u043e\u0432, \u043a\u0430\u0440\u0442\u043e\u0447\u043a\u0438 \u0442\u043e\u0432\u0430\u0440\u043e\u0432 \u0438 \u043b\u044e\u0431\u044b\u0435 AI-\u0440\u043e\u043b\u0438.
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
    # \u0417\u0430\u0440\u0443\u0431\u0435\u0436\u043d\u044b\u0435 \u043a\u0430\u043d\u0430\u043b\u044b (\u0430\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u0438\u0439/\u0438\u0441\u043f\u0430\u043d\u0441\u043a\u0438\u0439)
    '@remotegraphicdesignjobs',
    '@findmyremote_design',
]
# \u0421\u0442\u0440\u043e\u0433\u0438\u0439 \u0444\u0438\u043b\u044c\u0442\u0440: \u043f\u0440\u043e\u043f\u0443\u0441\u043a\u0430\u0435\u043c \u0442\u043e\u043b\u044c\u043a\u043e \u044f\u0432\u043d\u044b\u0439 \u043f\u043e\u0438\u0441\u043a \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044f/\u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430.
# \u041e\u0431\u0449\u0438\u0435 \u0441\u043b\u043e\u0432\u0430 \u0432\u0440\u043e\u0434\u0435 \u00ab\u0438\u043d\u0444\u043e\u0433\u0440\u0430\u0444\u0438\u043a\u0430\u00bb, \u00abWB\u00bb \u0438 \u00ab\u043a\u0430\u0440\u0442\u043e\u0447\u043a\u0438\u00bb \u0441\u0430\u043c\u0438 \u043f\u043e \u0441\u0435\u0431\u0435 \u043d\u0435 \u043f\u043e\u0434\u0445\u043e\u0434\u044f\u0442.
POSITIVE = [
    "\u0438\u0449\u0443 \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430",
    "\u0438\u0449\u0435\u043c \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430",
    "\u043d\u0443\u0436\u0435\u043d \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440",
    "\u043d\u0443\u0436\u043d\u0430 \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440",
    "\u043d\u0443\u0436\u0435\u043d \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u043a\u0430\u0440\u0442\u043e\u0447\u0435\u043a",
    "\u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440",
    "\u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u043a\u0430\u0440\u0442\u043e\u0447\u0435\u043a",
    "\u0438\u0449\u0443 \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430 \u043a\u0430\u0440\u0442\u043e\u0447\u0435\u043a",
    "\u0438\u0449\u0435\u043c \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430 \u043a\u0430\u0440\u0442\u043e\u0447\u0435\u043a",
    "\u0438\u0449\u0443 \u0438\u043d\u0444\u043e\u0433\u0440\u0430\u0444\u0438\u0441\u0442\u0430",
    "\u0438\u0449\u0435\u043c \u0438\u043d\u0444\u043e\u0433\u0440\u0430\u0444\u0438\u0441\u0442\u0430",
    "\u043d\u0443\u0436\u0435\u043d \u0438\u043d\u0444\u043e\u0433\u0440\u0430\u0444\u0438\u0441\u0442",
    "\u043d\u0443\u0436\u043d\u0430 \u0438\u043d\u0444\u043e\u0433\u0440\u0430\u0444\u0438\u0441\u0442",
    "\u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u0438\u043d\u0444\u043e\u0433\u0440\u0430\u0444\u0438\u0441\u0442",
    "\u0438\u0449\u0443 \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044f",
    "\u0438\u0449\u0435\u043c \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044f",
    "\u043d\u0443\u0436\u0435\u043d \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c",
    "\u043d\u0443\u0436\u043d\u0430 \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c",
    "\u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c",
    "\u0438\u0449\u0443 \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0441\u0442\u0430 \u043f\u043e \u0434\u0438\u0437\u0430\u0439\u043d\u0443",
    "\u0438\u0449\u0435\u043c \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0441\u0442\u0430 \u043f\u043e \u0434\u0438\u0437\u0430\u0439\u043d\u0443",
    "\u043d\u0443\u0436\u0435\u043d \u0441\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0441\u0442 \u043f\u043e \u0434\u0438\u0437\u0430\u0439\u043d\u0443",
    "\u043d\u0443\u0436\u0435\u043d \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u0434\u043b\u044f",
    "\u043d\u0443\u0436\u043d\u0430 \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u0434\u043b\u044f",
    "\u0437\u0430\u043a\u0430\u0437 \u043d\u0430 \u0434\u0438\u0437\u0430\u0439\u043d",
    "\u0435\u0441\u0442\u044c \u0437\u0430\u043a\u0430\u0437 \u043d\u0430 \u0434\u0438\u0437\u0430\u0439\u043d",
    "\u0438\u0449\u0443 \u0447\u0435\u043b\u043e\u0432\u0435\u043a\u0430 \u0434\u043b\u044f \u0434\u0438\u0437\u0430\u0439\u043d\u0430",
    # \u041b\u043e\u0433\u043e\u0442\u0438\u043f\u044b, \u0431\u0430\u043d\u043d\u0435\u0440\u044b \u0438 \u0444\u0438\u0440\u043c\u0435\u043d\u043d\u044b\u0439 \u0441\u0442\u0438\u043b\u044c (\u0440\u0443\u0441\u0441\u043a\u0438\u0439)
    "\u0438\u0449\u0443 \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430 \u043b\u043e\u0433\u043e\u0442\u0438\u043f\u0430",
    "\u0438\u0449\u0435\u043c \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430 \u043b\u043e\u0433\u043e\u0442\u0438\u043f\u0430",
    "\u043d\u0443\u0436\u0435\u043d \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u043b\u043e\u0433\u043e\u0442\u0438\u043f\u0430",
    "\u043d\u0443\u0436\u0435\u043d \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u0434\u043b\u044f \u043b\u043e\u0433\u043e\u0442\u0438\u043f\u0430",
    "\u0437\u0430\u043a\u0430\u0437\u0430\u0442\u044c \u043b\u043e\u0433\u043e\u0442\u0438\u043f",
    "\u0437\u0430\u043a\u0430\u0437 \u043d\u0430 \u043b\u043e\u0433\u043e\u0442\u0438\u043f",
    "\u0438\u0449\u0443 \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430 \u0431\u0430\u043d\u043d\u0435\u0440\u043e\u0432",
    "\u0438\u0449\u0435\u043c \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430 \u0431\u0430\u043d\u043d\u0435\u0440\u043e\u0432",
    "\u043d\u0443\u0436\u0435\u043d \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u0431\u0430\u043d\u043d\u0435\u0440\u043e\u0432",
    "\u043d\u0443\u0436\u0435\u043d \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u0434\u043b\u044f \u0431\u0430\u043d\u043d\u0435\u0440\u0430",
    "\u0437\u0430\u043a\u0430\u0437\u0430\u0442\u044c \u0431\u0430\u043d\u043d\u0435\u0440",
    "\u0437\u0430\u043a\u0430\u0437 \u043d\u0430 \u0431\u0430\u043d\u043d\u0435\u0440",
    "\u0438\u0449\u0443 \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430 \u0444\u0438\u0440\u043c\u0435\u043d\u043d\u043e\u0433\u043e \u0441\u0442\u0438\u043b\u044f",
    "\u043d\u0443\u0436\u0435\u043d \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u0444\u0438\u0440\u043c\u0435\u043d\u043d\u043e\u0433\u043e \u0441\u0442\u0438\u043b\u044f",
    # \u0410\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u0438\u0435 \u0444\u043e\u0440\u043c\u0443\u043b\u0438\u0440\u043e\u0432\u043a\u0438 \u0437\u0430\u043a\u0430\u0437\u043e\u0432 \u0432 \u0437\u0430\u0440\u0443\u0431\u0435\u0436\u043d\u044b\u0445 \u043a\u0430\u043d\u0430\u043b\u0430\u0445
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
    "\u043f\u0440\u0435\u0434\u043b\u0430\u0433\u0430\u044e \u0443\u0441\u043b\u0443\u0433\u0438",
    "\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u044e \u0443\u0441\u043b\u0443\u0433\u0438",
    "\u043c\u043e\u0438 \u0443\u0441\u043b\u0443\u0433\u0438",
    "\u0443\u0441\u043b\u0443\u0433\u0438 \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440\u0430",
    "\u044f \u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440",
    "\u0434\u0438\u0437\u0430\u0439\u043d\u0435\u0440 \u043d\u0430 \u0441\u0432\u044f\u0437\u0438",
    "\u0438\u0449\u0443 \u0440\u0430\u0431\u043e\u0442\u0443",
    "\u0438\u0449\u0443 \u0437\u0430\u043a\u0430\u0437\u044b",
    "\u0438\u0449\u0443 \u0437\u0430\u043a\u0430\u0437\u0447\u0438\u043a\u043e\u0432",
    "\u0438\u0449\u0443 \u043a\u043b\u0438\u0435\u043d\u0442\u043e\u0432",
    "\u0438\u0449\u0443 \u043f\u0440\u043e\u0435\u043a\u0442\u044b",
    "\u0432\u043e\u0437\u044c\u043c\u0443 \u0437\u0430\u043a\u0430\u0437",
    "\u0432\u043e\u0437\u044c\u043c\u0443 \u0437\u0430\u043a\u0430\u0437\u044b",
    "\u0441\u0432\u043e\u0431\u043e\u0434\u0435\u043d \u0434\u043b\u044f \u0437\u0430\u043a\u0430\u0437\u043e\u0432",
    "\u0441\u0432\u043e\u0431\u043e\u0434\u043d\u0430 \u0434\u043b\u044f \u0437\u0430\u043a\u0430\u0437\u043e\u0432",
    "\u043f\u043e\u0440\u0442\u0444\u043e\u043b\u0438\u043e",
    "\u043e\u0431\u0443\u0447\u0435\u043d\u0438\u0435",
    "\u043a\u0443\u0440\u0441",
    "\u0432\u0435\u0431\u0438\u043d\u0430\u0440",
    # \u0410\u043d\u0433\u043b\u043e\u044f\u0437\u044b\u0447\u043d\u0430\u044f \u0441\u0430\u043c\u043e\u0440\u0435\u043a\u043b\u0430\u043c\u0430 \u0438 \u043f\u043e\u0438\u0441\u043a \u0437\u0430\u043a\u0430\u0437\u043e\u0432 \u0441\u0430\u043c\u0438\u043c \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u0435\u043c
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
    normalized = re.sub(r"\s+", " ", text.lower().replace("\u0451", "\u0435"))
    # \u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u043e\u0442\u0441\u0435\u043a\u0430\u0435\u043c \u0441\u0430\u043c\u043e\u0440\u0435\u043a\u043b\u0430\u043c\u0443 \u0438 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u044f \u0443\u0441\u043b\u0443\u0433.
    if any(word in normalized for word in NEGATIVE):
        return False
    # \u0422\u0440\u0435\u0431\u0443\u0435\u043c \u044f\u0432\u043d\u0443\u044e \u0444\u043e\u0440\u043c\u0443\u043b\u0438\u0440\u043e\u0432\u043a\u0443, \u0447\u0442\u043e \u0430\u0432\u0442\u043e\u0440 \u0438\u0449\u0435\u0442 \u0438\u0441\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044f.
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
                        text=f"\U0001f195 \u041d\u0430\u0439\u0434\u0435\u043d\u043e \u043d\u043e\u0432\u044b\u0445 \u0437\u0430\u043a\u0430\u0437\u043e\u0432: {found}\n\U0001f4cb \u0423 \u0442\u0435\u0431\u044f \u043e\u0436\u0438\u0434\u0430\u044e\u0442 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430: {count}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f440 \u0421\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u0437\u0430\u043a\u0430\u0437\u044b", callback_data="queue:open")]]),
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


def _has_mojibake(value):
    """\u041e\u043f\u0440\u0435\u0434\u0435\u043b\u044f\u0435\u0442 \u0440\u0430\u0441\u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0451\u043d\u043d\u044b\u0435 \u0441\u043b\u0435\u0434\u044b \u043d\u0435\u0432\u0435\u0440\u043d\u043e\u0439 \u0434\u0435\u043a\u043e\u0434\u0438\u0440\u043e\u0432\u043a\u0438 \u0442\u0435\u043a\u0441\u0442\u0430."""
    if not isinstance(value, str):
        return False
    markers = (
        "\u00c3", "\u00c2", "\u00d0", "\u00d1", "\u00f0",
        "\u00de", "\u00e2\u20ac", "\u0420\u045f", "\u0421\u045f",
    )
    return any(marker in value for marker in markers)


def _repair_mojibake(value):
    """\u0418\u0441\u043f\u0440\u0430\u0432\u043b\u044f\u0435\u0442 \u0440\u0430\u0441\u043f\u0440\u043e\u0441\u0442\u0440\u0430\u043d\u0451\u043d\u043d\u0443\u044e \u043e\u0448\u0438\u0431\u043a\u0443, \u043a\u043e\u0433\u0434\u0430 UTF-8 \u043f\u0440\u043e\u0447\u0438\u0442\u0430\u043d \u043a\u0430\u043a legacy-\u043a\u043e\u0434\u0438\u0440\u043e\u0432\u043a\u0430."""
    if not isinstance(value, str):
        return value

    # \u0418\u043d\u043e\u0433\u0434\u0430 \u0442\u0435\u043a\u0441\u0442 \u0431\u044b\u043b \u0438\u0441\u043f\u043e\u0440\u0447\u0435\u043d \u0431\u043e\u043b\u044c\u0448\u0435 \u043e\u0434\u043d\u043e\u0433\u043e \u0440\u0430\u0437\u0430, \u043f\u043e\u044d\u0442\u043e\u043c\u0443 \u043f\u0440\u043e\u0431\u0443\u0435\u043c \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u043e \u043f\u0440\u043e\u0445\u043e\u0434\u043e\u0432.
    current = value
    for _ in range(3):
        if not _has_mojibake(current):
            break
        candidates = []
        for encoding in ("cp1252", "latin-1", "cp1251"):
            try:
                candidate = current.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            if candidate != current:
                candidates.append(candidate)
        if not candidates:
            break
        # \u0412\u044b\u0431\u0438\u0440\u0430\u0435\u043c \u043f\u0440\u0435\u043e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u043d\u0438\u0435, \u043f\u043e\u0441\u043b\u0435 \u043a\u043e\u0442\u043e\u0440\u043e\u0433\u043e \u043e\u0441\u0442\u0430\u043b\u043e\u0441\u044c \u043c\u0435\u043d\u044c\u0448\u0435 \u043c\u0430\u0440\u043a\u0435\u0440\u043e\u0432.
        current = min(candidates, key=lambda item: sum(
            item.count(marker) for marker in (
                "\u00c3", "\u00c2", "\u00d0", "\u00d1", "\u00f0",
                "\u00de", "\u00e2\u20ac", "\u0420\u045f", "\u0421\u045f",
            )
        ))
    return current


def _safe_job_body(body):
    """\u041d\u0435 \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044e \u043d\u0435\u0447\u0438\u0442\u0430\u0435\u043c\u044b\u0439 \u0442\u0435\u043a\u0441\u0442 \u0438\u0437 \u0441\u0442\u0430\u0440\u044b\u0445 \u0437\u0430\u043f\u0438\u0441\u0435\u0439 \u0431\u0430\u0437\u044b."""
    repaired = _repair_mojibake(body or "")
    if _has_mojibake(repaired):
        return "\u26a0\ufe0f \u0422\u0435\u043a\u0441\u0442 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u044f \u043f\u043e\u043b\u0443\u0447\u0435\u043d \u0432 \u043f\u043e\u0432\u0440\u0435\u0436\u0434\u0451\u043d\u043d\u043e\u0439 \u043a\u043e\u0434\u0438\u0440\u043e\u0432\u043a\u0435. \u041e\u0442\u043a\u0440\u043e\u0439 \u043e\u0440\u0438\u0433\u0438\u043d\u0430\u043b \u043f\u043e \u0441\u0441\u044b\u043b\u043a\u0435 \u043d\u0438\u0436\u0435."
    return repaired


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
    """\u0427\u0438\u0442\u0430\u0435\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u043f\u0443\u0431\u043b\u0438\u0447\u043d\u044b\u0435 JSON API, \u0431\u0435\u0437 \u0432\u0445\u043e\u0434\u0430 \u0438 \u043e\u0431\u0445\u043e\u0434\u0430 \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0435\u043d\u0438\u0439 \u0441\u0430\u0439\u0442\u043e\u0432."""
    checked = errors = found = 0
    for source, url in WEB_SOURCES.items():
        try:
            data = await asyncio.to_thread(_fetch_json, url)
            checked += 1
            for item in _extract_web_jobs(source, data):
                title = _repair_mojibake(str(item.get("title") or "")).strip()
                if _has_mojibake(title):
                    title = ""
                description = _repair_mojibake(str(item.get("description") or "")).strip()
                if _has_mojibake(description):
                    description = ""
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
                    f"\U0001f310 <b>\u0417\u0430\u0440\u0443\u0431\u0435\u0436\u043d\u044b\u0439 \u0441\u0430\u0439\u0442: {html.escape(source)}</b>\n"
                    f"\U0001f4bc <b>{html.escape(title[:300])}</b>\n"
                    f"\U0001f3e2 {html.escape(_repair_mojibake(str(item.get('company') or '\u041a\u043e\u043c\u043f\u0430\u043d\u0438\u044f \u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d\u0430'))[:200])}\n\n"
                    f"{html.escape(_plain_text(description)[:2200])}\n\n"
                    f"\U0001f50e \u0422\u0435\u043c\u0430\u0442\u0438\u043a\u0430: {html.escape(', '.join(k for k in WEB_KEYWORDS if k.casefold() in (title + ' ' + _plain_text(description)).casefold())[:500])}"
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
                        text=f"\U0001f310 \u041d\u0430\u0439\u0434\u0435\u043d\u044b \u043d\u043e\u0432\u044b\u0435 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u0438 \u043d\u0430 \u0437\u0430\u0440\u0443\u0431\u0435\u0436\u043d\u044b\u0445 \u0441\u0430\u0439\u0442\u0430\u0445: {found}\n\U0001f4cb \u041e\u0436\u0438\u0434\u0430\u044e\u0442 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430: {count}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f440 \u0421\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u0437\u0430\u043a\u0430\u0437\u044b", callback_data="queue:open")]]),
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
            f"\U0001f389 \u0412\u0441\u0435 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u044f \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u043d\u044b!\n\u2b50 \u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e: {saved_count(user_id)}",
            reply_markup=None,
        )
        return
    key, body, channel, link = jobs[0]
    total = len(jobs)
    # \u041d\u043e\u043c\u0435\u0440 \u0442\u0435\u043a\u0443\u0449\u0435\u0433\u043e \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u044f \u043e\u0442\u043d\u043e\u0441\u0438\u0442\u0435\u043b\u044c\u043d\u043e \u0443\u0436\u0435 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u043d\u043d\u044b\u0445 \u0432 \u044d\u0442\u043e\u0439 \u043e\u0447\u0435\u0440\u0435\u0434\u0438.
    with db() as con:
        reviewed = con.execute(
            "SELECT COUNT(*) FROM decisions WHERE user_id=?", (str(user_id),)
        ).fetchone()[0]
    number = reviewed + 1
    text = (
        f"\U0001f4cb <b>\u0417\u0430\u043a\u0430\u0437 {number} \u0438\u0437 {number + total - 1}</b>\n"
        f"\u2b50 \u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e: {saved_count(user_id)}\n\n"
        f"{html.escape(_safe_job_body(body))}\n\n"
        f"\U0001f4e3 \u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a: {html.escape(channel)}\n"
        f'<a href="{html.escape(link, quote=True)}">\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043e\u0440\u0438\u0433\u0438\u043d\u0430\u043b</a>'
    )
    # \u041a\u043e\u0440\u043e\u0442\u043a\u0438\u0435 callback_data: Telegram \u0434\u043e\u043f\u0443\u0441\u043a\u0430\u0435\u0442 \u043d\u0435 \u0431\u043e\u043b\u0435\u0435 64 \u0431\u0430\u0439\u0442.
    # \u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0437\u0430\u043a\u0430\u0437 \u0431\u0435\u0440\u0451\u0442\u0441\u044f \u0438\u0437 \u043e\u0447\u0435\u0440\u0435\u0434\u0438 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u0432 queue_callback.
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("\u274c \u041f\u0440\u043e\u043f\u0443\u0441\u0442\u0438\u0442\u044c", callback_data="queue:skip"),
         InlineKeyboardButton("\u2705 \u041e\u0441\u0442\u0430\u0432\u0438\u0442\u044c", callback_data="queue:keep")],
        [InlineKeyboardButton("\U0001f1f7\U0001f1fa \u041f\u0435\u0440\u0435\u0432\u0435\u0441\u0442\u0438", callback_data="queue:translate")],
        [InlineKeyboardButton("\u2b05\ufe0f \u041d\u0430\u0437\u0430\u0434", callback_data="queue:back")],
    ])
    text = _repair_mojibake(text)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard, disable_web_page_preview=True)


def translate_to_russian(text: str) -> str:
    """\u041f\u0435\u0440\u0435\u0432\u043e\u0434\u0438\u0442 \u0442\u0435\u043a\u0441\u0442 \u0447\u0435\u0440\u0435\u0437 \u043f\u0443\u0431\u043b\u0438\u0447\u043d\u044b\u0439 Google Translate endpoint."""
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
        await query.answer("\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.", show_alert=True)
        return
    data = query.data or ""
    if data == "queue:translate":
        await query.answer("\u041f\u0435\u0440\u0435\u0432\u043e\u0436\u0443\u2026")
        jobs = pending_jobs(user_id)
        if not jobs:
            await query.answer("\u041e\u0447\u0435\u0440\u0435\u0434\u044c \u043f\u0443\u0441\u0442\u0430.", show_alert=True)
            return
        key, body, channel, link = jobs[0]
        try:
            translated = await asyncio.to_thread(translate_to_russian, body)
            translated = translated[:3500]
            await query.message.reply_text(
                "\U0001f1f7\U0001f1fa <b>\u041f\u0435\u0440\u0435\u0432\u043e\u0434 \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u0438\u0439</b>\n\n" + html.escape(translated),
                parse_mode="HTML", disable_web_page_preview=True,
            )
        except Exception as exc:
            log.warning("Translation failed: %s", type(exc).__name__)
            await query.message.reply_text(
                "\u26a0\ufe0f \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u0435\u0440\u0435\u0432\u0435\u0441\u0442\u0438. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 \u043f\u043e\u0437\u0436\u0435."
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
            await query.edit_message_text("\U0001f4ed \u041e\u0447\u0435\u0440\u0435\u0434\u044c \u043f\u0443\u0441\u0442\u0430.", reply_markup=None)
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
        await reply(update, "\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.")
        return
    user_id = str(update.effective_user.id)
    with db() as con:
        rows = con.execute(
            "SELECT j.body, j.link FROM jobs j JOIN decisions d ON d.job_key=j.key "
            "WHERE d.user_id=? AND d.decision='keep' ORDER BY d.decided_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
    if not rows:
        await reply(update, "\u2b50 \u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0441\u043e\u0445\u0440\u0430\u043d\u0451\u043d\u043d\u044b\u0445 \u0437\u0430\u043a\u0430\u0437\u043e\u0432.")
        return
    text = "\u2b50 <b>\u0421\u043e\u0445\u0440\u0430\u043d\u0451\u043d\u043d\u044b\u0435 \u0437\u0430\u043a\u0430\u0437\u044b</b>\n\n" + "\n\n".join(
        f"{i}. {html.escape(body[:700])}\n<a href=\"{html.escape(link, quote=True)}\">\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043e\u0440\u0438\u0433\u0438\u043d\u0430\u043b</a>"
        for i, (body, link) in enumerate(rows, 1)
    )
    await update.effective_chat.send_message(text=text, parse_mode="HTML", disable_web_page_preview=True)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.")
        return
    user_id = str(update.effective_user.id)
    with db() as con:
        total = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        kept = con.execute("SELECT COUNT(*) FROM decisions WHERE user_id=? AND decision='keep'", (user_id,)).fetchone()[0]
        skipped = con.execute("SELECT COUNT(*) FROM decisions WHERE user_id=? AND decision='skip'", (user_id,)).fetchone()[0]
    paused, keyword = get_pref(user_id)
    await reply(update, f"\U0001f4ca \u0422\u0432\u043e\u044f \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430\n\u0412\u0441\u0435\u0433\u043e \u043d\u0430\u0439\u0434\u0435\u043d\u043e: {total}\n\u2b50 \u0421\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u043e: {kept}\n\u274c \u041f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u043e: {skipped}\n\u23f3 \u041e\u0436\u0438\u0434\u0430\u044e\u0442 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430: {pending_count(user_id)}\n\u0423\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f: {'\u043f\u0430\u0443\u0437\u0430' if paused else '\u0432\u043a\u043b\u044e\u0447\u0435\u043d\u044b'}\n\u0424\u0438\u043b\u044c\u0442\u0440: {html.escape(keyword) if keyword else '\u043d\u0435 \u0437\u0430\u0434\u0430\u043d'}")


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.")
        return
    user_id = str(update.effective_user.id)
    paused, _ = get_pref(user_id)
    set_paused(user_id, not paused)
    await reply(update, "\u23f8\ufe0f \u0423\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f \u043f\u0440\u0438\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u044b. \u041e\u0447\u0435\u0440\u0435\u0434\u044c \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u043a\u043e\u043c\u0430\u043d\u0434\u043e\u0439 /queue." if not paused else "\u25b6\ufe0f \u0423\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u044f \u0441\u043d\u043e\u0432\u0430 \u0432\u043a\u043b\u044e\u0447\u0435\u043d\u044b.")


async def filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.")
        return
    user_id = str(update.effective_user.id)
    keyword = " ".join(context.args).strip()
    if keyword.lower() == "clear":
        keyword = ""
    set_keyword(user_id, keyword)
    await reply(update, (f"\U0001f50d \u0424\u0438\u043b\u044c\u0442\u0440 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d: {html.escape(keyword)}\n\u0412 \u043e\u0447\u0435\u0440\u0435\u0434\u0438: {pending_count(user_id)}" if keyword else "\U0001f50d \u0424\u0438\u043b\u044c\u0442\u0440 \u043e\u0447\u0438\u0449\u0435\u043d. \u041f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u044e \u0432\u0441\u0435 \u043f\u043e\u0434\u0445\u043e\u0434\u044f\u0449\u0438\u0435 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u044f."))


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.")
        return
    user_id = str(update.effective_user.id)
    jobs = pending_jobs(user_id)
    if not jobs:
        await reply(update, "\U0001f4ed \u041d\u0435\u0442 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439 \u0434\u043b\u044f \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439 /scan \u0438\u043b\u0438 \u043e\u0447\u0438\u0441\u0442\u0438 \u0444\u0438\u043b\u044c\u0442\u0440 \u043a\u043e\u043c\u0430\u043d\u0434\u043e\u0439 /filter clear.")
        return
    await update.effective_chat.send_message(
        text=f"\U0001f4cb \u041d\u0430\u0439\u0434\u0435\u043d\u043e \u0434\u043b\u044f \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430: {len(jobs)}\n\u041d\u0430\u0436\u043c\u0438 \u043a\u043d\u043e\u043f\u043a\u0443, \u0447\u0442\u043e\u0431\u044b \u043d\u0430\u0447\u0430\u0442\u044c.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("\U0001f440 \u0421\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u0437\u0430\u043a\u0430\u0437\u044b", callback_data="queue:open")]]),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.")
        return
    await reply(
        update,
        "\u041f\u0440\u0438\u0432\u0435\u0442! \u042f \u0438\u0449\u0443 \u0441\u0432\u0435\u0436\u0438\u0435 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u044f \u043e \u0437\u0430\u043a\u0430\u0437\u0430\u0445 \u043d\u0430 \u0434\u0438\u0437\u0430\u0439\u043d \u043a\u0430\u0440\u0442\u043e\u0447\u0435\u043a \u0442\u043e\u0432\u0430\u0440\u043e\u0432.\n\n"
        f"\u0412\u043e\u0437\u0440\u0430\u0441\u0442 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439: \u0434\u043e {MAX_AGE_HOURS} \u0447.\n"
        f"\u0418\u043d\u0442\u0435\u0440\u0432\u0430\u043b \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438: {SCAN_MINUTES} \u043c\u0438\u043d.\n\n"
        "/status \u2014 \u0441\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435\n"
        "/scan \u2014 \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c Telegram-\u043a\u0430\u043d\u0430\u043b\u044b \u0441\u0435\u0439\u0447\u0430\u0441\n"
        "/webscan \u2014 \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0437\u0430\u0440\u0443\u0431\u0435\u0436\u043d\u044b\u0435 \u0441\u0430\u0439\u0442\u044b \u0441\u0435\u0439\u0447\u0430\u0441\n"
        "/saved \u2014 \u0441\u043e\u0445\u0440\u0430\u043d\u0451\u043d\u043d\u044b\u0435 \u0437\u0430\u043a\u0430\u0437\u044b\n"
        "/stats \u2014 \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430\n"
        "/queue \u2014 \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u043e\u0447\u0435\u0440\u0435\u0434\u044c\n"
        "/pause \u2014 \u043f\u0430\u0443\u0437\u0430/\u0432\u043e\u0437\u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u0443\u0432\u0435\u0434\u043e\u043c\u043b\u0435\u043d\u0438\u0439\n"
        "/filter \u0441\u043b\u043e\u0432\u043e \u2014 \u0444\u0438\u043b\u044c\u0442\u0440 \u043f\u043e \u0441\u043b\u043e\u0432\u0430\u043c; /filter clear \u2014 \u0441\u0431\u0440\u043e\u0441\n"
        "/myid \u2014 \u0443\u0437\u043d\u0430\u0442\u044c Telegram ID\n"
        "\u041f\u043e\u0438\u0441\u043a \u0440\u0430\u0431\u043e\u0442\u0430\u0435\u0442 \u0431\u0435\u0437 \u043d\u0435\u0439\u0440\u043e\u0441\u0435\u0442\u0438.",
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(
        update,
        f"\u0422\u0432\u043e\u0439 Telegram ID: "
        f"{update.effective_user.id if update.effective_user else '\u043d\u0435 \u043e\u043f\u0440\u0435\u0434\u0435\u043b\u0451\u043d'}",
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.")
        return
    connected = user_client is not None and user_client.is_connected()
    await reply(
        update,
        f"\U0001f7e2 \u0411\u043e\u0442 \u0437\u0430\u043f\u0443\u0449\u0435\u043d\n"
        f"Telegram-\u0430\u043a\u043a\u0430\u0443\u043d\u0442 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d: {'\u0434\u0430' if connected else '\u043d\u0435\u0442'}\n"
        f"\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439: {len(ALLOWED_USER_IDS)}\n"
        f"\u041a\u0430\u043d\u0430\u043b\u043e\u0432 \u0432 \u0441\u043f\u0438\u0441\u043a\u0435: {len(CHANNELS)}\n"
        f"\u0421\u0430\u0439\u0442\u043e\u0432 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u0439: {len(WEB_SOURCES)}\n"
        f"\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0441\u0430\u0439\u0442\u043e\u0432: \u043a\u0430\u0436\u0434\u044b\u0435 {WEB_SCAN_HOURS} \u0447.\n"
        f"\u0418\u043d\u0442\u0435\u0440\u0432\u0430\u043b \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438: {SCAN_MINUTES} \u043c\u0438\u043d.\n"
        f"\u041c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u044b\u0439 \u0432\u043e\u0437\u0440\u0430\u0441\u0442 \u0437\u0430\u044f\u0432\u043a\u0438: {MAX_AGE_HOURS} \u0447.",
    )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.")
        return
    if scan_lock.locked():
        await reply(update, "\u23f3 \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0443\u0436\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u044f\u0435\u0442\u0441\u044f.")
        return
    await reply(update, "\U0001f50e \u041f\u0440\u043e\u0432\u0435\u0440\u044f\u044e Telegram-\u043a\u0430\u043d\u0430\u043b\u044b\u2026")
    result = await run_scan(context.application)
    if result is None:
        await reply(update, "\u26a0\ufe0f \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043d\u0435 \u0437\u0430\u0432\u0435\u0440\u0448\u0438\u043b\u0430\u0441\u044c. \u041f\u043e\u0441\u043c\u043e\u0442\u0440\u0438 \u0436\u0443\u0440\u043d\u0430\u043b FadeHost.")
    else:
        await reply(
            update,
            "\u2705 \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430.\n"
            f"\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u043e \u043a\u0430\u043d\u0430\u043b\u043e\u0432: {result['checked']} \u0438\u0437 {result['total']}\n"
            f"\u041e\u0448\u0438\u0431\u043e\u043a: {result['errors']}\n"
            f"\u041d\u043e\u0432\u044b\u0445 \u043f\u043e\u0434\u0445\u043e\u0434\u044f\u0449\u0438\u0445 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439: {result['found']}\n"
            f"\u0421\u0442\u0430\u0440\u044b\u0445 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439 \u043f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u043e: {result['old']}",
        )



async def webscan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await reply(update, "\u0414\u043e\u0441\u0442\u0443\u043f \u0437\u0430\u043a\u0440\u044b\u0442.")
        return
    await reply(update, "\U0001f310 \u041f\u0440\u043e\u0432\u0435\u0440\u044f\u044e \u0437\u0430\u0440\u0443\u0431\u0435\u0436\u043d\u044b\u0435 \u0441\u0430\u0439\u0442\u044b \u0441 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u044f\u043c\u0438\u2026")
    result = await scan_websites(context.application)
    await reply(
        update,
        "\u2705 \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0441\u0430\u0439\u0442\u043e\u0432 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430.\n"
        f"\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u043e\u0432 \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043e: {result['checked']} \u0438\u0437 {result['total']}\n"
        f"\u041e\u0448\u0438\u0431\u043e\u043a: {result['errors']}\n"
        f"\u041d\u043e\u0432\u044b\u0445 \u043f\u043e\u0434\u0445\u043e\u0434\u044f\u0449\u0438\u0445 \u043e\u0431\u044a\u044f\u0432\u043b\u0435\u043d\u0438\u0439: {result['found']}",
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
