"""
STREET TEST — Test Tekshirish Telegram Boti va Mini App Serveri
Aiogram 3.x + aiohttp WebApp Server
============================================================
Barcha muhim sozlamalar environment variable orqali o'rnatiladi.
Tokenlar va ID lar bu yerda saqlanmaydi — faqat os.getenv() ishlatiladi.
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import sys
import time
import re
import urllib.parse
from typing import Optional, Dict, Any, Tuple, List
import html

from aiogram import Bot, Dispatcher, F, Router, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, KICKED, MEMBER
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    WebAppInfo, FSInputFile, MenuButtonWebApp, MenuButtonDefault, BotCommand, ChatMemberUpdated
)
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest, TelegramAPIError
from aiohttp import web
import test_db
from datetime import datetime, timezone, timedelta

UZB_TZ = timezone(timedelta(hours=5))

def format_uzb_time(timestamp: Optional[float] = None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    """O'zbekiston (Toshkent, UTC+5) vaqti bo'yicha formatlash"""
    if timestamp is None:
        dt = datetime.now(UZB_TZ)
    else:
        dt = datetime.fromtimestamp(timestamp, tz=UZB_TZ)
    return dt.strftime(fmt)

def get_test_schedule_status(test: Dict[str, Any]) -> Dict[str, Any]:
    """
    Testning joriy vaqtga (UZB_TZ) nisbatan aniq holatini hisoblaydi:
    - is_upcoming: Test boshlanish vaqti hali kelmagan
    - is_active: Test ayni paytda faol va yechish mumkin
    - is_closed: Test vaqti tugagan yoki to'xtatilgan
    """
    now_uzb = datetime.now(UZB_TZ)
    now_minutes = now_uzb.hour * 60 + now_uzb.minute
    today_date = now_uzb.date()

    sdate = str(test.get('scheduled_date') or '').strip()
    sstart = str(test.get('scheduled_start') or '').strip()
    send = str(test.get('scheduled_end') or '').strip()
    raw_active = (test.get('is_active', 1) == 1)

    # Agar jadval belgilanmagan bo'lsa
    if not sstart:
        return {
            "is_upcoming": False,
            "is_active": raw_active,
            "is_closed": not raw_active,
            "reason": "no_schedule"
        }

    # Sana tekshiruvi (agar sdate berilgan bo'lsa)
    test_date_obj = None
    if sdate:
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%Y.%m.%d"):
            try:
                test_date_obj = datetime.strptime(sdate, fmt).date()
                break
            except Exception:
                pass

    if test_date_obj:
        if test_date_obj > today_date:
            return {
                "is_upcoming": True,
                "is_active": False,
                "is_closed": False,
                "reason": "future_date"
            }
        elif test_date_obj < today_date:
            return {
                "is_upcoming": False,
                "is_active": False,
                "is_closed": True,
                "reason": "past_date"
            }

    # Bugungi kun bo'yicha start va end daqiqalarini tekshiramiz
    start_minutes = None
    end_minutes = None
    try:
        sh, sm = map(int, sstart.split(":"))
        start_minutes = sh * 60 + sm
    except Exception:
        pass

    if send:
        try:
            eh, em = map(int, send.split(":"))
            end_minutes = eh * 60 + em
        except Exception:
            pass

    if start_minutes is not None:
        if end_minutes is not None and end_minutes < start_minutes:
            # Yarim tun orqali o'tuvchi test (masalan 23:30 dan 00:30 gacha)
            if now_minutes >= start_minutes or now_minutes < end_minutes:
                return {
                    "is_upcoming": False,
                    "is_active": raw_active,
                    "is_closed": not raw_active,
                    "reason": "running_overnight"
                }
            else:
                return {
                    "is_upcoming": True,
                    "is_active": False,
                    "is_closed": False,
                    "reason": "before_start_time"
                }
        else:
            # Bir kunlik normal vaqt oralig'i
            if now_minutes < start_minutes:
                return {
                    "is_upcoming": True,
                    "is_active": False,
                    "is_closed": False,
                    "reason": "before_start_time"
                }
            elif end_minutes is not None and now_minutes >= end_minutes:
                return {
                    "is_upcoming": False,
                    "is_active": False,
                    "is_closed": True,
                    "reason": "after_end_time"
                }
            else:
                return {
                    "is_upcoming": False,
                    "is_active": raw_active,
                    "is_closed": not raw_active,
                    "reason": "running"
                }

    return {
        "is_upcoming": False,
        "is_active": raw_active,
        "is_closed": not raw_active,
        "reason": "default"
    }

# ── 45 DAQIQALIK TOPSHIRISH CHEKLOVI (MILLIY SERTIFIKAT STANDARTI) ──
def get_test_min_submit_info(test: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test boshlanganidan keyingi dastlabki 45 daqiqa davomida javob yuborishni cheklash holatini aniqlaydi.
    Qaytaradi:
    - can_submit: bool (45 daqiqa o'tgan bo'lsa True, aks holda False)
    - remaining_seconds: int (topshirish ochilishigacha qolgan soniyalar)
    - start_time_str: str (boshlangan vaqt, masalan: '20:00')
    - unlock_time_str: str (topshirish ochiladigan vaqt, masalan: '20:45:00')
    - is_before_start: bool (test hali boshlanmaganmi)
    """
    now_uzb = datetime.now(UZB_TZ)
    now_ts = now_uzb.timestamp()

    sdate = str(test.get('scheduled_date') or '').strip()
    sstart = str(test.get('scheduled_start') or '').strip()

    start_dt = None
    if sstart:
        test_date = now_uzb.date()
        if sdate:
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%Y.%m.%d"):
                try:
                    test_date = datetime.strptime(sdate, fmt).date()
                    break
                except Exception:
                    pass
        try:
            sh, sm = map(int, sstart.split(":"))
            start_dt = datetime(test_date.year, test_date.month, test_date.day, sh, sm, 0, tzinfo=UZB_TZ)
        except Exception:
            start_dt = None

    if not start_dt:
        created_at = test.get('created_at')
        if created_at:
            start_dt = datetime.fromtimestamp(created_at, tz=UZB_TZ)
        else:
            start_dt = now_uzb

    start_ts = start_dt.timestamp()
    unlock_dt = start_dt + timedelta(minutes=45)
    unlock_ts = unlock_dt.timestamp()

    if now_ts < unlock_ts:
        rem_sec = max(0, int(unlock_ts - now_ts))
        return {
            "can_submit": False,
            "remaining_seconds": rem_sec,
            "start_time_str": start_dt.strftime("%H:%M"),
            "unlock_time_str": unlock_dt.strftime("%H:%M:%S"),
            "is_before_start": (now_ts < start_ts)
        }

    return {
        "can_submit": True,
        "remaining_seconds": 0,
        "start_time_str": start_dt.strftime("%H:%M"),
        "unlock_time_str": unlock_dt.strftime("%H:%M:%S"),
        "is_before_start": False
    }

# ── TUN REJIMI: 23:00 – 07:00 ────────────────────────────
WORK_START_HOUR = 7   # 07:00 Toshkent
WORK_END_HOUR   = 23  # 23:00 Toshkent

def is_working_hours() -> bool:
    """Hozir ish vaqti (07:00–23:00 Toshkent)mi?"""
    now_hour = datetime.now(UZB_TZ).hour
    return WORK_START_HOUR <= now_hour < WORK_END_HOUR

def get_night_message() -> str:
    """Tun rejimi xabari."""
    now = datetime.now(UZB_TZ)
    if now.hour < WORK_START_HOUR:
        wait_h = WORK_START_HOUR - now.hour
        wait_text = f"{wait_h} soatdan so'ng (07:00 da)"
    else:
        wait_text = "ertaga ertalab 07:00 da"
    return (
        f"🌙 <b>Tun rejimi — Bot hozir dam olmoqda</b>\n\n"
        f"⏰ <b>Ish vaqti:</b> har kuni 07:00 – 23:00 (Toshkent)\n"
        f"🕐 <b>Hozir:</b> {now.strftime('%H:%M')}\n\n"
        f"✅ Bot <b>{wait_text}</b> yana faol bo'ladi.\n\n"
        f"<i>Iltimos, ish vaqtida qayta murojaat qiling!</i> 🙏\n\n"
        f"⛔️ <b>Iltimos, qayta /start yoki boshqa tugmalarni bosmang</b> — "
        f"har bir xabar serverni keraksiz uyg'otadi va bot tezroq o'chib qolishi mumkin."
    )

# ── TEXNIK PROFILAKTIKA REJIMI XABARI VA MIDDLEWARE ──────
def get_maintenance_message() -> str:
    """Texnik profilaktika rejimi xabari."""
    now = datetime.now(UZB_TZ)
    return (
        "🛠 <b>Hozirda botda texnik profilaktika ishlari olib borilmoqda!</b>\n\n"
        "Hurmatli foydalanuvchi, tizim barqarorligini oshirish, yangi imkoniyatlarni sozlash "
        "va ma'lumotlar xavfsizligini ta'minlash maqsadida bot vaqtincha to'xtatildi.\n\n"
        f"🕐 <b>Vaqt:</b> {now.strftime('%H:%M')} (Toshkent)\n"
        "⏱ <b>Holat:</b> Rejali texnik tanaffus\n"
        "👨‍💻 <b>Bajarilmoqda:</b> Tizim yangilanishi va optimallashtirish\n\n"
        "✅ <i>Tez orada barcha xizmatlar to'liq va odatdagidek qayta tiklanadi.</i>\n\n"
        "🙏 <b>Keltirilgan vaqtinchalik noqulayliklar uchun uzr so'raymiz!</b>"
    )

# ── SOZLAMALAR ────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan! .env faylini yoki Render env varsni tekshiring.")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8039427064"))
PORT = int(os.getenv("PORT", "8080"))
_raw_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("WEBAPP_URL", "")
if _raw_url:
    if not _raw_url.startswith("http"):
        _raw_url = f"https://{_raw_url}"
    WEBAPP_URL = _raw_url.rstrip("/")
else:
    WEBAPP_URL = "https://fizika-bot-t560.onrender.com"

CACHED_BOT_USERNAME = os.getenv("BOT_USERNAME", "fizika_rash_testbot")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

class MaintenanceMiddleware(BaseMiddleware):
    """Texnik profilaktika vaqtida FAQAT Bosh Admin (ADMIN_ID) o'ta oladi. Boshqalar to'xtatiladi."""
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user and test_db.is_maintenance_mode():
            if user.id != ADMIN_ID:
                if isinstance(event, Message):
                    await event.answer(get_maintenance_message())
                    return
                elif isinstance(event, CallbackQuery):
                    await event.answer("⚠️ Botda texnik profilaktika ketmoqda!", show_alert=True)
                    try:
                        await event.message.answer(get_maintenance_message())
                    except Exception:
                        pass
                    return
        return await handler(event, data)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.message.outer_middleware(MaintenanceMiddleware())
dp.callback_query.outer_middleware(MaintenanceMiddleware())

router = Router()
dp.include_router(router)

# ── FSM HOLATLARI ─────────────────────────────────────
class RegistrationState(StatesGroup):
    fullname = State()
    phone = State()

class SolveTestState(StatesGroup):
    test_code = State()

class UploadPostPdfState(StatesGroup):
    pdf_file = State()

class AddAdminState(StatesGroup):
    tg_id_or_user = State()

class SetTimeLimitState(StatesGroup):
    test_id = State()
    time_limit = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()
    confirm_send = State()

class ScheduleState(StatesGroup):
    waiting_date = State()
    waiting_start = State()
    waiting_end = State()

class SetYoutubeState(StatesGroup):
    waiting_for_url = State()

class StudentTahlilState(StatesGroup):
    waiting_for_code = State()

class EditProfileState(StatesGroup):
    waiting_new_name = State()
    waiting_new_phone = State()

class ContactUserState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_message = State()

# ── KEYBOARDS (TUGMALAR) ──────────────────────────────
def main_menu_kb(user_tg_id: int) -> ReplyKeyboardMarkup:
    is_adm = test_db.is_admin(user_tg_id, ADMIN_ID)
    
    app_url = f"{WEBAPP_URL}/app.html?tg_id={user_tg_id}&v=20261004_physickb1"
    admin_webapp_url = f"{WEBAPP_URL}/admin.html?tg_id={user_tg_id}&v=20261004_physickb1"

    # Agar HTTPS bo'lsa to'g'ridan-to'g'ri Telegram WebApp ochadi
    if app_url.startswith("https://"):
        results_btn = KeyboardButton(text="◈ Mening natijalarim", web_app=WebAppInfo(url=app_url))
    else:
        results_btn = KeyboardButton(text="◈ Mening natijalarim")

    if admin_webapp_url.startswith("https://"):
        create_test_btn = KeyboardButton(text="✦ Yangi test yaratish", web_app=WebAppInfo(url=admin_webapp_url))
    else:
        create_test_btn = KeyboardButton(text="✦ Yangi test yaratish")

    if is_adm:
        # Adminlar uchun menyu:
        # 1-qator: Test kodini kiritish + Yangi test yaratish (Mini App)
        # 2-qator: Test natijalari va reyting + Testlarni boshqarish
        # 3-qator: Admin Panel
        buttons = [
            [KeyboardButton(text="✦ Test kodini kiritish"), create_test_btn],
            [KeyboardButton(text="◈ Test natijalari va reyting"), KeyboardButton(text="◈ Testlarni boshqarish")],
            [KeyboardButton(text="⚙ Admin Panel")]
        ]
    else:
        # Oddiy foydalanuvchilar uchun menyu tartibi:
        # 1-qator: Test kodini kiritish + Mening natijalarim (Asosiy App)
        # 2-qator: Profilim + Yordam (adminga murojaat)
        buttons = [
            [KeyboardButton(text="✦ Test kodini kiritish"), results_btn],
            [KeyboardButton(text="◈ Profilim"), KeyboardButton(text="› Yordam")]
        ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def profile_webapp_kb(user_tg_id: int) -> InlineKeyboardMarkup:
    """Shaxsiy profil mini ilovasini ochish tugmasi."""
    app_url = f"{WEBAPP_URL}/app.html?tg_id={user_tg_id}&v=20261004_physickb1"
    buttons = [
        [make_webapp_button("◈ Shaxsiy profilni ochish", app_url, fallback_cb="open_app_info")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def results_webapp_kb(user_tg_id: int = 0) -> InlineKeyboardMarkup:
    """Natijalarni ko'rish mini ilovasi tugmasi."""
    qs = f"?tg_id={user_tg_id}&v=20261004_physickb1" if user_tg_id else "?v=20261004_physickb1"
    app_url = f"{WEBAPP_URL}/app.html{qs}"
    buttons = [
        [make_webapp_button("◈ Asosiy ilovani ochish", app_url, fallback_cb="open_app_info")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def contact_share_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="▫️ Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def admin_menu_kb() -> InlineKeyboardMarkup:
    """
    Admin Panel inline menyusi — xabarlar, texnik rejim, test vaqti va adminlar boshqaruvi.
    Foydalanuvchilar boshqaruvi to'liq Asosiy Web Ilovaga (Main App) ko'chirilgan.
    """
    maint_on = test_db.is_maintenance_mode()
    maint_status = "YOQILGAN (Faol)" if maint_on else "O'CHIQ"
    maint_btn_text = f"⚙ Texnik rejim: {maint_status}"

    buttons = [
        [InlineKeyboardButton(text="◈ MacBook Dashboard (Katta Baza)", url=f"{WEBAPP_URL}/dashboard")],
        [InlineKeyboardButton(text="› Foydalanuvchiga yozish / Chat", callback_data="admin_contact_user_prompt")],
        [InlineKeyboardButton(text="✦ O'quvchilarga xabar yuborish", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton(text="▫️ Faoliyatsizlarga ogohlantirish", callback_data="admin_warn_inactive_menu")],
        [InlineKeyboardButton(text="✕ Botni bloklaganlarni tozalash", callback_data="admin_clean_blocked_prompt")],
        [InlineKeyboardButton(text=maint_btn_text, callback_data="admin_toggle_maint_prompt")],
        [InlineKeyboardButton(text="⚙ Adminlar boshqaruvi", callback_data="admin_manage_admins")],
        [make_webapp_button("◈ Foydalanuvchilar boshqaruvi (Web App)", f"{WEBAPP_URL}/app.html?tab=admin&tg_id={ADMIN_ID}", "admin_webapp_redirect_info")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def make_webapp_button(text: str, url: str, fallback_cb: str = "open_webapp_info") -> InlineKeyboardButton:
    """Telegram WebApp faqat HTTPS talab qiladi. Agar HTTP (localhost) bo'lsa callback ishlatiladi."""
    if url.startswith("https://"):
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
    elif url.startswith("http://") and not ("localhost" in url or "127.0.0.1" in url):
        return InlineKeyboardButton(text=text, url=url)
    else:
        return InlineKeyboardButton(text=text, callback_data=fallback_cb)

# ── TEST KARTASINI FOYDALANUVCHIGA YUBORISH (BIR MARTALIK TEKSHIRUV BILAN) ──
async def send_test_card_to_user_chat(user_tg_id: int, test: Dict[str, Any]):
    """Test ma'lumotlari, PDF va WebApp tugmasini foydalanuvchining chatiga yuboradi. Agar foydalanuvchi allaqachon topshirgan bo'lsa qayta topshirish taqiqlanadi."""
    existing_sub = test_db.get_user_submission_for_test(test["id"], user_tg_id)
    is_admin = test_db.is_admin(user_tg_id, ADMIN_ID)
    
    if existing_sub and not is_admin:
        dt = format_uzb_time(existing_sub["submitted_at"])
        is_published = test_db.is_test_results_published(test["id"])
        if is_published:
            grade = test_db.calculate_grade(existing_sub.get("score", 0))
            score_val = existing_sub.get("score", 0)
            corr_val = existing_sub.get("correct_count", 0)
            text = (
                f"✕ <b>Siz ushbu testni topshirgansiz!</b>\n\n"
                f"• <b>Test:</b> {test['title']}\n"
                f"✦ <b>Milliy Sertifikat darajangiz:</b> <b>{grade}</b> ({score_val} ball)\n"
                f"✓ <b>To'g'ri javoblar:</b> {corr_val} ta\n"
                f"• <b>Topshirilgan vaqt:</b> {dt}\n\n"
                f"ℹ <i>Test tahlilini ko'rish uchun quyidagi tugmani bosing:</i>"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◈ Test tahlili", callback_data=f"user_req_tahlil_{test['id']}")]
            ])
            try:
                await bot.send_message(chat_id=user_tg_id, text=text, reply_markup=kb)
            except Exception as e:
                log.warning(f"send_message error: {e}")
        else:
            text = (
                f"▫️ <b>Siz ushbu testni topshirgansiz!</b>\n\n"
                f"• <b>Test:</b> {test['title']}\n"
                f"• <b>Holat:</b> <b>Javoblaringiz tekshirilmoqda...</b>\n"
                f"• <b>Topshirilgan vaqt:</b> {dt}\n\n"
                f"ℹ <i>Test hozirda davom etmoqda. Admin testni to'xtatib, Rasch tahlilini e'lon qilgandan so'ng, "
                f"to'g'ri javoblar soni, yakuniy ball va Milliy sertifikat darajangiz bot orqali shaxsiy xabar qilib yuboriladi!</i>"
            )
            try:
                await bot.send_message(chat_id=user_tg_id, text=text)
            except Exception as e:
                log.warning(f"send_message error: {e}")
        return

    sched_stat = get_test_schedule_status(test)
    if sched_stat["is_upcoming"] and not is_admin:
        sdate = test.get('scheduled_date') or 'Bugun'
        sstart = test.get('scheduled_start') or ''
        try:
            await bot.send_message(
                chat_id=user_tg_id,
                text=(
                    f"▫️ <b>«{test['title']}» testi hali boshlanmagan!</b>\n\n"
                    f"• Belgilangan sana: <b>{sdate}</b>\n"
                    f"• Boshlanish vaqti: <b>{sstart} (UZB)</b>\n\n"
                    f"<i>Test belgilangan vaqtda avtomatik boshlanadi va test kodi hamda savollar ochiladi. Ungacha kuting!</i>"
                )
            )
        except Exception as e:
            log.warning(f"send_message error: {e}")
        return

    if (test.get("is_active", 1) == 0 or sched_stat["is_closed"]) and not is_admin:
        try:
            await bot.send_message(
                chat_id=user_tg_id,
                text=f"✕ <b>«{test['title']}» testi to'xtatilgan!</b>\nAdmin tomonidan javoblar qabul qilish yopilgan."
            )
        except Exception as e:
            log.warning(f"send_message error: {e}")
        return

    params = {
        "test_id": test["id"],
        "test_code": test["test_code"],
        "title": test["title"],
        "subject": test.get("subject", "Fizika"),
        "tg_id": user_tg_id,
        "v": f"20261004_physickb1_{int(time.time())}"
    }
    encoded_url = f"{WEBAPP_URL}?{urllib.parse.urlencode(params)}"

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_webapp_button("✦ Javoblarni topshirish (Mini App)", encoded_url, fallback_cb=f"solve_test_{test['id']}")]
    ])

    time_info = f"• <b>Vaqt chegarasi:</b> {test['time_limit_min']} daqiqa\n" if test.get("time_limit_min", 0) > 0 else ""

    caption = (
        f"✦ <b>{test['title']}</b>\n"
        f"• <b>Fan:</b> {test.get('subject', 'Fizika')}\n"
        f"• <b>Savollar:</b> 55 ta (1-32 ABCD, 33-35 ABCDEF, 36a-45b Yozma)\n"
        f"{time_info}\n"
        f"ℹ <i>Eslatma: Testni faqat 1 marta topshirish mumkin! Javoblaringizni belgilab bo'lgach, «Testni yakunlash» tugmasini bosing.</i>"
    )

    sent = False
    if test.get("pdf_file_id"):
        try:
            await bot.send_document(
                chat_id=user_tg_id,
                document=test["pdf_file_id"],
                caption=caption,
                reply_markup=inline_kb
            )
            sent = True
        except Exception as e:
            log.warning(f"PDF yuborishda xatolik: {e}")

    if not sent:
        try:
            await bot.send_message(chat_id=user_tg_id, text=caption, reply_markup=inline_kb)
        except Exception as e:
            log.error(f"Xabar yuborishda xatolik: {e}")

async def send_test_card(target_message: Message, test: Dict[str, Any], user_tg_id: int):
    await send_test_card_to_user_chat(user_tg_id, test)

# ── BOT HANDLERLARI (FOYDALANUVCHI QISMI) ──────────────

def get_all_admin_ids() -> list:
    """Bosh admin va bazadagi barcha tayinlangan yordamchi adminlar ID ro'yxati"""
    admin_ids = {ADMIN_ID}
    try:
        for a in test_db.get_all_admins():
            if a.get("tg_id"):
                admin_ids.add(int(a["tg_id"]))
    except Exception as e:
        log.warning(f"Adminlar ro'yxatini olishda xatolik: {e}")
    return list(admin_ids)

async def check_access(message: Message) -> bool:
    """Foydalanuvchi admin tomonidan tasdiqlanganligini tekshiradi."""
    uid = message.from_user.id
    if test_db.is_admin(uid, ADMIN_ID):
        return True
    # Tun rejimi tekshiruvi (23:00 – 07:00)
    if not is_working_hours():
        await message.answer(get_night_message())
        return False
    u = test_db.get_user(uid)
    if not u:
        await message.answer("⚠️ Iltimos, avval /start buyrug'i orqali ro'yxatdan o'ting.")
        return False
    st = u.get("status", "approved")
    if st in ["blocked", "rejected"]:
        await message.answer(
            "⛔️ <b>Sizning botdan foydalanish huquqingiz to'xtatilgan yoki chiqarib yuborilgansiz!</b>\n\n"
            "Murojaat uchun: @eshmbetov"
        )
        return False
    return True

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    user_tg_id = message.from_user.id

    # Admin uchun tun rejimi qo'llanilmaydi
    if not test_db.is_admin(user_tg_id, ADMIN_ID) and not is_working_hours():
        await message.answer(get_night_message())
        return

    user = test_db.get_user(user_tg_id)

    if not user:
        await state.set_state(RegistrationState.fullname)
        await message.answer(
            "👋 <b>Assalomu alaykum! Test Tekshirish Tizimiga xush kelibsiz!</b>\n\n"
            "Tizimdan to'liq foydalanish va ruxsat olish uchun ro'yxatdan o'ting.\n\n"
            "✍️ <b>Iltimos, Ism va Familiyangizni kiriting:</b>\n"
            "<i>(Misol: Shaxriyor Eshimbetov)</i>",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        is_adm = test_db.is_admin(user_tg_id, ADMIN_ID)
        st = user.get("status", "approved")
        if not is_adm:
            if st in ["blocked", "rejected"]:
                await message.answer(
                    "⛔️ <b>Sizning botdan foydalanish huquqingiz to'xtatilgan!</b>\n\n"
                    "Murojaat uchun: @eshmbetov"
                )
                return

        await state.clear()
        await message.answer(
            f"👋 <b>Xush kelibsiz, {user['fullname']}!</b>\n\n"
            "Kerakli bo'limni tanlang yoki to'g'ridan-to'g'ri test kodini yuboring 👇",
            reply_markup=main_menu_kb(user_tg_id)
        )

BLACKLIST_NAME_WORDS = {
    "kimsan", "kimsanov", "kimsanova", "hechkim", "hechkimov", "hechkimova", "hech", "kim",
    "falonchi", "pismadonchi", "nomalum", "noma'lum", "noma’lum", "nomaʼlum", "kimdir", "birov",
    "test", "tester", "testov", "testova", "admin", "administrator", "moderator",
    "bot", "user", "foydalanuvchi", "anonim", "anonymous", "null", "undefined",
    "qwerty", "asdf", "asdfgh", "zxcv", "salom", "qalesan", "ism", "familiya",
    "yoq", "yo'q", "yo’q", "yoʼq", "bilmayman", "blabla", "bla", "hacker", "pro", "master",
    "super", "king", "killer", "qizaloq", "yigit", "patsan", "brat", "aka", "uka",
    "shohruh", "matematika", "susik", "susiksks", "ahshshs", "ahahaha", "hahaha", "xaxa",
    "nik", "login", "parol", "password"
}

def validate_fullname(fullname: str) -> tuple[bool, str]:
    """Ism va familiyani g'alati belgilar, buyruqlar, soxta nomlar va klaviatura terishlaridan tekshirish."""
    if not fullname or not isinstance(fullname, str):
        return False, "⚠️ Iltimos, Ism va Familiyangizni kiriting."
    
    name = fullname.strip()
    
    # 1. Bot buyruqlari tekshiruvi (/start, /help va h.k.)
    if name.startswith("/"):
        return False, "⚠️ Bot buyruqlari ism sifatida qabul qilinmaydi. Iltimos, haqiqiy Ism va Familiyangizni kiriting."
    
    # 2. Maxsus belgilar va raqamlar tekshiruvi (Faqat lotin/kirill harflari, bo'sh joy, defis, apostroflar)
    clean_chars = re.sub(r"[a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲ\s\-\'ʻʼ`’]", "", name)
    if clean_chars:
        return False, "⚠️ Ism-familiyada raqamlar yoki maxsus belgilar bo'lmasligi kerak. Faqat harflar bilan yozing."

    # 3. So'zlar soni (kamida Ism va Familiya bo'lishi shart)
    words = [w for w in name.split() if w]
    if len(words) < 2:
        return False, "⚠️ Iltimos, Ism va Familiyangizni to'liq kiriting (kamida 2 ta so'z, masalan: <i>Ali Valiyev</i>)."
    if len(words) > 4:
        return False, "⚠️ Iltimos, faqat o'zingizning haqiqiy Ism va Familiyangizni kiriting (ortiqcha so'zlarsiz)."

    vowels = set("aeiouyаеёиоуыэюяў")

    for w in words:
        w_lower = w.lower().strip("'-`ʻʼ’")
        letters_only = re.sub(r"[^a-zA-Zа-яА-ЯёЁўқғҳЎҚҒҲ]", "", w_lower)
        
        # Har bir so'z kamida 2 ta harfdan iborat bo'lishi kerak
        if len(letters_only) < 2:
            return False, f"⚠️ Kiritilgan so'z juda qisqa: <b>{w}</b>. Haqiqiy ism va familiyangizni kiriting."
        
        # Qora ro'yxat (soxta, hazil yoki buyruq ma'nosidagi nomlar)
        if letters_only in BLACKLIST_NAME_WORDS:
            return False, f"⚠️ Hazil yoki soxta nomlar (<b>{w}</b>) qabul qilinmaydi! Iltimos, haqiqiy Ism va Familiyangizni kiriting."
        
        # 3 tadan ortiq ketma-ket bir xil harf (masalan: aaa, sss, zzz)
        if re.search(r"(.)\1\1", letters_only):
            return False, "⚠️ Ism-familiyada harflarni ketma-ket asossiz takrorlash mumkin emas. Haqiqiy ismingizni kiriting."
        
        # Qisqa takrorlanuvchi klaviatura bo'g'inlari (masalan: shshsh, sksks, ababab)
        if re.search(r"(.{2,3})\1\1", letters_only):
            return False, "⚠️ Tushunarsiz yoki soxta nom kiritildi. Iltimos, haqiqiy Ism va Familiyangizni kiriting."

        # Unli harf tekshiruvi (so'z 3 harfdan uzun bo'lsa va unli umuman bo'lmasa — klaviatura spam)
        if len(letters_only) >= 3 and not any(ch in vowels for ch in letters_only):
            return False, f"⚠️ Noto'g'ri so'z kiritildi: <b>{w}</b>. Iltimos, haqiqiy Ism va Familiyangizni kiriting."

        # Ketma-ket 5 ta undosh harf (o'zbek va rus tilida 5 ta undosh ketma-ket kelmaydi: Ahshshs, susiksks)
        consec_cons = 0
        for ch in letters_only:
            if ch not in vowels:
                consec_cons += 1
                if consec_cons >= 5:
                    return False, "⚠️ Tushunarsiz yoki xato yozilgan ism. Iltimos, haqiqiy Ism va Familiyangizni kiriting."
            else:
                consec_cons = 0

    return True, ""


# Ro'yxatdan o'tish: Ism kiritildi (Telefon so'ralmaydi, darhol ro'yxatdan o'tadi)
@router.message(RegistrationState.fullname)
async def reg_fullname(message: Message, state: FSMContext):
    raw_fullname = (message.text or "").strip()
    
    # Qat'iy tekshiruv: g'alati nomlar, buyruqlar va klaviatura spamlarini rad etish
    is_valid, err_msg = validate_fullname(raw_fullname)
    if not is_valid:
        await message.answer(
            f"{err_msg}\n\n"
            f"✍️ <i>Masalan: Rustam Karimov yoki Dilnoza Rahimova</i>"
        )
        return

    # Chiroyli bosh harflar bilan formatlash
    fullname = " ".join(w.capitalize() for w in raw_fullname.split())

    user_tg_id = message.from_user.id
    username = message.from_user.username
    phone = ""

    # 1. Yangi foydalanuvchi to'g'ridan-to'g'ri faol (approved) bo'ladi
    status = "approved"
    test_db.add_or_update_user(user_tg_id, fullname, phone, username, status=status)
    await state.clear()

    # 2. O'quvchiga darhol asosiy menyuni ochish
    await message.answer(
        f"🎉 <b>Tabriklaymiz, {fullname}! Siz muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n\n"
        f"Kerakli bo'limni tanlang yoki to'g'ridan-to'g'ri test kodini yuboring 👇",
        reply_markup=main_menu_kb(user_tg_id)
    )

    # 3. Adminga shunchaki yangi a'zo haqida ma'lumot (so'rovsiz)
    username_str = f"@{username}" if username else "Mavjud emas"
    admin_notify_text = (
        f"👤 <b>Yangi foydalanuvchi ro'yxatdan o'tdi:</b>\n\n"
        f"👤 <b>Ism-familiya:</b> {fullname}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_tg_id}</code>\n"
        f"🔗 <b>Username:</b> {username_str}\n"
        f"🕒 <b>Vaqt:</b> {format_uzb_time()}"
    )

    for adm_id in get_all_admin_ids():
        try:
            await bot.send_message(
                chat_id=adm_id,
                text=admin_notify_text
            )
        except Exception as ex:
            log.warning(f"Adminga ({adm_id}) yangi a'zo xabarini yuborishda xatolik: {ex}")

# Ixtiyoriy: Telefon yuborilgan holat uchun zaxira handler
@router.message(RegistrationState.phone)
async def reg_phone(message: Message, state: FSMContext):
    phone = ""
    if message.contact:
        phone = message.contact.phone_number
    elif message.text:
        phone = message.text.strip()

    data = await state.get_data()
    fullname = data.get("fullname", "Foydalanuvchi")
    user_tg_id = message.from_user.id
    username = message.from_user.username

    status = "approved"
    test_db.add_or_update_user(user_tg_id, fullname, phone, username, status=status)
    await state.clear()

    await message.answer(
        f"🎉 <b>Tabriklaymiz, {fullname}! Siz muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n\n"
        f"Kerakli bo'limni tanlang yoki to'g'ridan-to'g'ri test kodini yuboring 👇",
        reply_markup=main_menu_kb(user_tg_id)
    )

# 1. ✦ Test kodini kiritish (Prompt)
@router.message(F.text.in_({"✦ Test kodini kiritish", "⚛️ Test kodini kiritish", "🔢 Test kodini kiritish"}))
@router.message(Command("solve"))
async def enter_test_code_prompt(message: Message, state: FSMContext):
    if not await check_access(message):
        return
    await state.set_state(SolveTestState.test_code)
    await message.answer(
        "✦ <b>Test kodini kiriting:</b>\n\n"
        "<i>(Masalan: <code>1</code> yoki <code>FIZ-01</code>)</i>\n\n"
        "Bekor qilish uchun menyudan foydalanishingiz mumkin."
    )

# Test kodi kiritildi (FSM)
@router.message(SolveTestState.test_code)
async def process_solve_test_code(message: Message, state: FSMContext):
    if not await check_access(message):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        return
    menu_cmds = [
        "✦ Test kodini kiritish", "⚛️ Test kodini kiritish", "🔢 Test kodini kiritish",
        "◈ Mening natijalarim", "📊 Mening natijalarim",
        "◈ Profilim", "👤 Profilim",
        "› Yordam", "💡 Yordam", "ℹ️ Yordam", "ℹ️ Bot haqida",
        "⚙ Admin Panel", "⚙️ Admin Panel",
        "✦ Yangi test yaratish", "➕ Yangi test yaratish",
        "◈ Test natijalari va reyting", "📊 Test natijalari va reyting",
        "◈ Testlarni boshqarish", "🔬 Testlarni boshqarish", "📋 Testlarni boshqarish"
    ]
    if text in menu_cmds:
        await state.clear()
        if text in ["◈ Mening natijalarim", "📊 Mening natijalarim"]:
            await show_my_results(message)
        elif text in ["◈ Profilim", "👤 Profilim"]:
            await show_profile(message)
        elif text in ["› Yordam", "💡 Yordam", "ℹ️ Yordam", "ℹ️ Bot haqida"]:
            await show_help(message)
        elif text in ["⚙ Admin Panel", "⚙️ Admin Panel"]:
            await admin_panel_handler(message)
        elif text in ["✦ Yangi test yaratish", "➕ Yangi test yaratish"]:
            await admin_create_test_text_handler(message)
        elif text in ["◈ Test natijalari va reyting", "📊 Test natijalari va reyting"]:
            await admin_leaderboard_text_handler(message)
        elif text in ["◈ Testlarni boshqarish", "🔬 Testlarni boshqarish", "📋 Testlarni boshqarish"]:
            await admin_manage_tests_text_handler(message)
        elif text in ["✦ Test kodini kiritish", "⚛️ Test kodini kiritish", "🔢 Test kodini kiritish"]:
            await enter_test_code_prompt(message, state)
        return

    code = text.upper().replace("#", "")
    test = test_db.get_test_by_code(code)
    await state.clear()

    if not test:
        await message.answer(
            f"❌ <b>«{text}» kodi bo'yicha test topilmadi!</b>\n\n"
            f"Iltimos, kodni to'g'ri kiritganingizni tekshiring.",
            reply_markup=main_menu_kb(message.from_user.id)
        )
        return

    await send_test_card(message, test, message.from_user.id)


@router.callback_query(F.data.startswith("solve_test_"))
async def solve_test_cb(call: CallbackQuery):
    test_id = int(call.data.split("_")[2])
    t = test_db.get_test_by_id(test_id)
    if not t:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    sched_stat = get_test_schedule_status(t)
    if sched_stat["is_upcoming"] and not test_db.is_admin(call.from_user.id, ADMIN_ID):
        sstart = t.get('scheduled_start') or ''
        sdate = t.get('scheduled_date') or 'Bugun'
        await call.answer(f"⏳ Test hali boshlanmagan! Boshlanish vaqti: {sdate} {sstart} (UZB)", show_alert=True)
        return
    
    existing_sub = test_db.get_user_submission_for_test(test_id, call.from_user.id)
    if existing_sub:
        is_published = test_db.is_test_results_published(test_id)
        if is_published:
            grade = test_db.calculate_grade(existing_sub.get("score", 0))
            score_val = existing_sub.get("score", 0)
            await call.answer(f"⛔️ Siz bu testni topshirgansiz! Daraja: {grade} ({score_val} ball)", show_alert=True)
        else:
            await call.answer("⏳ Siz bu testni topshirgansiz! Javoblar tekshirilmoqda. Admin natijalarni e'lon qilgach, shaxsiy xabar yuboriladi.", show_alert=True)
        return

    params = {
        "test_id": t["id"],
        "test_code": t["test_code"],
        "title": t["title"],
        "subject": t.get("subject", "Fizika"),
        "v": "20261004_physickb1"
    }
    encoded_url = f"{WEBAPP_URL}?{urllib.parse.urlencode(params)}"
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_webapp_button("📝 Testni boshlash (Mini App)", encoded_url)]
    ])
    await call.message.answer(
        f"📝 <b>{t['title']}</b> testini yechish uchun quyidagi tugmani bosing 👇",
        reply_markup=reply_kb
    )
    await call.answer()

@router.callback_query(F.data == "admin_webapp_info")
async def admin_webapp_info_cb(call: CallbackQuery):
    admin_webapp_url = f"{WEBAPP_URL}/admin.html?tg_id={call.from_user.id}"
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_webapp_button("📱 Admin Panelni ochish (Mini App)", admin_webapp_url)],
        [InlineKeyboardButton(text="🔙 Admin Menyuga qaytish", callback_data="admin_back_to_menu")]
    ])
    text = (
        f"📱 <b>Admin Mini App (Kalit va ballar kiritish):</b>\n\n"
        f"Ushbu paneldan 45 ta savolning kalitlari va har biriga alohida ballarni qulay belgilashingiz mumkin!\n\n"
        f"Ochish uchun quyidagi tugmani bosing 👇"
    )
    try:
        await call.message.edit_text(text, reply_markup=reply_kb)
    except Exception:
        await call.message.answer(text, reply_markup=reply_kb)
    await call.answer()

# 2. ◈ Mening natijalarim
@router.message(F.text.in_({"◈ Mening natijalarim", "📊 Mening natijalarim"}))
@router.message(Command("results"))
async def show_my_results(message: Message):
    subs = test_db.get_user_submissions(message.from_user.id)
    pub_subs = [s for s in subs if s.get("results_published")]

    kb_rows = []
    if pub_subs:
        for s in pub_subs[:5]:
            t_title = s.get("test_title", "Test")
            t_code = s.get("test_code", "")
            btn_title = f"◈ #{t_code} tahlili" if t_code else f"◈ {t_title[:20]} tahlili"
            kb_rows.append([InlineKeyboardButton(text=btn_title, callback_data=f"user_req_tahlil_{s['test_id']}")])

    kb_rows.append([make_webapp_button("◈ Barcha natijalar va tahlillar (Mini App)", f"{WEBAPP_URL}/app.html?tab=tests")])

    await message.answer(
        "◈ <b>Mening natijalarim va tahlillar</b>\n\n"
        "Quyidagi tugmalar orqali topshirgan testlaringiz tahlilini ko'rishingiz yoki Mini ilovani ochishingiz mumkin:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
    )

# 3. ◈ Profil (Bot chatida ko'rish va tahrirlash)
@router.message(F.text.in_({"◈ Profilim", "👤 Profilim"}))
@router.message(Command("profile"))
async def show_profile(message: Message):
    user = test_db.get_user(message.from_user.id)
    if not user:
        await message.answer("Profil topilmadi. /start buyrug'ini bosing.")
        return

    submissions = test_db.get_user_submissions(message.from_user.id)
    tests_count = len(submissions)
    dt = format_uzb_time(user.get("registered_at"), "%d.%m.%Y") if user.get("registered_at") else "Noma'lum"

    scores = [float(s.get('score', s.get('correct_count', 0))) for s in submissions] if submissions else []
    avg_score = f"{sum(scores)/len(scores):.1f}" if scores else "0.0"
    max_score = f"{max(scores):.1f}" if scores else "0.0"

    st = (user.get("status") or "pending").lower()
    st_text = "✅ Faol o'quvchi" if st == "approved" else ("⏳ Kutilmoqda" if st == "pending" else "⛔️ Bloklangan")

    phone_str = user.get('phone') or "Biriktirilmagan"
    username_str = f"@{message.from_user.username}" if message.from_user.username else (f"@{user.get('username')}" if user.get('username') else "Mavjud emas")

    text = (
        "👤 <b>SHAXSIY PROFILINGIZ</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {user['fullname']}\n"
        f"🔰 <b>Holat:</b> {st_text}\n\n"
        f"📊 <b>KO'RSATKICHLAR:</b>\n"
        f"• Ishlangan testlar: <b>{tests_count} ta</b>\n"
        f"• O'rtacha natija: <b>{avg_score} ball</b>\n"
        f"• Eng yuqori natija: <b>{max_score} ball</b>\n\n"
        f"<i>Batafsil ma'lumotlarni ko'rish yoki tahrirlash uchun quyidagi tugmalardan birini tanlang 👇</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Shaxsiy ma'lumotlar", callback_data="profile_show_details")],
        [
            InlineKeyboardButton(text="✏️ Ismni o'zgartirish", callback_data="profile_edit_name"),
            InlineKeyboardButton(text="📞 Raqamni o'zgartirish", callback_data="profile_edit_phone")
        ],
        [make_webapp_button("📱 Shaxsiy profil (Mini App)", f"{WEBAPP_URL}/app.html?tg_id={message.from_user.id}")],
        [InlineKeyboardButton(text="🗑 Akkauntni o'chirish", callback_data="profile_delete_account")]
    ])

    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "profile_show_details")
async def profile_show_details_handler(call: CallbackQuery):
    user = test_db.get_user(call.from_user.id)
    if not user:
        await call.answer("Foydalanuvchi topilmadi", show_alert=True)
        return
    submissions = test_db.get_user_submissions(call.from_user.id)
    tests_count = len(submissions)
    dt = format_uzb_time(user.get("registered_at"), "%d.%m.%Y %H:%M") if user.get("registered_at") else "Noma'lum"
    phone_str = user.get('phone') or "Biriktirilmagan"
    username_str = f"@{call.from_user.username}" if call.from_user.username else (f"@{user.get('username')}" if user.get('username') else "Mavjud emas")
    st = (user.get("status") or "pending").lower()
    st_text = "✅ Faol o'quvchi" if st == "approved" else ("⏳ Kutilmoqda" if st == "pending" else "⛔️ Bloklangan")

    detail_text = (
        "📋 <b>SHAXSIY AKKAUNT MA'LUMOTLARI</b>\n\n"
        f"👤 <b>Ism va familiya:</b> {user['fullname']}\n"
        f"📱 <b>Telefon raqam:</b> {phone_str}\n"
        f"🆔 <b>Telegram ID:</b> <code>{call.from_user.id}</code>\n"
        f"🔗 <b>Username:</b> {username_str}\n"
        f"📅 <b>Ro'yxatdan o'tgan:</b> {dt}\n"
        f"🔰 <b>Holat:</b> {st_text}\n"
        f"📝 <b>Yechilgan testlar:</b> {tests_count} ta\n\n"
        f"<i>Ma'lumotlarni tahrirlashingiz yoki menyuni yopishingiz mumkin 👇</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▲ Ma'lumotlarni yashirish", callback_data="profile_hide_details")],
        [
            InlineKeyboardButton(text="✏️ Ismni o'zgartirish", callback_data="profile_edit_name"),
            InlineKeyboardButton(text="📞 Raqamni o'zgartirish", callback_data="profile_edit_phone")
        ],
        [make_webapp_button("📱 Shaxsiy profil (Mini App)", f"{WEBAPP_URL}/app.html?tg_id={call.from_user.id}")],
        [InlineKeyboardButton(text="🗑 Akkauntni o'chirish", callback_data="profile_delete_account")]
    ])
    try:
        await call.message.edit_text(detail_text, reply_markup=kb)
    except Exception:
        pass
    await call.answer()

@router.callback_query(F.data == "profile_hide_details")
async def profile_hide_details_handler(call: CallbackQuery):
    user = test_db.get_user(call.from_user.id)
    if not user:
        await call.answer("Foydalanuvchi topilmadi", show_alert=True)
        return
    submissions = test_db.get_user_submissions(call.from_user.id)
    tests_count = len(submissions)
    scores = [float(s.get('score', s.get('correct_count', 0))) for s in submissions] if submissions else []
    avg_score = f"{sum(scores)/len(scores):.1f}" if scores else "0.0"
    max_score = f"{max(scores):.1f}" if scores else "0.0"
    st = (user.get("status") or "pending").lower()
    st_text = "✅ Faol o'quvchi" if st == "approved" else ("⏳ Kutilmoqda" if st == "pending" else "⛔️ Bloklangan")

    text = (
        "👤 <b>SHAXSIY PROFILINGIZ</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {user['fullname']}\n"
        f"🔰 <b>Holat:</b> {st_text}\n\n"
        f"📊 <b>KO'RSATKICHLAR:</b>\n"
        f"• Ishlangan testlar: <b>{tests_count} ta</b>\n"
        f"• O'rtacha natija: <b>{avg_score} ball</b>\n"
        f"• Eng yuqori natija: <b>{max_score} ball</b>\n\n"
        f"<i>Batafsil ma'lumotlarni ko'rish yoki tahrirlash uchun quyidagi tugmalardan birini tanlang 👇</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Shaxsiy ma'lumotlar", callback_data="profile_show_details")],
        [
            InlineKeyboardButton(text="✏️ Ismni o'zgartirish", callback_data="profile_edit_name"),
            InlineKeyboardButton(text="📞 Raqamni o'zgartirish", callback_data="profile_edit_phone")
        ],
        [make_webapp_button("📱 Shaxsiy profil (Mini App)", f"{WEBAPP_URL}/app.html?tg_id={call.from_user.id}")],
        [InlineKeyboardButton(text="🗑 Akkauntni o'chirish", callback_data="profile_delete_account")]
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer()

# ── PROFILNI TAHRIRLASH (BOT CHATIDA) ──────────────────
@router.callback_query(F.data == "profile_edit_name")
async def profile_edit_name_handler(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfileState.waiting_new_name)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="cancel_edit_profile")]
    ])
    await call.message.answer(
        "✏️ <b>Ismni o'zgartirish</b>\n\n"
        "Iltimos, yangi ism va familiyangizni yozib yuboring:\n"
        "<i>(Masalan: Ali Valiyev)</i>",
        reply_markup=cancel_kb
    )
    await call.answer()

@router.message(EditProfileState.waiting_new_name)
async def process_new_profile_name(message: Message, state: FSMContext):
    new_name = (message.text or "").strip()
    if not new_name or len(new_name) < 3 or len(new_name) > 60:
        await message.answer("⚠️ Iltimos, haqiqiy ism va familiyangizni to'liq kiriting (kamida 3 ta belgi):")
        return
    
    test_db.update_user_profile(message.from_user.id, fullname=new_name)
    await state.clear()
    await message.answer(f"✅ Ismingiz muvaffaqiyatli yangilandi: <b>{new_name}</b>")
    await show_profile(message)

@router.callback_query(F.data == "profile_edit_phone")
async def profile_edit_phone_handler(call: CallbackQuery, state: FSMContext):
    await state.set_state(EditProfileState.waiting_new_phone)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="🔙 Bekor qilish")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await call.message.answer(
        "📞 <b>Telefon raqamni o'zgartirish</b>\n\n"
        "Iltimos, pastdagi <b>'📱 Telefon raqamni yuborish'</b> tugmasini bosing yoki yangi raqamingizni yozing (Masalan: +998901234567):",
        reply_markup=kb
    )
    await call.answer()

@router.message(EditProfileState.waiting_new_phone, F.contact)
async def process_new_profile_phone_contact(message: Message, state: FSMContext):
    contact = message.contact
    if not contact:
        await message.answer("Raqam aniqlanmadi.")
        return
    phone = contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    test_db.update_user_profile(message.from_user.id, phone=phone)
    await state.clear()
    await message.answer(
        f"✅ Telefon raqamingiz muvaffaqiyatli yangilandi: <b>{phone}</b>",
        reply_markup=main_menu_kb(message.from_user.id)
    )
    await show_profile(message)

@router.message(EditProfileState.waiting_new_phone)
async def process_new_profile_phone_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if text == "🔙 Bekor qilish":
        await state.clear()
        await message.answer("Amal bekor qilindi.", reply_markup=main_menu_kb(message.from_user.id))
        await show_profile(message)
        return

    import re
    cleaned = re.sub(r'[^\d+]', '', text)
    if len(cleaned.replace("+", "")) < 9:
        await message.answer("⚠️ Noto'g'ri telefon raqam formati. Masalan: +998901234567")
        return
    if not cleaned.startswith("+"):
        cleaned = "+" + cleaned

    test_db.update_user_profile(message.from_user.id, phone=cleaned)
    await state.clear()
    await message.answer(
        f"✅ Telefon raqamingiz muvaffaqiyatli yangilandi: <b>{cleaned}</b>",
        reply_markup=main_menu_kb(message.from_user.id)
    )
    await show_profile(message)

@router.callback_query(F.data == "cancel_edit_profile")
async def cancel_edit_profile_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.answer("Tahrirlash bekor qilindi")

@router.callback_query(F.data == "profile_delete_account")
async def profile_delete_account_confirm(call: CallbackQuery):
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Ha, butunlay o'chirilsin", callback_data="do_delete_my_account")],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="cancel_edit_profile")]
    ])
    await call.message.answer(
        "⚠️ <b>DIQQAT! AKKAUNTNI O'CHIRISH</b>\n\n"
        "Haqiqatan ham akkauntingizni va barcha ishlangan test natijalaringizni butunlay o'chirib tashlamoqchimisiz?\n\n"
        "<i>Bu amalni ortga qaytarib bo'lmaydi!</i>",
        reply_markup=confirm_kb
    )
    await call.answer()

@router.callback_query(F.data == "do_delete_my_account")
async def do_delete_my_account_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = call.from_user.id
    user_info = test_db.delete_user(uid)
    await call.message.answer(
        "🗑 <b>Akkauntingiz va barcha natijalaringiz butunlay o'chirildi.</b>\n\n"
        "Qaytadan ro'yxatdan o'tish uchun /start buyrug'ini bosing.",
        reply_markup=ReplyKeyboardRemove()
    )
    await call.answer()

    # Adminga zudlik bilan bildirishnoma jo'natish
    if ADMIN_ID:
        try:
            fn = user_info.get("fullname") if user_info else (call.from_user.full_name or "Noma'lum")
            ph = user_info.get("phone", "—") if user_info else "—"
            un = f"@{user_info.get('username')}" if (user_info and user_info.get("username")) else (f"@{call.from_user.username}" if call.from_user.username else "Mavjud emas")
            alert_text = (
                f"🗑 <b>OGOHLANTIRISH: Foydalanuvchi akkauntini o'chirdi!</b>\n\n"
                f"👤 <b>Ism:</b> {fn}\n"
                f"📞 <b>Telefon:</b> <code>{ph}</code>\n"
                f"🔗 <b>Username:</b> {un}\n"
                f"🆔 <b>Telegram ID:</b> <code>{uid}</code>\n"
                f"🕒 <b>Vaqt:</b> {format_uzb_time()}\n\n"
                f"<i>Foydalanuvchi Telegram botidagi «Akkauntni o'chirish» tugmasini bosib chiqib ketdi.</i>"
            )
            await bot.send_message(chat_id=ADMIN_ID, text=alert_text)
        except Exception as ex:
            log.warning(f"Admin alert yuborishda xatolik: {ex}")

# ──────────────────────────────────────────────────────────
# BOTNI BLOKLASH / O'CHIRISHNI REAL-VAQTDA ANIQLASH (MY_CHAT_MEMBER)
# ──────────────────────────────────────────────────────────

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def user_blocked_bot_handler(event: ChatMemberUpdated):
    """
    Foydalanuvchi botni to'xtatganda (Stop bot), bloklaganda yoki chatni o'chirganda
    Telegram avtomatik ravishda botga ushbu hodisani yuboradi (foydalanuvchiga xabar bormaydi).
    """
    try:
        user_id = event.from_user.id
        u = test_db.get_user(user_id)
        
        # Botni bloklagan foydalanuvchini bazadan to'liq o'chiramiz
        test_db.delete_user(user_id)
        
        fn = (u and u.get("fullname")) or event.from_user.full_name or "Noma'lum"
        un = f"@{u.get('username')}" if (u and u.get('username')) else (f"@{event.from_user.username}" if event.from_user.username else "Mavjud emas")
        ph = (u and u.get("phone")) or "—"
        now_str = format_uzb_time(fmt="%d.%m.%Y %H:%M:%S")
        
        alert_text = (
            f"🚫 <b>OGOHLANTIRISH: Foydalanuvchi botni blokladi va bazadan o'chirildi!</b>\n\n"
            f"👤 <b>Foydalanuvchi:</b> {fn}\n"
            f"🔗 <b>Username:</b> {un}\n"
            f"📞 <b>Telefon:</b> <code>{ph}</code>\n"
            f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
            f"🕒 <b>Vaqt:</b> <b>{now_str}</b>\n\n"
            f"🗑 <i>Foydalanuvchi botni to'xtatgani/bloklagani sababli uning barcha ma'lumotlari bazadan to'liq o'chirildi.</i>"
        )
        
        # Faqat Bosh adminga (ADMIN_ID) yuboriladi, tayinlangan yordamchi adminlarga yuborilmaydi
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=alert_text)
        except Exception as ex:
            log.warning(f"Bosh adminga ({ADMIN_ID}) blok bildirishnomasi yuborishda xatolik: {ex}")
    except Exception as e:
        log.error(f"user_blocked_bot_handler error: {e}", exc_info=True)


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def user_unblocked_bot_handler(event: ChatMemberUpdated):
    """
    Foydalanuvchi botni blokdan chiqarganda (Unblock/Restart).
    """
    try:
        user_id = event.from_user.id
        u = test_db.get_user(user_id)
        
        # Agar avval ro'yxatdan o'tgan bo'lsa va bloklangan bo'lsa, 'approved' qilamiz
        if u and u.get("status") == "blocked":
            test_db.approve_user(user_id)
            note = "<i>Bazada holati qayta «Faol» qilindi.</i>"
        else:
            note = "<i>Botdan qayta foydalanishi mumkin.</i>"
            
        fn = (u and u.get("fullname")) or event.from_user.full_name or "Noma'lum"
        un = f"@{u.get('username')}" if (u and u.get('username')) else (f"@{event.from_user.username}" if event.from_user.username else "Mavjud emas")
        ph = (u and u.get("phone")) or "—"
        now_str = format_uzb_time(fmt="%d.%m.%Y %H:%M:%S")
        
        alert_text = (
            f"🟢 <b>Foydalanuvchi botni qayta faollashtirdi (Unblock)!</b>\n\n"
            f"👤 <b>Foydalanuvchi:</b> {fn}\n"
            f"🔗 <b>Username:</b> {un}\n"
            f"📞 <b>Telefon:</b> <code>{ph}</code>\n"
            f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
            f"🕒 <b>Vaqt:</b> <b>{now_str}</b>\n\n"
            f"ℹ️ {note}"
        )
        
        # Faqat Bosh adminga (ADMIN_ID) yuboriladi, tayinlangan yordamchi adminlarga yuborilmaydi
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=alert_text)
        except Exception as ex:
            log.warning(f"Bosh adminga ({ADMIN_ID}) unblock bildirishnomasi yuborishda xatolik: {ex}")
    except Exception as e:
        log.error(f"user_unblocked_bot_handler error: {e}", exc_info=True)


async def clean_blocked_users_from_db(initiator_id: int = ADMIN_ID) -> dict:
    """
    Bazada mavjud barcha foydalanuvchilarni tekshirib, botni bloklaganlarni bazadan to'liq o'chirib tashlash.
    """
    # 1. Bazada 'blocked' holatida turganlarni avval butunlay o'chirib olamiz
    already_blocked = test_db.delete_all_blocked_users()
    deleted_users = []
    for bu in already_blocked:
        deleted_users.append({
            "id": bu.get("id"),
            "tg_id": bu.get("tg_id"),
            "fullname": bu.get("fullname") or "Noma'lum",
            "username": f"@{bu.get('username')}" if bu.get("username") else "—",
            "tests_count": bu.get("tests_count", 0),
            "reason": "Oldindan bloklangan holatda"
        })

    users = test_db.get_all_users()
    admin_ids = set(get_all_admin_ids())

    active_users = []

    for u in users:
        uid = u.get("tg_id")
        if not uid or uid <= 0 or uid in admin_ids:
            continue
        try:
            # Ko'rinmas ping: yozmoqda effekti (agar bloklagan bo'lsa darhol exception qaytadi)
            await bot.send_chat_action(chat_id=uid, action="typing")
            active_users.append(u)
        except (TelegramForbiddenError, TelegramBadRequest) as ex:
            err_text = str(ex).lower()
            if "blocked" in err_text or "deactivated" in err_text or "chat not found" in err_text:
                test_db.delete_user(uid)
                deleted_users.append({
                    "id": u.get("id"),
                    "tg_id": uid,
                    "fullname": u.get("fullname") or "Noma'lum",
                    "username": f"@{u.get('username')}" if u.get("username") else "—",
                    "tests_count": u.get("tests_count", 0),
                    "reason": err_text[:60]
                })
                log.info(f"🗑 Bloklagan foydalanuvchi {uid} ({u.get('fullname')}) bazadan o'chirildi")
            else:
                active_users.append(u)
        except Exception as e:
            err_text = str(e).lower()
            if "blocked" in err_text or "forbidden" in err_text or "deactivated" in err_text:
                test_db.delete_user(uid)
                deleted_users.append({
                    "id": u.get("id"),
                    "tg_id": uid,
                    "fullname": u.get("fullname") or "Noma'lum",
                    "username": f"@{u.get('username')}" if u.get("username") else "—",
                    "tests_count": u.get("tests_count", 0),
                    "reason": err_text[:60]
                })
                log.info(f"🗑 Bloklagan foydalanuvchi {uid} bazadan o'chirildi: {err_text}")
            else:
                active_users.append(u)

        await asyncio.sleep(0.04)

    # Admin ga hisobot xabarini yuborish
    try:
        report_text = (
            f"🧹 <b>BOTNI BLOKLAGANLARNI TOZALASH YAKUNLANDI:</b>\n\n"
            f"👥 <b>Tekshirildi:</b> {len(users)} nafar\n"
            f"✅ <b>Faol qolganlar:</b> {len(active_users)} nafar\n"
            f"🗑 <b>Bazadan o'chirilgan bloklaganlar:</b> {len(deleted_users)} nafar"
        )
        if deleted_users:
            report_text += "\n\n<b>O'chirilgan foydalanuvchilar:</b>\n"
            for du in deleted_users[:25]:
                report_text += f"• {du['fullname']} ({du['username']}, ID: <code>{du['tg_id']}</code>)\n"
            if len(deleted_users) > 25:
                report_text += f"\n<i>...va yana {len(deleted_users) - 25} ta foydalanuvchi.</i>"
        await bot.send_message(chat_id=ADMIN_ID, text=report_text)
    except Exception as e:
        log.error(f"Admin tozalash hisoboti yuborishda xato: {e}")

    return {
        "success": True,
        "total_checked": len(users),
        "active_count": len(active_users),
        "deleted_count": len(deleted_users),
        "deleted_users": deleted_users
    }

@router.message(Command("check_blocks"))
@router.message(Command("clean_blocked"))
async def admin_check_blocks_handler(message: Message):
    """
    Admin uchun: Bazadagi barcha foydalanuvchilarni tekshirib, botni bloklaganlarni bazadan to'liq o'chirish.
    """
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        await message.answer("⛔️ Bu buyruq faqat bot administratori uchun!")
        return

    users = test_db.get_all_users()
    total = len(users)
    status_msg = await message.answer(
        f"🔍 <b>Bazadagi {total} ta foydalanuvchi tekshirilmoqda...</b>\n\n"
        f"<i>(Botni bloklagan yoki o'chirgan foydalanuvchilar aniqlansa, darhol bazadan o'chiriladi)</i>"
    )

    result = await clean_blocked_users_from_db(initiator_id=message.from_user.id)
    deleted_list = result["deleted_users"]
    active_count = result["active_count"]

    res_text = (
        f"📊 <b>Foydalanuvchilar holati tekshiruvi yakunlandi:</b>\n\n"
        f"👥 <b>Jami tekshirildi:</b> {total} ta\n"
        f"✅ <b>Faol foydalanuvchilar:</b> {active_count} ta\n"
        f"🗑 <b>Botni bloklagani uchun bazadan o'chirildi:</b> {len(deleted_list)} ta\n\n"
    )

    if deleted_list:
        res_text += "<b>Bazadan o'chirilgan foydalanuvchilar:</b>\n"
        for i, bu in enumerate(deleted_list[:30], 1):
            bun = f" ({bu['username']})" if bu.get('username') and bu['username'] != '—' else ""
            res_text += f"{i}. <b>{bu['fullname']}</b>{bun} — <code>{bu['tg_id']}</code>\n"
        if len(deleted_list) > 30:
            res_text += f"\n<i>...va yana {len(deleted_list) - 30} ta foydalanuvchi.</i>"
    else:
        res_text += "🎉 <i>Hozirda botni bloklagan foydalanuvchilar aniqlanmadi (baza toza)!</i>"

    try:
        await status_msg.edit_text(res_text)
    except Exception:
        await message.answer(res_text)

def get_inactive_target_users(target_count: str = "both", time_filter: str = "min_2d") -> list:
    """
    Shartlar bo'yicha nishondagi foydalanuvchilar ro'yxatini hisoblash.
    target_count: "0", "1", "both"
    time_filter: "min_2d" (2+ kun oldin), "last_2d" (oxirgi 2 kun ichida), "all" (barchasi)
    """
    users = test_db.get_all_users()
    admin_ids = set(get_all_admin_ids())
    now_ts = int(time.time())
    two_days_secs = 2 * 86400

    target_users = []
    for u in users:
        uid = u.get("tg_id")
        if not uid or uid <= 0 or uid in admin_ids:
            continue
        if u.get("status") != "approved":
            continue

        t_count = u.get("tests_count", 0)
        if target_count == "0" and t_count != 0:
            continue
        elif target_count == "1" and t_count != 1:
            continue
        elif target_count == "both" and t_count not in (0, 1):
            continue

        reg_at = u.get("registered_at") or 0
        if time_filter == "min_2d":
            # Qo'shilganiga kamida 2 kun bo'lganlar (2 kundan oshganlar)
            if reg_at > (now_ts - two_days_secs):
                continue
        elif time_filter == "last_2d":
            # Oxirgi 2 kunda qo'shilganlar (so'nggi 48 soat)
            if reg_at < (now_ts - two_days_secs):
                continue

        target_users.append(u)

    return target_users

async def send_inactive_warning_messages(
    initiator_id: int = ADMIN_ID,
    target_count: str = "both",
    time_filter: str = "min_2d"
) -> dict:
    """
    Tanlangan parametrlar bo'yicha foydalanuvchilarga formal ogohlantirish xabari yuborish.
    Adminlarga yuborilmaydi. Botni bloklaganlar avtomatik bazadan o'chiriladi.
    """
    target_users = get_inactive_target_users(target_count=target_count, time_filter=time_filter)

    sent_users = []
    failed_users = []
    deleted_blocked_users = []

    for u in target_users:
        uid = u.get("tg_id")
        fname = u.get("fullname") or "Foydalanuvchi"
        uname = f"@{u.get('username')}" if u.get("username") else "—"
        t_count = u.get("tests_count", 0)

        if t_count == 0:
            text = (
                "⚠️ <b>RASMIY OGOHLANTIRISH</b>\n\n"
                f"Hurmatli <b>{fname}</b>!\n\n"
                "Siz tizimimizda ro'yxatdan o'tgan bo'lsangiz-da, shu kunga qadar <b>birorta ham test ishlamadingiz</b> "
                "va sizga berilgan bepul imkoniyatdan foydalanmadingiz.\n\n"
                "📌 <b>Muhim eslatma:</b> Bugungi bo'lib o'tadigan testda ham qatnashmasangiz, faoliyatsizligingiz sababli sizni "
                "<b>botdan va tizimdan chiqarib yuborishga</b> majbur bo'lamiz.\n\n"
                "<i>O'z o'rningizni saqlab qolish va bilimingizni sinash uchun bugungi testda albatta ishtirok eting!</i>"
            )
        else:
            text = (
                "⚠️ <b>RASMIY OGOHLANTIRISH</b>\n\n"
                f"Hurmatli <b>{fname}</b>!\n\n"
                "Siz shu kunga qadar faqat <b>1 ta test</b> ishladingiz va sizga taqdim etilgan bepul imkoniyatlardan "
                "to'liq foydalanmadingiz.\n\n"
                "📌 <b>Muhim eslatma:</b> Bugungi bo'lib o'tadigan testda ham qatnashmasangiz, faoliyatsizligingiz sababli sizni "
                "<b>botdan va tizimdan chiqarib yuborishga</b> majbur bo'lamiz.\n\n"
                "<i>O'z o'rningizni saqlab qolish va natijalaringizni oshirish uchun bugungi testda albatta ishtirok eting!</i>"
            )

        try:
            await bot.send_message(chat_id=uid, text=text, parse_mode=ParseMode.HTML)
            sent_users.append({
                "id": u.get("id"),
                "tg_id": uid,
                "fullname": fname,
                "username": uname,
                "tests_count": t_count,
                "status": "sent"
            })
            await asyncio.sleep(0.04)
        except Exception as e:
            err_text = str(e).lower()
            if "blocked" in err_text or "forbidden" in err_text or "deactivated" in err_text:
                test_db.delete_user(uid)
                deleted_blocked_users.append(u)
            failed_users.append({
                "id": u.get("id"),
                "tg_id": uid,
                "fullname": fname,
                "username": uname,
                "tests_count": t_count,
                "error": str(e),
                "status": "failed"
            })
            log.warning(f"Ogohlantirish yuborishda xatolik user {uid}: {e}")

    # Admin ga hisobot xabarini yuborish
    try:
        z_count = len([u for u in target_users if u.get('tests_count') == 0])
        o_count = len([u for u in target_users if u.get('tests_count') == 1])
        report_text = (
            "📊 <b>FAOLIYATSIZ FOYDALANUVCHILARGA OGOHLANTIRISH YUBORILDI</b>\n\n"
            f"🎯 <b>Jami rejalashtirilgan:</b> {len(target_users)} nafar\n"
            f"✅ <b>Yetkazildi:</b> {len(sent_users)} nafar\n"
            f"⚠️ <b>Yetkazilmadi:</b> {len(failed_users)} nafar\n"
        )
        if deleted_blocked_users:
            report_text += f"🗑 <b>Botni bloklagani uchun bazadan o'chirildi:</b> {len(deleted_blocked_users)} nafar\n"
        report_text += (
            f"\n• 0 ta test ishlaganlar: {z_count} nafar\n"
            f"• 1 ta test ishlaganlar: {o_count} nafar"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=report_text)
    except Exception as e:
        log.error(f"Admin hisobotini yuborishda xato: {e}")

    return {
        "success": True,
        "total_targets": len(target_users),
        "sent_count": len(sent_users),
        "fail_count": len(failed_users),
        "deleted_count": len(deleted_blocked_users),
        "deleted_users": deleted_blocked_users,
        "zero_tests_count": len([u for u in target_users if u.get("tests_count") == 0]),
        "one_test_count": len([u for u in target_users if u.get("tests_count") == 1]),
        "sent_users": sent_users,
        "failed_users": failed_users
    }

def get_warn_inactive_step1_kb():
    text = (
        "⚠️ <b>FAOLIYATSIZ FOYDALANUVCHILARGA OGOHLANTIRISH</b>\n\n"
        "Qaysi toifadagi foydalanuvchilarga ogohlantirish yubormoqchisiz?\n\n"
        "0️⃣ <b>Faqat 0 ta test ishlaganlar:</b> Ro'yxatdan o'tib, umuman test topshirmaganlar\n"
        "1️⃣ <b>Faqat 1 ta test ishlaganlar:</b> Shu kungacha faqat bitta testda qatnashganlar\n"
        "🔢 <b>Ikkalasi ham (0 va 1 ta):</b> Barcha sust/kam faol o'quvchilar"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0️⃣ Faqat 0 ta ishlaganlar", callback_data="adm_warn_cnt_0")],
        [InlineKeyboardButton(text="1️⃣ Faqat 1 ta ishlaganlar", callback_data="adm_warn_cnt_1")],
        [InlineKeyboardButton(text="🔢 Ikkalasi ham (0 va 1 ta)", callback_data="adm_warn_cnt_both")],
        [InlineKeyboardButton(text="🔙 Admin Menyuga", callback_data="admin_back_to_menu")]
    ])
    return text, kb

@router.message(Command("warn_inactive"))
async def admin_warn_inactive_handler(message: Message):
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        await message.answer("⛔️ Bu buyruq faqat bot administratori uchun!")
        return
    text, kb = get_warn_inactive_step1_kb()
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "admin_warn_inactive_menu")
async def admin_warn_inactive_menu_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return
    text, kb = get_warn_inactive_step1_kb()
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("adm_warn_cnt_"))
async def adm_warn_cnt_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    cnt = call.data.replace("adm_warn_cnt_", "")
    cnt_labels = {
        "0": "Faqat 0 ta test ishlaganlar",
        "1": "Faqat 1 ta test ishlaganlar",
        "both": "0 va 1 ta test ishlaganlar"
    }
    label = cnt_labels.get(cnt, cnt)

    text = (
        f"⏱ <b>RO'YXATDAN O'TGAN VAQTI BO'YICHA SARALASH</b>\n\n"
        f"🎯 Tanlangan toifa: <b>{label}</b>\n\n"
        f"Foydalanuvchilar qaysi muddat bo'yicha saralansin?\n\n"
        f"⏳ <b>Qo'shilganiga 2+ kun bo'lganlar (tavsiya):</b>\n"
        f"<i>Yangi ro'yxatdan o'tganlarga (bugun yoki kecha kirganlarga) tegilmaydi, faqat kamida 2 kun oldin qo'shilganlarga yuboriladi.</i>\n\n"
        f"🆕 <b>Oxirgi 2 kunda qo'shilganlar:</b>\n"
        f"<i>Faqat so'nggi 48 soat ichida ro'yxatdan o'tganlarga yuboriladi.</i>\n\n"
        f"🗓 <b>Barcha vaqt bo'yicha:</b>\n"
        f"<i>Qachon qo'shilganidan qat'i nazar barcha tegishli o'quvchilarga yuboriladi.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Qo'shilganiga 2+ kun bo'lganlar", callback_data=f"adm_warn_time_{cnt}_min_2d")],
        [InlineKeyboardButton(text="🆕 Oxirgi 2 kunda qo'shilganlar", callback_data=f"adm_warn_time_{cnt}_last_2d")],
        [InlineKeyboardButton(text="🗓 Barcha vaqt bo'yicha (hammasi)", callback_data=f"adm_warn_time_{cnt}_all")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_warn_inactive_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("adm_warn_time_"))
async def adm_warn_time_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    parts = call.data.replace("adm_warn_time_", "").split("_", 1)
    cnt = parts[0]
    time_f = parts[1]

    cnt_labels = {
        "0": "Faqat 0 ta test ishlaganlar",
        "1": "Faqat 1 ta test ishlaganlar",
        "both": "0 va 1 ta test ishlaganlar"
    }
    time_labels = {
        "min_2d": "Qo'shilganiga 2+ kun bo'lganlar (2 kundan oshganlar)",
        "last_2d": "Oxirgi 2 kunda qo'shilganlar (so'nggi 48 soat)",
        "all": "Barcha vaqt bo'yicha (cheklovsiz)"
    }

    target_users = get_inactive_target_users(target_count=cnt, time_filter=time_f)
    user_count = len(target_users)

    if user_count == 0:
        text = (
            f"ℹ️ <b>FOYDALANUVCHILAR TOPILMADI</b>\n\n"
            f"Siz tanlagan shartlar bo'yicha:\n"
            f"• Toifa: <b>{cnt_labels.get(cnt)}</b>\n"
            f"• Muddat: <b>{time_labels.get(time_f)}</b>\n\n"
            f"Hozirda hech qanday foydalanuvchi mavjud emas."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Qayta tanlash", callback_data="admin_warn_inactive_menu")],
            [InlineKeyboardButton(text="🔙 Admin Menyuga", callback_data="admin_back_to_menu")]
        ])
        await call.message.edit_text(text, reply_markup=kb)
        await call.answer()
        return

    text = (
        f"📋 <b>OGOHLANTIRISH YUBORISHNI TASDIQLASH</b>\n\n"
        f"Siz tanlagan filtr sozlamalari:\n"
        f"🎯 <b>Toifa:</b> {cnt_labels.get(cnt)}\n"
        f"⏱ <b>Muddat:</b> {time_labels.get(time_f)}\n\n"
        f"👥 <b>Topilgan o'quvchilar soni:</b> <b>{user_count} nafar</b>\n\n"
        f"⚠️ <i>Har bir foydalanuvchiga uning testlari soniga mos rasmiy ogohlantirish xabari yetkaziladi. "
        f"Agar foydalanuvchi botni bloklagan bo'lsa, u avtomatik bazadan o'chiriladi.</i>\n\n"
        f"<b>Haqiqatan ham ushbu {user_count} nafar foydalanuvchiga xabar yuborilsinmi?</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚀 Ha, yuborilsin ({user_count} ta)", callback_data=f"adm_warn_send_{cnt}_{time_f}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_back_to_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("adm_warn_send_"))
async def adm_warn_send_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    parts = call.data.replace("adm_warn_send_", "").split("_", 1)
    cnt = parts[0]
    time_f = parts[1]

    await call.answer("⏳ Xabarlar yuborilmoqda...")
    status_msg = await call.message.edit_text(
        "⏳ <b>Xabarlar yuborilmoqda, iltimos kuting...</b>\n\n"
        "<i>Har bir foydalanuvchiga xabar yetkazilmoqda va bloklaganlar tekshirilmoqda...</i>"
    )

    result = await send_inactive_warning_messages(
        initiator_id=call.from_user.id,
        target_count=cnt,
        time_filter=time_f
    )

    total = result["total_targets"]
    sent = result["sent_count"]
    fail = result["fail_count"]
    deleted = result.get("deleted_count", 0)

    res_text = (
        f"✅ <b>Ogohlantirish xabarlari muvaffaqiyatli tarqatildi!</b>\n\n"
        f"🎯 <b>Rejalashtirilgan:</b> {total} nafar\n"
        f"📨 <b>Yetkazildi:</b> {sent} nafar\n"
        f"⚠️ <b>Yetkazilmadi (bloklangan):</b> {fail} nafar\n"
    )
    if deleted > 0:
        res_text += f"🗑 <b>Botni bloklagani uchun bazadan o'chirildi:</b> {deleted} nafar\n"

    res_text += "\n<i>Batafsil hisobot qabul qilindi.</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
    ])
    try:
        await status_msg.edit_text(res_text, reply_markup=kb)
    except Exception:
        await call.message.answer(res_text, reply_markup=kb)

@router.callback_query(F.data == "admin_clean_blocked_prompt")
async def admin_clean_blocked_prompt_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    users_count = len(test_db.get_all_users())
    text = (
        f"🧹 <b>BOTNI BLOKLAGANLARNI TOZALASH</b>\n\n"
        f"Hozirda bazada jami: <b>{users_count} nafar</b> foydalanuvchi mavjud.\n\n"
        f"Ushbu funksiya barcha foydalanuvchilarni ko'rinmas usulda (hech qanday xabar bormasdan) tekshirib chiqadi.\n\n"
        f"Agar biror foydalanuvchi botni to'xtatgan yoki bloklagan bo'lsa, u <b>bazadan to'liq o'chirib tashlanadi</b>.\n\n"
        f"<b>Tekshiruv va tozalashni boshlashni tasdiqlaysizmi?</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Ha, tozalashni boshlash", callback_data="adm_clean_blocked_start")],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_back_to_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "adm_clean_blocked_start")
async def adm_clean_blocked_start_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    await call.answer("⏳ Tozalash boshlandi...")
    await call.message.edit_text(
        "⏳ <b>Bazadagi barcha foydalanuvchilar tekshirilmoqda...</b>\n\n"
        "<i>Bu bir necha soniya vaqt olishi mumkin, iltimos kuting...</i>"
    )

    result = await clean_blocked_users_from_db(initiator_id=call.from_user.id)
    total = result["total_checked"]
    active = result["active_count"]
    deleted = result["deleted_count"]
    deleted_list = result["deleted_users"]

    res_text = (
        f"📊 <b>Foydalanuvchilar holati tekshiruvi yakunlandi:</b>\n\n"
        f"👥 <b>Jami tekshirildi:</b> {total} ta\n"
        f"✅ <b>Faol foydalanuvchilar:</b> {active} ta\n"
        f"🗑 <b>Botni bloklagani uchun bazadan o'chirildi:</b> {deleted} ta\n\n"
    )
    if deleted_list:
        res_text += "<b>Bazadan o'chirilgan foydalanuvchilar:</b>\n"
        for i, bu in enumerate(deleted_list[:25], 1):
            bun = f" ({bu['username']})" if bu.get('username') and bu['username'] != '—' else ""
            res_text += f"{i}. <b>{bu['fullname']}</b>{bun} — <code>{bu['tg_id']}</code>\n"
        if len(deleted_list) > 25:
            res_text += f"\n<i>...va yana {len(deleted_list) - 25} ta foydalanuvchi.</i>"
    else:
        res_text += "🎉 <i>Hozirda botni bloklagan foydalanuvchilar aniqlanmadi (baza toza)!</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
    ])
    await call.message.edit_text(res_text, reply_markup=kb)

# 4. › Yordam va murojaat
@router.message(F.text.in_({"› Yordam", "💡 Yordam", "ℹ️ Yordam", "ℹ️ Bot haqida"}))
@router.message(Command("help"))
async def show_help(message: Message):
    contact_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="› Adminga murojaat (@eshmbetov)", url="https://t.me/eshmbetov")],
        [make_webapp_button("◈ Fizika (Mini App)", f"{WEBAPP_URL}/app.html")]
    ])
    await message.answer(
        "ℹ <b>YORDAM VA QO'LLAB-QUVVATLASH</b>\n\n"
        "◈ <b>FIZIKA — MILLIY SERTIFIKAT TEST TIZIMI</b>\n\n"
        "Ushbu tizim orqali siz:\n"
        "• Milliy sertifikat formatidagi 55 talik testlarni yechishingiz;\n"
        "• Virtual klaviaturadan foydalanib yozma javoblarni kiritishingiz;\n"
        "• Rasch modeli bo'yicha darajangiz (A+, A, B+, B, ...) va to'liq tahlilni ko'rishingiz mumkin.\n\n"
        "💬 <b>Savol, taklif yoki yordam uchun to'g'ridan-to'g'ri bog'lanishingiz mumkin:</b>\n"
        "• <b>Aloqa:</b> @eshmbetov\n\n"
        "<i>Pastdagi havola orqali murojaat yuborishingiz mumkin:</i>",
        reply_markup=contact_kb
    )

show_about = show_help

# ✦ Yangi test yaratish (Admin Mini App ochish)
@router.message(F.text.in_({"✦ Yangi test yaratish", "➕ Yangi test yaratish"}))
async def admin_create_test_text_handler(message: Message):
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        return
    admin_webapp_url = f"{WEBAPP_URL}/admin.html?tg_id={message.from_user.id}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_webapp_button("✦ Yangi test yaratish (Mini App)", admin_webapp_url)]
    ])
    await message.answer(
        "✦ <b>YANGI TEST YARATISH BO'LIMI</b>\n\n"
        "Quyidagi tugma orqali Admin Mini Appni ochib, test kodi, fani, vaqti va 55 ta savol kalitlarini kiritishingiz mumkin:",
        reply_markup=kb
    )

# ◈ Testlarni boshqarish (O'chirish, to'xtatish, vaqt)
@router.message(F.text.in_({"◈ Testlarni boshqarish", "🔬 Testlarni boshqarish", "📋 Testlarni boshqarish"}))
async def admin_manage_tests_text_handler(message: Message):
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        return
    tests = test_db.get_all_tests()
    if not tests:
        await message.answer("ℹ Hozircha bazada birorta ham test yo'q.")
        return

    text = (
        "◈ <b>Barcha testlar ro'yxati va boshqaruvi:</b>\n\n"
        "<i>Boshqarish (to'xtatish / vaqt / o'chirish) uchun kerakli testni tanlang:</i>\n\n"
    )
    buttons = []
    for idx, t in enumerate(tests, 1):
        status_icon = "✓" if t["is_active"] == 1 else "✕"
        time_str = f"{t['time_limit_min']} daqiqa" if t.get("time_limit_min", 0) > 0 else "Cheksiz"
        text += f"<b>{idx}. #{t['test_code']}</b> — {t['title']} ({status_icon}, ⏱ {time_str})\n"
        buttons.append([InlineKeyboardButton(text=f"[{status_icon}] #{t['test_code']} — {t['title'][:25]}", callback_data=f"adm_mng_test_{t['id']}")])

    buttons.append([InlineKeyboardButton(text="‹ Admin menyusiga qaytish", callback_data="admin_back_to_menu")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ◈ Test natijalari va reyting
@router.message(F.text.in_({"◈ Test natijalari va reyting", "📊 Test natijalari va reyting"}))
async def admin_leaderboard_text_handler(message: Message):
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        return
    tests = test_db.get_tests_with_stats()
    if not tests:
        await message.answer("ℹ Hozirda tizimda mavjud testlar yo'q.")
        return
    buttons = []
    msg_list = ""
    for idx, t in enumerate(tests, 1):
        sub_cnt = t.get("submissions_count", 0)
        btn_text = f"◈ #{t['test_code']} — {sub_cnt} kishi"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_tstat_{t['id']}")])
        creator_name = t.get("created_by_name") or ("Bosh Admin" if t.get("created_by") == ADMIN_ID else "")
        creator_info = f" ({creator_name})" if creator_name else ""
        msg_list += f"<b>{idx}. #{t['test_code']}</b> — {t['title']}{creator_info}: <b>{sub_cnt} kishi</b>\n"

    buttons.append([InlineKeyboardButton(text="‹ Admin Panelga qaytish", callback_data="admin_panel_back")])
    msg_text = (
        "◈ <b>Mavjud Testlar va Ishtirokchilar Soni:</b>\n\n"
        f"{msg_list}\n"
        "<i>Batafsil natijalarni (Matn yoki PDF shaklida) olish uchun kerakli test kodini tanlang:</i>"
    )
    await message.answer(msg_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# 5. ◈ Mini App buyrug'i
@router.message(Command("app"))
async def open_app_command(message: Message):
    await message.answer(
        "◈ <b>RASCH TEST Mini App tizimiga kirish:</b>\n\n"
        "Quyidagi tugmani bosing:",
        reply_markup=results_webapp_kb(message.from_user.id)
    )

# ── ADMIN PANEL HANDLERLARI ───────────────────────────

@router.message(F.text.in_({"⚙ Admin Panel", "⚙️ Admin Panel"}))
@router.message(Command("admin"))
@router.message(Command("dashboard"))
async def admin_panel_handler(message: Message):
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        await message.answer("✕ Bu bo'lim faqat bot administratori uchun!")
        return

    await message.answer(
        "⚙️ <b>ADMIN BOSHQARUV PANELI</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang 👇",
        reply_markup=admin_menu_kb()
    )


# ── FOYDALANUVCHIGA YOZISH VA PROFIL CHATIGA O'TISH ──

def build_user_contact_card(user: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """Foydalanuvchi kartasi va profil chatiga olib o'tuvchi tugmalarni shakllantiradi."""
    tg_id = user.get("tg_id")
    fullname = user.get("fullname", "Noma'lum")
    raw_uname = (user.get("username") or "").strip()
    username = raw_uname.lstrip("@").strip()
    phone = user.get("phone", "—")
    status = user.get("status", "approved")
    tests_count = user.get("tests_count", 0)
    reg_ts = user.get("registered_at")
    reg_fmt = format_uzb_time(reg_ts, "%d.%m.%Y %H:%M") if reg_ts else "Noma'lum"

    last_test_ts = user.get("last_test_at")
    last_test_fmt = format_uzb_time(last_test_ts, "%d.%m.%Y %H:%M") if last_test_ts else "Topshirmagan"

    status_icon = "🟢 Faol" if status == "approved" else "🔴 Bloklangan"

    clean_phone = re.sub(r"[^\d+]", "", str(phone or ""))

    if username:
        uname_text = f"@{username}"
        profile_mention = (
            f"👉 <b>Telegram chat:</b> <a href=\"https://t.me/{username}\">@{username} shaxsiy chatini ochish ↗️</a>"
        )
    else:
        uname_text = "<i>Mavjud emas</i>"
        profile_mention = (
            f"👉 <b>Telegram chat (Telegramning o'zida ochish):</b>\n"
            f"👉 <a href=\"tg://user?id={tg_id}\"><b>{fullname} profil chatini ochish (ustiga bosing) 💬</b></a>"
        )

    card_text = (
        f"👤 <b>FOYDALANUVCHI MA'LUMOTLARI VA PROFIL CHATI</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{tg_id}</code>\n"
        f"👤 <b>F.I.SH:</b> <b>{fullname}</b>\n"
        f"🔗 <b>Username:</b> {uname_text}\n"
        f"📞 <b>Telefon:</b> <code>{phone}</code>\n"
        f"📊 <b>Topshirgan testlari:</b> <b>{tests_count} ta</b>\n"
        f"🕒 <b>Oxirgi faolligi:</b> {last_test_fmt}\n"
        f"📅 <b>Ro'yxatdan o'tgan:</b> {reg_fmt}\n"
        f"🔘 <b>Holati:</b> {status_icon}\n\n"
        f"💬 <b>Shaxsiy chatga o'tish:</b>\n"
        f"{profile_mention}\n\n"
        f"<i>Quyidagi tugmalar orqali Telegramning o'zida kontaktni ochishingiz yoki bot orqali xabar yuborishingiz mumkin 👇</i>"
    )

    buttons = []
    if username:
        buttons.append([InlineKeyboardButton(text="💬 Shaxsiy profil chatini ochish ↗️", url=f"https://t.me/{username}")])
    else:
        # Username yo'q foydalanuvchilar uchun web ochmasdan, Telegram ilovasining o'zida kontakt orqali chat ochish tugmasi
        if clean_phone and clean_phone not in ["—", "-", ""]:
            buttons.append([InlineKeyboardButton(text="📇 Telegram kontakt kartasini ko'rish (Chat) ↗️", callback_data=f"adm_send_contact_{tg_id}")])

    buttons.append([InlineKeyboardButton(text="✉️ Bot orqali xabar yozish", callback_data=f"adm_msg_user_{tg_id}")])
    buttons.append([InlineKeyboardButton(text="🔍 Boshqa foydalanuvchi qidirish", callback_data="admin_contact_user_prompt")])
    buttons.append([InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")])

    return card_text, InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("user"))
@router.message(Command("write_user"))
@router.message(Command("contact"))
@router.message(Command("msg"))
async def admin_contact_user_command(message: Message, state: FSMContext):
    """Admin uchun /user <id> yoki /user buyrug'i."""
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        await message.answer("⛔️ Bu buyruq faqat bot administratori uchun!")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) > 1:
        query = parts[1].strip()
        user = test_db.find_user(query)
        if user:
            await state.clear()
            try:
                clean_phone = re.sub(r"[^\d+]", "", str(user.get("phone") or ""))
                if not user.get("username") and clean_phone and clean_phone not in ["—", "-", ""]:
                    parts_name = (user.get("fullname") or "Foydalanuvchi").split(maxsplit=1)
                    fn = parts_name[0]
                    ln = parts_name[1] if len(parts_name) > 1 else ""
                    try:
                        await message.answer_contact(
                            phone_number=clean_phone,
                            first_name=fn,
                            last_name=ln
                        )
                    except Exception:
                        pass

                card_text, card_kb = build_user_contact_card(user)
                await message.answer(card_text, reply_markup=card_kb)
            except Exception as e:
                log.error(f"Xatolik foydalanuvchi kartasini chiqarishda: {e}", exc_info=True)
                uid = user.get('tg_id')
                fallback_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✉️ Bot orqali xabar yozish", callback_data=f"adm_msg_user_{uid}")],
                    [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
                ])
                await message.answer(
                    f"👤 <b>{html.escape(user.get('fullname', 'Foydalanuvchi'))}</b> (ID: <code>{uid}</code>)\n\n"
                    f"👉 <a href=\"tg://user?id={uid}\"><b>Telegram chatini ochish (ustiga bosing)</b></a>",
                    reply_markup=fallback_kb
                )
            return
        else:
            await message.answer(
                f"❌ <b>Foydalanuvchi topilmadi!</b>\n\n"
                f"Kiritilgan ma'lumot (<code>{html.escape(query)}</code>) bo'yicha foydalanuvchi bazadan topilmadi.\n\n"
                f"Iltimos, ID raqamini tekshirib qaytadan kiriting:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_back_to_menu")]
                ])
            )
            await state.set_state(ContactUserState.waiting_for_user_id)
            return

    await state.set_state(ContactUserState.waiting_for_user_id)
    text = (
        "💬 <b>FOYDALANUVCHIGA YOZISH / PROFIL CHATIGA O'TISH</b>\n\n"
        "Foydalanuvchining <b>Telegram ID</b> raqamini kiriting:\n"
        "<i>(Shuningdek @username yoki telefon raqami orqali ham qidirishingiz mumkin)</i>\n\n"
        "Masalan: <code>8039427064</code> yoki <code>@foydalanuvchi</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_back_to_menu")]
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "admin_contact_user_prompt")
async def admin_contact_user_prompt_cb(call: CallbackQuery, state: FSMContext):
    """Admin panel orqali ID so'rash oynasi."""
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    await state.set_state(ContactUserState.waiting_for_user_id)
    text = (
        "💬 <b>FOYDALANUVCHIGA YOZISH / PROFIL CHATIGA O'TISH</b>\n\n"
        "Foydalanuvchining <b>Telegram ID</b> raqamini kiriting:\n"
        "<i>(Shuningdek @username yoki telefon raqami orqali ham qidirishingiz mumkin)</i>\n\n"
        "Masalan: <code>8039427064</code> yoki <code>@foydalanuvchi</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_back_to_menu")]
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@router.message(ContactUserState.waiting_for_user_id)
async def admin_process_contact_user_id(message: Message, state: FSMContext):
    """Admin ID yoki Username kiritganda qidirib profil va chat havolalarini ko'rsatish."""
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        await state.clear()
        return

    query = message.text.strip() if message.text else ""
    if query in ["/admin", "/cancel", "/start"]:
        await state.clear()
        if query == "/admin":
            await admin_panel_handler(message)
        elif query == "/start":
            await start_handler(message, state)
        else:
            await message.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    if not query:
        await message.answer("⚠️ Iltimos, Telegram ID yoki username matnini kiriting:")
        return

    user = test_db.find_user(query)
    if not user:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_back_to_menu")]
        ])
        await message.answer(
            f"❌ <b>Foydalanuvchi topilmadi!</b>\n\n"
            f"Kiritilgan ma'lumot (<code>{html.escape(query)}</code>) bo'yicha foydalanuvchi bazadan topilmadi.\n\n"
            f"Iltimos, Telegram ID yoki usernameni to'g'ri tekshirib qaytadan kiriting:",
            reply_markup=kb
        )
        return

    await state.clear()
    try:
        clean_phone = re.sub(r"[^\d+]", "", str(user.get("phone") or ""))
        if not user.get("username") and clean_phone and clean_phone not in ["—", "-", ""]:
            parts_name = (user.get("fullname") or "Foydalanuvchi").split(maxsplit=1)
            fn = parts_name[0]
            ln = parts_name[1] if len(parts_name) > 1 else ""
            try:
                await message.answer_contact(
                    phone_number=clean_phone,
                    first_name=fn,
                    last_name=ln
                )
            except Exception:
                pass

        card_text, card_kb = build_user_contact_card(user)
        await message.answer(card_text, reply_markup=card_kb)
    except Exception as e:
        log.error(f"Foydalanuvchi kartasini yuborishda xatolik: {e}", exc_info=True)
        uid = user.get('tg_id')
        fallback_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✉️ Bot orqali xabar yozish", callback_data=f"adm_msg_user_{uid}")],
            [InlineKeyboardButton(text="🔍 Boshqa foydalanuvchi qidirish", callback_data="admin_contact_user_prompt")],
            [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
        ])
        await message.answer(
            f"👤 <b>{html.escape(user.get('fullname', 'Foydalanuvchi'))}</b> (ID: <code>{uid}</code>)\n\n"
            f"👉 <a href=\"tg://user?id={uid}\"><b>Telegram chatini ochish (ustiga bosing)</b></a>",
            reply_markup=fallback_kb
        )


@router.callback_query(F.data.startswith("adm_view_user_"))
async def adm_view_user_cb(call: CallbackQuery, state: FSMContext):
    """Foydalanuvchi kartasini qayta ko'rsatish."""
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    await state.clear()
    target_tg_id = int(call.data.replace("adm_view_user_", ""))
    user = test_db.find_user(target_tg_id)
    if not user:
        await call.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
    card_text, card_kb = build_user_contact_card(user)
    try:
        await call.message.edit_text(card_text, reply_markup=card_kb)
    except Exception:
        await call.message.answer(card_text, reply_markup=card_kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm_msg_user_"))
async def adm_msg_user_cb(call: CallbackQuery, state: FSMContext):
    """Foydalanuvchiga bot nomidan xabar yozish holatiga o'tish."""
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        await call.answer("Ruxsat yo'q!", show_alert=True)
        return

    target_tg_id = int(call.data.replace("adm_msg_user_", ""))
    user = test_db.find_user(target_tg_id)
    fullname = user.get("fullname", f"ID: {target_tg_id}") if user else f"ID: {target_tg_id}"

    await state.set_state(ContactUserState.waiting_for_message)
    await state.update_data(target_tg_id=target_tg_id, target_fullname=fullname)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data=f"adm_view_user_{target_tg_id}")]
    ])
    text = (
        f"✉️ <b>FOYDALANUVCHIGA XABAR YOZISH</b>\n\n"
        f"Kimga: <b>{fullname}</b> (ID: <code>{target_tg_id}</code>)\n\n"
        f"Foydalanuvchiga yubormoqchi bo'lgan xabaringizni yozing (matn, rasm yoki hujjat):\n"
        f"<i>Xabar foydalanuvchiga bot nomidan yetkaziladi.</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@router.message(ContactUserState.waiting_for_message)
async def adm_send_user_message_handler(message: Message, state: FSMContext):
    """Admin yozgan xabarni foydalanuvchiga yetkazish."""
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        await state.clear()
        return

    text_val = message.text or message.caption or ""
    if text_val in ["/admin", "/cancel"]:
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=admin_menu_kb())
        return

    data = await state.get_data()
    target_tg_id = data.get("target_tg_id")
    target_fullname = data.get("target_fullname", "Foydalanuvchi")
    await state.clear()

    if not target_tg_id:
        await message.answer("⚠️ Ma'lumot topilmadi, iltimos qaytadan urinib ko'ring.", reply_markup=admin_menu_kb())
        return

    user_reply_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Adminga javob yozish (@eshmbetov)", url="https://t.me/eshmbetov")]
    ])

    try:
        if message.text:
            out_text = (
                f"📩 <b>ADMINISTRATSIYADAN XABAR:</b>\n\n"
                f"{message.text}\n\n"
                f"<i>Hurmat bilan, RASH TEST administratsiyasi</i>"
            )
            await bot.send_message(chat_id=target_tg_id, text=out_text, reply_markup=user_reply_kb)
        elif message.photo:
            caption = message.caption or ""
            out_caption = (
                f"📩 <b>ADMINISTRATSIYADAN XABAR:</b>\n\n"
                f"{caption}\n\n"
                f"<i>Hurmat bilan, RASH TEST administratsiyasi</i>"
            ) if caption else "📩 <b>ADMINISTRATSIYADAN XABAR:</b>\n\n<i>Hurmat bilan, RASH TEST administratsiyasi</i>"
            await bot.send_photo(chat_id=target_tg_id, photo=message.photo[-1].file_id, caption=out_caption, reply_markup=user_reply_kb)
        elif message.document:
            caption = message.caption or ""
            out_caption = (
                f"📩 <b>ADMINISTRATSIYADAN HUJJAT:</b>\n\n"
                f"{caption}\n\n"
                f"<i>Hurmat bilan, RASH TEST administratsiyasi</i>"
            ) if caption else "📩 <b>ADMINISTRATSIYADAN HUJJAT:</b>\n\n<i>Hurmat bilan, RASH TEST administratsiyasi</i>"
            await bot.send_document(chat_id=target_tg_id, document=message.document.file_id, caption=out_caption, reply_markup=user_reply_kb)
        else:
            await message.send_copy(chat_id=target_tg_id, reply_markup=user_reply_kb)

        user_info = test_db.find_user(target_tg_id)
        uname = (user_info.get("username") or "").strip().lstrip("@") if user_info else ""
        buttons = []
        if uname:
            buttons.append([InlineKeyboardButton(text="💬 Shaxsiy profil chatini ochish ↗️", url=f"https://t.me/{uname}")])
        else:
            phone_val = re.sub(r"[^\d+]", "", str(user_info.get("phone") if user_info else "" or ""))
            if phone_val and phone_val not in ["—", "-", ""]:
                buttons.append([InlineKeyboardButton(text="📇 Telegram kontakt kartasini ko'rish (Chat) ↗️", callback_data=f"adm_send_contact_{target_tg_id}")])

        buttons.append([InlineKeyboardButton(text="✉️ Yana xabar yozish", callback_data=f"adm_msg_user_{target_tg_id}")])
        buttons.append([InlineKeyboardButton(text="🔍 Boshqa foydalanuvchi qidirish", callback_data="admin_contact_user_prompt")])
        buttons.append([InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")])

        await message.answer(
            f"✅ <b>Xabar muvaffaqiyatli yetkazildi!</b>\n\n"
            f"👤 Kimga: <b>{target_fullname}</b>\n"
            f"🆔 Telegram ID: <code>{target_tg_id}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    except Exception as e:
        err_msg = str(e)
        log.warning(f"Error sending message to user {target_tg_id}: {err_msg}")
        user_info = test_db.find_user(target_tg_id)
        uname = (user_info.get("username") or "").strip().lstrip("@") if user_info else ""
        buttons = []
        if uname:
            buttons.append([InlineKeyboardButton(text="💬 Shaxsiy profil chatini ochish ↗️", url=f"https://t.me/{uname}")])
        else:
            phone_val = re.sub(r"[^\d+]", "", str(user_info.get("phone") if user_info else "" or ""))
            if phone_val and phone_val not in ["—", "-", ""]:
                buttons.append([InlineKeyboardButton(text="📇 Telegram kontakt kartasini ko'rish (Chat) ↗️", callback_data=f"adm_send_contact_{target_tg_id}")])
        buttons.append([InlineKeyboardButton(text="🔍 Boshqa foydalanuvchi qidirish", callback_data="admin_contact_user_prompt")])
        buttons.append([InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")])

        if "forbidden" in err_msg.lower() or "blocked" in err_msg.lower():
            await message.answer(
                f"❌ <b>Xabar yetkazilmadi!</b>\n\n"
                f"Foydalanuvchi (<b>{target_fullname}</b>, ID: <code>{target_tg_id}</code>) botni bloklagan yoki to'xtatgan.\n\n"
                f"Siz Telegram ilovasining o'zida profiliga o'tishingiz mumkin.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
        else:
            await message.answer(
                f"❌ <b>Xatolik yuz berdi:</b> {html.escape(err_msg)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )


@router.callback_query(F.data.startswith("adm_send_contact_"))
async def adm_send_contact_cb(call: CallbackQuery):
    """Admin uchun foydalanuvchining Telegram kontakt kartasini chatga yuborish."""
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        await call.answer("⛔️ Ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    try:
        target_tg_id = int(parts[3])
    except Exception:
        await call.answer("Xatolik: ID topilmadi", show_alert=True)
        return
    user = test_db.find_user(target_tg_id)
    if not user:
        await call.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
    phone = user.get("phone", "")
    fullname = user.get("fullname", "Foydalanuvchi")
    clean_phone = re.sub(r"[^\d+]", "", str(phone or ""))
    if not clean_phone or clean_phone in ["—", "-", ""]:
        await call.answer("Foydalanuvchining telefon raqami mavjud emas!", show_alert=True)
        return

    await call.answer("Kontakt kartasi yuborilmoqda...")
    try:
        parts_name = fullname.split(maxsplit=1)
        first_name = parts_name[0]
        last_name = parts_name[1] if len(parts_name) > 1 else ""

        contact_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✉️ Bot orqali xabar yozish", callback_data=f"adm_msg_user_{target_tg_id}")],
            [InlineKeyboardButton(text="🔙 Foydalanuvchi ma'lumotlariga qaytish", callback_data=f"adm_view_user_{target_tg_id}")]
        ])

        await call.message.answer_contact(
            phone_number=clean_phone,
            first_name=first_name,
            last_name=last_name,
            reply_markup=contact_kb
        )
    except Exception as e:
        log.error(f"Kontakt kartasini yuborishda xatolik: {e}")
        await call.message.answer(f"⚠️ Kontaktni yuborishda xatolik: {e}")


# 1. Yangi test yaratish (Faqat Admin Mini App orqali)
@router.callback_query(F.data == "admin_add_test")
async def admin_start_add_test(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    await state.clear()
    await admin_webapp_info_cb(call)


# 2. Testlarni boshqarish (O'chirish, To'xtatish/Yoqish, Vaqt)
@router.callback_query(F.data == "admin_manage_tests")
async def admin_manage_tests(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    tests = test_db.get_all_tests()
    if not tests:
        text = "ℹ️ Hozircha bazada birorta ham test yo'q."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Menyuga qaytish", callback_data="admin_back_to_menu")]
        ])
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            await call.message.answer(text, reply_markup=kb)
        await call.answer()
        return

    text = (
        "📋 <b>Barcha testlar ro'yxati va boshqaruvi:</b>\n\n"
        "<i>Boshqarish (to'xtatish / vaqt / o'chirish) uchun kerakli testni tanlang 👇</i>\n\n"
    )
    buttons = []
    for idx, t in enumerate(tests, 1):
        status_icon = "🟢" if t["is_active"] == 1 else "🔴"
        time_str = f"{t['time_limit_min']} daqiqa" if t.get("time_limit_min", 0) > 0 else "Cheksiz"
        creator_name = t.get("created_by_name") or ("Bosh Admin" if t.get("created_by") == ADMIN_ID else "")
        creator_info = f" (👤 {creator_name})" if creator_name else ""
        text += f"<b>{idx}. #{t['test_code']}</b> — {t['title']} ({status_icon}, ⏱ {time_str}){creator_info}\n"
        buttons.append([InlineKeyboardButton(text=f"{status_icon} #{t['test_code']} — {t['title'][:22]}", callback_data=f"adm_mng_test_{t['id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 Admin Menyuga qaytish", callback_data="admin_back_to_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("adm_mng_test_"))
async def admin_manage_test_card(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    t = test_db.get_test_by_id(test_id)
    if not t:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    status_str = "🟢 Faol (O'quvchilarga ko'rinadi)" if t["is_active"] == 1 else "🔴 To'xtatilgan (Yashiringan)"
    time_str = f"{t['time_limit_min']} daqiqa" if t.get("time_limit_min", 0) > 0 else "Cheksiz"
    toggle_btn_text = "🔴 To'xtatish" if t["is_active"] == 1 else "🟢 Faollashtirish"

    has_pdf_str = f"📄 <b>PDF:</b> {t.get('pdf_file_name') or 'Biriktirilgan ✅'}\n" if t.get("pdf_file_id") else "📄 <b>PDF:</b> ❌ Yuklanmagan\n"
    pdf_btn_text = "📄 PDF almashtirish" if t.get("pdf_file_id") else "📥 PDF yuklash"

    creator_str = t.get('created_by_name') or ('Bosh Admin' if t.get('created_by') == ADMIN_ID else 'Admin')
    card_text = (
        f"📖 <b>{t['title']}</b> (<code>#{t['test_code']}</code>)\n"
        f"👤 <b>Yaratuvchi:</b> {creator_str}\n"
        f"📌 <b>Fan:</b> {t.get('subject', 'Fizika')}\n"
        f"📊 <b>Holati:</b> {status_str}\n"
        f"⏱ <b>Vaqt chegarasi:</b> {time_str}\n"
        f"{has_pdf_str}\n"
        f"<i>Boshqarish uchun quyidagi amallardan birini tanlang:</i>"
    )

    edit_keys_url = f"{WEBAPP_URL}/admin.html?edit_test_id={t['id']}"
    kb_rows = [
        [make_webapp_button("✏️ Kalitlarni tahrirlash (Mini App)", edit_keys_url)],
        [InlineKeyboardButton(text=toggle_btn_text, callback_data=f"toggle_test_{t['id']}")],
        [InlineKeyboardButton(text=pdf_btn_text, callback_data=f"ask_pdf_{t['id']}")],
        [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_test_confirm_{t['id']}")],
        [InlineKeyboardButton(text="⬅️ Testlar ro'yxatiga qaytish", callback_data="admin_manage_tests")]
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    try:
        await call.message.edit_text(card_text, reply_markup=kb)
    except Exception:
        await call.message.answer(card_text, reply_markup=kb)
    await call.answer()

# Test holatini o'zgartirish (Toggle Active)
@router.callback_query(F.data.startswith("toggle_test_"))
async def admin_toggle_test_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[2])
    new_status = test_db.toggle_test_status(test_id)
    if new_status is not None:
        status_text = "🟢 Faol" if new_status == 1 else "🔴 To'xtatildi"
        await call.answer(f"Test holati: {status_text}", show_alert=True)
        call.data = f"adm_mng_test_{test_id}"
        await admin_manage_test_card(call)
    else:
        await call.answer("Xatolik yuz berdi!", show_alert=True)

# Test vaqtini belgilash prompt
@router.callback_query(F.data.startswith("set_time_prompt_"))
async def admin_set_time_prompt(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    await state.update_data(target_test_id=test_id)
    await state.set_state(SetTimeLimitState.time_limit)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"adm_mng_test_{test_id}")]
    ])
    text = (
        "⏱ <b>Test uchun vaqt chegarasini daqiqalarda kiriting:</b>\n\n"
        "<i>(Masalan: 120, 180 yoki cheksiz bo'lishi uchun 0 deb yozing)</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=cancel_kb)
    except Exception:
        await call.message.answer(text, reply_markup=cancel_kb)
    await call.answer()

@router.message(SetTimeLimitState.time_limit)
async def admin_save_time_limit(message: Message, state: FSMContext):
    data = await state.get_data()
    test_id = data.get("target_test_id")
    try:
        minutes = int(message.text.strip())
        test_db.update_test_time_limit(test_id, minutes)
        await state.clear()
        time_text = f"{minutes} daqiqa" if minutes > 0 else "Cheksiz"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Testga qaytish", callback_data=f"adm_mng_test_{test_id}")],
            [InlineKeyboardButton(text="🔙 Admin Menyuga", callback_data="admin_back_to_menu")]
        ])
        await message.answer(f"✅ Test vaqt chegarasi <b>{time_text}</b> qilib belgilandi!", reply_markup=kb)
    except ValueError:
        await message.answer("⚠️ Iltimos, faqat butun son kiriting (masalan: 120 yoki 0):")

# Testni o'chirish
@router.callback_query(F.data.startswith("del_test_confirm_"))
async def admin_delete_test_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    test_db.delete_test(test_id)
    await call.answer("🗑 Test muvaffaqiyatli o'chirildi!", show_alert=True)
    await admin_manage_tests(call)

# ── TEZKOR FOYDALANUVCHI TASDIQLASH / RAD ETISH HANDLERLARI ──
@router.callback_query(F.data.startswith("user_quick_approve_"))
async def user_quick_approve_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        await call.answer("Siz admin emassiz!", show_alert=True)
        return
    uid = int(call.data.split("_")[3])
    u = test_db.get_user(uid)

    # Agar allaqachon hal qilingan bo'lsa — xabar chiqar, qayta ishlamasin
    if u and u.get("status") in ["approved", "rejected", "blocked"]:
        status_map = {
            "approved": "✅ Bu foydalanuvchi allaqachon boshqa admin tomonidan RUXSAT BERILGAN!",
            "rejected": "❌ Bu foydalanuvchi allaqachon RAD ETILGAN!",
            "blocked": "⛔️ Bu foydalanuvchi BLOKLANGAN!"
        }
        await call.answer(status_map.get(u["status"], "Allaqachon hal qilingan!"), show_alert=True)
        # Ushbu admindagi tugmalarni ham o'chirib qo'y
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    uname = u["fullname"] if u else f"ID: {uid}"
    admin_name = call.from_user.full_name or "Admin"

    test_db.approve_user(uid)

    # Ushbu admindagi xabarni yangilash
    try:
        await call.message.edit_text(
            f"{call.message.text}\n\n✅ <b>RUXSAT BERILDI!</b>\nTasdiqladi: <b>{admin_name}</b>",
            reply_markup=None
        )
    except Exception:
        pass

    # Boshqa BARCHA adminlarga xabar yuborish (tugmalarsiz)
    done_text = (
        f"✅ <b>ARIZA HAL QILINDI</b>\n\n"
        f"👤 <b>{uname}</b> foydalanuvchisiga\n"
        f"<b>{admin_name}</b> tomonidan ruxsat berildi.\n\n"
        f"<i>Siz hech narsa qilishingiz shart emas.</i>"
    )
    for adm_id in get_all_admin_ids():
        if adm_id == call.from_user.id:
            continue  # O'ziga yubormasin
        try:
            await bot.send_message(chat_id=adm_id, text=done_text)
        except Exception:
            pass

    # Foydalanuvchiga xabar
    try:
        await bot.send_message(
            chat_id=uid,
            text=(
                f"🎉 <b>Xushxabar, hurmatli {uname}!</b>\n\n"
                f"Admin sizga test tizimidan to'liq foydalanishga ruxsat berdi! ✅\n"
                f"Endi bemalol barcha testlarni yechishingiz, natijalarni ko'rishingiz va mini ilovadan foydalanishingiz mumkin 👇"
            ),
            reply_markup=main_menu_kb(uid)
        )
    except Exception as e:
        log.warning(f"Foydalanuvchiga ruxsat xabarini yuborishda xatolik: {e}")
    await call.answer("✅ Foydalanuvchiga ruxsat berildi!", show_alert=True)

@router.callback_query(F.data.startswith("user_quick_reject_"))
async def user_quick_reject_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        await call.answer("Siz admin emassiz!", show_alert=True)
        return
    uid = int(call.data.split("_")[3])
    u = test_db.get_user(uid)

    # Agar allaqachon hal qilingan bo'lsa
    if u and u.get("status") in ["approved", "rejected", "blocked"]:
        status_map = {
            "approved": "✅ Bu foydalanuvchi allaqachon RUXSAT BERILGAN!",
            "rejected": "❌ Bu foydalanuvchi allaqachon RAD ETILGAN!",
            "blocked": "⛔️ Bu foydalanuvchi BLOKLANGAN!"
        }
        await call.answer(status_map.get(u["status"], "Allaqachon hal qilingan!"), show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    uname = u["fullname"] if u else f"ID: {uid}"
    admin_name = call.from_user.full_name or "Admin"

    test_db.reject_user(uid)

    # Ushbu admindagi xabarni yangilash
    try:
        await call.message.edit_text(
            f"{call.message.text}\n\n❌ <b>RAD ETILDI!</b>\nRad etdi: <b>{admin_name}</b>",
            reply_markup=None
        )
    except Exception:
        pass

    # Boshqa BARCHA adminlarga xabar yuborish (tugmalarsiz)
    done_text = (
        f"❌ <b>ARIZA HAL QILINDI</b>\n\n"
        f"👤 <b>{uname}</b> foydalanuvchisining arizasi\n"
        f"<b>{admin_name}</b> tomonidan rad etildi.\n\n"
        f"<i>Siz hech narsa qilishingiz shart emas.</i>"
    )
    for adm_id in get_all_admin_ids():
        if adm_id == call.from_user.id:
            continue
        try:
            await bot.send_message(chat_id=adm_id, text=done_text)
        except Exception:
            pass

    # Foydalanuvchiga xabar
    try:
        await bot.send_message(
            chat_id=uid,
            text="❌ <b>Kechirasiz, sizning botdan foydalanish arizangiz rad etildi.</b>\n\nMurojaat uchun: @eshmbetov"
        )
    except Exception:
        pass
    await call.answer("❌ Ariza rad etildi!", show_alert=True)


@router.callback_query(F.data.startswith("user_req_access_"))
async def user_req_access_cb(call: CallbackQuery):
    """O'quvchi tomonidan ruxsat so'rash tugmasi bosilganda - avtomatik darhol ruxsat berish"""
    uid = int(call.data.split("_")[3])
    test_db.approve_user(uid)
    try:
        await call.message.edit_text(
            "🎉 <b>Xush kelibsiz! Botdan to'liq foydalanishingiz mumkin.</b>\n\n"
            "Kerakli bo'limni tanlang yoki to'g'ridan-to'g'ri test kodini yuboring 👇",
            reply_markup=None
        )
    except Exception:
        pass
    try:
        await call.message.answer(
            "Asosiy menyu:",
            reply_markup=main_menu_kb(uid)
        )
    except Exception:
        pass
    await call.answer("✅ Sizga to'liq ruxsat berildi!", show_alert=True)

@router.callback_query(F.data.startswith("ask_pdf_"))
async def ask_pdf_cb(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[2])
    await state.update_data(test_id=test_id)
    await state.set_state(UploadPostPdfState.pdf_file)
    await call.message.edit_text(
        f"{call.message.text}\n\n✅ <i>Siz PDF yuklashni tanladingiz.</i>\n\n"
        f"📥 <b>Iltimos, test uchun PDF faylni yuboring:</b>",
        reply_markup=None
    )

@router.callback_query(F.data.startswith("no_pdf_"))
async def no_pdf_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    await call.message.edit_text(
        f"{call.message.text}\n\n❌ <i>PDF fayl yuklanmadi. Test asosiysiz qabul qilindi.</i>",
        reply_markup=None
    )

@router.message(UploadPostPdfState.pdf_file, F.document)
async def process_post_create_pdf(message: Message, state: FSMContext):
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        await message.answer("Sizda ushbu amalni bajarish uchun admin ruxsati yo'q.")
        await state.clear()
        return

    data = await state.get_data()
    test_id = data.get("test_id")
    if not test_id:
        await message.answer("Xatolik! Test topilmadi.")
        await state.clear()
        return

    pdf_file_id = message.document.file_id
    pdf_file_name = message.document.file_name

    test_db.update_test_pdf(test_id, pdf_file_id, pdf_file_name)
    await message.answer(f"✅ <b>PDF fayl muvaffaqiyatli biriktirildi!</b>\n📄 Fayl: {pdf_file_name}")
    await state.clear()

# 3. Foydalanuvchilar boshqaruvi to'liq Asosiy Web Ilovaga (Main App) ko'chirildi
@router.callback_query(F.data.in_(["admin_view_users", "admin_webapp_redirect_info"]))
async def admin_view_users_redirect_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    text = (
        "🌐 <b>Foydalanuvchilar boshqaruvi Asosiy Web Ilovaga (Main App) ko'chirildi!</b>\n\n"
        "Foydalanuvchilar bilan bog'liq barcha amallar (ko'rish, qidirish, ruxsat berish, cheklash, bloklash, o'chirish va barchani cheklash) "
        "endi <b>Asosiy ilovaning «Admin»</b> bo'limida amalga oshiriladi.\n\n"
        "Quyidagi tugma orqali ilovani ochishingiz mumkin 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [make_webapp_button("🚀 Foydalanuvchilarni boshqarish (Web App)", f"{WEBAPP_URL}/app.html?tab=admin&tg_id={ADMIN_ID}")],
        [InlineKeyboardButton(text="🔙 Admin Menyuga qaytish", callback_data="admin_back_to_menu")]
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("adm_user_card_") | F.data.startswith("adm_act_") | F.data.startswith("admin_restrict_all_"))
async def adm_legacy_users_redirect_cb(call: CallbackQuery):
    await call.answer("Foydalanuvchilar boshqaruvi Web Appga ko'chirilgan!", show_alert=True)

# 4. Adminlar boshqaruvi
@router.callback_query(F.data == "admin_manage_admins")
async def admin_manage_admins_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    admins = test_db.get_all_admins()
    text = "👑 <b>Adminlar ro'yxati:</b>\n\n"
    for idx, a in enumerate(admins, 1):
        is_super = " (Bosh Admin)" if a["tg_id"] == ADMIN_ID else ""
        text += f"<b>{idx}. {a.get('fullname', 'Admin')}</b> — <code>{a['tg_id']}</code>{is_super}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="admin_add_new_prompt")],
        [InlineKeyboardButton(text="🔙 Admin Menyuga qaytish", callback_data="admin_back_to_menu")]
    ])

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.in_(["admin_back_to_menu", "admin_panel_back"]))
async def admin_back_to_menu_cb(call: CallbackQuery, state: FSMContext = None):
    if state:
        await state.clear()
    text = (
        "⚙️ <b>ADMIN BOSHQARUV PANELI</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang 👇"
    )
    try:
        await call.message.edit_text(text, reply_markup=admin_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=admin_menu_kb())
    await call.answer()

@router.callback_query(F.data == "admin_add_new_prompt")
async def admin_add_new_prompt_cb(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Faqat Bosh Admin yangi admin tayinlashi mumkin!", show_alert=True)
        return

    await state.set_state(AddAdminState.tg_id_or_user)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_manage_admins")]
    ])
    text = (
        "👑 <b>Yangi admin qo'shish:</b>\n\n"
        "Admin qilmoqchi bo'lgan foydalanuvchining <b>Telegram ID</b> raqamini kiriting:\n"
        "<i>(Masalan: 123456789)</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=cancel_kb)
    except Exception:
        await call.message.answer(text, reply_markup=cancel_kb)
    await call.answer()

@router.message(AddAdminState.tg_id_or_user)
async def admin_save_new_admin(message: Message, state: FSMContext):
    try:
        new_tg_id = int(message.text.strip())
        user_info = test_db.get_user(new_tg_id)
        fullname = user_info["fullname"] if user_info else "Admin"
        username = user_info["username"] if user_info else ""

        test_db.add_admin(new_tg_id, fullname, username, added_by=message.from_user.id)
        await state.clear()
        await message.answer(
            f"✅ <b>Yangi admin tayinlandi!</b>\n\n"
            f"👤 <b>Ism:</b> {fullname}\n"
            f"🆔 <b>Telegram ID:</b> <code>{new_tg_id}</code>\n\n"
            f"Endi ushbu foydalanuvchi ham Admin Panelga kira oladi.",
            reply_markup=admin_menu_kb()
        )
    except ValueError:
        await message.answer("⚠️ Iltimos, to'g'ri Telegram ID (raqam) kiriting:")

# ── TEXNIK PROFILAKTIKA VA BROADCAST (XABAR YUBORISH) BOSHQARUVI ──

MAINT_START_TEXT = (
    "⚠️ <b>DIQQAT: REJALI TEXNIK PROFILAKTIKA BOSHLANDI!</b>\n\n"
    "Hurmatli o'quvchilar va foydalanuvchilar!\n"
    "Hozirda bot tizimida rejali texnik profilaktika, yangilash va optimallashtirish ishlari olib borilmoqda.\n\n"
    "⏱ <b>Holat:</b> Bot vaqtincha to'xtatildi\n"
    "👨‍💻 <b>Maqsad:</b> Tizim barqarorligi va yangi imkoniyatlarni ishga tushirish\n\n"
    "✅ <i>Texnik jarayon yakunlangach, bot yana avtomatik tarzda to'liq ishga tushadi va bu haqda qo'shimcha xabar beriladi.</i>\n\n"
    "🙏 <b>Keltirilgan vaqtinchalik noqulayliklar uchun uzr so'raymiz!</b>"
)

MAINT_END_TEXT = (
    "✅ <b>XUSHXABAR: TEXNIK ISHLAR YAKUNLANDI!</b>\n\n"
    "Hurmatli o'quvchilar va foydalanuvchilar!\n"
    "Botdagi barcha texnik profilaktika va yangilash ishlari muvaffaqiyatli yakunlandi.\n\n"
    "🎉 <b>Tizim to'liq ishchi holatda!</b>\n"
    "Endi bemalol test topshirishingiz, natijalaringizni ko'rishingiz va botdan foydalanishingiz mumkin.\n\n"
    "🌟 <i>Barchangizga bilim olishda va testlarda ulkan zafarlar tilaymiz!</i>"
)

import uuid

async def send_broadcast_to_users(
    message_text: str = "",
    photo_id: str = "",
    caption: str = "",
    sender_tg_id: int = 0,
    messages_list: Optional[List[Dict[str, Any]]] = None
) -> tuple[int, int, str]:
    """Barcha faol (bloklanmagan) o'quvchilarga xabar tarqatish va keyinchalik o'chirish uchun ID larni saqlash."""
    users = test_db.get_broadcast_users()
    sent_count = 0
    fail_count = 0
    blocked_users = []  # Botni bloklagan foydalanuvchilar

    batch_id = f"BC-{datetime.now(UZB_TZ).strftime('%y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

    batch_summary = ""
    if messages_list:
        batch_summary = " | ".join([m.get("desc", "Xabar") for m in messages_list])[:1000]
    else:
        batch_summary = caption or message_text

    test_db.create_broadcast_batch(
        batch_id=batch_id,
        sender_tg_id=sender_tg_id or ADMIN_ID,
        message_text=batch_summary,
        photo_id=photo_id
    )

    for u in users:
        uid = u.get("tg_id")
        if not uid:
            continue
        try:
            user_sent_any = False
            if messages_list:
                for m in messages_list:
                    sent_msg = await bot.copy_message(
                        chat_id=uid,
                        from_chat_id=m["chat_id"],
                        message_id=m["message_id"]
                    )
                    if sent_msg and hasattr(sent_msg, "message_id"):
                        test_db.record_broadcast_message(batch_id, uid, sent_msg.message_id)
                        user_sent_any = True
                    await asyncio.sleep(0.02)
            elif photo_id:
                sent_msg = await bot.send_photo(chat_id=uid, photo=photo_id, caption=caption or message_text)
                if sent_msg and hasattr(sent_msg, "message_id"):
                    test_db.record_broadcast_message(batch_id, uid, sent_msg.message_id)
                    user_sent_any = True
            else:
                sent_msg = await bot.send_message(chat_id=uid, text=message_text)
                if sent_msg and hasattr(sent_msg, "message_id"):
                    test_db.record_broadcast_message(batch_id, uid, sent_msg.message_id)
                    user_sent_any = True

            if user_sent_any:
                sent_count += 1
            await asyncio.sleep(0.04)
        except Exception as e:
            fail_count += 1
            err_str = str(e).lower()
            if "blocked" in err_str or "forbidden" in err_str or "deactivated" in err_str:
                test_db.delete_user(uid)
                blocked_users.append(u)
            log.warning(f"Broadcast xatosi user {uid}: {e}")

    test_db.update_broadcast_sent_count(batch_id, sent_count)

    # Admin ga bloklagan userlar haqida xabar
    if blocked_users:
        blocked_text = "🚫 <b>Botni bloklagani uchun bazadan o'chirilgan foydalanuvchilar:</b>\n\n"
        for bu in blocked_users:
            bname = bu.get('fullname', 'Noma\'lum')
            btid = bu.get('tg_id', '-')
            blocked_text += f"• <b>{bname}</b> (ID: <code>{btid}</code>)\n"
        blocked_text += "\n<i>Ular botni to'xtatgani/bloklagani sababli bazadan to'liq o'chirildi.</i>"
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=blocked_text)
        except Exception:
            pass

    return sent_count, fail_count, batch_id


async def delete_broadcast_batch_from_users(batch_id: str, progress_callback=None) -> tuple[int, int]:
    """Berilgan batch_id bo'yicha barcha yuborilgan xabarlarni o'quvchilar chatidan tezkor parallel o'chirib tashlash."""
    msgs = test_db.get_broadcast_messages(batch_id)
    if not msgs:
        test_db.mark_broadcast_deleted(batch_id)
        return 0, 0

    sem = asyncio.Semaphore(12)  # Bir vaqtning o'zida 12 ta parallel so'rov
    deleted_count = [0]
    fail_count = [0]
    total = len(msgs)
    processed = [0]

    async def _del_one(m):
        chat_id = m.get("chat_id")
        msg_id = m.get("message_id")
        if not chat_id or not msg_id:
            return
        async with sem:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                deleted_count[0] += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(min(e.retry_after, 1.5))
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    deleted_count[0] += 1
                except Exception:
                    fail_count[0] += 1
            except Exception:
                fail_count[0] += 1
            finally:
                processed[0] += 1
                if progress_callback:
                    try:
                        await progress_callback(processed[0], total, deleted_count[0])
                    except Exception:
                        pass

    await asyncio.gather(*[_del_one(m) for m in msgs], return_exceptions=True)
    test_db.mark_broadcast_deleted(batch_id)
    return deleted_count[0], fail_count[0]


async def delete_recent_bot_messages_from_all_users(count: int = 1, progress_callback=None) -> tuple[int, int]:
    """
    Barcha o'quvchilar chatidagi so'nggi bot xabarlarini tezkor o'chirish (hatto oldingilarini ham).
    1. Avval bazadagi faol o'chirilmagan broadcast partiyalaridan xabarlarni parallel o'chiradi.
    2. Bazada saqlanmagan xabarlar uchun faol foydalanuvchilar chatidagi so'nggi 3 ta ID ni parallel tekshiradi.
    """
    deleted_total = 0

    # 1. Agar bazada o'chirilmagan broadcast partiyalar bo'lsa, ularni to'g'ridan-to'g'ri o'chiramiz
    recent_batches = test_db.get_recent_broadcasts(limit=max(5, count * 2))
    active_batches = [b for b in recent_batches if b.get('is_deleted') != 1]
    if active_batches:
        for b in active_batches[:count]:
            d_cnt, _ = await delete_broadcast_batch_from_users(b['batch_id'], progress_callback=progress_callback)
            deleted_total += d_cnt
        if deleted_total > 0:
            return deleted_total, len(test_db.get_broadcast_users())

    # 2. Agar bazada partiya topilmasa, chatdagi so'nggi bot xabarlarini tezkor parallel tozalash:
    users = test_db.get_broadcast_users()
    if not users:
        return 0, 0

    sem = asyncio.Semaphore(5)  # Telegram API flood limitiga tushmaslik uchun 5 ta parallel worker
    total_users = len(users)
    processed_count = [0]
    deleted_count = [0]

    async def _clean_one_user(u):
        uid = u.get("tg_id")
        if not uid:
            return
        async with sem:
            try:
                # O'quvchini bezovta qilmaslik uchun bildirishnomasiz jim (silent) probe
                probe = await bot.send_message(chat_id=uid, text=".", disable_notification=True)
                top_id = probe.message_id
                try:
                    await bot.delete_message(chat_id=uid, message_id=top_id)
                except Exception:
                    pass

                # Faqat so'nggi 3 ta ID ni tekshiramiz (ortiqcha yuzlab so'rov yubormaslik uchun)
                u_del = 0
                for mid in range(top_id - 1, max(1, top_id - 4), -1):
                    try:
                        await bot.delete_message(chat_id=uid, message_id=mid)
                        u_del += 1
                        deleted_count[0] += 1
                        if u_del >= count:
                            break
                        await asyncio.sleep(0.04)
                    except TelegramRetryAfter as e:
                        await asyncio.sleep(min(e.retry_after, 1.5))
                        break
                    except Exception:
                        continue
            except TelegramForbiddenError:
                pass
            except TelegramRetryAfter as e:
                await asyncio.sleep(min(e.retry_after, 1.5))
            except Exception as e:
                log.debug(f"User clean exception {uid}: {e}")
            finally:
                processed_count[0] += 1
                if progress_callback:
                    try:
                        await progress_callback(processed_count[0], total_users, deleted_count[0])
                    except Exception:
                        pass

    await asyncio.gather(*[_clean_one_user(u) for u in users], return_exceptions=True)
    return deleted_count[0], processed_count[0]

# 1. Texnik rejimni yoqish / o'chirish so'rovi
@router.callback_query(F.data == "admin_toggle_maint_prompt")
async def admin_toggle_maint_prompt_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("⛔️ Faqat Bosh Admin texnik profilaktika rejimini boshqarishi mumkin!", show_alert=True)
        return

    is_maint = test_db.is_maintenance_mode()
    if not is_maint:
        text = (
            "🛠 <b>TEXNIK PROFILAKTIKA REJIMINI YOQISH</b>\n\n"
            "⚠️ <b>Eslatma:</b>\n"
            "• Ushbu rejim yoqilganda sizdan (Bosh Admin) tashqari <b>hech kim</b> — "
            "na oddiy o'quvchilar va na tayinlangan adminlar botdan foydalana olmaydi.\n"
            "• Botga yozgan har qanday foydalanuvchiga: <i>«Hozirda botda texnik profilaktika ketmoqda...»</i> xabari chiqadi.\n\n"
            "Quyidagi amallardan birini tanlang 👇"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Yoqish va o'quvchilarga ogohlantirish yuborish", callback_data="adm_maint_set_on_notify")],
            [InlineKeyboardButton(text="🤫 Faqat Yoqish (xabarsiz)", callback_data="adm_maint_set_on_silent")],
            [InlineKeyboardButton(text="⬅️ Bekor qilish / Orqaga", callback_data="admin_back_to_menu")]
        ])
    else:
        text = (
            "✅ <b>TEXNIK PROFILAKTIKA REJIMINI O'CHIRISH</b>\n\n"
            "Tizim yana barcha o'quvchilar va adminlar uchun to'liq ochiladi va odatdagidek ishlay boshlaydi.\n\n"
            "Quyidagi amallardan birini tanlang 👇"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 O'chirish va barchaga xushxabar berish", callback_data="adm_maint_set_off_notify")],
            [InlineKeyboardButton(text="🤫 Faqat O'chirish (xabarsiz)", callback_data="adm_maint_set_off_silent")],
            [InlineKeyboardButton(text="⬅️ Bekor qilish / Orqaga", callback_data="admin_back_to_menu")]
        ])

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.in_(["adm_maint_set_on_silent", "adm_maint_set_on_notify"]))
async def adm_maint_set_on_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Faqat Bosh Admin!", show_alert=True)
        return
    test_db.set_maintenance_mode(True)
    if call.data == "adm_maint_set_on_notify":
        await call.answer("⏳ Xabar tarqatilmoqda...")
        status_msg = await call.message.answer("⏳ O'quvchilarga texnik profilaktika boshlanganligi haqida xabar yuborilmoqda...")
        sent, fail, batch_id = await send_broadcast_to_users(message_text=MAINT_START_TEXT)
        await status_msg.edit_text(
            f"🛠 <b>Texnik rejim YOQILDI va xabar tarqatildi!</b>\n\n"
            f"📨 <b>Yetkazildi:</b> {sent} ta\n"
            f"⚠️ <b>Yetkazilmadi:</b> {fail} ta\n\n"
            f"<i>Endi botdan faqat siz (Bosh Admin) foydalana olasiz.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑 Ushbu xabarni barchadan o'chirish", callback_data=f"adm_bc_del_{batch_id}")],
                [InlineKeyboardButton(text="⚙️ Admin panelga", callback_data="admin_back_to_menu")]
            ])
        )
    else:
        await call.answer("🛠 Texnik rejim yoqildi (xabarsiz)!", show_alert=True)
        await call.message.edit_text(
            "⚙️ <b>ADMIN BOSHQARUV PANELI</b>\n\n"
            "🔴 <b>Texnik profilaktika rejimi YOQILGAN.</b> Faqat siz (Bosh Admin) foydalana olasiz.\n\n"
            "Quyidagi bo'limlardan birini tanlang 👇",
            reply_markup=admin_menu_kb()
        )

@router.callback_query(F.data.in_(["adm_maint_set_off_silent", "adm_maint_set_off_notify"]))
async def adm_maint_set_off_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Faqat Bosh Admin!", show_alert=True)
        return
    test_db.set_maintenance_mode(False)
    if call.data == "adm_maint_set_off_notify":
        await call.answer("⏳ Xabar tarqatilmoqda...")
        status_msg = await call.message.answer("⏳ O'quvchilarga texnik ishlar yakunlanganligi haqida xabar yuborilmoqda...")
        sent, fail, batch_id = await send_broadcast_to_users(message_text=MAINT_END_TEXT)
        await status_msg.edit_text(
            f"✅ <b>Texnik rejim O'CHIRILDI va xushxabar tarqatildi!</b>\n\n"
            f"📨 <b>Yetkazildi:</b> {sent} ta\n"
            f"⚠️ <b>Yetkazilmadi:</b> {fail} ta\n\n"
            f"<i>Bot barcha o'quvchilar va adminlar uchun yana to'liq faol.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑 Ushbu xabarni barchadan o'chirish", callback_data=f"adm_bc_del_{batch_id}")],
                [InlineKeyboardButton(text="⚙️ Admin panelga", callback_data="admin_back_to_menu")]
            ])
        )
    else:
        await call.answer("✅ Texnik rejim o'chirildi (xabarsiz)!", show_alert=True)
        await call.message.edit_text(
            "⚙️ <b>ADMIN BOSHQARUV PANELI</b>\n\n"
            "🟢 <b>Texnik profilaktika rejimi O'CHIRILGAN.</b> Bot barcha uchun ochiq.\n\n"
            "Quyidagi bo'limlardan birini tanlang 👇",
            reply_markup=admin_menu_kb()
        )

# 2. O'quvchilarga xabar yuborish menyusi
def get_broadcast_started_text() -> str:
    active_tests = test_db.get_active_tests()
    test_code = ""
    if active_tests:
        test_code = active_tests[0].get("test_code", "")
    if not test_code:
        all_tests = test_db.get_all_tests()
        if all_tests:
            test_code = all_tests[0].get("test_code", "")
    
    code_display = f"#{test_code}" if test_code and not str(test_code).startswith("#") else (str(test_code) or "#TEST_KODI")
    return (
        "🚀 <b>Test boshlandi! Barchaga omad tilaymiz.</b>\n"
        "Belgilangan vaqt ichida javoblarni topshirishni unutmang.\n\n"
        f"📌 <b>Test kodi:</b> <code>{code_display}</code>"
    )

def get_broadcast_ended_text() -> str:
    active_tests = test_db.get_active_tests()
    test_code = ""
    title = ""
    if active_tests:
        test_code = active_tests[0].get("test_code", "")
        title = active_tests[0].get("title", "")
    if not test_code:
        all_tests = test_db.get_all_tests()
        if all_tests:
            test_code = all_tests[0].get("test_code", "")
            title = all_tests[0].get("title", "")
    
    code_display = f"#{test_code}" if test_code and not str(test_code).startswith("#") else (str(test_code) or "#TEST_KODI")
    title_line = f"📖 <b>Test:</b> {title}\n" if title else ""
    return (
        "🛑 <b>Test yakunlandi!</b>\n\n"
        "Javoblarni qabul qilish to'xtatildi. Ishtirok etgan barcha o'quvchilarga minnatdorchilik bildiramiz.\n\n"
        f"{title_line}"
        f"📌 <b>Test kodi:</b> <code>{code_display}</code>\n\n"
        "📊 <i>Tez orada to'liq tahlil va rasmiy natijalar e'lon qilinadi. Mini ilovaga kirib yangiliklarni kuzatib boring!</i>"
    )

BROADCAST_TEMPLATES = {
    "30m": {
        "title": "⏳ 30 daqiqa qoldi",
        "text": "⏳ <b>Diqqat! Test boshlanishiga 30 daqiqa qoldi!</b>\n\nInternet aloqangizni tekshirib, qoralama qog'ozlarni tayyorlab oling."
    },
    "10m": {
        "title": "⚠️ 10 daqiqa qoldi",
        "text": "⚠️ <b>Test boshlanishiga 10 daqiqa qoldi!</b>\n\nMini ilovaga kirib, tayyor bo'lib turing."
    },
    "started": {
        "title": "🚀 Test boshlandi",
        "get_text": get_broadcast_started_text
    },
    "15m": {
        "title": "⏰ 15 daqiqa qoldi",
        "text": "⏰ <b>Diqqat, test yakunlanishiga 15 daqiqa qoldi!</b>\n\nQolgan javoblarni tekshirib, topshirishga shoshiling."
    },
    "ended": {
        "title": "🛑 Test yakunlandi",
        "get_text": get_broadcast_ended_text
    }
}

@router.callback_query(F.data == "admin_broadcast_menu")
async def admin_broadcast_menu_cb(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        await call.answer("Siz admin emassiz!", show_alert=True)
        return
    await state.clear()
    users_count = len(test_db.get_broadcast_users())
    text = (
        f"📢 <b>O'QUVCHILARGA XABAR YUBORISH BO'LIMI</b>\n\n"
        f"👥 <b>Qabul qiluvchilar:</b> {users_count} nafar faol foydalanuvchi\n\n"
        f"Quyidagi tezkor tayyor shablonlardan birini tanlashingiz yoki o'zingiz erkin xabar yozishingiz mumkin:\n\n"
        f"⏳ <b>30 daqiqa qoldi:</b> Test boshlanishiga 30 daqiqa ogohlantirishi\n"
        f"⚠️ <b>10 daqiqa qoldi:</b> Test boshlanishiga 10 daqiqa ogohlantirishi\n"
        f"🚀 <b>Test boshlandi:</b> Test kodi bilan boshlanganlik xabari\n"
        f"⏰ <b>15 daqiqa qoldi:</b> Test yakunlanishiga 15 daqiqa ogohlantirishi\n"
        f"🛑 <b>Test yakunlandi:</b> Test yakunlanganlik xabari\n\n"
        f"🛠 <b>Texnik profilaktika:</b> Tizim ta'mirlash xabarlari\n"
        f"✍️ <b>Erkin xabar:</b> O'zingiz matn yoki rasm yuborishingiz mumkin"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏳ 30 daqiqa qoldi", callback_data="adm_bc_tmpl_30m"),
            InlineKeyboardButton(text="⚠️ 10 daqiqa qoldi", callback_data="adm_bc_tmpl_10m")
        ],
        [
            InlineKeyboardButton(text="🚀 Test boshlandi", callback_data="adm_bc_tmpl_started"),
            InlineKeyboardButton(text="⏰ 15 daqiqa qoldi", callback_data="adm_bc_tmpl_15m")
        ],
        [
            InlineKeyboardButton(text="🛑 Test yakunlandi", callback_data="adm_bc_tmpl_ended")
        ],
        [
            InlineKeyboardButton(text="🛠 1. Texnik ishlar boshlandi", callback_data="adm_bc_preview_start"),
            InlineKeyboardButton(text="✅ 2. Texnik ishlar yakunlandi", callback_data="adm_bc_preview_end")
        ],
        [InlineKeyboardButton(text="✍️ 3. O'zingiz erkin xabar yozish", callback_data="adm_bc_custom_input")],
        [InlineKeyboardButton(text="🗑 4. Yuborilgan xabarlarni o'chirish (Tarix)", callback_data="adm_bc_history_menu")],
        [InlineKeyboardButton(text="🧹 5. Oldingi xabarlarni barchadan tozalash", callback_data="adm_bc_clean_past_prompt")],
        [InlineKeyboardButton(text="⬅️ Admin panelga qaytish", callback_data="admin_back_to_menu")]
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("adm_bc_tmpl_"))
async def adm_bc_tmpl_preview_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    tmpl_key = call.data.replace("adm_bc_tmpl_", "")
    tmpl = BROADCAST_TEMPLATES.get(tmpl_key)
    if not tmpl:
        await call.answer("Shablon topilmadi!", show_alert=True)
        return

    text_to_send = tmpl["get_text"]() if "get_text" in tmpl else tmpl["text"]

    preview_text = (
        f"📋 <b>XABAR KO'RINISHI (PREVIEW):</b>\n\n"
        f"────────────────────\n"
        f"{text_to_send}\n"
        f"────────────────────\n\n"
        f"<b>Ushbu tayyor shablon xabarini barcha o'quvchilarga yuborishni tasdiqlaysizmi?</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Barchaga yuborish", callback_data=f"adm_bc_send_tmpl_{tmpl_key}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_broadcast_menu")]
    ])
    await call.message.edit_text(preview_text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("adm_bc_send_tmpl_"))
async def adm_bc_send_tmpl_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    tmpl_key = call.data.replace("adm_bc_send_tmpl_", "")
    tmpl = BROADCAST_TEMPLATES.get(tmpl_key)
    if not tmpl:
        await call.answer("Shablon topilmadi!", show_alert=True)
        return

    text_to_send = tmpl["get_text"]() if "get_text" in tmpl else tmpl["text"]

    await call.answer("⏳ Xabar tarqatilmoqda...")
    status_msg = await call.message.answer("⏳ Barcha o'quvchilarga tayyor shablon xabari yuborilmoqda...")
    sent, fail, batch_id = await send_broadcast_to_users(message_text=text_to_send, sender_tg_id=call.from_user.id)
    await status_msg.edit_text(
        f"✅ <b>Xabar muvaffaqiyatli tarqatildi!</b>\n\n"
        f"📨 <b>Yetkazildi:</b> {sent} nafar o'quvchiga\n"
        f"⚠️ <b>Yetkazilmadi (bloklangan):</b> {fail} ta\n\n"
        f"<i>Agar xabarni o'chirmoqchi bo'lsangiz, pastdagi tugmani bosing:</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Ushbu xabarni barchadan o'chirish", callback_data=f"adm_bc_del_{batch_id}")],
            [InlineKeyboardButton(text="⬅️ Xabar yuborish bo'limiga", callback_data="admin_broadcast_menu")],
            [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
        ])
    )


@router.callback_query(F.data == "adm_bc_preview_start")
async def adm_bc_preview_start_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    text = (
        f"📋 <b>XABAR KO'RINISHI (PREVIEW):</b>\n\n"
        f"────────────────────\n"
        f"{MAINT_START_TEXT}\n"
        f"────────────────────\n\n"
        f"<b>Ushbu xabarni barcha o'quvchilarga yuborishni tasdiqlaysizmi?</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Barchaga yuborish", callback_data="adm_bc_send_start")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_broadcast_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "adm_bc_preview_end")
async def adm_bc_preview_end_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    text = (
        f"📋 <b>XABAR KO'RINISHI (PREVIEW):</b>\n\n"
        f"────────────────────\n"
        f"{MAINT_END_TEXT}\n"
        f"────────────────────\n\n"
        f"<b>Ushbu xabarni barcha o'quvchilarga yuborishni tasdiqlaysizmi?</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Barchaga yuborish", callback_data="adm_bc_send_end")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_broadcast_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "adm_bc_send_start")
async def adm_bc_send_start_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    await call.answer("⏳ Xabar tarqatilmoqda...")
    status_msg = await call.message.answer("⏳ Barcha o'quvchilarga xabar yuborilmoqda...")
    sent, fail, batch_id = await send_broadcast_to_users(message_text=MAINT_START_TEXT, sender_tg_id=call.from_user.id)
    await status_msg.edit_text(
        f"✅ <b>Xabar muvaffaqiyatli tarqatildi!</b>\n\n"
        f"📨 <b>Yetkazildi:</b> {sent} nafar o'quvchiga\n"
        f"⚠️ <b>Yetkazilmadi (bloklangan):</b> {fail} ta\n\n"
        f"<i>Agar xabarni o'chirmoqchi bo'lsangiz, pastdagi tugmani bosing:</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Ushbu xabarni barchadan o'chirish", callback_data=f"adm_bc_del_{batch_id}")],
            [InlineKeyboardButton(text="⬅️ Xabar yuborish bo'limiga", callback_data="admin_broadcast_menu")],
            [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
        ])
    )

@router.callback_query(F.data == "adm_bc_send_end")
async def adm_bc_send_end_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    await call.answer("⏳ Xabar tarqatilmoqda...")
    status_msg = await call.message.answer("⏳ Barcha o'quvchilarga xabar yuborilmoqda...")
    sent, fail, batch_id = await send_broadcast_to_users(message_text=MAINT_END_TEXT, sender_tg_id=call.from_user.id)
    await status_msg.edit_text(
        f"✅ <b>Xabar muvaffaqiyatli tarqatildi!</b>\n\n"
        f"📨 <b>Yetkazildi:</b> {sent} nafar o'quvchiga\n"
        f"⚠️ <b>Yetkazilmadi (bloklangan):</b> {fail} ta\n\n"
        f"<i>Agar xabarni o'chirmoqchi bo'lsangiz, pastdagi tugmani bosing:</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Ushbu xabarni barchadan o'chirish", callback_data=f"adm_bc_del_{batch_id}")],
            [InlineKeyboardButton(text="⬅️ Xabar yuborish bo'limiga", callback_data="admin_broadcast_menu")],
            [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
        ])
    )

def get_broadcast_item_summary(message: Message) -> str:
    if message.document:
        fname = message.document.file_name or "Hujjat"
        return f"📄 PDF/Fayl: {fname}"
    elif message.photo:
        cap = (message.caption or "").strip()
        cap_prev = f" ('{cap[:30]}...')" if cap else ""
        return f"🖼 Rasm{cap_prev}"
    elif message.video:
        cap = (message.caption or "").strip()
        cap_prev = f" ('{cap[:30]}...')" if cap else ""
        return f"🎬 Video{cap_prev}"
    elif message.sticker:
        emoji = message.sticker.emoji or "🎭"
        return f"🎭 Stiker ({emoji})"
    elif message.voice:
        return f"🎙 Ovozli xabar ({message.voice.duration}s)"
    elif message.audio:
        title = message.audio.title or "Audio fayl"
        return f"🎵 Audio: {title}"
    elif message.video_note:
        return f"📹 Dumaloq video ({message.video_note.duration}s)"
    elif message.animation:
        return "👾 GIF animatsiya"
    elif message.text:
        txt = message.text.strip().replace("\n", " ")
        if len(txt) > 40:
            txt = txt[:37] + "..."
        return f"📝 Matn: '{txt}'"
    else:
        return "📬 Telegram xabari"

@router.callback_query(F.data == "adm_bc_custom_input")
async def adm_bc_custom_input_cb(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    await state.clear()
    await state.set_state(BroadcastState.waiting_for_message)
    await state.update_data(messages_list=[])

    text = (
        "✍️ <b>O'QUVCHILARGA XABAR YUBORISH (HAMMA FORMATLAR)</b>\n\n"
        "Siz istalgan turdagi xabarlarni yuborishingiz mumkin:\n"
        "• 📄 <b>PDF yoki har qanday fayl / hujjat</b>\n"
        "• 🎭 <b>Stiker (Sticker) yoki 👾 GIF animatsiya</b>\n"
        "• 🖼 <b>Rasm / Foto (matnli yoki matnsiz)</b>\n"
        "• 🎬 <b>Video yoki 📹 Dumaloq video (video-note)</b>\n"
        "• 🎙 <b>Ovozli xabar (Voice) yoki 🎵 Audio</b>\n"
        "• 📝 <b>Oddiy yoki formatlangan matn</b>\n"
        "• 🔄 <b>Kanallardan to'g'ridan-to'g'ri forward xabarlar</b>\n\n"
        "💡 <b>Bittada bir nechta xabar yuborish:</b>\n"
        "Ketma-ket 1 ta yoki bir nechta xabarlarni botga yuboring (masalan: avval yo'riqnoma matni, keyin PDF fayl, keyin stiker). "
        "Barchasi to'plamga yig'iladi va bitta tugma bilan barcha o'quvchilarga ketma-ket yetkaziladi!\n\n"
        "<i>Xabarlaringizni yuboring (yoki bekor qilish uchun /cancel yozing):</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_broadcast_menu")]
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@router.message(BroadcastState.waiting_for_message)
async def adm_bc_receive_custom_msg(message: Message, state: FSMContext):
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Xabar yuborish bekor qilindi.", reply_markup=admin_menu_kb())
        return

    data = await state.get_data()
    messages_list = list(data.get("messages_list", []))

    summary = get_broadcast_item_summary(message)
    messages_list.append({
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "desc": summary
    })
    await state.update_data(messages_list=messages_list)

    count = len(messages_list)
    list_items = "\n".join([f"<b>{i+1}.</b> {m['desc']}" for i, m in enumerate(messages_list)])

    text = (
        f"📥 <b>{count}-xabar to'plamga qo'shildi!</b>\n\n"
        f"📋 <b>Hozirgi xabarlar ro'yxati:</b>\n"
        f"{list_items}\n\n"
        f"💡 <i>Yana xabar yuborishingiz mumkin (PDF, stiker, rasm, audio, matn...) yoki barchasini birdaniga o'quvchilarga tarqatish uchun quyidagi tugmani bosing:</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🚀 Barchaga yuborish ({count} ta xabar)", callback_data="adm_bc_custom_confirm")],
        [InlineKeyboardButton(text="🗑 Ro'yxatni tozalash", callback_data="adm_bc_custom_clear")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_broadcast_menu")]
    ])

    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data == "adm_bc_custom_clear", BroadcastState.waiting_for_message)
async def adm_bc_custom_clear_cb(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    await state.update_data(messages_list=[])
    text = (
        "🗑 <b>Barcha tayyorlangan xabarlar ro'yxati tozalandi.</b>\n\n"
        "Endi yangidan istalgan xabarlaringizni yuborishingiz mumkin (PDF, rasm, stiker, audio, matn...):"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_broadcast_menu")]
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer("Ro'yxat tozalandi!")

@router.callback_query(F.data == "adm_bc_custom_confirm")
async def adm_bc_custom_confirm_cb(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    data = await state.get_data()
    messages_list = data.get("messages_list", [])

    if not messages_list:
        await call.answer("Hech qanday xabar kiritilmagan! Avval xabar yuboring.", show_alert=True)
        return

    await state.clear()
    await call.answer("⏳ Xabarlar tarqatilmoqda...")

    count = len(messages_list)
    status_msg = await call.message.answer(f"⏳ Barcha o'quvchilarga <b>{count} ta xabar</b> yuborilmoqda, iltimos kuting...")

    sent, fail, batch_id = await send_broadcast_to_users(
        messages_list=messages_list,
        sender_tg_id=call.from_user.id
    )

    await status_msg.edit_text(
        f"✅ <b>{count} ta xabar muvaffaqiyatli tarqatildi!</b>\n\n"
        f"📨 <b>Yetkazildi:</b> {sent} nafar o'quvchiga\n"
        f"⚠️ <b>Yetkazilmadi (bloklangan):</b> {fail} ta\n\n"
        f"<i>Agar ushbu xabarlar to'plamini o'chirmoqchi bo'lsangiz, pastdagi tugmani bosing:</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Ushbu xabarlarni barchadan o'chirish", callback_data=f"adm_bc_del_{batch_id}")],
            [InlineKeyboardButton(text="⬅️ Xabar yuborish bo'limiga", callback_data="admin_broadcast_menu")],
            [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
        ])
    )


# ── YUBORILGAN XABARLARNI O'CHIRISH (RECALL & DEEP CLEAN) ──

@router.callback_query(F.data.startswith("adm_bc_del_"))
async def adm_bc_del_cb(call: CallbackQuery):
    """Aniq bir batch bo'yicha yuborilgan xabarlarni barcha o'quvchilar chatidan tezkor o'chirish."""
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        await call.answer("Siz admin emassiz!", show_alert=True)
        return
    batch_id = call.data.replace("adm_bc_del_", "").strip()
    await call.answer("⏳ O'chirish boshlandi...", show_alert=False)

    try:
        await call.message.edit_text(
            "⏳ <b>Xabarni o'chirish boshlandi...</b>\n\n"
            "O'quvchilar chatidan bir zumda tozalanmoqda...\n"
            "<i>Iltimos, kuting...</i>"
        )
    except Exception:
        pass

    last_update = [0.0]
    async def on_progress(done, total, del_cnt):
        now = time.time()
        if now - last_update[0] >= 1.0:
            last_update[0] = now
            try:
                await call.message.edit_text(
                    f"⏳ <b>Xabar o'chirilmoqda...</b>\n\n"
                    f"📨 <b>Jarayon:</b> {done} / {total} o'quvchi ({del_cnt} ta o'chirildi)\n\n"
                    f"<i>Iltimos, kuting...</i>"
                )
            except Exception:
                pass

    try:
        deleted_count, fail_count = await asyncio.wait_for(
            delete_broadcast_batch_from_users(batch_id, progress_callback=on_progress),
            timeout=20.0
        )
    except asyncio.TimeoutError:
        log.warning(f"delete_broadcast_batch_from_users timeout for {batch_id}")
        deleted_count, fail_count = 0, 0

    result_text = (
        f"🗑 <b>XABAR O'CHIRILDI!</b>\n\n"
        f"✅ <b>O'chirildi:</b> {deleted_count} nafar o'quvchi chatidan\n"
        f"⚠️ <b>Yetib bormagan / allaqachon yo'q:</b> {fail_count} ta\n\n"
        f"<i>Ushbu xabar endi o'quvchilar ekranida ko'rinmaydi.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Xabar yuborish bo'limiga", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
    ])
    try:
        await call.message.edit_text(result_text, reply_markup=kb)
    except Exception:
        await call.message.answer(result_text, reply_markup=kb)


@router.callback_query(F.data == "adm_bc_history_menu")
async def adm_bc_history_menu_cb(call: CallbackQuery):
    """Yaqinda yuborilgan xabarlar ro'yxati va ularni o'chirish menyusi."""
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    recent = test_db.get_recent_broadcasts(8)
    if not recent:
        text = (
            "📭 <b>Yuborilgan xabarlar tarixi bo'sh.</b>\n\n"
            "Hozircha tizimda saqlangan xabarlar mavjud emas.\n"
            "Oldingi xabarlarni tozalash uchun quyidagi tugmadan foydalanishingiz mumkin:"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Oldingi xabarlarni barchadan tozalash", callback_data="adm_bc_clean_past_prompt")],
            [InlineKeyboardButton(text="⬅️ Xabar yuborish bo'limiga", callback_data="admin_broadcast_menu")]
        ])
        await call.message.edit_text(text, reply_markup=kb)
        return

    text = "🗑 <b>YUBORILGAN XABARLAR TARIXI VA O'CHIRISH</b>\n\n"
    text += "Kerakli xabar ostidagi <b>«🗑 O'chirish»</b> tugmasini bossangiz, u barcha o'quvchilar chatidan bir zumda o'chirib tashlanadi:\n\n"

    buttons = []
    for idx, b in enumerate(recent, 1):
        dt = format_uzb_time(b.get("created_at"), "%d.%m %H:%M")
        raw_msg = (b.get("message_text") or "Rasmli xabar").replace("<br>", " ").replace("\n", " ")
        snippet = (raw_msg[:35] + "...") if len(raw_msg) > 35 else raw_msg
        is_del = (b.get("is_deleted") == 1)

        status_icon = "🗑 O'chirilgan" if is_del else f"✅ {b.get('total_sent', 0)} ta o'quvchiga"
        text += f"{idx}. <b>[{dt}]</b> {snippet}\n   <i>Holat: {status_icon}</i>\n\n"

        if not is_del:
            buttons.append([InlineKeyboardButton(
                text=f"🗑 {idx}-xabarni barchadan o'chirish",
                callback_data=f"adm_bc_del_{b['batch_id']}"
            )])

    buttons.append([InlineKeyboardButton(text="🧹 Oldingi xabarlarni barchadan tozalash", callback_data="adm_bc_clean_past_prompt")])
    buttons.append([InlineKeyboardButton(text="⬅️ Xabar yuborish bo'limiga", callback_data="admin_broadcast_menu")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()


@router.callback_query(F.data == "adm_bc_clean_past_prompt")
async def adm_bc_clean_past_prompt_cb(call: CallbackQuery):
    """Oldingi xabarlarni barcha o'quvchilar chatidan tozalash taklifi."""
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    text = (
        "🧹 <b>OLDINGI XABARLARNI TOZALASH (DEEP CLEAN)</b>\n\n"
        "Ushbu funksiya tarixda saqlanmagan yoki avvalroq yuborilgan xabarlarni barcha o'quvchilar chatidan o'chirish uchun mo'ljallangan.\n\n"
        "Bot barcha o'quvchilar chatidagi so'nggi xabarlarni tezkor parallel tekshirib tozalab chiqadi.\n\n"
        "<b>Nechta so'nggi bot xabarini o'chirmoqchisiz?</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 1 ta so'nggi xabarni o'chirish", callback_data="adm_bc_clean_1"),
            InlineKeyboardButton(text="🗑 2 ta so'nggi xabarni o'chirish", callback_data="adm_bc_clean_2")
        ],
        [
            InlineKeyboardButton(text="🗑 3 ta so'nggi xabarni o'chirish", callback_data="adm_bc_clean_3"),
            InlineKeyboardButton(text="🗑 5 ta so'nggi xabarni o'chirish", callback_data="adm_bc_clean_5")
        ],
        [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="admin_broadcast_menu")]
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm_bc_clean_"))
async def adm_bc_clean_action_cb(call: CallbackQuery):
    """Barcha o'quvchilardan so'nggi N ta xabarni o'chirish amali."""
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    try:
        count = int(call.data.replace("adm_bc_clean_", "").strip())
    except Exception:
        count = 1

    await call.answer(f"⏳ So'nggi {count} ta xabarni tozalash boshlandi...", show_alert=False)

    try:
        await call.message.edit_text(
            f"⏳ <b>Tozalash boshlandi...</b>\n\n"
            f"O'quvchilar chatidagi so'nggi {count} ta bot xabari o'chirilmoqda...\n"
            f"<i>Iltimos, kuting...</i>"
        )
    except Exception:
        pass

    last_update = [0.0]
    async def on_progress(done_users, total_users, del_count):
        now = time.time()
        if now - last_update[0] >= 1.0:
            last_update[0] = now
            try:
                await call.message.edit_text(
                    f"⏳ <b>Tozalanmoqda...</b>\n\n"
                    f"👥 <b>Jarayon:</b> {done_users} / {total_users} o'quvchi\n"
                    f"🗑 <b>O'chirildi:</b> {del_count} ta xabar\n\n"
                    f"<i>Iltimos, kuting...</i>"
                )
            except Exception:
                pass

    try:
        deleted_total, checked_users = await asyncio.wait_for(
            delete_recent_bot_messages_from_all_users(count=count, progress_callback=on_progress),
            timeout=25.0
        )
    except asyncio.TimeoutError:
        log.warning("delete_recent_bot_messages_from_all_users timeout reached")
        deleted_total = 0
        checked_users = len(test_db.get_broadcast_users())

    res_text = (
        f"🧹 <b>TOZALASH MUVAFFAQIYATLI YAKUNLANDI!</b>\n\n"
        f"👥 <b>Tekshirilgan o'quvchilar:</b> {checked_users} nafar\n"
        f"🗑 <b>O'chirilgan jami bot xabarlari:</b> {deleted_total} ta\n\n"
        f"<i>O'quvchilar chatidagi so'nggi bot xabarlari tozalandi.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Xabar yuborish bo'limiga", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton(text="🔙 Admin panelga", callback_data="admin_back_to_menu")]
    ])
    try:
        await call.message.edit_text(res_text, reply_markup=kb)
    except Exception:
        await call.message.answer(res_text, reply_markup=kb)

# 5. Natijalar va hisobotlar boshqaruvi
@router.callback_query(F.data == "admin_leaderboard")
async def admin_leaderboard(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    tests = test_db.get_tests_with_stats()
    if not tests:
        text = "⚠️ Hozirda tizimda mavjud testlar yo'q."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Admin Panelga qaytish", callback_data="admin_panel_back")]
        ])
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            await call.message.answer(text, reply_markup=kb)
        await call.answer()
        return

    buttons = []
    msg_list = ""
    for idx, t in enumerate(tests, 1):
        sub_cnt = t.get("submissions_count", 0)
        btn_text = f"📊 #{t['test_code']} — 👥 {sub_cnt} kishi"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_tstat_{t['id']}")])
        msg_list += f"<b>{idx}. #{t['test_code']}</b> — {t['title']}: <b>{sub_cnt} kishi</b>\n"

    buttons.append([InlineKeyboardButton(text="⬅️ Admin Panelga qaytish", callback_data="admin_panel_back")])

    msg_text = (
        "📊 <b>Mavjud Testlar va Ishtirokchilar Soni:</b>\n\n"
        f"{msg_list}\n"
        "<i>Batafsil natijalarni (Matn yoki PDF shaklida) olish uchun kerakli test kodini tanlang 👇</i>"
    )

    try:
        await call.message.edit_text(msg_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await call.message.answer(msg_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@router.callback_query(F.data.startswith("adm_tstat_"))
async def admin_test_stats_detail(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    test_id = int(call.data.split("_")[2])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    results = test_db.get_test_results_leaderboard(test_id)
    count = len(results)
    avg_score = 0
    if count > 0:
        avg_score = round(sum(r['score'] for r in results) / count, 1)

    is_active = (test.get("is_active", 1) == 1)
    is_pub = test_db.is_test_results_published(test_id)

    status_badge = "🟢 Javoblar qabul qilinmoqda" if is_active else "🔴 Javoblar qabul qilish to'xtatilgan"
    pub_badge = "📢 Natijalar e'lon qilingan" if is_pub else "🔒 Yashirin (O'quvchilarga «Javoblar tekshirilmoqda» ko'rinadi)"

    # Jadval vaqt ma'lumoti
    sched_date = test.get('scheduled_date') or ''
    sched_start = test.get('scheduled_start') or ''
    sched_end = test.get('scheduled_end') or ''
    if sched_date and sched_start and sched_end:
        sched_badge = f"⏰ {sched_date} | {sched_start}–{sched_end} (UZB)"
    elif sched_start and sched_end:
        sched_badge = f"⏰ {sched_start}–{sched_end} (UZB, sana belgilanmagan)"
    else:
        sched_badge = "➖ Belgilanmagan"

    yt_url = (test.get('youtube_url') or '').strip()
    yt_badge = f'<a href="{yt_url}">Mavjud (Ko\'rish 🎬)</a>' if yt_url else "❌ Kiritilmagan"

    creator_str = test.get('created_by_name') or ('Bosh Admin' if test.get('created_by') == ADMIN_ID else 'Admin')
    text = (
        f"📊 <b>Test natijalari va tahlil bo'limi:</b>\n\n"
        f"📖 <b>Nomi:</b> {test['title']}\n"
        f"🔑 <b>Kodi:</b> <code>#{test['test_code']}</code>\n"
        f"👤 <b>Yaratuvchi:</b> {creator_str}\n"
        f"📌 <b>Fani:</b> {test.get('subject', 'Fizika')}\n"
        f"🚦 <b>Holati:</b> {status_badge}\n"
        f"📢 <b>Natijalar:</b> {pub_badge}\n"
        f"🎬 <b>Video tahlil:</b> {yt_badge}\n\n"
        f"👥 <b>Topshirganlar soni:</b> <b>{count} nafar</b>\n"
        f"📈 <b>O'rtacha ball:</b> <b>{avg_score} ball</b>\n\n"
        f"<i>Hisoblash, tahlil qilish va natijalarni e'lon qilish usulini tanlang 👇</i>"
    )

    edit_keys_url = f"{WEBAPP_URL}/admin.html?edit_test_id={test_id}"
    buttons = [
        [make_webapp_button("✏️ Kalitlarni tahrirlash (Mini App)", edit_keys_url)],
        [InlineKeyboardButton(text="🧮 Rasch modeli (JMLE) bo'yicha hisoblash", callback_data=f"adm_broadcast_rasch_{test_id}")],
        [InlineKeyboardButton(text="✅ Standart hisoblash (To'g'ri javoblar)", callback_data=f"adm_broadcast_std_{test_id}")],
    ]

    if not is_pub:
        buttons.append([InlineKeyboardButton(text="📢 Natijalarni e'lon qilish va yuborish", callback_data=f"adm_eval_prompt_{test_id}")])
    else:
        buttons.append([
            InlineKeyboardButton(text="🔄 Natijalarni qayta yuborish", callback_data=f"adm_eval_prompt_{test_id}"),
            InlineKeyboardButton(text="🔒 Natijalarni yashirish", callback_data=f"adm_hide_results_{test_id}")
        ])

    buttons.append([
        InlineKeyboardButton(text="📄 Matn shaklida reyting", callback_data=f"adm_restxt_{test_id}"),
        InlineKeyboardButton(text="📑 PDF hisobot", callback_data=f"adm_respdf_{test_id}")
    ])
    yt_btn_text = "🎬 Video tahlil ✅" if yt_url else "🎬 Video tahlil ➕"
    buttons.append([
        InlineKeyboardButton(text="🧮 Rasch tahlil", callback_data=f"adm_rasch_{test_id}"),
        InlineKeyboardButton(text="🔍 Shovqin & Savollar", callback_data=f"adm_item_diag_{test_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text=yt_btn_text, callback_data=f"adm_set_yt_{test_id}"),
        InlineKeyboardButton(text="⬅️ Testlar ro'yxati", callback_data="admin_leaderboard")
    ])

    try:
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    try:
        await call.answer()
    except Exception:
        pass

@router.callback_query(F.data.startswith("adm_set_yt_"))
async def adm_set_yt_cb(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    await state.clear()
    test_id = int(call.data.split("_")[3])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return
    yt_url = (test.get("youtube_url") or "").strip()
    status_text = f"🔗 <b>Joriy havola:</b> <code>{yt_url}</code>\n\n" if yt_url else "❌ <b>Hozircha havola kiritilmagan.</b>\n\n"
    text = (
        f"🎬 <b>YOUTUBE VIDEO TAHLIL SOZLAMALARI</b>\n\n"
        f"📖 <b>Test:</b> {test['title']} (<code>#{test['test_code']}</code>)\n"
        f"{status_text}"
        f"Quyidagi amallardan birini tanlang:"
    )
    buttons = [
        [InlineKeyboardButton(text="✍️ Havolani kiritish / Yangilash", callback_data=f"adm_input_yt_{test_id}")],
    ]
    if yt_url:
        buttons.append([InlineKeyboardButton(text="🗑 Havolani o'chirish", callback_data=f"adm_del_yt_{test_id}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Test boshqaruviga qaytish", callback_data=f"adm_tstat_{test_id}")])
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@router.callback_query(F.data.startswith("adm_input_yt_"))
async def adm_input_yt_cb(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    await state.update_data(yt_test_id=test_id)
    await state.set_state(SetYoutubeState.waiting_for_url)
    await call.message.answer(
        "🎬 <b>YouTube video tahlil havolasini (URL) yuboring:</b>\n\n"
        "<i>Masalan: https://youtu.be/... yoki https://www.youtube.com/watch?v=...</i>\n\n"
        "Bekor qilish uchun /cancel deb yozing."
    )
    await call.answer()

@router.message(SetYoutubeState.waiting_for_url)
async def adm_save_yt_msg(message: Message, state: FSMContext):
    if not test_db.is_admin(message.from_user.id, ADMIN_ID):
        return
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Havola kiritish bekor qilindi.")
        return
    data = await state.get_data()
    test_id = data.get("yt_test_id")
    url = (message.text or "").strip()
    if not ("youtube.com" in url or "youtu.be" in url or url.startswith("http")):
        await message.answer("⚠️ Iltimos, to'g'ri YouTube havolasini (URL) yuboring (masalan: https://youtu.be/...):")
        return
    test_db.set_test_youtube_url(test_id, url)
    await state.clear()
    test = test_db.get_test_by_id(test_id)
    title = test['title'] if test else f"#{test_id}"
    await message.answer(
        f"✅ <b>«{title}» testi uchun YouTube video tahlil havolasi muvaffaqiyatli saqlandi!</b>\n\n"
        f"🔗 Havola: {url}\n\n"
        f"<i>Natijalar e'lon qilinganda o'quvchilarga video tahlil tugmasi orqali ochiladi.</i>"
    )

@router.callback_query(F.data.startswith("adm_del_yt_"))
async def adm_del_yt_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    test_db.set_test_youtube_url(test_id, "")
    await call.answer("🗑 Video tahlil havolasi o'chirildi!", show_alert=True)
    call.data = f"adm_tstat_{test_id}"
    await admin_test_stats_detail(call)

# Testni o'chirishni tasdiqlash
@router.callback_query(F.data.startswith("adm_del_test_prompt_"))
async def adm_del_test_prompt_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[4])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return
    
    text = (
        f"⚠️ <b>DIQQAT! TESTNI O'CHIRISH</b>\n\n"
        f"📖 Nomi: <b>{test['title']}</b> (#{test['test_code']})\n\n"
        f"Ushbu testni va uning barcha o'quvchilar topshirgan natijalarini <b>butunlay o'chirib tashlamoqchimisiz?</b>\n"
        f"<i>Ushbu amalni ortga qaytarib bo'lmaydi!</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Ha, butunlay o'chirilsin!", callback_data=f"adm_del_test_exec_{test_id}")],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data=f"adm_tstat_{test_id}")]
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("adm_del_test_exec_"))
async def adm_del_test_exec_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[4])
    ok = test_db.delete_test(test_id)
    if ok:
        await call.answer("🗑 Test muvaffaqiyatli o'chirildi!", show_alert=True)
        call.data = "admin_leaderboard"
        await admin_leaderboard(call)
    else:
        await call.answer("O'chirishda xatolik yuz berdi!", show_alert=True)

# Javob qabul qilishni boshlash / to'xtatish
@router.callback_query(F.data.startswith("toggle_test_tstat_"))
async def admin_toggle_test_tstat_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    new_status = test_db.toggle_test_status(test_id)
    if new_status is not None:
        status_text = "🟢 Javoblar qabul qilinmoqda" if new_status == 1 else "🔴 Javoblar to'xtatildi"
        try:
            await call.answer(f"Test holati: {status_text}", show_alert=True)
        except Exception:
            pass
        call.data = f"adm_tstat_{test_id}"
        await admin_test_stats_detail(call)
    else:
        try:
            await call.answer("Xatolik yuz berdi!", show_alert=True)
        except Exception:
            pass

# Natijalarni qayta yashirish (o'quvchilarga yana "tekshirilmoqda" qilish)
@router.callback_query(F.data.startswith("adm_hide_results_"))
async def admin_hide_results_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    test_db.set_test_results_published(test_id, False)
    test_db.set_test_active_status(test_id, 1)
    await call.answer("🔒 Natijalar yashirildi va test faollashtirildi! Endi o'quvchilarga «Javoblar tekshirilmoqda» ko'rinadi.", show_alert=True)
    call.data = f"adm_tstat_{test_id}"
    await admin_test_stats_detail(call)

# Natijalarni e'lon qilishdan oldin SO'ROV: Rasch modeli bo'yicha yoki Standart
@router.callback_query(F.data.startswith("adm_eval_prompt_"))
@router.callback_query(F.data.startswith("adm_broadcast_results_"))
async def admin_eval_prompt_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    parts = call.data.split("_")
    test_id = int(parts[-1])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    text = (
        f"📋 <b>«{test['title']}»</b> (<code>#{test['test_code']}</code>)\n\n"
        f"🤔 <b>Natijalarni qaysi usulda tekshirib, o'quvchilarga e'lon qilmoqchisiz?</b>\n\n"
        f"1️⃣ <b>🧮 Rasch modeli (JMLE) bo'yicha:</b>\n"
        f"• Savollarning qiyinlik darajasi (b) va o'quvchilar qobiliyati (θ) hisoblanadi.\n"
        f"• Rasmiy Milliy Sertifikat darajalari (A+, A, B+, B, C+, C) beriladi.\n\n"
        f"2️⃣ <b>✅ Standart baholash (To'g'ri javoblar soni bo'yicha):</b>\n"
        f"• Har bir to'g'ri ishlangan savol soni va standart ball hisoblanadi.\n"
        f"• Oddiy va shaffof: nechta to'g'ri, noto'g'ri va to'plangan ball ko'rsatiladi.\n\n"
        f"<i>Quyidagi usullardan birini tanlang 👇</i>"
    )

    buttons = [
        [InlineKeyboardButton(text="🧮 1. Rasch modeli (JMLE) bo'yicha e'lon qilish", callback_data=f"adm_broadcast_rasch_{test_id}")],
        [InlineKeyboardButton(text="✅ 2. Standart (To'g'ri javoblar soni) bo'yicha", callback_data=f"adm_broadcast_std_{test_id}")],
        [InlineKeyboardButton(text="⬅️ Bekor qilish / Orqaga", callback_data=f"adm_tstat_{test_id}")]
    ]

    try:
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

def build_detailed_tahlil_text(sub: dict, test: dict) -> str:
    """O'quvchi uchun to'g'ri va noto'g'ri ishlangan savollar tahlili matni."""
    name = sub.get("fullname") or "O'quvchi"
    score = sub.get("score", 0.0)
    grade = sub.get("grade") or test_db.calculate_grade(score)
    corr = sub.get("correct_count", 0)
    total = sub.get("total_count", 55) or 55
    incorr = max(0, total - corr)
    code = sub.get("test_code", test.get("test_code", ""))
    test_title = test.get("title", "Fizika Testi")
    yt_url = (test.get("youtube_url") or "").strip()

    details = {}
    raw_details = sub.get("details_json")
    if isinstance(raw_details, dict):
        details = raw_details
    elif raw_details:
        try:
            details = json.loads(raw_details)
        except Exception:
            details = {}

    def sort_key(k):
        m = re.match(r"^(\d+)([ab]?)$", str(k).strip())
        if m:
            return (int(m.group(1)), m.group(2))
        return (999, str(k))

    correct_keys = []
    partial_keys = []
    incorrect_keys = []
    unanswered_keys = []
    for k in sorted(details.keys(), key=sort_key):
        item = details[k]
        st = item.get("status")
        if st == "correct":
            correct_keys.append(str(k))
        elif st == "partial":
            partial_keys.append(str(k))
        elif st == "unanswered":
            unanswered_keys.append(str(k))
        else:
            incorrect_keys.append(str(k))

    corr_str = ", ".join(correct_keys) if correct_keys else "Mavjud emas"
    partial_str = ", ".join(partial_keys) if partial_keys else ""
    incorr_str = ", ".join(incorrect_keys) if incorrect_keys else "Yo'q"

    text = (
        f"◈ <b>SAVOLLAR TAHLILI — «{test_title}»</b> (<code>#{code}</code>)\n\n"
        f"• <b>O'quvchi:</b> {name}\n"
        f"✦ <b>Milliy Sertifikat darajasi:</b> <b>{grade}</b> ({score} ball)\n"
        f"✓ <b>To'g'ri ishlangan:</b> {corr} / {total} ta band\n"
    )
    if partial_keys:
        text += f"› <b>Qisman to'g'ri (30% ball):</b> {len(partial_keys)} ta band\n"
    text += (
        f"✕ <b>Noto'g'ri / qoldirilgan:</b> {incorr} ta\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✓ <b>TO'G'RI ISHLANGAN SAVOLLAR ({len(correct_keys)} ta):</b>\n"
        f"<code>{corr_str}</code>\n"
    )
    if partial_keys:
        text += (
            f"\n› <b>QISMAN TO'G'RI (30% ball berilgan, oxirgacha hisoblanmagan) ({len(partial_keys)} ta):</b>\n"
            f"<code>{partial_str}</code>\n"
        )
    text += (
        f"\n✕ <b>NOTO'G'RI ISHLANGAN SAVOLLAR ({len(incorrect_keys)} ta):</b>\n"
        f"<code>{incorr_str}</code>"
    )
    if unanswered_keys:
        unans_str = ", ".join(unanswered_keys)
        text += f"\n\n▫️ <b>BELGILANMAGAN SAVOLLAR ({len(unanswered_keys)} ta):</b>\n<code>{unans_str}</code>"
    text += "\n━━━━━━━━━━━━━━━━━━━━"
    if yt_url:
        text += f"\n\n› <b>Video tahlil:</b> <a href=\"{yt_url}\">YouTube orqali ko'rish</a>"
    return text

def build_student_result_message(sub: dict, test: dict, eval_type: str = "rasch") -> tuple:
    """O'quvchi uchun natija matni va video tahlil / mini ilova tugmalarini shakllantirish."""
    name = sub.get("fullname") or "O'quvchi"
    score = sub.get("score", 0.0)
    grade = sub.get("grade") or test_db.calculate_grade(score)
    corr = sub.get("correct_count", 0)
    total = sub.get("total_count", 55) or 55
    incorr = max(0, total - corr)
    code = sub.get("test_code", test.get("test_code", ""))
    test_title = test.get("title", "Fizika Testi")
    yt_url = (test.get("youtube_url") or "").strip()

    if eval_type == "rasch":
        msg_text = (
            f"✦ <b>DIQQAT: TEST NATIJALARI E'LON QILINDI!</b>\n\n"
            f"Hurmatli <b>{name}</b>, sizning <b>«{test_title}»</b> (<code>#{code}</code>) testi bo'yicha rasmiy natijangiz:\n\n"
            f"• <b>Baholash tizimi:</b> Rasch Modeli (JMLE)\n"
            f"✦ <b>Milliy Sertifikat darajangiz:</b> <b>{grade}</b> ({score} ball)\n"
            f"✓ <b>To'g'ri ishlangan:</b> {corr} ta band\n"
            f"✕ <b>Noto'g'ri / belgilanmagan:</b> {incorr} ta\n"
            f"• <b>Jami savollar:</b> {total} ta\n"
            f"• <b>E'lon vaqti:</b> {format_uzb_time()}\n\n"
            f"ℹ <i>Qaysi savollaringiz to'g'ri yoki noto'g'ri ekanligini ko'rish uchun quyidagi <b>«◈ Test tahlili»</b> tugmasini bosing:</i>\n\n"
            f"✦ <i>Ishtirokingiz uchun tashakkur!</i>"
        )
    else:
        msg_text = (
            f"✦ <b>DIQQAT: TEST NATIJALARI E'LON QILINDI!</b>\n\n"
            f"Hurmatli <b>{name}</b>, sizning <b>«{test_title}»</b> (<code>#{code}</code>) testi bo'yicha rasmiy natijangiz:\n\n"
            f"• <b>Baholash turi:</b> Standart (To'g'ri javoblar soni)\n"
            f"✓ <b>To'g'ri javoblar:</b> {corr} / {total} ta\n"
            f"✕ <b>Noto'g'ri javoblar:</b> {incorr} ta\n"
            f"✦ <b>To'plangan ball:</b> {score} ball\n"
            f"• <b>E'lon vaqti:</b> {format_uzb_time()}\n\n"
            f"ℹ <i>Qaysi savollaringiz to'g'ri yoki noto'g'ri ekanligini ko'rish uchun quyidagi <b>«◈ Test tahlili»</b> tugmasini bosing:</i>\n\n"
            f"✦ <i>Ishtirokingiz uchun tashakkur!</i>"
        )

    kb_rows = [
        [InlineKeyboardButton(text="◈ Test tahlili", callback_data=f"user_req_tahlil_{test['id']}")]
    ]
    if yt_url:
        kb_rows.append([InlineKeyboardButton(text="› Video tahlilni ko'rish (YouTube)", url=yt_url)])
    else:
        kb_rows.append([InlineKeyboardButton(text="› Video tahlil (mavjud emas)", callback_data="no_video_analysis")])

    kb_rows.append([InlineKeyboardButton(text="✦ Mini ilovada to'liq ko'rish", web_app=WebAppInfo(url=f"{WEBAPP_URL}/app.html?tab=tests"))])

    return msg_text, InlineKeyboardMarkup(inline_keyboard=kb_rows)

@router.callback_query(F.data == "no_video_analysis")
async def no_video_analysis_cb(call: CallbackQuery):
    await call.answer("ℹ Ushbu test uchun video tahlil kiritilmagan.", show_alert=True)

# ── FOYDALANUVCHI TEST TAHLILI HANDLERLARI (KOD SO'RASH VA TAHLILNI MATN QILIB YUBORISH) ──
@router.callback_query(F.data.startswith("user_req_tahlil_"))
async def user_req_tahlil_cb(call: CallbackQuery, state: FSMContext):
    test_id = int(call.data.split("_")[3])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    sub = test_db.get_user_submission_for_test(test_id, call.from_user.id)
    if not sub:
        await call.answer("Siz ushbu testni topshirmagansiz!", show_alert=True)
        return

    await state.set_state(StudentTahlilState.waiting_for_code)
    await state.update_data(tahlil_test_id=test_id)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✕ Bekor qilish", callback_data="cancel_tahlil_code")]
    ])
    await call.message.answer(
        f"✦ <b>«{test['title']}» (<code>#{test.get('test_code', '')}</code>) testi tahlili</b>\n\n"
        f"Savollar tahlilini ko'rish uchun test kodini yoki admin tomonidan berilgan maxsus parolni kiriting:\n\n"
        f"<i>(Masalan: <code>{test.get('test_code', '101')}</code>)</i>",
        reply_markup=cancel_kb
    )
    await call.answer()

@router.callback_query(F.data == "cancel_tahlil_code")
async def cancel_tahlil_code_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text("✕ Tahlil kodini kiritish bekor qilindi.")
    except Exception:
        pass
    await call.answer()

@router.message(StudentTahlilState.waiting_for_code)
async def process_tahlil_code(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        return

    menu_cmds = [
        "✦ Test kodini kiritish", "⚛️ Test kodini kiritish", "🔢 Test kodini kiritish",
        "◈ Mening natijalarim", "📊 Mening natijalarim",
        "• Profilim", "👤 Profilim",
        "ℹ Bot haqida", "ℹ️ Yordam", "ℹ️ Bot haqida", "💡 Yordam",
        "⚙ Admin Panel", "⚙️ Admin Panel",
        "✦ Yangi test yaratish", "➕ Yangi test yaratish",
        "◈ Test natijalari va reyting", "📊 Test natijalari va reyting",
        "› Testlarni boshqarish", "🔬 Testlarni boshqarish", "📋 Testlarni boshqarish"
    ]
    if text in menu_cmds:
        await state.clear()
        if text in ["◈ Mening natijalarim", "📊 Mening natijalarim"]:
            await show_my_results(message)
        elif text in ["• Profilim", "👤 Profilim"]:
            await show_profile(message)
        elif text in ["ℹ Bot haqida", "💡 Yordam", "ℹ️ Yordam", "ℹ️ Bot haqida"]:
            await show_help(message)
        elif text in ["⚙ Admin Panel", "⚙️ Admin Panel"]:
            await admin_panel_handler(message)
        elif text in ["✦ Yangi test yaratish", "➕ Yangi test yaratish"]:
            await admin_create_test_text_handler(message)
        elif text in ["◈ Test natijalari va reyting", "📊 Test natijalari va reyting"]:
            await admin_leaderboard_text_handler(message)
        elif text in ["› Testlarni boshqarish", "🔬 Testlarni boshqarish", "📋 Testlarni boshqarish"]:
            await admin_manage_tests_text_handler(message)
        elif text in ["✦ Test kodini kiritish", "⚛️ Test kodini kiritish", "🔢 Test kodini kiritish"]:
            await enter_test_code_prompt(message, state)
        return

    data = await state.get_data()
    test_id = data.get("tahlil_test_id")
    if not test_id:
        await state.clear()
        await message.answer("Test ma'lumotlari topilmadi. Qaytadan urinib ko'ring.")
        return

    test = test_db.get_test_by_id(test_id)
    if not test:
        await state.clear()
        await message.answer("Test topilmadi.")
        return

    sub = test_db.get_user_submission_for_test(test_id, message.from_user.id)
    if not sub:
        await state.clear()
        await message.answer("Siz ushbu testni topshirmagansiz.")
        return

    entered_norm = text.upper().replace("#", "").strip()
    test_code_norm = str(test.get("test_code", "")).upper().replace("#", "").strip()
    key_code_norm = str(test.get("key_access_code", "")).upper().replace("#", "").strip()

    code_matches = False
    if key_code_norm and entered_norm == key_code_norm:
        code_matches = True
    elif test_code_norm and entered_norm == test_code_norm:
        code_matches = True

    if not code_matches:
        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_tahlil_code")]
        ])
        await message.answer(
            f"❌ <b>Kiritilgan kod noto'g'ri!</b>\n\n"
            f"«{text}» kodi ushbu testga to'g'ri kelmadi. Iltimos, to'g'ri kodni kiriting yoki bekor qilish tugmasini bosing:",
            reply_markup=cancel_kb
        )
        return

    await state.clear()
    tahlil_text = build_detailed_tahlil_text(sub, test)

    kb_rows = []
    yt_url = (test.get("youtube_url") or "").strip()
    if yt_url:
        kb_rows.append([InlineKeyboardButton(text="🎬 Video tahlilni ko'rish (YouTube)", url=yt_url)])
    kb_rows.append([InlineKeyboardButton(text="📱 Mini ilovada to'liq ko'rish", web_app=WebAppInfo(url=f"{WEBAPP_URL}/app.html?tab=tests"))])

    await message.answer(
        tahlil_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
        disable_web_page_preview=False
    )

async def notify_admins_test_results_published(test_id: int, publisher_tg_id: int, eval_type: str = "rasch"):
    """
    Test natijalari e'lon qilinganda:
    - Barcha adminlarga (agar Bosh Admin e'lon qilsa tayinlangan adminga, agar tayinlangan admin e'lon qilsa Bosh Adminga va boshqa adminlarga)
      '«Test nomi» natijalari [Admin ismi] tomonidan e'lon qilindi' deb xabar va tayyor natijalar PDF fayli biriktirib yuboriladi.
    """
    try:
        test = await asyncio.to_thread(test_db.get_test_by_id, test_id)
        if not test:
            return

        publisher_tg_id = int(publisher_tg_id or 0)
        if publisher_tg_id == ADMIN_ID:
            publisher_name = "Shaxriyor (Bosh Admin)"
        else:
            u = await asyncio.to_thread(test_db.get_user, publisher_tg_id)
            publisher_name = u.get("fullname", "Admin") if u else f"Admin (ID: {publisher_tg_id})"

        subs = await asyncio.to_thread(test_db.get_test_results_leaderboard, test_id)
        subs_count = len(subs)

        eval_title = "Rasch modeli (JMLE)" if eval_type == "rasch" else "Standart ballar"
        caption = (
            f"📢 <b>«{test['title']}»</b> (<code>#{test.get('test_code', '')}</code>) test natijalari "
            f"<b>{publisher_name}</b> tomonidan e'lon qilindi!\n\n"
            f"🧮 <b>Baholash usuli:</b> {eval_title}\n"
            f"👥 <b>Ishtirokchilar soni:</b> {subs_count} nafar\n"
            f"🕒 <b>E'lon vaqti:</b> {format_uzb_time()}\n\n"
            f"📑 <i>To'liq natijalar reyting jadvali (PDF) quyida ilova qilindi:</i>"
        )

        # PDF natijalar faylini generatsiya qilish
        pdf_path = await asyncio.to_thread(test_db.generate_test_results_pdf, test_id)

        # Adminlar ro'yxatini yig'ish (Bosh Admin + barcha tayinlangan adminlar)
        all_admins = await asyncio.to_thread(test_db.get_all_admins)
        admin_ids = set()
        admin_ids.add(ADMIN_ID)
        for a in (all_admins or []):
            if a.get("tg_id"):
                admin_ids.add(int(a["tg_id"]))

        for aid in admin_ids:
            try:
                if pdf_path and os.path.exists(pdf_path):
                    await bot.send_document(
                        chat_id=aid,
                        document=FSInputFile(pdf_path),
                        caption=caption
                    )
                else:
                    await bot.send_message(
                        chat_id=aid,
                        text=caption
                    )
            except Exception as e_send:
                log.warning(f"Adminga ({aid}) test natijalari va PDF yuborishda xatolik: {e_send}")

        # PDF faylni o'chirish
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass
    except Exception as e:
        log.error(f"notify_admins_test_results_published error: {e}", exc_info=True)


# 1. Rasch modeli bo'yicha e'lon qilish
@router.callback_query(F.data.startswith("adm_broadcast_rasch_"))
async def admin_broadcast_rasch_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    test_id = int(call.data.split("_")[3])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    await call.answer("⏳ Rasch modeli hisoblanmoqda va e'lon qilinmoqda...")
    status_msg = await call.message.answer(
        f"⏳ <b>«{test['title']}»</b> testi to'xtatilmoqda, Rasch modeli (JMLE) bo'yicha yakuniy ballar kalibrlanmoqda va o'quvchilarga shaxsiy natijalar yuborilmoqda..."
    )

    submissions = test_db.get_test_submissions_with_users(test_id)
    if not submissions:
        await status_msg.edit_text(
            f"⚠️ <b>«{test['title']}»</b> testini hali hech kim topshirmagan!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Test boshqaruviga qaytish", callback_data=f"adm_tstat_{test_id}")]
            ])
        )
        return

    if len(submissions) < 2:
        await status_msg.edit_text(
            f"⚠️ <b>Rasch modeli (JMLE) uchun kamida 2 nafar o'quvchi topshirgan bo'lishi kerak!</b>\n\n"
            f"Hozirda testni faqat 1 nafar o'quvchi topshirgan. O'quvchilar soni ko'payishini kuting yoki Standart baholash bo'yicha e'lon qiling.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Standart baholash bilan e'lon qilish", callback_data=f"adm_broadcast_std_{test_id}")],
                [InlineKeyboardButton(text="⬅️ Test boshqaruviga qaytish", callback_data=f"adm_tstat_{test_id}")]
            ])
        )
        return

    try:
        # 1. Testni to'xtatish (is_active = 0)
        test_db.set_test_active_status(test_id, 0)

        # 2. Rasch modeli orqali yakuniy kalibrlash va bazani yangilash
        rasch_res = test_db.evaluate_test_rasch(test_id, auto_update_db=True)

        # 3. Test natijalarini e'lon qilingan holatga o'tkazish
        test_db.set_test_results_published(test_id, True)

        # 4. Topshirgan barcha o'quvchilarga shaxsiy Telegram xabarini yuborish
        submissions = test_db.get_test_submissions_with_users(test_id)
        sent_count = 0
        fail_count = 0

        for sub in submissions:
            uid = sub.get("user_tg_id")
            if not uid:
                continue
            msg_text, reply_kb = build_student_result_message(sub, test, eval_type="rasch")
            try:
                await bot.send_message(chat_id=uid, text=msg_text, reply_markup=reply_kb)
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception as ex:
                log.warning(f"O'quvchi {uid} ga natija yuborishda xatolik: {ex}")
                fail_count += 1

        fail_text = f"⚠️ Yetkazilmadi (bot bloklangan): {fail_count} ta\n" if fail_count > 0 else ""

        items = rasch_res.get("items", []) if rasch_res else []
        noisy = [it for it in items if it.get("is_noisy")]
        if noisy:
            noisy_names = ", ".join([f"<code>{it['item_label']}</code>" for it in noisy[:10]])
            noisy_info = f"⚠️ <b>Shovqinli savollar ({len(noisy)} ta):</b> {noisy_names}\n"
        else:
            noisy_info = "✨ <b>Savollar sifati:</b> Barcha savollar sifatli (shovqin yo'q)\n"

        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Savollar qiyinligi va Shovqin tahlili", callback_data=f"adm_item_diag_{test_id}")],
            [InlineKeyboardButton(text="⬅️ Test boshqaruviga qaytish", callback_data=f"adm_tstat_{test_id}")]
        ])
        await status_msg.edit_text(
            f"✅ <b>Rasch modeli bo'yicha natijalar e'lon qilindi!</b>\n\n"
            f"📨 <b>Yuborildi:</b> {sent_count} nafar o'quvchiga\n"
            f"{fail_text}"
            f"{noisy_info}\n"
            f"📌 <i>O'quvchilar botda va mini ilovada o'z ballari va to'liq tahlilni ko'ra oladilar.</i>",
            reply_markup=back_kb
        )
        # Barcha adminlarga e'lon xabari va rasmiy natijalar PDF ini yuborish
        asyncio.create_task(notify_admins_test_results_published(test_id, call.from_user.id, eval_type="rasch"))
    except Exception as e:
        log.error(f"Xatolik broadcastda: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ <b>Natijalarni e'lon qilishda xatolik yuz berdi:</b>\n<code>{e}</code>")

# 2. Standart baholash (To'g'ri javoblar soni) bo'yicha e'lon qilish
@router.callback_query(F.data.startswith("adm_broadcast_std_"))
async def admin_broadcast_std_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    test_id = int(call.data.split("_")[3])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    await call.answer("⏳ Standart natijalar e'lon qilinmoqda...")
    status_msg = await call.message.answer(
        f"⏳ <b>«{test['title']}»</b> testi to'xtatilmoqda va standart to'g'ri javoblar soni bo'yicha natijalar yuborilmoqda..."
    )

    submissions = test_db.get_test_submissions_with_users(test_id)
    if not submissions:
        await status_msg.edit_text(
            f"⚠️ <b>«{test['title']}»</b> testini hali hech kim topshirmagan!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Test boshqaruviga qaytish", callback_data=f"adm_tstat_{test_id}")]
            ])
        )
        return

    try:
        # 1. Testni to'xtatish (is_active = 0)
        test_db.set_test_active_status(test_id, 0)

        # 2. Test natijalarini e'lon qilingan holatga o'tkazish
        test_db.set_test_results_published(test_id, True)

        # 3. Topshirgan barcha o'quvchilarga shaxsiy Telegram xabarini yuborish
        sent_count = 0
        fail_count = 0

        for sub in submissions:
            uid = sub.get("user_tg_id")
            if not uid:
                continue
            msg_text, reply_kb = build_student_result_message(sub, test, eval_type="std")
            try:
                await bot.send_message(chat_id=uid, text=msg_text, reply_markup=reply_kb)
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception as ex:
                log.warning(f"O'quvchi {uid} ga natija yuborishda xatolik: {ex}")
                fail_count += 1

        fail_text = f"⚠️ Yetkazilmadi (bot bloklangan): {fail_count} ta\n" if fail_count > 0 else ""
        back_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Test boshqaruviga qaytish", callback_data=f"adm_tstat_{test_id}")]
        ])
        await status_msg.edit_text(
            f"✅ <b>Standart natijalar muvaffaqiyatli e'lon qilindi!</b>\n\n"
            f"📨 <b>Yuborildi:</b> {sent_count} nafar o'quvchiga\n"
            f"{fail_text}"
            f"📌 <i>Endi barcha o'quvchilar botda va mini ilovada o'z ballari va to'liq tahlilni ko'ra oladilar.</i>",
            reply_markup=back_kb
        )
        # Barcha adminlarga e'lon xabari va rasmiy natijalar PDF ini yuborish
        asyncio.create_task(notify_admins_test_results_published(test_id, call.from_user.id, eval_type="std"))
    except Exception as e:
        log.error(f"Xatolik broadcastda: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ <b>Natijalarni e'lon qilishda xatolik yuz berdi:</b>\n<code>{e}</code>")

# ── KECH TOPSHIRILGAN NATIJANI TESTGA QO'SHISH YOKI RAD ETISH ──
@router.callback_query(F.data.startswith("adm_accept_late_"))
async def admin_accept_late_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    sub_id = int(call.data.split("_")[3])
    sub = test_db.get_submission_by_id(sub_id)
    if not sub:
        await call.answer("Topshiriq topilmadi!", show_alert=True)
        return

    # 1. Bazada statusni yangilash: is_late = 0
    test_db.set_submission_late_status(sub_id, 0)
    test_id = sub["test_id"]
    test = test_db.get_test_by_id(test_id)

    # 2. Agar test natijalari e'lon qilingan bo'lsa, Rasch va PDF ni yangilash
    if test and test.get("results_published", 0) == 1:
        try:
            test_db.evaluate_test_rasch(test_id, auto_update_db=True)
        except Exception as e:
            log.warning(f"Rasch re-eval error: {e}")
        try:
            test_db.generate_test_results_pdf(test_id)
        except Exception as e:
            log.warning(f"PDF regeneration error: {e}")

    # 3. O'quvchiga natijani yuborish
    uid = sub.get("user_tg_id")
    if uid:
        try:
            updated_sub = test_db.get_submission_by_id(sub_id) or sub
            msg_text, reply_kb = build_student_result_message(updated_sub, test, eval_type="rasch")
            await bot.send_message(
                chat_id=uid,
                text=(
                    f"🎉 <b>Xushxabar!</b>\n\n"
                    f"Admin sizning kech topshirgan javoblaringizni qabul qildi va test natijalariga qo'shdi!\n\n"
                    f"{msg_text}"
                ),
                reply_markup=reply_kb
            )
        except Exception as ex:
            log.warning(f"O'quvchiga tasdiq xabarini yuborishda xatolik: {ex}")

    try:
        cur_html = call.message.html_text or call.message.text or ""
        await call.message.edit_text(
            cur_html + "\n\n✅ <b>Natija testga muvaffaqiyatli qo'shildi va o'quvchiga yuborildi!</b>",
            reply_markup=None
        )
    except Exception:
        pass
    await call.answer("Natija testga qo'shildi!", show_alert=True)


@router.callback_query(F.data.startswith("adm_reject_late_"))
async def admin_reject_late_cb(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    sub_id = int(call.data.split("_")[3])
    sub = test_db.get_submission_by_id(sub_id)
    if not sub:
        await call.answer("Topshiriq topilmadi!", show_alert=True)
        return

    # 2 = rad etilgan
    test_db.set_submission_late_status(sub_id, 2)

    try:
        cur_html = call.message.html_text or call.message.text or ""
        await call.message.edit_text(
            cur_html + "\n\n❌ <b>Ushbu kech topshirilgan natija hisobga olinmadi (rad etildi).</b>",
            reply_markup=None
        )
    except Exception:
        pass
    await call.answer("Natija rad etildi!", show_alert=True)

@router.callback_query(F.data.startswith("adm_rasch_"))
async def admin_test_rasch_eval(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    test_id = int(call.data.split("_")[2])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    await call.answer("⏳ Rasch modeli hisoblanmoqda...")
    status_msg = await call.message.answer("⏳ <i>Rasch JMLE modeli bo'yicha savollar qiyinligi va o'quvchilar qobiliyati hisoblanmoqda...</i>")

    res = test_db.evaluate_test_rasch(test_id, auto_update_db=True)
    if not res or not res.get("students"):
        await status_msg.edit_text(
            f"⚠️ <b>«{test['title']}»</b> testi uchun Rasch modelini hisoblashning imkoni bo'lmadi.\n\n"
            f"📌 <i>Talab: Rasch modeli ishlashi uchun testni kamida 2 nafar o'quvchi topshirgan bo'lishi kerak.</i>"
        )
        return

    meta = res.get("meta", {})
    students = res.get("students", [])
    items = res.get("items", [])

    is_active = (test.get("is_active", 1) == 1)
    is_pub = test_db.is_test_results_published(test_id)

    status_note = ""
    if is_active or not is_pub:
        status_note = (
            f"⚠️ <b>Eslatma:</b> Test hozirda to'xtatilmagan yoki natijalar o'quvchilarga hali e'lon qilinmagan. "
            f"O'quvchilarga natijalar ko'rinmaydi (ularga <i>«Javoblaringiz tekshirilmoqda»</i> ko'rinadi).\n"
            f"Testni to'xtatib, barchaga natijalarni e'lon qilish uchun quyidagi tugmani bosing 👇\n\n"
        )

    noisy = [it for it in items if it.get("is_noisy")]
    if noisy:
        noisy_summary = f"⚠️ <b>Shovqinli savollar ({len(noisy)} ta):</b> " + ", ".join([f"<code>{it['item_label']}</code>" for it in noisy[:10]]) + "\n\n"
    else:
        noisy_summary = "✨ <b>Savollar sifati:</b> Barcha savollar sifatli (shovqin yo'q)\n\n"

    text = (
        f"🧮 <b>Rasch Modeli (JMLE) Baholash Natijalari</b>\n\n"
        f"📖 <b>Test:</b> {test['title']} (<code>#{test['test_code']}</code>)\n"
        f"👥 <b>Talabalar:</b> {meta.get('n_students', meta.get('num_students', len(students)))} nafar\n"
        f"❓ <b>Elementlar:</b> {meta.get('n_items', meta.get('num_items', len(items)))} ta (55 ta band)\n"
        f"🔄 <b>Iteratsiyalar:</b> {meta.get('iterations', 0)} (Konvergensiya: {meta.get('converged', True)})\n\n"
        f"{noisy_summary}"
        f"{status_note}"
        f"🏆 <b>O'quvchilar darajalari va yakuniy ballari (0-100):</b>\n"
    )

    for idx, s in enumerate(students[:25], 1):
        sid = s.get('student_id')
        u = test_db.get_user(sid) if sid else None
        name = u['fullname'] if u else f"ID: {sid}"
        theta_val = s.get('theta', 0.0)
        text += f"<b>{idx}. {name}</b>: <b>{s['final_score']} ball</b> [🎖 <b>{s['grade']}</b>] (θ={theta_val:+.2f})\n"

    if len(students) > 25:
        text += f"\n<i>...va yana {len(students) - 25} nafar talaba.</i>"

    buttons = [
        [InlineKeyboardButton(text="🔍 Savollar qiyinligi va Shovqin tahlili", callback_data=f"adm_item_diag_{test_id}")],
        [InlineKeyboardButton(text="📢 Testni to'xtatish va Natijalarni e'lon qilish", callback_data=f"adm_broadcast_results_{test_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"adm_tstat_{test_id}")]
    ]
    await status_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("adm_item_diag_"))
async def admin_item_diag_cb(call: CallbackQuery):
    """Admin uchun savollarning qiyinligi va shovqin (infit/outfit) tahlili."""
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    res = test_db.evaluate_test_rasch(test_id)
    if not res or not res.get("items"):
        await call.answer("Tahlil uchun kamida 2 nafar o'quvchi topshirgan bo'lishi kerak!", show_alert=True)
        return

    items = res.get("items", [])
    n_students = res.get("meta", {}).get("n_students", 0)
    noisy = [it for it in items if it.get("is_noisy")]

    # Sort by difficulty
    items_sorted = sorted(items, key=lambda x: x.get("difficulty_b", 0), reverse=True)
    hardest = items_sorted[:5]
    easiest = items_sorted[-5:]
    easiest.reverse()

    text = (
        f"🔍 <b>«{test['title']}» — Savollar Sifati va Shovqin Tahlili</b>\n\n"
        f"👥 <b>Ishtirokchilar:</b> {n_students} nafar | ❓ <b>Jami elementlar:</b> 55 ta band\n\n"
    )

    if noisy:
        text += f"⚠️ <b>SHOVQINLI SAVOLLAR ({len(noisy)} TA):</b>\n"
        text += f"<i>(Infit yoki Outfit > 1.3 — kutilmagan javoblar yuqori bo'lgan):</i>\n"
        for it in noisy:
            solved = it.get('solved_count', 0)
            score_pts = it.get('item_score', 0)
            infit = it.get('infit_mnsq', 1.0)
            outfit = it.get('outfit_mnsq', 1.0)
            text += f"• <b>{it['item_label']}</b>: {solved}/{n_students} kishi yechgan | Ball: <b>{score_pts}</b> | Infit: <code>{infit}</code>, Outfit: <code>{outfit}</code>\n"
        text += f"\nℹ️ <i>Eslatma: Ushbu savollarni to'g'ri topgan o'quvchilarga ball to'liq berilgan.</i>\n\n"
    else:
        text += f"✨ <b>SHOVQINLI SAVOLLAR:</b>\nHech qanday shovqinli savol aniqlanmadi. Barcha 55 ta savol Rasch modeliga ideal mos tushgan!\n\n"

    text += f"🔥 <b>ENG QIYIN 5 TA SAVOL (Eng yuqori ball):</b>\n"
    for it in hardest:
        solved = it.get('solved_count', 0)
        score_pts = it.get('item_score', 0)
        b_val = it.get('difficulty_b', 0)
        text += f"• <b>{it['item_label']}</b>: {solved}/{n_students} kishi topgan (Qiyinlik: <code>{b_val:+.2f}</code>) ➔ <b>{score_pts} ball</b>\n"

    text += f"\n🟢 <b>ENG OSON 5 TA SAVOL (Ko'pchilik yechgan):</b>\n"
    for it in easiest:
        solved = it.get('solved_count', 0)
        score_pts = it.get('item_score', 0)
        b_val = it.get('difficulty_b', 0)
        text += f"• <b>{it['item_label']}</b>: {solved}/{n_students} kishi topgan (Qiyinlik: <code>{b_val:+.2f}</code>) ➔ <b>{score_pts} ball</b>\n"

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧮 Rasch reytingiga qaytish", callback_data=f"adm_rasch_{test_id}")],
        [InlineKeyboardButton(text="⬅️ Test boshqaruviga qaytish", callback_data=f"adm_tstat_{test_id}")]
    ])

    try:
        await call.message.edit_text(text, reply_markup=back_kb)
    except Exception:
        await call.message.answer(text, reply_markup=back_kb)

@router.callback_query(F.data.startswith("adm_restxt_"))
async def admin_test_res_text(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    test_id = int(call.data.split("_")[2])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    results = test_db.get_test_results_leaderboard(test_id)
    if not results:
        await call.answer("Bu testni hali hech kim topshirmagan!", show_alert=True)
        return

    text = f"🏆 <b>«{test['title']}» Natijalari (Matn ko'rinishida):</b>\n"
    text += f"👥 <b>Jami ishtirokchilar:</b> {len(results)} nafar | 🕒 {format_uzb_time()}\n\n"

    for idx, row in enumerate(results[:30], 1):
        grade = test_db.calculate_grade(row["score"])
        text += f"<b>{idx}. {row['fullname']}</b> — <b>{row['score']} ball</b> [🎖 {grade}] ({row['correct_count']} ta to'g'ri)\n"

    if len(results) > 30:
        text += f"\n<i>...va yana {len(results) - 30} nafar ishtirokchi (barchasini ko'rish uchun PDF yuklab oling).</i>"

    buttons = [
        [InlineKeyboardButton(text="📑 PDF hisobotni yuklab olish", callback_data=f"adm_respdf_{test_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"adm_tstat_{test_id}")]
    ]

    try:
        await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception:
        await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@router.callback_query(F.data.startswith("adm_respdf_"))
async def admin_test_res_pdf(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return

    test_id = int(call.data.split("_")[2])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    results = test_db.get_test_results_leaderboard(test_id)
    if not results:
        await call.answer("Ushbu testni hali hech kim topshirmagan, PDF chiqarib bo'lmaydi.", show_alert=True)
        return

    await call.answer("⏳ PDF hisobot yaratilmoqda...")
    status_msg = await call.message.answer("⏳ <i>PDF reyting jadvali shakllantirilmoqda, iltimos kuting...</i>")

    pdf_path = test_db.generate_test_results_pdf(test_id)
    if pdf_path and os.path.exists(pdf_path):
        try:
            caption = (
                f"📑 <b>«{test['title']}»</b> bo'yicha rasmiy test natijalari va reyting hisoboti.\n\n"
                f"👥 <b>Ishtirokchilar:</b> {len(results)} nafar\n"
                f"🕒 <b>Sana:</b> {format_uzb_time()}"
            )
            await bot.send_document(
                chat_id=call.from_user.id,
                document=FSInputFile(pdf_path),
                caption=caption
            )
            await status_msg.delete()
        except Exception as e:
            log.error(f"PDF yuborishda xatolik: {e}")
            await status_msg.edit_text(f"⚠️ PDF yuborishda xatolik yuz berdi: {e}")
        finally:
            try:
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
            except Exception:
                pass
    else:
        await status_msg.edit_text("⚠️ PDF hisobotini shakllantirishda xatolik yuz berdi.")

# Foydalanuvchi to'g'ridan-to'g'ri test kodini yuborganida
@router.message(F.text)
async def handle_direct_text(message: Message, state: FSMContext):
    cur_state = await state.get_state()
    if cur_state is not None:
        return

    raw_text = (message.text or "").strip()
    if not raw_text:
        return

    if not await check_access(message):
        return

    menu_cmds = [
        "⚛️ Test kodini kiritish", "🔢 Test kodini kiritish", "📊 Mening natijalarim", "👤 Profilim",
        "ℹ️ Yordam", "ℹ️ Bot haqida", "⚙️ Admin Panel",
        "➕ Yangi test yaratish", "📊 Test natijalari va reyting", "🔬 Testlarni boshqarish", "📋 Testlarni boshqarish"
    ]
    if raw_text in menu_cmds:
        return

    code = raw_text.upper().replace("#", "")
    test = test_db.get_test_by_code(code)
    if test:
        await send_test_card(message, test, message.from_user.id)
    else:
        user_info = test_db.get_user(message.from_user.id)
        name = user_info['fullname'] if user_info else (message.from_user.first_name or "Foydalanuvchi")
        await message.answer(
            f"👋 Salom, <b>{name}</b>!\n\n"
            f"Test topshirish uchun «🔢 Test kodini kiritish» tugmasini bosing yoki menyudan foydalaning 👇",
            reply_markup=main_menu_kb(message.from_user.id)
        )

# ── HIGH-LOAD RATE LIMITING & CONCURRENCY CONTROLLER ──────────────────
class HighLoadRateLimiter:
    """
    Foydalanuvchi tg_id yoki IP bo'yicha so'rovlar chastotasini xavfsiz cheklash (Rate Limiting).
    1-3 soniyalik limit: 1 soniyada 1 tadan, 2 soniyada ko'pi bilan 1 tadan ortiq og'ir so'rov yuborishni bloklaydi.
    """
    def __init__(self):
        self._history: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
        self._last_clean = time.time()

    async def check(self, key: str, max_requests: int = 1, window_seconds: float = 2.0) -> Tuple[bool, float]:
        async with self._lock:
            now = time.time()
            if now - self._last_clean > 60.0:
                self._cleanup(now)

            timestamps = self._history.get(key, [])
            recent = [t for t in timestamps if now - t < window_seconds]

            if len(recent) >= max_requests:
                earliest = recent[0]
                retry_after = round(max(0.3, window_seconds - (now - earliest)), 1)
                return False, retry_after

            recent.append(now)
            self._history[key] = recent
            return True, 0.0

    def _cleanup(self, now: float):
        self._last_clean = now
        stale = now - 30.0
        to_del = [k for k, v in self._history.items() if not v or v[-1] < stale]
        for k in to_del:
            del self._history[k]

GLOBAL_RATE_LIMITER = HighLoadRateLimiter()

# Neon PostgreSQL Connection Pool (maxconn=20) ga to'liq moslangan Asinxron Navbat (Queue/Semaphore)
# Bir vaqtda ko'pi bilan 20 ta og'ir DB tranzaksiyasiga ruxsat beriladi.
# 20 tadan ortiq so'rov kelsa, ular xato bermasdan FIFO navbatida asinxron kutadi.
SUBMIT_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(20)
COMPARE_CONCURRENCY_SEMAPHORE = asyncio.Semaphore(15)

# ── AIOHTTP MINI APP VEB SERVERI ──────────────────────

async def handle_submit_test_api(request):
    """Mini App dan kelgan javoblarni tekshirish va bot orqali faqat foydalanuvchiga natijani xabar qilish"""
    try:
        data = await request.json()
        test_id = data.get("test_id", 1)
        user_tg_id = data.get("user_tg_id")
        if not user_tg_id:
            init_data = data.get("init_data") or request.headers.get("X-Telegram-Init-Data", "")
            if init_data:
                import urllib.parse
                try:
                    parsed = dict(urllib.parse.parse_qsl(init_data))
                    if "user" in parsed:
                        u_dict = json.loads(parsed["user"])
                        if u_dict and u_dict.get("id"):
                            user_tg_id = int(u_dict["id"])
                except Exception:
                    pass
            if not user_tg_id and request.rel_url.query.get("tg_id"):
                try:
                    user_tg_id = int(request.rel_url.query.get("tg_id", 0))
                except Exception:
                    pass
        user_answers = data.get("answers", {})

        if not user_tg_id or int(user_tg_id) <= 0:
            return web.json_response({
                "success": False,
                "message": "⚠️ Web orqali ishlash mumkin emas! Testni faqat rasmiy Telegram botimiz (@fizika_rash_testbot) va Mini ilova orqali topshirish mumkin."
            }, status=403)

        # ── RATE LIMITING (1-3 soniya cheklovi) ─────────────────
        rate_key = f"submit_{user_tg_id or request.remote or 'unknown'}"
        is_allowed, retry_sec = await GLOBAL_RATE_LIMITER.check(rate_key, max_requests=1, window_seconds=2.0)
        if not is_allowed and not test_db.is_admin(user_tg_id or 0, ADMIN_ID):
            return web.json_response({
                "success": False,
                "retry_after": retry_sec,
                "message": f"Iltimos, {retry_sec} soniya kuting! So'rovingiz navbatda qayta ishlanmoqda..."
            }, status=429)

        async with SUBMIT_CONCURRENCY_SEMAPHORE:
            test_obj = await asyncio.to_thread(test_db.get_test_by_id, test_id)
            if not test_obj:
                return web.json_response({
                    "success": False,
                    "message": "Test topilmadi!"
                }, status=404)

            # Bo'sh (0 ta belgilangan) testni topshirishni bloklash (tasodifiy bosilib ketishdan himoya)
            has_any_answer = False
            if isinstance(user_answers, dict):
                for k, v in user_answers.items():
                    if v is not None and str(v).strip():
                        has_any_answer = True
                        break

            if not has_any_answer and not test_db.is_admin(user_tg_id, ADMIN_ID):
                return web.json_response({
                    "success": False,
                    "message": "⚠️ Testda birorta ham savolga javob belgilanmagan! Bo'sh testni topshirib bo'lmaydi. Iltimos, kamida bitta javobni belgilang."
                }, status=400)

        sched_stat = get_test_schedule_status(test_obj)
        if sched_stat["is_upcoming"] and not test_db.is_admin(user_tg_id, ADMIN_ID):
            sdate = test_obj.get('scheduled_date') or 'Bugun'
            sstart = test_obj.get('scheduled_start') or ''
            return web.json_response({
                "success": False,
                "message": f"Test hali boshlanmagan! Boshlanish vaqti: {sdate} {sstart} (UZB)"
            }, status=400)

        # Dastlabki 45 daqiqa davomida javob topshirishni cheklash (Milliy sertifikat qoidasi)
        min_submit_info = get_test_min_submit_info(test_obj)
        if not min_submit_info["can_submit"] and not test_db.is_admin(user_tg_id, ADMIN_ID):
            rem_sec = min_submit_info["remaining_seconds"]
            rem_min = rem_sec // 60
            rem_s = rem_sec % 60
            unlock_t = min_submit_info["unlock_time_str"]
            return web.json_response({
                "success": False,
                "error_code": "EARLY_SUBMISSION_BLOCKED",
                "remaining_seconds": rem_sec,
                "unlock_time": unlock_t,
                "message": (
                    f"⚠️ Test boshlanganidan so'ng dastlabki 45 daqiqa davomida javob topshirish mumkin emas!\n\n"
                    f"⏱ Qolgan vaqt: {rem_min} daqiqa {rem_s} soniya\n"
                    f"🕒 Topshirish ochiladigan vaqt: {unlock_t}\n\n"
                    f"Sababi: Milliy sertifikat qoidalari va imtihon shaffofligini ta'minlash, "
                    f"shoshmashosharlik hamda tasodifiy (tavakkal) belgilashlarning oldini olish maqsadida "
                    f"test boshlanganidan so'ng dastlabki 45 daqiqa davomida javoblarni topshirish taqiqlanadi. "
                    f"Iltimos, ajratilgan vaqtdan unumli foydalanib savollarni qayta tekshirib chiqing!"
                )
            }, status=400)

        # Kech topshirilgan holatni aniqlash
        is_late_submission = False
        if not test_db.is_admin(user_tg_id, ADMIN_ID):
            if sched_stat.get("is_closed") or test_obj.get("is_active", 1) == 0 or test_obj.get("results_published", 0) == 1:
                is_late_submission = True

        # Bazada tekshirish va saqlash (Asinxron navbat / Semaphore bilan)
        async with SUBMIT_CONCURRENCY_SEMAPHORE:
            result = await asyncio.to_thread(
                test_db.check_and_save_submission,
                test_id, user_tg_id, user_answers,
                is_late=1 if is_late_submission else 0
            )

        now_uzb = datetime.now(UZB_TZ)
        time_str_sec = now_uzb.strftime("%H:%M:%S")
        datetime_str_sec = now_uzb.strftime("%d.%m.%Y %H:%M:%S")

        if is_late_submission:
            # 1. Foydalanuvchiga Telegram xabari: kech topshirdingiz, hisobga olinmaydi
            if user_tg_id:
                msg_user = (
                    f"⚠️ <b>Hurmatli {result['fullname']}, siz testni belgilangan vaqtdan kech topshirdingiz!</b>\n\n"
                    f"📚 <b>Test:</b> {result['test_title']} (<code>#{result['test_code']}</code>)\n"
                    f"🕒 <b>Topshirilgan vaqt:</b> <b>{time_str_sec}</b> ({datetime_str_sec})\n"
                    f"🚫 <b>Holat:</b> <b>Natijangiz umumiy hisobga olinmaydi!</b>\n\n"
                    f"ℹ️ Test javoblaringiz qabul qilindi va ko'rib chiqish uchun <b>adminga yuborildi</b>. "
                    f"Agar admin ruxsat bersa, natijangiz umumiy testga qo'shiladi va bu haqda sizga xabar beriladi."
                )
                try:
                    await bot.send_message(chat_id=user_tg_id, text=msg_user)
                except Exception as ex:
                    log.warning(f"Foydalanuvchiga kechikish xabari yuborishda xatolik: {ex}")

            # 2. Adminga bildirishnoma: nechta ishlagan, vaqti soniyasigacha va qaror tugmalari
            sub_id = result.get("submission_id")
            corr_cnt = result.get("correct_count", 0)
            score_val = result.get("score", 0.0)
            u_info = test_db.get_user(user_tg_id)
            username_str = f" (@{u_info.get('username')})" if (u_info and u_info.get('username')) else ""
            phone_str = f"\n📞 <b>Telefon:</b> {result.get('phone', '—')}" if result.get('phone') else ""

            admin_text = (
                f"⏰ <b>DIQQAT: Kech topshirilgan test javobi keldi!</b>\n\n"
                f"👤 <b>O'quvchi:</b> {result['fullname']}{username_str}\n"
                f"🆔 <b>Telegram ID:</b> <code>{user_tg_id}</code>{phone_str}\n"
                f"📚 <b>Test:</b> {result['test_title']} (<code>#{result['test_code']}</code>)\n"
                f"🕒 <b>Topshirilgan vaqt:</b> <b>{datetime_str_sec}</b>\n\n"
                f"📊 <b>Ishlagan natijasi:</b> <b>{corr_cnt} ta to'g'ri</b> (55 tadan) — <b>{score_val} ball</b>\n\n"
                f"❓ <b>Ushbu o'quvchining natijasini testga qo'shamizmi?</b>"
            )

            admin_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Testga natijasini qo'shish", callback_data=f"adm_accept_late_{sub_id}")],
                [InlineKeyboardButton(text="❌ Hisobga olmaslik (Rad etish)", callback_data=f"adm_reject_late_{sub_id}")]
            ])

            target_admin = ADMIN_ID
            if test_obj.get("created_by") and test_db.is_admin(test_obj.get("created_by"), ADMIN_ID):
                target_admin = test_obj.get("created_by")

            try:
                await bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=admin_kb)
            except Exception as ex_a:
                log.warning(f"Admin alert error: {ex_a}")

            if target_admin != ADMIN_ID:
                try:
                    await bot.send_message(chat_id=target_admin, text=admin_text, reply_markup=admin_kb)
                except Exception:
                    pass

            client_data = dict(result)
            client_data["is_published"] = False
            client_data["is_late"] = True
            client_data["score"] = None
            client_data["grade"] = "Kech topshirildi"
            client_data["correct_count"] = None
            client_data["incorrect_count"] = None
            client_data["unanswered_count"] = None
            client_data["rasch_theta"] = None
            client_data["details"] = None

            return web.json_response({
                "success": True,
                "is_late": True,
                "message": f"⚠️ Siz testni belgilangan vaqtdan kech topshirdingiz (Soat: {time_str_sec})! Natijangiz hisobga olinmaydi va adminga ko'rib chiqish uchun yuborildi.",
                "data": client_data
            })
        else:
            # Oddiy, vaqtida topshirilgan test
            if user_tg_id:
                msg_user = (
                    f"✓ <b>Hurmatli {result['fullname']}, javoblaringiz qabul qilindi!</b>\n\n"
                    f"• <b>Test:</b> {result['test_title']} (<code>#{result['test_code']}</code>)\n"
                    f"• <b>Holat:</b> <b>Javoblaringiz qabul qilindi (Jarayonda)...</b>\n"
                    f"• <b>Topshirilgan vaqt:</b> {format_uzb_time()}\n\n"
                    f"ℹ <b>Eslatma:</b> Test hozirda barcha o'quvchilar uchun davom etmoqda. "
                    f"Admin testni yakunlab, <b>Rasch modeli (JMLE)</b> bo'yicha tahlil o'tkazgach, "
                    f"to'g'ri ishlangan savollar soni, yakuniy ballingiz va Milliy sertifikat darajangiz botingizga shaxsiy xabar qilib yuboriladi!\n\n"
                    f"✦ <i>Javoblaringiz tizimda muvaffaqiyatli saqlandi.</i>"
                )
                try:
                    await bot.send_message(chat_id=user_tg_id, text=msg_user)
                except Exception as ex:
                    log.warning(f"Foydalanuvchiga xabar yuborishda xatolik: {ex}")

            client_data = dict(result)
            client_data["is_published"] = False
            client_data["is_late"] = False
            client_data["score"] = None
            client_data["grade"] = "Kutilmoqda"
            client_data["correct_count"] = None
            client_data["incorrect_count"] = None
            client_data["unanswered_count"] = None
            client_data["rasch_theta"] = None
            client_data["details"] = None

            return web.json_response({"success": True, "data": client_data})

    except Exception as e:
        log.error(f"Submit API Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_create_test_api(request):
    """Admin Mini App dan yuborilgan yangi test, kalitlar va ballarni saqlash"""
    try:
        data = await request.json()
        title = data.get("title", "").strip() or "Fizika Milliy Sertifikat Testi"
        test_code = data.get("test_code", "").strip().upper()
        if not test_code:
            test_code = test_db.get_next_test_code()
        
        subject = data.get("subject", "Fizika").strip() or "Fizika"
        answers = data.get("answers", {})
        time_limit_min = int(data.get("time_limit_min", 0))
        key_access_code = data.get("key_access_code", "").strip()
        youtube_url = (data.get("youtube_url") or "").strip()

        creator_id = int(data.get("creator_tg_id", 0) or data.get("tg_id", 0))
        if not creator_id:
            init_data = data.get("init_data", "") or request.headers.get("X-Telegram-Init-Data", "")
            if init_data:
                try:
                    import urllib.parse
                    parsed = dict(urllib.parse.parse_qsl(init_data))
                    if 'user' in parsed:
                        u_dict = json.loads(parsed['user'])
                        if u_dict and u_dict.get('id'):
                            creator_id = int(u_dict['id'])
                except Exception:
                    pass

        creator_name = ""
        if creator_id:
            u_info = test_db.get_user(creator_id)
            if u_info:
                creator_name = u_info.get("fullname", "")
            if not creator_name and creator_id == ADMIN_ID:
                creator_name = "Bosh Admin"

        if not creator_name:
            creator_name = "Admin"

        success = test_db.create_test(
            test_code=test_code,
            title=title,
            subject=subject,
            answers=answers,
            time_limit_min=time_limit_min,
            key_access_code=key_access_code,
            created_by=creator_id,
            created_by_name=creator_name,
            youtube_url=youtube_url
        )

        sched_date = data.get("scheduled_date", "").strip()
        sched_start = data.get("scheduled_start", "").strip()
        sched_end = data.get("scheduled_end", "").strip()

        if success:
            try:
                t_obj = test_db.get_test_by_code(test_code)
                test_id = t_obj['id'] if t_obj else 0
                
                # Jadval vaqtini sozlash
                if sched_start and sched_end and test_id:
                    test_db.set_test_schedule(test_id, sched_date, sched_start, sched_end)

                if youtube_url and test_id:
                    test_db.set_test_youtube_url(test_id, youtube_url)

                time_info = f"⏱ <b>Vaqt chegarasi:</b> {time_limit_min} daqiqa\n" if time_limit_min > 0 else ""
                sched_info = f"⏰ <b>O'tkazilish vaqti:</b> {sched_date} {sched_start}–{sched_end} (UZB)\n" if (sched_start and sched_end) else ""
                yt_info = f"🎬 <b>Video tahlil:</b> {youtube_url}\n" if youtube_url else ""
                
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📥 Ha, PDF yuklayman", callback_data=f"ask_pdf_{test_id}")],
                    [InlineKeyboardButton(text="❌ Yo'q, kerak emas", callback_data=f"no_pdf_{test_id}")]
                ])

                # Testni yaratgan adminga (bosh admin yoki tayinlangan admin) PDF so'rovini yuborish
                creator_id = int(data.get("creator_tg_id", 0) or data.get("tg_id", 0))
                if not creator_id:
                    init_data = data.get("init_data", "") or request.headers.get("X-Telegram-Init-Data", "")
                    if init_data:
                        try:
                            import urllib.parse
                            parsed = dict(urllib.parse.parse_qsl(init_data))
                            if 'user' in parsed:
                                u_dict = json.loads(parsed['user'])
                                if u_dict and u_dict.get('id'):
                                    creator_id = int(u_dict['id'])
                        except Exception:
                            pass

                target_chat_id = creator_id if (creator_id and test_db.is_admin(creator_id, ADMIN_ID)) else ADMIN_ID

                # Testni yaratgan adminga (bosh admin yoki tayinlangan admin) PDF so'rovini yuborish
                await bot.send_message(
                    chat_id=target_chat_id,
                    text=(
                        f"✅ <b>Yangi test yaratildi va saqlandi!</b>\n\n"
                        f"📖 <b>Nomi:</b> {title} (<code>#{test_code}</code>)\n"
                        f"📌 <b>Fani:</b> {subject}\n"
                        f"{sched_info}"
                        f"{time_info}"
                        f"🎯 <i>Barcha 55 ta savol kalitlari muvaffaqiyatli saqlandi!</i>\n\n"
                        f"📥 <b>Ushbu test uchun PDF fayl yuklaysizmi?</b>"
                    ),
                    reply_markup=kb
                )

                # Agar testni tayinlangan admin yaratgan bo'lsa -> Bosh Adminga PDF so'rovsiz, faqat 1 ta toza bildirishnoma:
                if target_chat_id != ADMIN_ID:
                    try:
                        creator_u = test_db.get_user(target_chat_id)
                        creator_name = creator_u.get("fullname", "Admin") if creator_u else f"Admin (ID: {target_chat_id})"
                        await bot.send_message(
                            chat_id=ADMIN_ID,
                            text=(
                                f"📢 <b>Yangi test yaratildi!</b>\n\n"
                                f"📖 <b>Nomi:</b> {title} (<code>#{test_code}</code>)\n"
                                f"📌 <b>Fani:</b> {subject}\n"
                                f"{sched_info}"
                                f"{time_info}"
                                f"👤 <b>Yaratuvchi:</b> <b>{creator_name}</b> tomonidan yaratildi."
                            )
                        )
                    except Exception as e_adm:
                        log.warning(f"Bosh adminga xabar yuborishda xatolik: {e_adm}")
                else:
                    # Agar Bosh Admin yaratgan bo'lsa -> tayinlangan adminlarga ham PDF so'rovsiz 1 ta toza bildirishnoma:
                    try:
                        all_adms = test_db.get_all_admins()
                        for adm in (all_adms or []):
                            aid = adm.get("tg_id")
                            if aid and aid != ADMIN_ID:
                                await bot.send_message(
                                    chat_id=aid,
                                    text=(
                                        f"📢 <b>Yangi test yaratildi!</b>\n\n"
                                        f"📖 <b>Nomi:</b> {title} (<code>#{test_code}</code>)\n"
                                        f"📌 <b>Fani:</b> {subject}\n"
                                        f"{sched_info}"
                                        f"{time_info}"
                                        f"👤 <b>Yaratuvchi:</b> <b>Shaxriyor (Bosh Admin)</b> tomonidan yaratildi."
                                    )
                                )
                    except Exception as e_adm2:
                        log.warning(f"Tayinlangan adminga xabar yuborishda xatolik: {e_adm2}")
            except Exception as ex:
                log.warning(f"Adminga xabar yuborishda xatolik: {ex}")

            return web.json_response({"success": True, "message": "Test muvaffaqiyatli saqlandi!"})
        else:
            return web.json_response({"success": False, "message": "Ma'lumotlar bazasiga yozishda xatolik yuz berdi"}, status=400)

    except Exception as e:
        log.error(f"Create Test API Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_admin_get_test_keys(request):
    """Admin Mini App uchun test tafsilotlari va mavjud kalitlarini qaytaradi."""
    try:
        test_id_str = request.query.get("test_id", "")
        if not test_id_str:
            return web.json_response({"success": False, "message": "Test ID ko'rsatilmadi"}, status=400)
        try:
            test_id = int(test_id_str)
        except ValueError:
            return web.json_response({"success": False, "message": "Noto'g'ri test ID"}, status=400)

        test = test_db.get_test_by_id(test_id)
        if not test:
            return web.json_response({"success": False, "message": "Test topilmadi"}, status=404)

        answers = {}
        if test.get("answers_json"):
            try:
                answers = json.loads(test["answers_json"])
            except Exception:
                answers = {}

        return web.json_response({
            "success": True,
            "test": {
                "id": test["id"],
                "test_code": test.get("test_code", ""),
                "title": test.get("title", ""),
                "subject": test.get("subject", "Fizika"),
                "time_limit_min": test.get("time_limit_min", 0),
                "key_access_code": test.get("key_access_code", "") or "",
                "scheduled_date": test.get("scheduled_date", "") or "",
                "scheduled_start": test.get("scheduled_start", "") or "",
                "scheduled_end": test.get("scheduled_end", "") or "",
                "youtube_url": test.get("youtube_url", "") or "",
                "answers": answers
            }
        })
    except Exception as e:
        log.error(f"Get Test Keys API Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=500)


async def handle_admin_update_test_keys(request):
    """Admin Mini App dan yuborilgan yangi kalitlarni saqlash va natijalarni avtomatik qayta hisoblash."""
    try:
        data = await request.json()
        test_id = int(data.get("test_id", 0))
        if not test_id:
            return web.json_response({"success": False, "message": "Test ID ko'rsatilmadi"}, status=400)

        answers = data.get("answers", {})
        if not answers:
            return web.json_response({"success": False, "message": "Kalitlar kiritilmadi"}, status=400)

        title = data.get("title")
        time_limit_min = data.get("time_limit_min")
        key_access_code = data.get("key_access_code")
        scheduled_date = data.get("scheduled_date")
        scheduled_start = data.get("scheduled_start")
        scheduled_end = data.get("scheduled_end")
        youtube_url = data.get("youtube_url")

        res = test_db.update_test_keys(
            test_id=test_id,
            new_answers=answers,
            title=title,
            time_limit_min=time_limit_min,
            key_access_code=key_access_code,
            scheduled_date=scheduled_date,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            youtube_url=youtube_url
        )

        # Adminga Telegram orqali ham bildirishnoma yuborish
        try:
            t_obj = test_db.get_test_by_id(test_id)
            code_str = t_obj.get("test_code", str(test_id)) if t_obj else str(test_id)
            rec_cnt = res.get("recalculated_count", 0)
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"✏️ <b>Test #{code_str} kalitlari Mini App orqali yangilandi!</b>\n\n"
                    f"👥 <b>Qayta tekshirilgan o'quvchilar:</b> {rec_cnt} nafar\n"
                    f"🧮 <b>Rasch modeli va reyting:</b> Qayta kalibrlandi ✅\n"
                    f"📑 <b>PDF hisobot:</b> Yangilandi ✅"
                )
            )
        except Exception as e_notify:
            log.warning(f"Admin notify error on key update: {e_notify}")

        return web.json_response(res)
    except Exception as e:
        log.error(f"Update Test Keys API Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=500)

def sanitize_math_expression(val: str) -> str:
    """LaTeX formatidagi matematik ifodalarni toza Unicode formatiga o'tkazish."""
    if not isinstance(val, str):
        val = str(val)
    s = val.strip()

    # Dollar belgilarini olib tashlash ($...$ yoki $$...$$)
    s = s.replace("$", "").strip()

    # Standart LaTeX almashtirishlari
    s = re.sub(r"\\+(?:cdot|times)\b", "*", s)
    s = re.sub(r"\\+pm\b", "±", s)
    s = re.sub(r"\\+pi\b", "π", s)
    s = re.sub(r"\\+(?:degree|\^\s*\\+circ)\b", "°", s)
    s = re.sub(r"\\+(?:left|right)", "", s)
    s = re.sub(r"\\+(?:text|mathrm|mathbf)\{([^}]+)\}", r"\1", s)

    # Ildizlar: \sqrt[3]{...} -> ∛...
    s = re.sub(r"\\+sqrt\[3\]\{([^{}]+)\}", r"∛\1", s)
    s = re.sub(r"\\+sqrt\[3\]([0-9a-zA-Z]+)", r"∛\1", s)

    # Ildizlar: \sqrt{...} -> √...
    while "sqrt{" in s:
        s = re.sub(r"\\+sqrt\{([^{}]+)\}", r"√\1", s)
    s = re.sub(r"\\+sqrt([0-9a-zA-Z]+)", r"√\1", s)

    # Kasrlar: \frac{a}{b} yoki \dfrac{a}{b} -> a/b
    while re.search(r"\\+d?frac\{([^{}]+)\}\{([^{}]+)\}", s):
        s = re.sub(r"\\+d?frac\{([^{}]+)\}\{([^{}]+)\}", r"\1/\2", s)

    # Qavslar va figurali qavslarni tozalash
    s = re.sub(r"\{([^{}]+)\}", r"\1", s)

    # Ortiqcha teskari slesh (\) larni tozalash
    s = s.replace("\\", "")

    # Belgilar atrofidagi bo'shliqlarni me'yorga keltirish
    s = re.sub(r"\s*\+\s*", " + ", s)
    s = re.sub(r"\s*\-\s*", " - ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _sync_extract_keys_gemini(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    import base64
    import re
    import requests

    gemini_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or test_db.get_setting("gemini_api_key", "").strip()
    )
    if not gemini_key:
        raise ValueError("GEMINI_API_KEY o'rnatilmagan")

    prompt = (
        r"""Ushbu rasmda FIZIKA fani bo'yicha test javoblari/kalitlari varaqasi yoki jadvali berilgan.
Iltimos, rasmdagi har bir savol javobini diqqat bilan o'qib, faqat to'g'ri JSON formatida qaytar.

Test strukturasi (55 ta element):
- 1 dan 32 gacha: 4 variantli yopiq savollar (A, B, C, D)
- 33, 34, 35: 6 variantli yopiq savollar (A, B, C, D, E, F)
- 36a dan 45b gacha: ochiq javoblar. O'lchov birliklari va izohlari bilan aynan yozing (masalan: 400 J, 900 J, 4 m/s², 12 s, 9 m/s, 5 cm², 44 mm, ≈ 1450 nJ, 2400 J ga kamaydi, -800 J, 10 kV/m, ≈ 177 nC/m², 360 V, 4,8 nC, 10 cm, 22,5 cm, 2-nur (1,89 eV), hech qaysi nur).

MUHIM TALABLAR:
1. Hech qachon LaTeX (\frac, \sqrt, \cdot) ishlatma! Faqat oddiy Unicode belgilari: kasrlar (a/b), ildizlar (√), darajalar (m/s², cm²).
2. Fizika birliklarini (J, m/s, m/s², s, cm, mm, nJ, kV/m, nC, V, eV, va h.k.) va izohlarni ('ga kamaydi', 'hech qaysi nur', '2-nur') aynan rasmdagidek to'liq saqla!
3. Taqribiy belgilarni (≈) va manfiy ishoralarni (- yoki −) aniq yoz.
4. O'nlik kasrlarda vergul (,) yoki nuqta (.) ni rasmdagidek saqla.

Qaytadigan javob aynan toza JSON obyekti bo'lsin:
{
  "1": "A",
  "2": "B",
  "33": "C",
  "36a": "400 J",
  "36b": "900 J",
  "37a": "4 m/s²",
  "37b": "12 s",
  ...
  "45b": "hech qaysi nur"
}

DIQQAT: Faqat toza JSON matnini qaytar, hech qanday qo'shimcha so'z, sharh yoki izoh yozma!"""
    )

    models_to_try = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
    ]

    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"inlineData": {"mimeType": mime_type, "data": b64_data}},
                {"text": prompt}
            ]
        }]
    }

    last_err = None
    for model_name in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code != 200:
                raise ValueError(f"HTTP {resp.status_code}: {resp.text[:200]}")

            res_json = resp.json()
            candidates = res_json.get("candidates", [])
            if not candidates:
                raise ValueError("Bo'sh javob qaytdi (candidates yo'q)")

            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
            if match:
                raw_text = match.group(1).strip()
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                cleaned = {}
                for k, v in parsed.items():
                    k_clean = str(k).strip().lower().replace("q", "").replace("-savol", "").replace("savol", "").strip()
                    v_str = str(v).strip()
                    if k_clean.isdigit() and int(k_clean) <= 35:
                        v_str = v_str.upper()
                    else:
                        v_str = sanitize_math_expression(v_str)
                    cleaned[k_clean] = v_str
                if cleaned:
                    return cleaned
        except Exception as ex:
            log.warning(f"Gemini {model_name} xatosi: {ex}")
            last_err = ex
            continue

    return {}

async def handle_scan_keys_api(request):
    """Admin panel uchun javoblar varaqasi rasmidan kalitlarni OCR qilish."""
    try:
        image_bytes = None
        mime_type = "image/jpeg"

        if request.content_type.startswith("multipart/"):
            reader = await request.multipart()
            while True:
                part = await reader.next()
                if part is None:
                    break
                if part.name in ["image", "file", "photo"]:
                    image_bytes = await part.read()
                    mime_type = part.headers.get("Content-Type", "image/jpeg")
                    break
        else:
            data = await request.json()
            raw_b64 = data.get("image", "")
            if "," in raw_b64:
                header, raw_b64 = raw_b64.split(",", 1)
                if "image/png" in header:
                    mime_type = "image/png"
                elif "image/webp" in header:
                    mime_type = "image/webp"
            import base64
            image_bytes = base64.b64decode(raw_b64)

        if not image_bytes:
            return web.json_response({"success": False, "message": "Rasm topilmadi yoki yuklanmadi"}, status=400)

        loop = asyncio.get_running_loop()
        keys_dict = await loop.run_in_executor(None, _sync_extract_keys_gemini, image_bytes, mime_type)

        if not keys_dict:
            return web.json_response({
                "success": False,
                "message": "Rasmdan kalitlarni ajratib bo'lmadi. Iltimos, aniqroq yoki sifatliroq rasm yuklang."
            }, status=200)

        return web.json_response({
            "success": True,
            "data": keys_dict,
            "count": len(keys_dict),
            "message": f"Muvaffaqiyatli! {len(keys_dict)} ta kalit aniqlandi."
        })

    except Exception as e:
        log.error(f"Scan keys API Error: {e}", exc_info=True)
        is_key_err = "GEMINI_API_KEY" in str(e) or "API_KEY" in str(e) or "API key not valid" in str(e)
        return web.json_response({
            "success": False,
            "need_api_key": is_key_err,
            "message": f"OCR tahlilida xatolik: {str(e)}"
        }, status=500)

async def handle_set_gemini_key_api(request):
    """Admin uchun Gemini API kalitini bazaga saqlash."""
    try:
        data = await request.json()
        key = (data.get("key") or "").strip()
        if not key:
            return web.json_response({"success": False, "message": "API kalit kiritilmadi"}, status=400)
        test_db.set_setting("gemini_api_key", key)
        return web.json_response({"success": True, "message": "Gemini API kaliti saqlandi!"})
    except Exception as e:
        log.error(f"Set Gemini key API error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=500)


async def handle_user_chat_redirect(request):
    """
    Foydalanuvchi ID si bo'yicha Telegram chatiga xavfsiz yo'naltiruvchi sahifa.
    Telegram Bot API dagi BUTTON_URL_INVALID cheklovini to'liq aylanib o'tadi va
    foydalanuvchining shaxsiy Telegram ilovasida to'g'ridan-to'g'ri profil/chatni ochadi.
    """
    tg_id = request.match_info.get('id', '')
    html_page = f"""<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <title>Telegram Chatni Ochish</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      margin: 0;
      padding: 16px;
      box-sizing: border-box;
    }}
    .box {{
      background: #1e293b;
      border: 1px solid rgba(255,255,255,0.1);
      padding: 28px 24px;
      border-radius: 18px;
      text-align: center;
      max-width: 360px;
      width: 100%;
      box-shadow: 0 20px 40px rgba(0,0,0,0.5);
    }}
    .icon {{ font-size: 48px; margin-bottom: 12px; }}
    h2 {{ margin: 0 0 8px 0; font-size: 19px; font-weight: 800; }}
    p {{ font-size: 13px; color: #94a3b8; margin: 0 0 20px 0; line-height: 1.5; }}
    .btn {{
      display: block;
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: #ffffff;
      text-decoration: none;
      padding: 13px 20px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 14px;
      box-shadow: 0 4px 14px rgba(37,99,235,0.4);
    }}
  </style>
  <script>
    window.location.href = "tg://user?id={tg_id}";
    setTimeout(function() {{
      window.location.href = "tg://openmessage?user_id={tg_id}";
    }}, 400);
  </script>
</head>
<body>
  <div class="box">
    <div class="icon">💬</div>
    <h2>Telegram Chat Ochilmoqda</h2>
    <p>Agar Telegram ilovasi avtomatik ochilmasa, pastdagi tugmani bosing:</p>
    <a href="tg://user?id={tg_id}" class="btn">Telegramda Chatni Ochish ↗️</a>
  </div>
</body>
</html>"""
    return web.Response(text=html_page, content_type='text/html', charset='utf-8')


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'test_webapp')

# Agar test_webapp eskidan qolgan bo'lsa, joriy git fayllari xalaqitsiz ishlashi uchun tozalash
try:
    if os.path.exists(WEB_DIR):
        import shutil
        shutil.rmtree(WEB_DIR, ignore_errors=True)
except Exception:
    pass

async def find_web_file(filename: str) -> str:
    filename_clean = filename.lstrip('/')

    # Qaysi papkada ekanligini yo'l prefixi bo'yicha aniqlaymiz
    if filename_clean.startswith('js/'):
        priority_subdirs = ['js']
    elif filename_clean.startswith('css/'):
        priority_subdirs = ['css']
    elif filename_clean.startswith('img/'):
        priority_subdirs = ['img']
    else:
        priority_subdirs = []

    candidates = []

    # 1. Prioritet: to'g'ri papkada to'liq yo'l bilan qidirish
    for base in [BASE_DIR, os.getcwd()]:
        candidates.append(os.path.join(base, filename_clean))

    # 2. Prioritet subdirlar (js/, css/, img/) faqat agar yo'l prefixsiz berilgan bo'lsa
    if priority_subdirs:
        pass  # allaqachon filename_clean ichida bor
    else:
        # Oddiy fayl nomi — barcha subdirlarda qidirish
        for base in [BASE_DIR, os.getcwd()]:
            for sub in ['js', 'css', 'img']:
                candidates.append(os.path.join(base, sub, filename_clean))

    candidates.append(os.path.join(WEB_DIR, filename_clean))

    for c in candidates:
        if os.path.exists(c) and os.path.isfile(c):
            return c

    # Fallback: basename bo'yicha rekursiv qidirish (faqat to'g'ri papkada)
    target = os.path.basename(filename_clean)
    search_roots = [BASE_DIR, os.getcwd()]
    for root_dir in search_roots:
        if not os.path.exists(root_dir):
            continue
        for root, dirs, files in os.walk(root_dir):
            # .git papkasini o'tkazib yuboramiz
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules'}]
            if target in files:
                found = os.path.join(root, target)
                # js/ prefixli so'rov uchun faqat js/ papkasidagi natijani qabul qilamiz
                if filename_clean.startswith('js/') and '/js/' not in found and not found.endswith('/js/' + target):
                    continue
                if filename_clean.startswith('css/') and '/css/' not in found:
                    continue
                log.info(f"🔍 Topildi (recursive search): {found}")
                return found

    return os.path.join(BASE_DIR, filename_clean)


def set_no_cache_headers(resp):
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

async def handle_index(request):
    fpath = await find_web_file('index.html')
    if os.path.exists(fpath) and os.path.isfile(fpath):
        return set_no_cache_headers(web.FileResponse(fpath))
    try:
        import web_assets_fallback
        data, mime = web_assets_fallback.get_asset_bytes('index.html')
        if data:
            return set_no_cache_headers(web.Response(body=data, content_type=mime or 'text/html', charset='utf-8'))
    except Exception as e:
        log.error(f"index.html yuklashda xatolik: {e}")
    return web.Response(status=404, text="index.html topilmadi")

async def handle_admin(request):
    fpath = await find_web_file('admin.html')
    if os.path.exists(fpath) and os.path.isfile(fpath):
        return set_no_cache_headers(web.FileResponse(fpath))
    try:
        import web_assets_fallback
        data, mime = web_assets_fallback.get_asset_bytes('admin.html')
        if data:
            return set_no_cache_headers(web.Response(body=data, content_type=mime or 'text/html', charset='utf-8'))
    except Exception as e:
        log.error(f"admin.html yuklashda xatolik: {e}")
    return web.Response(status=404, text="admin.html topilmadi")

async def handle_app(request):
    fpath = await find_web_file('app.html')
    if os.path.exists(fpath) and os.path.isfile(fpath):
        resp = web.FileResponse(fpath)
    else:
        # Fallback ishlatilmaydi — eski app.html dan eski kod qaytib chiqmasligi uchun
        log.warning("app.html topilmadi — fallback o'chirilgan, real fayl talab etiladi")
        resp = web.Response(status=404, text="app.html topilmadi")
    return set_no_cache_headers(resp)


async def handle_static_file(request):
    path_name = request.match_info.get('path', '')
    if '..' in path_name:
        return web.Response(status=403, text="Ruxsat berilmagan yo'l")
    fpath = await find_web_file(path_name)
    if os.path.exists(fpath) and os.path.isfile(fpath):
        resp = web.FileResponse(fpath)
        if any(path_name.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.svg', '.webp', '.ico']):
            resp.headers['Cache-Control'] = 'public, max-age=86400'
        else:
            set_no_cache_headers(resp)
        return resp

    # Fallback to embedded in-memory asset
    try:
        import web_assets_fallback
        if hasattr(web_assets_fallback, 'get_asset_bytes'):
            # Eski app.js va app.html fallbackdan qaytarilmasin —
            _basename = os.path.basename(path_name)
            _STALE_SKIP = {'app.js', 'app.html', 'admin.html', 'index.html', 'physics_keyboard.js', 'math_keyboard.js', 'test_style.css'}
            if _basename not in _STALE_SKIP:
                data, mime = web_assets_fallback.get_asset_bytes(path_name)
                if data:
                    resp = web.Response(body=data, content_type=mime or 'application/octet-stream')
                    if any(path_name.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.svg', '.webp', '.ico']):
                        resp.headers['Cache-Control'] = 'public, max-age=86400'
                    else:
                        set_no_cache_headers(resp)
                    return resp
    except Exception:
        pass


    if 'apple-touch-icon' in path_name or path_name.endswith('.ico'):
        return web.Response(status=204)

    return web.Response(status=404, text="Fayl topilmadi")



# ── ASOSIY MINI APP API ENDPOINTLARI ────────────────────────────────────────

def _fetch_profile_data_sync(tg_id: int):
    user = test_db.get_user(tg_id)
    is_admin = test_db.is_admin(tg_id, ADMIN_ID)
    submissions = test_db.get_user_submissions(tg_id)
    pending_users = 0
    if is_admin:
        try:
            counts = test_db.get_users_count()
            pending_users = counts.get('pending', 0)
        except Exception:
            pass
    return user, is_admin, submissions, pending_users

async def handle_app_profile(request):
    """Foydalanuvchi profili va statistikasi (Asosiy Mini App uchun)."""
    try:
        bot_user = CACHED_BOT_USERNAME

        tg_id = int(request.rel_url.query.get('tg_id', 0))
        if not tg_id or tg_id == 0:
            return web.json_response({
                "success": True,
                "user": {
                    "tg_id": 0,
                    "fullname": "Mehmon",
                    "phone": "—",
                    "status": "not_registered",
                    "is_registered": False,
                    "registered_at": int(time.time()),
                    "tests_count": 0,
                    "avg_score": 0,
                    "max_score": 0,
                    "has_pin": False
                },
                "is_admin": False,
                "pending_users": 0,
                "bot_username": bot_user
            })

        user, is_admin, submissions, pending_users = await asyncio.to_thread(_fetch_profile_data_sync, tg_id)

        # Foydalanuvchi statistikasi
        avg_score = 0.0
        max_score_val = 0
        if submissions:
            scores = [float(s.get('score', s.get('correct_count', 0))) for s in submissions]
            avg_score = sum(scores) / len(scores) if scores else 0
            max_score_val = max(scores) if scores else 0

        if not user:
            user_data = {
                'tg_id': tg_id,
                'fullname': 'Foydalanuvchi',
                'phone': '—',
                'status': 'not_registered',
                'is_registered': False,
                'registered_at': int(time.time()),
                'tests_count': 0,
                'avg_score': 0,
                'max_score': 0,
                'has_pin': False
            }
        else:
            user_data = dict(user)
            user_data['is_registered'] = True
            user_data['tests_count'] = len(submissions)
            user_data['avg_score'] = round(avg_score, 1)
            user_data['max_score'] = max_score_val
            user_data['has_pin'] = bool(user and user.get('pin_code'))

        return web.json_response({
            "success": True,
            "user": user_data,
            "is_admin": is_admin,
            "pending_users": pending_users,
            "bot_username": bot_user
        })
    except Exception as e:
        log.error(f"App Profile API Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_set_pin(request):
    """Foydalanuvchi PIN kodini bazada saqlash."""
    try:
        data = await request.json()
        tg_id = int(data.get('tg_id', 0))
        pin = str(data.get('pin', '')).strip()
        if not tg_id or len(pin) != 4:
            return web.json_response({"success": False, "message": "4 xonali PIN kerak"}, status=400)
        await asyncio.to_thread(test_db.set_user_pin, tg_id, pin)
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_status(request):
    """Bot va server holatini (online/active) tekshirish."""
    import time
    return web.json_response({
        "success": True,
        "status": "online",
        "bot_active": True,
        "bot_username": CACHED_BOT_USERNAME,
        "server_time": int(time.time()),
        "uptime": int(time.time())
    }, headers={"Access-Control-Allow-Origin": "*"})

async def handle_app_verify_pin(request):
    """Foydalanuvchi PIN kodini bazadan tekshirish."""
    try:
        data = await request.json()
        tg_id = int(data.get('tg_id', 0))
        pin = str(data.get('pin', '')).strip()
        stored = await asyncio.to_thread(test_db.get_user_pin, tg_id)
        if stored and stored == pin:
            return web.json_response({"success": True, "valid": True})
        return web.json_response({"success": True, "valid": False})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_compare_keys(request):
    """Parol orqali test kalitlarini va o'quvchi javoblarini solishtirish."""
    try:
        data = await request.json()
        tg_id = int(data.get('tg_id', 0))
        test_id = int(data.get('test_id', 0))
        code = str(data.get('code', '')).strip()

        if not tg_id or not test_id:
            return web.json_response({"success": False, "message": "Noto'g'ri so'rov"}, status=400)

        # ── RATE LIMITING (1-3 soniya cheklovi) ─────────────────
        rate_key = f"compare_{tg_id or request.remote or 'unknown'}"
        is_allowed, retry_sec = await GLOBAL_RATE_LIMITER.check(rate_key, max_requests=1, window_seconds=2.0)
        if not is_allowed and not test_db.is_admin(tg_id or 0, ADMIN_ID):
            return web.json_response({
                "success": False,
                "retry_after": retry_sec,
                "message": f"Iltimos, {retry_sec} soniya kuting! So'rovingiz navbatda qayta ishlanmoqda..."
            }, status=429)

        async with COMPARE_CONCURRENCY_SEMAPHORE:
            test = await asyncio.to_thread(test_db.get_test_by_id, test_id)
            if not test:
                return web.json_response({"success": False, "message": "Test topilmadi"}, status=404)

            is_published = await asyncio.to_thread(test_db.is_test_results_published, test_id)
            if not is_published:
                return web.json_response({
                    "success": False, 
                    "message": "Natijalar va kalitlar admin tomonidan test yakunlanib, rasmiy e'lon qilingach ochiladi."
                }, status=403)

            expected_code = str(test.get('key_access_code', '')).strip()
            if expected_code and expected_code != code:
                return web.json_response({"success": False, "message": "Parol noto'g'ri!"}, status=403)

            sub = await asyncio.to_thread(test_db.get_user_submission_for_test, test_id, tg_id)
            if not sub:
                return web.json_response({"success": False, "message": "Siz ushbu testni topshirmagansiz"}, status=400)

            correct_answers = test_db.parse_answers_json(test.get('answers_json', '{}'))
            user_answers = test_db.parse_answers_json(sub.get('answers_json', '{}'))

            results = {}
            total_correct_closed = 0
            total_correct_open = 0

            # 1-bosqich: 1-35 yopiq savollar
            for i in range(1, 36):
                k = str(i)
                c_val = correct_answers.get(k)
                u_val = user_answers.get(k)
                is_matched, ratio, status = test_db.check_answer_match(u_val, c_val)
                if status == "correct":
                    total_correct_closed += 1
                results[k] = {
                    "status": status,
                    "user": str(u_val or "").strip(),
                    "ratio": ratio
                }

            # 2-bosqich: 36-45 ochiq savollar (36a–45b, jami 20 ta band)
            for q in range(36, 46):
                for sub_letter in ('a', 'b'):
                    k = f"{q}{sub_letter}"
                    c_val = correct_answers.get(k)
                    u_val = user_answers.get(k)
                    is_matched, ratio, status = test_db.check_answer_match(u_val, c_val)
                    if status == "correct":
                        total_correct_open += 1
                    results[k] = {
                        "status": status,
                        "user": str(u_val or "").strip(),
                        "ratio": ratio
                    }

            total_correct = total_correct_closed + total_correct_open

            # Xavfsizlik: To'g'ri kalitlar klientga yuborilmaydi, faqat tekshiruv natijasi qaytariladi
            return web.json_response({
                "success": True,
                "total_correct": total_correct,
                "total_correct_closed": total_correct_closed,
                "total_correct_open": total_correct_open,
                "total_questions": 55,
                "results": results
            })
    except Exception as e:
        log.error(f"App Compare Keys API Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

def _fetch_active_tests_payload_sync(tg_id: int):
    all_tests = test_db.get_all_tests()
    all_bounds = test_db.get_all_tests_submission_bounds()
    user_subs = test_db.get_user_submissions_map(tg_id) if tg_id else {}
    is_user_admin = bool(tg_id and test_db.is_admin(tg_id, ADMIN_ID))

    result = []
    for t in all_tests:
        td = dict(t)
        td.pop('answers_json', None)  # Javoblarni yashirish

        # Foydalanuvchi allaqachon topshirganmi?
        if tg_id:
            existing = user_subs.get(t['id'])
            td['already_submitted'] = bool(existing)
            is_pub = bool(t.get('results_published', 0))
            if existing:
                is_rej = (str(existing.get('status', '')).strip().lower() == 'rejected')
                td['is_rejected'] = is_rej
                td['submission_status'] = existing.get('status', 'valid')
                td['reject_reason'] = existing.get('reject_reason', '')
                if is_rej:
                    td['user_score'] = 0
                    td['user_correct'] = 0
                    td['user_incorrect'] = 0
                    td['user_total'] = 0
                    td['user_grade'] = "Bekor qilingan"
                elif is_pub:
                    td['user_score'] = existing.get('score')
                    td['user_correct'] = existing.get('correct_count')
                    td['user_incorrect'] = existing.get('incorrect_count')
                    td['user_total'] = existing.get('total_count')
                    td['user_grade'] = existing.get('grade')
                else:
                    td['user_score'] = None
                    td['user_correct'] = None
                    td['user_incorrect'] = None
                    td['user_total'] = None
                    td['user_grade'] = "Kutilmoqda"
                td['submitted_at'] = existing.get('submitted_at')
            else:
                td['is_rejected'] = False
        else:
            td['already_submitted'] = False
            td['is_rejected'] = False

        sched_stat = get_test_schedule_status(t)
        is_upcoming = sched_stat['is_upcoming']
        is_act = sched_stat['is_active']
        is_closed = sched_stat['is_closed']

        td['is_active'] = is_act
        td['is_upcoming'] = is_upcoming
        td['is_planned'] = is_upcoming
        td['is_closed'] = is_closed

        # Haqiqiy topshirilish vaqtlari (har bir testning o'ziga xos vaqt chegaralari)
        bounds = all_bounds.get(t['id'], {})
        if bounds.get('first_submitted_at'):
            td['first_submission_at'] = bounds['first_submitted_at']
        if bounds.get('last_submitted_at'):
            td['last_submission_at'] = bounds['last_submitted_at']
        td['submissions_count'] = bounds.get('count', 0)

        # Agar test boshlanish vaqti kelmagan bo'lsa (is_upcoming):
        if is_upcoming:
            td['code_hidden'] = True
            td['test_code'] = '🔒 Boshlanganda ochiladi'
            if td.get('title'):
                td['title'] = re.sub(r'\s*#[\w\d]+\s*$', '', td['title']).strip()
        else:
            td['code_hidden'] = False

        td['min_submit_info'] = get_test_min_submit_info(t)
        result.append(td)
    now_uzb = datetime.now(UZB_TZ)
    return result, is_user_admin, now_uzb

async def handle_app_active_tests(request):
    """Faol testlar ro'yxati (user uchun topshirilgan-topshirilmaganligini ham qaytaradi)."""
    try:
        tg_id = int(request.rel_url.query.get('tg_id', 0))
        if not tg_id:
            init_data = request.rel_url.query.get('init_data', '') or request.headers.get('X-Telegram-Init-Data', '')
            if init_data:
                import urllib.parse, json
                try:
                    parsed = dict(urllib.parse.parse_qsl(init_data))
                    if 'user' in parsed:
                        u_dict = json.loads(parsed['user'])
                        if u_dict and u_dict.get('id'):
                            tg_id = int(u_dict['id'])
                except Exception:
                    pass

        result, is_user_admin, now_uzb = await asyncio.to_thread(_fetch_active_tests_payload_sync, tg_id)
        return web.json_response({
            "success": True, 
            "tests": result,
            "is_admin": is_user_admin,
            "server_time": int(time.time()),
            "server_uzb": now_uzb.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        log.error(f"App Active Tests API Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_my_results(request):
    """Foydalanuvchining o'z test natijalari tarixi."""
    try:
        tg_id = int(request.rel_url.query.get('tg_id', 0))
        if not tg_id:
            return web.json_response({"success": True, "results": []})
        submissions = await asyncio.to_thread(test_db.get_user_submissions, tg_id)
        return web.json_response({"success": True, "results": submissions})
    except Exception as e:
        log.error(f"App My Results API Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_users(request):
    """Admin uchun barcha foydalanuvchilar ro'yxati va statistika."""
    try:
        tg_id = int(request.rel_url.query.get('tg_id', 0))
        if not tg_id or not test_db.is_admin(tg_id, ADMIN_ID):
            init_data = request.rel_url.query.get('init_data', '') or request.headers.get('X-Telegram-Init-Data', '')
            import urllib.parse, json
            try:
                parsed = dict(urllib.parse.parse_qsl(init_data))
                if 'user' in parsed:
                    u_dict = json.loads(parsed['user'])
                    if u_dict and u_dict.get('id'):
                        tg_id = int(u_dict['id'])
            except Exception:
                pass

        if not test_db.is_admin(tg_id, ADMIN_ID):
            return web.json_response({"success": False, "message": "Ruxsat yo'q"}, status=403)

        users = test_db.get_all_users()
        counts = test_db.get_users_count()
        return web.json_response({
            "success": True,
            "users": users,
            "stats": counts
        })
    except Exception as e:
        log.error(f"App Users API Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_update_user_status(request):
    """Admin tomonidan foydalanuvchi holatini (approved / pending / blocked / delete) o'zgartirish."""
    try:
        data = await request.json()
        admin_id = int(data.get('admin_id', 0))
        target_uid = int(data.get('target_uid', 0))
        action = str(data.get('status', '')).strip().lower()

        if not admin_id or not test_db.is_admin(admin_id, ADMIN_ID):
            init_data = data.get('init_data', '') or request.headers.get('X-Telegram-Init-Data', '')
            import urllib.parse, json
            try:
                parsed = dict(urllib.parse.parse_qsl(init_data))
                if 'user' in parsed:
                    u_dict = json.loads(parsed['user'])
                    if u_dict and u_dict.get('id'):
                        admin_id = int(u_dict['id'])
            except Exception:
                pass

        if not test_db.is_admin(admin_id, ADMIN_ID):
            return web.json_response({"success": False, "message": "Ruxsat yo'q"}, status=403)

        if not target_uid:
            return web.json_response({"success": False, "message": "Foydalanuvchi ID ko'rsatilmadi"}, status=400)

        if action == 'delete':
            # Foydalanuvchini bazadan butunlay o'chirish
            deleted_user = test_db.delete_user(target_uid)
            return web.json_response({"success": bool(deleted_user), "status": "deleted"})

        if action not in ['approved', 'rejected', 'blocked', 'pending']:
            return web.json_response({"success": False, "message": "Noto'g'ri amal"}, status=400)

        if action == 'approved':
            test_db.approve_user(target_uid)
            try:
                await bot.send_message(
                    chat_id=target_uid,
                    text=(
                        "🎉 <b>Xushxabar! Sizga test tizimidan to'liq foydalanishga ruxsat berildi!</b>\n\n"
                        "Endi botdagi barcha imkoniyatlar va Mini ilovadan to'siqsiz foydalanishingiz mumkin.\n"
                        "Test topshirish uchun bot menyusidan foydalaning!"
                    ),
                    reply_markup=main_menu_kb(target_uid)
                )
            except Exception:
                pass
        elif action in ['rejected', 'pending']:
            test_db.set_user_pending(target_uid)
            try:
                req_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔔 Admindan ruxsat so'rash", callback_data=f"user_req_access_{target_uid}")]
                ])
                await bot.send_message(
                    chat_id=target_uid,
                    text=(
                        "⏳ <b>Sizning botdan foydalanish huquqingiz admin tomonidan to'xtatildi!</b>\n\n"
                        "Qayta foydalanish uchun quyidagi tugma orqali adminga so'rov yuborishingiz mumkin."
                    ),
                    reply_markup=req_kb
                )
            except Exception:
                pass
        elif action == 'blocked':
            test_db.block_user(target_uid)
            try:
                await bot.send_message(
                    chat_id=target_uid,
                    text="⛔️ <b>Sizning botdan foydalanish huquqingiz admin tomonidan bekor qilindi va bloklandingiz!</b>",
                    reply_markup=ReplyKeyboardRemove()
                )
            except Exception:
                pass

        return web.json_response({"success": True, "status": action})
    except Exception as e:
        log.error(f"App Update User Status Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_update_profile(request):
    """Foydalanuvchi o'z ism va telefon raqamini tahrirlashi uchun API."""
    try:
        data = await request.json()
        tg_id = int(data.get('tg_id', 0))
        fullname = str(data.get('fullname', '')).strip()
        phone = str(data.get('phone', '')).strip()

        if not tg_id:
            init_data = data.get('init_data', '') or request.headers.get('X-Telegram-Init-Data', '')
            import urllib.parse, json
            try:
                parsed = dict(urllib.parse.parse_qsl(init_data))
                if 'user' in parsed:
                    u_dict = json.loads(parsed['user'])
                    if u_dict and u_dict.get('id'):
                        tg_id = int(u_dict['id'])
            except Exception:
                pass

        if not tg_id:
            return web.json_response({"success": False, "message": "Foydalanuvchi aniqlanmadi"}, status=400)

        if not fullname:
            return web.json_response({"success": False, "message": "Ism kiritilmadi"}, status=400)

        is_valid, err_msg = validate_fullname(fullname)
        if not is_valid:
            clean_err = re.sub(r'<[^>]+>', '', err_msg)
            return web.json_response({"success": False, "message": clean_err}, status=400)

        # Chiroyli bosh harflar bilan formatlash
        fullname = " ".join(w.capitalize() for w in fullname.split())

        ok = test_db.update_user_profile(tg_id, fullname=fullname, phone=phone if phone else None)
        return web.json_response({"success": ok})
    except Exception as e:
        log.error(f"App Update Profile Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_delete_my_account(request):
    """Foydalanuvchi o'z akkauntini o'chirish uchun API."""
    try:
        data = await request.json()
        tg_id = int(data.get('tg_id', 0))

        if not tg_id:
            init_data = data.get('init_data', '') or request.headers.get('X-Telegram-Init-Data', '')
            import urllib.parse, json
            try:
                parsed = dict(urllib.parse.parse_qsl(init_data))
                if 'user' in parsed:
                    u_dict = json.loads(parsed['user'])
                    if u_dict and u_dict.get('id'):
                        tg_id = int(u_dict['id'])
            except Exception:
                pass

        if not tg_id:
            return web.json_response({"success": False, "message": "Foydalanuvchi aniqlanmadi"}, status=400)

        user_info = test_db.delete_user(tg_id)
        if ADMIN_ID and user_info:
            try:
                fn = user_info.get("fullname", "Noma'lum")
                ph = user_info.get("phone", "—")
                un = f"@{user_info.get('username')}" if user_info.get("username") else "Mavjud emas"
                alert_text = (
                    f"🗑 <b>OGOHLANTIRISH: Foydalanuvchi akkauntini o'chirdi (Mini App)!</b>\n\n"
                    f"👤 <b>Ism:</b> {fn}\n"
                    f"📞 <b>Telefon:</b> <code>{ph}</code>\n"
                    f"🔗 <b>Username:</b> {un}\n"
                    f"🆔 <b>Telegram ID:</b> <code>{tg_id}</code>\n"
                    f"🕒 <b>Vaqt:</b> {format_uzb_time()}\n\n"
                    f"<i>Foydalanuvchi Mini ilovadagi Profil bo'limidan akkauntini o'chirdi.</i>"
                )
                await bot.send_message(chat_id=ADMIN_ID, text=alert_text)
            except Exception as ex:
                log.warning(f"Admin alert yuborishda xatolik: {ex}")
        return web.json_response({"success": bool(user_info)})
    except Exception as e:
        log.error(f"App Delete My Account Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_restrict_all_users(request):
    """Admin tomonidan barcha oddiy foydalanuvchilarni kutilmoqda (pending) holatiga o'tkazish."""
    try:
        data = await request.json()
        admin_id = int(data.get('admin_id', 0))
        if not test_db.is_admin(admin_id, ADMIN_ID):
            return web.json_response({"success": False, "message": "Ruxsat yo'q"}, status=403)

        count = test_db.restrict_all_users(ADMIN_ID)
        return web.json_response({"success": True, "count": count})
    except Exception as e:
        log.error(f"App Restrict All Users Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_broadcast(request):
    """Admin tomonidan barcha o'quvchilarga xabar yuborish (Mini App orqali)."""
    try:
        data = await request.json()
        admin_id = int(data.get('admin_id', 0))
        message_text = str(data.get('message', '')).strip()

        if not admin_id or not test_db.is_admin(admin_id, ADMIN_ID):
            init_data = data.get('init_data', '') or request.headers.get('X-Telegram-Init-Data', '')
            import urllib.parse, json
            try:
                parsed = dict(urllib.parse.parse_qsl(init_data))
                if 'user' in parsed:
                    u_dict = json.loads(parsed['user'])
                    if u_dict and u_dict.get('id'):
                        admin_id = int(u_dict['id'])
            except Exception:
                pass

        if not test_db.is_admin(admin_id, ADMIN_ID):
            return web.json_response({"success": False, "message": "Ruxsat yo'q"}, status=403)

        if not message_text:
            return web.json_response({"success": False, "message": "Xabar matni bo'sh bo'lishi mumkin emas!"}, status=400)

        # Barcha faol o'quvchilarga xabar tarqatish
        sent, fail, batch_id = await send_broadcast_to_users(message_text=message_text, sender_tg_id=admin_id)
        return web.json_response({
            "success": True,
            "sent": sent,
            "fail": fail,
            "batch_id": batch_id,
            "message": f"Xabar {sent} nafar o'quvchiga muvaffaqiyatli yetkazildi!"
        })
    except Exception as e:
        log.error(f"App Broadcast Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_app_broadcast_delete(request):
    """Admin tomonidan yuborilgan xabarni o'chirish yoki so'nggi xabarlarni tozalash (Mini App API)."""
    try:
        data = await request.json()
        admin_id = int(data.get('admin_id', 0))
        batch_id = str(data.get('batch_id', '')).strip()
        clean_count = int(data.get('clean_count', 0))

        if not admin_id or not test_db.is_admin(admin_id, ADMIN_ID):
            init_data = data.get('init_data', '') or request.headers.get('X-Telegram-Init-Data', '')
            import urllib.parse, json
            try:
                parsed = dict(urllib.parse.parse_qsl(init_data))
                if 'user' in parsed:
                    u_dict = json.loads(parsed['user'])
                    if u_dict and u_dict.get('id'):
                        admin_id = int(u_dict['id'])
            except Exception:
                pass

        if not test_db.is_admin(admin_id, ADMIN_ID):
            return web.json_response({"success": False, "message": "Ruxsat yo'q"}, status=403)

        if batch_id:
            deleted, fail = await delete_broadcast_batch_from_users(batch_id)
            return web.json_response({
                "success": True,
                "deleted": deleted,
                "fail": fail,
                "message": f"Xabar {deleted} nafar o'quvchi chatidan o'chirildi!"
            })
        elif clean_count > 0:
            deleted, users = await delete_recent_bot_messages_from_all_users(count=clean_count)
            return web.json_response({
                "success": True,
                "deleted": deleted,
                "users": users,
                "message": f"{users} nafar o'quvchidan {deleted} ta so'nggi bot xabari tozalandi!"
            })
        else:
            return web.json_response({"success": False, "message": "O'chirish parametri ko'rsatilmadi"}, status=400)
    except Exception as e:
        log.error(f"App Broadcast Delete Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=400)

async def handle_next_test_code_api(request):
    """Keyingi navbatdagi ketma-ket unikal test kodini qaytarish."""
    try:
        next_code = test_db.get_next_test_code()
        return web.json_response({"success": True, "next_code": next_code})
    except Exception as e:
        return web.json_response({"success": False, "next_code": "1", "message": str(e)})

async def handle_app_test_submissions(request):
    """Admin uchun test topshirgan barcha foydalanuvchilar va ularning tafsilotlari."""
    try:
        tg_id = int(request.rel_url.query.get('tg_id', 0))
        if not test_db.is_admin(tg_id, ADMIN_ID):
            return web.json_response({"success": False, "message": "Ruxsat yo'q"}, status=403)
        test_id = int(request.match_info.get('test_id', 0))
        subs = test_db.get_test_submissions_with_users(test_id)
        return web.json_response({"success": True, "submissions": subs})
    except Exception as e:
        log.error(f"App Test Submissions Error: {e}", exc_info=True)
        return web.json_response({"success": False, "message": str(e)}, status=500)

async def handle_rasch_evaluate_api(request):
    try:
        test_id = int(request.match_info.get('test_id', 0))
        tg_id = int(request.rel_url.query.get('tg_id', 0))
        is_adm = test_db.is_admin(tg_id, ADMIN_ID) if tg_id else False
        is_pub = test_db.is_test_results_published(test_id)

        if not is_adm and not is_pub:
            return web.json_response({
                "success": False,
                "message": "Ushbu test natijalari hali e'lon qilinmagan yoki ruxsat yo'q"
            }, status=403)

        res = test_db.evaluate_test_rasch(test_id)
        if not res:
            return web.json_response({"success": False, "message": "Kamida 2 ta talaba topshirgan bo'lishi kerak yoki test topilmadi"}, status=400)
        return web.json_response({"success": True, "data": res})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=500)

async def handle_app_trigger_solve(request):
    """Mini ilovadan 'Testni yechish' bosilganda Telegram chatga test kartasini yuborish."""
    try:
        tg_id = 0
        test_code = ""
        test_id_str = ""

        if request.query.get("tg_id"):
            try:
                tg_id = int(request.query.get("tg_id", 0))
            except Exception:
                pass
        test_code = request.query.get("test_code", "").strip()
        test_id_str = request.query.get("test_id", "").strip()

        if not tg_id and request.method == "POST":
            try:
                if request.content_type == "application/json":
                    body = await request.json()
                else:
                    body = await request.post()
                if body.get("tg_id"):
                    tg_id = int(body.get("tg_id"))
                if not test_code:
                    test_code = str(body.get("test_code", "")).strip()
                if not test_id_str:
                    test_id_str = str(body.get("test_id", "")).strip()
            except Exception:
                pass

        if not tg_id:
            return web.json_response({"ok": False, "error": "Foydalanuvchi ID si topilmadi"}, status=400)

        test = None
        if test_code:
            code_clean = test_code.upper().replace("#", "")
            test = test_db.get_test_by_code(code_clean)
        if not test and test_id_str and test_id_str.isdigit():
            test = test_db.get_test_by_id(int(test_id_str))

        if not test:
            return web.json_response({"ok": False, "error": "Test topilmadi"}, status=404)

        sched_stat = get_test_schedule_status(test)
        if sched_stat["is_upcoming"] and not test_db.is_admin(tg_id, ADMIN_ID):
            sdate = test.get('scheduled_date') or 'Bugun'
            sstart = test.get('scheduled_start') or ''
            return web.json_response({
                "ok": False, 
                "error": f"Test hali boshlanmagan! Boshlanish vaqti: {sdate} {sstart} (UZB)"
            }, status=400)

        # Telegram chatga testni taqdim etish (asinxron)
        asyncio.create_task(send_test_card_to_user_chat(tg_id, test))
        return web.json_response({"ok": True, "message": "Test chatga yuborildi"})
    except Exception as e:
        log.error(f"handle_app_trigger_solve xatolik: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500)

# ──────────────────────────────────────────────────────────
# MACBOOK DASHBOARD HANDLERS
# ──────────────────────────────────────────────────────────

async def handle_dashboard(request):
    fpath = await find_web_file('dashboard.html')
    if os.path.exists(fpath) and os.path.isfile(fpath):
        return set_no_cache_headers(web.FileResponse(fpath))
    try:
        import web_assets_fallback
        data, mime = web_assets_fallback.get_asset_bytes('dashboard.html')
        if data:
            return set_no_cache_headers(web.Response(body=data, content_type=mime or 'text/html', charset='utf-8'))
    except Exception as e:
        log.error(f"dashboard.html yuklashda xatolik: {e}")
    return web.Response(status=404, text="dashboard.html topilmadi")

_dashboard_overview_cache = {"data": None, "ts": 0}
_dashboard_users_cache = {"data": None, "ts": 0}
_dashboard_tests_cache = {"data": None, "ts": 0}

def invalidate_dashboard_cache():
    """Barcha dashboard keshlarini darhol tozalash."""
    global _dashboard_overview_cache, _dashboard_users_cache, _dashboard_tests_cache
    _dashboard_overview_cache["data"] = None
    _dashboard_overview_cache["ts"] = 0
    _dashboard_users_cache["data"] = None
    _dashboard_users_cache["ts"] = 0
    _dashboard_tests_cache["data"] = None
    _dashboard_tests_cache["ts"] = 0

test_db.register_cache_invalidator(invalidate_dashboard_cache)

async def handle_dashboard_overview(request):
    global _dashboard_overview_cache
    now = time.time()
    refresh = request.rel_url.query.get('refresh') == 'true'
    is_live = request.rel_url.query.get('live') == 'true'

    # Agar live yoki refresh bo'lmasa, 30 soniyalik keshdan beramiz
    if not refresh and not is_live and _dashboard_overview_cache["data"] and (now - _dashboard_overview_cache["ts"] < 30.0):
        return web.json_response(_dashboard_overview_cache["data"])

    # Agar live so'rov kelsa va kesh 2 soniyadan kam bo'lsa, tezkor javob qaytaramiz (yuklamani kamaytirish uchun)
    if is_live and _dashboard_overview_cache["data"] and (now - _dashboard_overview_cache["ts"] < 2.0):
        return web.json_response(_dashboard_overview_cache["data"])

    try:
        summary, recent_subs, recent_users, logs, tests = await asyncio.gather(
            asyncio.to_thread(test_db.get_dashboard_summary),
            asyncio.to_thread(test_db.get_recent_submissions, 15),
            asyncio.to_thread(test_db.get_recent_users, 15),
            asyncio.to_thread(test_db.get_activity_logs, 80),
            asyncio.to_thread(test_db.get_tests_with_stats)
        )
        for s in recent_subs:
            s['submitted_at_fmt'] = format_uzb_time(s.get('submitted_at'), fmt="%d.%m.%Y %H:%M:%S")
        for u in recent_users:
            u['registered_at_fmt'] = format_uzb_time(u.get('registered_at'), fmt="%d.%m.%Y %H:%M:%S")
        for l in logs:
            l['time_fmt'] = format_uzb_time(l.get('time'), fmt="%d.%m.%Y %H:%M:%S")
            
        for t in tests:
            if t.get('created_at'):
                t['created_at_fmt'] = format_uzb_time(t.get('created_at'), fmt="%d.%m.%Y %H:%M")
        resp_data = {
            "success": True,
            "summary": summary,
            "recent_users": recent_users,
            "recent_submissions": recent_subs,
            "activity_logs": logs,
            "tests": tests,
            "server_time": format_uzb_time(fmt="%d.%m.%Y %H:%M:%S")
        }
        _dashboard_overview_cache["data"] = resp_data
        _dashboard_overview_cache["ts"] = now
        return web.json_response(resp_data)
    except Exception as e:
        log.error(f"Dashboard overview error: {e}", exc_info=True)
        if _dashboard_overview_cache["data"]:
            return web.json_response(_dashboard_overview_cache["data"])
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_submissions(request):
    try:
        limit = int(request.rel_url.query.get('limit', 1000))
        subs = await asyncio.to_thread(test_db.get_all_submissions_for_admin, limit)
        for s in subs:
            s['submitted_at_fmt'] = format_uzb_time(s.get('submitted_at'), fmt="%d.%m.%Y %H:%M:%S")
        return web.json_response({
            "success": True,
            "total": len(subs),
            "submissions": subs
        })
    except Exception as e:
        log.error(f"Dashboard submissions error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_submission_detail(request):
    try:
        sub_id = int(request.match_info.get('id', 0))
        detail = await asyncio.to_thread(test_db.get_submission_details_for_admin, sub_id)
        if not detail:
            return web.json_response({"success": False, "error": "Natija topilmadi"}, status=404)
        
        detail['submitted_at_fmt'] = format_uzb_time(detail.get('submitted_at'), fmt="%d.%m.%Y %H:%M:%S")
        try:
            if isinstance(detail.get('details_json'), str):
                detail['details'] = json.loads(detail['details_json'])
            else:
                detail['details'] = detail.get('details_json') or {}
        except Exception:
            detail['details'] = {}
            
        try:
            if isinstance(detail.get('answers_json'), str):
                detail['answers'] = json.loads(detail['answers_json'])
            else:
                detail['answers'] = detail.get('answers_json') or {}
        except Exception:
            detail['answers'] = {}

        return web.json_response({
            "success": True,
            "submission": detail
        })
    except Exception as e:
        log.error(f"Dashboard submission detail error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_user_submissions(request):
    try:
        user_tg_id = int(request.match_info.get('tg_id', 0))
        subs = await asyncio.to_thread(test_db.get_user_results, user_tg_id)
        for s in subs:
            s['submitted_at_fmt'] = format_uzb_time(s.get('submitted_at'), fmt="%d.%m.%Y %H:%M:%S")
        return web.json_response({
            "success": True,
            "submissions": subs
        })
    except Exception as e:
        log.error(f"Dashboard user submissions error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_users(request):
    global _dashboard_users_cache
    now = time.time()
    if _dashboard_users_cache["data"] and (now - _dashboard_users_cache["ts"] < 15.0):
        return web.json_response(_dashboard_users_cache["data"])
    try:
        users, counts = await asyncio.gather(
            asyncio.to_thread(test_db.get_all_users),
            asyncio.to_thread(test_db.get_users_count)
        )
        for u in users:
            u['registered_at_fmt'] = format_uzb_time(u.get('registered_at'), fmt="%d.%m.%Y %H:%M") if u.get('registered_at') else "—"
            u['last_test_at_fmt'] = format_uzb_time(u.get('last_test_at'), fmt="%d.%m.%Y %H:%M") if u.get('last_test_at') else "—"
        resp_data = {
            "success": True,
            "users": users,
            "stats": counts
        }
        _dashboard_users_cache["data"] = resp_data
        _dashboard_users_cache["ts"] = now
        return web.json_response(resp_data)
    except Exception as e:
        log.error(f"Dashboard users error: {e}", exc_info=True)
        if _dashboard_users_cache["data"]:
            return web.json_response(_dashboard_users_cache["data"])
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_tests(request):
    global _dashboard_tests_cache
    now = time.time()
    if _dashboard_tests_cache["data"] and (now - _dashboard_tests_cache["ts"] < 15.0):
        return web.json_response(_dashboard_tests_cache["data"])
    try:
        tests = await asyncio.to_thread(test_db.get_tests_with_stats)
        for t in tests:
            if t.get('created_at'):
                t['created_at_fmt'] = format_uzb_time(t.get('created_at'), fmt="%d.%m.%Y %H:%M")
        resp_data = {
            "success": True,
            "tests": tests
        }
        _dashboard_tests_cache["data"] = resp_data
        _dashboard_tests_cache["ts"] = now
        return web.json_response(resp_data)
    except Exception as e:
        log.error(f"Dashboard tests error: {e}", exc_info=True)
        if _dashboard_tests_cache["data"]:
            return web.json_response(_dashboard_tests_cache["data"])
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_logs(request):
    try:
        limit = int(request.rel_url.query.get('limit', 100))
        logs = await asyncio.to_thread(test_db.get_activity_logs, limit)
        for l in logs:
            l['time_fmt'] = format_uzb_time(l.get('time'), fmt="%d.%m.%Y %H:%M:%S")
        return web.json_response({
            "success": True,
            "logs": logs
        })
    except Exception as e:
        log.error(f"Dashboard logs error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_user_action(request):
    try:
        data = await request.json()
        target_uid = int(data.get('user_id', 0))
        action = str(data.get('action', '')).strip().lower()
        if not target_uid:
            return web.json_response({"success": False, "error": "Foydalanuvchi ID ko'rsatilmadi"}, status=400)
            
        if action == 'approve':
            test_db.approve_user(target_uid)
            msg = "Foydalanuvchi faollashtirildi"
        elif action == 'block':
            test_db.block_user(target_uid)
            msg = "Foydalanuvchi bloklandi"
        elif action == 'pending':
            test_db.set_user_pending(target_uid)
            msg = "Foydalanuvchi kutilmoqda holatiga o'tkazildi"
        elif action == 'delete':
            test_db.delete_user(target_uid)
            msg = "Foydalanuvchi bazadan o'chirildi"
        else:
            return web.json_response({"success": False, "error": f"Noma'lum amal: {action}"}, status=400)
            
        return web.json_response({"success": True, "message": msg})
    except Exception as e:
        log.error(f"Dashboard user action error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_late_action(request):
    try:
        data = await request.json()
        sub_id = int(data.get('submission_id', 0))
        action = str(data.get('action', '')).strip().lower()
        if not sub_id:
            return web.json_response({"success": False, "error": "Submission ID ko'rsatilmadi"}, status=400)
            
        if action == 'accept':
            test_db.set_submission_late_status(sub_id, 0)
            msg = "Kech topshirilgan natija testga qabul qilindi!"
        elif action == 'reject':
            test_db.set_submission_late_status(sub_id, 1)
            msg = "Natija hisobga olinmaydigan (kechikkan) deb belgilandi."
        else:
            return web.json_response({"success": False, "error": "Noma'lum amal"}, status=400)
            
        return web.json_response({"success": True, "message": msg})
    except Exception as e:
        log.error(f"Dashboard late action error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_cancel_submission(request):
    """
    O'quvchining test javobini bekor qilish amallari:
    1. action == 'reject': Javobni qabul qilmaslik (rad etish, qayta topshira olmaydi)
    2. action == 'allow_retake': Qayta topshirish (avvalgi javob o'chiriladi, qayta topshira oladi)
    Ikkala holatda ham o'quvchining Telegram chatiga xabar boradi.
    """
    try:
        data = await request.json()
        sub_id = int(data.get('submission_id', 0))
        action = str(data.get('action', '')).strip().lower()
        reason = str(data.get('reason', '')).strip()

        if not sub_id:
            return web.json_response({"success": False, "error": "Submission ID ko'rsatilmadi"}, status=400)
        if action not in ['reject', 'allow_retake']:
            return web.json_response({"success": False, "error": "Noto'g'ri amal turi (reject yoki allow_retake)"}, status=400)

        sub = test_db.get_submission_by_id(sub_id)
        if not sub:
            return web.json_response({"success": False, "error": "Topshirilgan natija topilmadi"}, status=404)

        user_tg_id = sub.get('user_tg_id')
        fullname = sub.get('fullname', 'Foydalanuvchi')
        test_id = sub.get('test_id')
        test_code = sub.get('test_code', '')
        test_obj = test_db.get_test_by_id(test_id) if test_id else None
        test_title = test_obj.get('title', f"Test #{test_code}") if test_obj else f"Test #{test_code}"

        if action == 'reject':
            # 1. Javobni qabul qilmaslik (rad etish)
            success = test_db.reject_submission(sub_id, reason=reason)
            if not success:
                return web.json_response({"success": False, "error": "Natijani rad etishda xatolik yuz berdi"}, status=500)

            user_msg = (
                f"⛔️ <b>DIQQAT: TEST JAVOBLARINGIZ QABUL QILINMADI!</b>\n\n"
                f"Hurmatli <b>{fullname}</b>!\n\n"
                f"Sizning <b>«{test_title}»</b> (Kod: <code>#{test_code}</code>) testi bo'yicha topshirgan javoblaringiz ma'muriyat tomonidan bekor qilindi va <b>qabul qilinmadi</b>.\n\n"
                f"ℹ️ <i>Izoh: Ushbu test natijangiz hisobga olinmaydi. Qayta topshirishga ruxsat berilmagan.</i>\n\n"
                f"Savollaringiz bo'lsa administrator bilan bog'lanishingiz mumkin."
            )
            admin_msg = f"{fullname}ning javoblari qabul qilinmadi (rad etildi)."

        elif action == 'allow_retake':
            # 2. Qayta topshirish (avvalgi javob o'chiriladi, yangidan topshira oladi)
            success = test_db.delete_submission(sub_id)
            if not success:
                return web.json_response({"success": False, "error": "Natijani o'chirishda xatolik yuz berdi"}, status=500)

            user_msg = (
                f"🔄 <b>DIQQAT: TESTNI QAYTA TOPSHIRISHINGIZ MUMKIN!</b>\n\n"
                f"Hurmatli <b>{fullname}</b>!\n\n"
                f"Sizning <b>«{test_title}»</b> (Kod: <code>#{test_code}</code>) testi bo'yicha topshirgan avvalgi javoblaringiz ma'muriyat tomonidan bekor qilindi va sizga testni <b>QAYTA TOPSHIRISHGA RUXSAT BERILDI!</b> ✅\n\n"
                f"Endi botimiz (@fizika_rash_testbot) va Mini ilova orqali testga qaytadan kirib, barcha savollarni boshidan ishlab topshirishingiz mumkin.\n\n"
                f"Omad tilaymiz! 🚀"
            )
            admin_msg = f"{fullname}ning avvalgi javoblari o'chirildi va unga qayta topshirishga ruxsat berildi."

        # Foydalanuvchining shaxsiy Telegram chatiga xabar yuborish
        sent_to_user = False
        try:
            if user_tg_id and int(user_tg_id) > 0:
                await bot.send_message(chat_id=int(user_tg_id), text=user_msg)
                sent_to_user = True
        except Exception as e:
            log.warning(f"Foydalanuvchiga ({user_tg_id}) xabar jo'natishda xatolik: {e}")

        # Audit jurnaliga yozish
        try:
            test_db.log_activity(
                action=f"submission_{action}",
                details=f"Test #{test_code} (Sub ID: {sub_id}) - {fullname} (ID: {user_tg_id}) amali: {action}. Userga xabar: {'yetkazildi' if sent_to_user else 'yetkazilmadi'}",
                actor="admin"
            )
        except Exception:
            pass

        return web.json_response({
            "success": True,
            "message": admin_msg,
            "sent_to_user": sent_to_user,
            "action": action
        })
    except Exception as e:
        log.error(f"Dashboard cancel submission error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_test_toggle(request):
    try:
        data = await request.json()
        test_id = int(data.get('test_id', 0))
        new_status = test_db.toggle_test_status(test_id)
        return web.json_response({
            "success": True,
            "is_active": new_status,
            "message": "Test faollashtirildi" if new_status == 1 else "Test to'xtatildi"
        })
    except Exception as e:
        log.error(f"Dashboard test toggle error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_test_publish(request):
    try:
        data = await request.json()
        test_id = int(data.get('test_id', 0))
        t = test_db.get_test_by_id(test_id)
        if not t:
            return web.json_response({"success": False, "error": "Test topilmadi"}, status=404)
        cur_pub = t.get('results_published', 0)
        new_pub = 0 if cur_pub == 1 else 1
        test_db.set_test_results_published(test_id, new_pub)
        if new_pub == 1:
            pub_id = int(data.get("admin_id") or data.get("tg_id") or ADMIN_ID)
            asyncio.create_task(notify_admins_test_results_published(test_id, pub_id, eval_type="rasch"))
        return web.json_response({
            "success": True,
            "results_published": new_pub,
            "message": "Natijalar e'lon qilindi!" if new_pub == 1 else "Natijalar e'loni yashirildi"
        })
    except Exception as e:
        log.error(f"Dashboard test publish error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_dashboard_query(request):
    try:
        data = await request.json()
        query = str(data.get('query', '')).strip()
        res = test_db.execute_admin_safe_query(query, limit=100)
        return web.json_response(res)
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=400)


async def handle_dashboard_warn_user(request):
    """Bitta foydalanuvchiga Telegram orqali rasmiy ogohlantirish xabari yuborish."""
    try:
        data = await request.json()
        tg_id = int(data.get('tg_id', 0))
        tests_count = int(data.get('tests_count', 0))
        if not tg_id:
            return web.json_response({"success": False, "error": "tg_id ko'rsatilmadi"}, status=400)

        user = await asyncio.to_thread(test_db.get_user, tg_id)
        fname = user.get("fullname") if user else "Foydalanuvchi"

        if tests_count == 0:
            text = (
                "⚠️ <b>RASMIY OGOHLANTIRISH</b>\n\n"
                f"Hurmatli <b>{fname}</b>!\n\n"
                "Siz tizimimizda ro'yxatdan o'tgan bo'lsangiz-da, shu kunga qadar <b>birorta ham test ishlamadingiz</b> "
                "va sizga berilgan bepul imkoniyatdan foydalanmadingiz.\n\n"
                "📌 <b>Muhim eslatma:</b> Bugungi bo'lib o'tadigan testda ham qatnashmasangiz, faoliyatsizligingiz sababli sizni "
                "<b>botdan va tizimdan chiqarib yuborishga</b> majbur bo'lamiz.\n\n"
                "<i>O'z o'rningizni saqlab qolish va bilimingizni sinash uchun bugungi testda albatta ishtirok eting!</i>"
            )
        else:
            text = (
                "⚠️ <b>RASMIY OGOHLANTIRISH</b>\n\n"
                f"Hurmatli <b>{fname}</b>!\n\n"
                f"Siz shu kunga qadar faqat <b>{tests_count} ta test</b> ishladingiz va sizga taqdim etilgan bepul imkoniyatlardan "
                "to'liq foydalanmadingiz.\n\n"
                "📌 <b>Muhim eslatma:</b> Bugungi bo'lib o'tadigan testda ham qatnashmasangiz, faoliyatsizligingiz sababli sizni "
                "<b>botdan va tizimdan chiqarib yuborishga</b> majbur bo'lamiz.\n\n"
                "<i>O'z o'rningizni saqlab qolish va natijalaringizni oshirish uchun bugungi testda albatta ishtirok eting!</i>"
            )

        try:
            await bot.send_message(chat_id=tg_id, text=text, parse_mode=ParseMode.HTML)
            return web.json_response({
                "success": True,
                "message": f"✅ {fname} ({tg_id}) ga rasmiy ogohlantirish xabari yetkazildi!"
            })
        except Exception as e:
            err_text = str(e).lower()
            if "blocked" in err_text or "forbidden" in err_text or "deactivated" in err_text:
                await asyncio.to_thread(test_db.delete_user, tg_id)
                return web.json_response({
                    "success": False,
                    "blocked": True,
                    "message": f"🚫 Foydalanuvchi botni bloklagani aniqlandi va bazadan o'chirildi!"
                })
            return web.json_response({
                "success": False,
                "error": f"Telegram xatolik: {e}"
            }, status=500)
    except Exception as e:
        log.error(f"Dashboard warn user error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_dashboard_warn_users_batch(request):
    """Filtrdagi barcha foydalanuvchilarga rasmiy ogohlantirish xabari yuborish."""
    try:
        data = await request.json()
        users_list = data.get('users', [])
        if not users_list:
            return web.json_response({"success": False, "error": "Foydalanuvchilar ro'yxati bo'sh"}, status=400)

        sent_count = 0
        failed_count = 0
        deleted_count = 0

        for item in users_list:
            tg_id = int(item.get('tg_id', 0))
            if not tg_id:
                continue
            tests_count = int(item.get('tests_count', 0))
            fname = item.get('fullname') or "Foydalanuvchi"

            if tests_count == 0:
                text = (
                    "⚠️ <b>RASMIY OGOHLANTIRISH</b>\n\n"
                    f"Hurmatli <b>{fname}</b>!\n\n"
                    "Siz tizimimizda ro'yxatdan o'tgan bo'lsangiz-da, shu kunga qadar <b>birorta ham test ishlamadingiz</b> "
                    "va sizga berilgan bepul imkoniyatdan foydalanmadingiz.\n\n"
                    "📌 <b>Muhim eslatma:</b> Bugungi bo'lib o'tadigan testda ham qatnashmasangiz, faoliyatsizligingiz sababli sizni "
                    "<b>botdan va tizimdan chiqarib yuborishga</b> majbur bo'lamiz.\n\n"
                    "<i>O'z o'rningizni saqlab qolish va bilimingizni sinash uchun bugungi testda albatta ishtirok eting!</i>"
                )
            else:
                text = (
                    "⚠️ <b>RASMIY OGOHLANTIRISH</b>\n\n"
                    f"Hurmatli <b>{fname}</b>!\n\n"
                    f"Siz shu kunga qadar faqat <b>{tests_count} ta test</b> ishladingiz va sizga taqdim etilgan bepul imkoniyatlardan "
                    "to'liq foydalanmadingiz.\n\n"
                    "📌 <b>Muhim eslatma:</b> Bugungi bo'lib o'tadigan testda ham qatnashmasangiz, faoliyatsizligingiz sababli sizni "
                    "<b>botdan va tizimdan chiqarib yuborishga</b> majbur bo'lamiz.\n\n"
                    "<i>O'z o'rningizni saqlab qolish va natijalaringizni oshirish uchun bugungi testda albatta ishtirok eting!</i>"
                )

            try:
                await bot.send_message(chat_id=tg_id, text=text, parse_mode=ParseMode.HTML)
                sent_count += 1
                await asyncio.sleep(0.04)
            except Exception as e:
                err_text = str(e).lower()
                if "blocked" in err_text or "forbidden" in err_text or "deactivated" in err_text:
                    await asyncio.to_thread(test_db.delete_user, tg_id)
                    deleted_count += 1
                else:
                    failed_count += 1

        del_msg = f" ({deleted_count} ta bloklagan akkaunt o'chirildi)" if deleted_count else ""
        return web.json_response({
            "success": True,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "deleted_count": deleted_count,
            "message": f"✅ {sent_count} nafar foydalanuvchiga ogohlantirish muvaffaqiyatli yetkazildi!{del_msg}"
        })
    except Exception as e:
        log.error(f"Dashboard warn users batch error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_notify_inactive_users(request):
    try:
        data = {}
        try:
            data = await request.json()
        except Exception:
            pass
        admin_id = int(data.get('admin_id', 0) or request.rel_url.query.get('admin_id', 0))
        secret_key = str(data.get('secret_key', '') or request.rel_url.query.get('secret_key', '')).strip()
        target_count = str(data.get('target_count', '') or request.rel_url.query.get('target_count', 'both')).strip()
        time_filter = str(data.get('time_filter', '') or request.rel_url.query.get('time_filter', 'min_2d')).strip()

        is_auth = (admin_id and test_db.is_admin(admin_id, ADMIN_ID)) or (secret_key == "rash_admin_secret_2026") or (admin_id == ADMIN_ID)
        if not is_auth:
            return web.json_response({"success": False, "message": "Ruxsat yo'q"}, status=403)

        result = await send_inactive_warning_messages(
            initiator_id=admin_id or ADMIN_ID,
            target_count=target_count,
            time_filter=time_filter
        )
        return web.json_response(result)
    except Exception as e:
        log.error(f"Notify inactive users error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_clean_blocked_users(request):
    try:
        data = {}
        try:
            data = await request.json()
        except Exception:
            pass
        admin_id = int(data.get('admin_id', 0) or request.rel_url.query.get('admin_id', 0))
        secret_key = str(data.get('secret_key', '') or request.rel_url.query.get('secret_key', '')).strip()

        is_auth = (admin_id and test_db.is_admin(admin_id, ADMIN_ID)) or (secret_key == "rash_admin_secret_2026") or (admin_id == ADMIN_ID)
        if not is_auth:
            return web.json_response({"success": False, "message": "Ruxsat yo'q"}, status=403)

        result = await clean_blocked_users_from_db(initiator_id=admin_id or ADMIN_ID)
        return web.json_response(result)
    except Exception as e:
        log.error(f"Clean blocked users error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def _dispatch_broadcast_task(log_id: int, target_user_ids: List[int], message_text: str, reply_markup=None):
    sent_count = 0
    failed_count = 0
    sem = asyncio.Semaphore(15)

    async def _send_to_one(uid: int):
        nonlocal sent_count, failed_count
        async with sem:
            try:
                await bot.send_message(
                    chat_id=uid,
                    text=message_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    disable_web_page_preview=False
                )
                sent_count += 1
            except TelegramRetryAfter as e:
                try:
                    await asyncio.sleep(min(float(e.retry_after), 3.0))
                    await bot.send_message(
                        chat_id=uid,
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup,
                        disable_web_page_preview=False
                    )
                    sent_count += 1
                except Exception:
                    failed_count += 1
            except Exception:
                failed_count += 1
            finally:
                await asyncio.sleep(0.04)

    batch_size = 25
    for i in range(0, len(target_user_ids), batch_size):
        chunk = target_user_ids[i:i + batch_size]
        await asyncio.gather(*[_send_to_one(uid) for uid in chunk], return_exceptions=True)

    status = "completed" if failed_count < len(target_user_ids) else "failed"
    await asyncio.to_thread(test_db.update_broadcast_log, log_id, sent_count, failed_count, status)
    log.info(f"Broadcast #{log_id} yakunlandi: {sent_count} muvaffaqiyatli, {failed_count} xato")


async def handle_dashboard_broadcast_history(request):
    try:
        limit = int(request.rel_url.query.get('limit', 50))
        logs = await asyncio.to_thread(test_db.get_broadcast_logs, limit)
        for l in logs:
            l['created_at_fmt'] = format_uzb_time(l.get('created_at'), fmt="%d.%m.%Y %H:%M:%S")
        return web.json_response({
            "success": True,
            "logs": logs
        })
    except Exception as e:
        log.error(f"Dashboard broadcast history error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_dashboard_broadcast_audience_count(request):
    try:
        target = request.rel_url.query.get('target', 'all')
        target_param = request.rel_url.query.get('target_param', None)
        cnt = await asyncio.to_thread(test_db.get_broadcast_audience_count, target, target_param)
        return web.json_response({
            "success": True,
            "target": target,
            "count": cnt
        })
    except Exception as e:
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def handle_dashboard_broadcast_send(request):
    try:
        data = await request.json()
        title = str(data.get('title', 'Telegram Xabarnoma')).strip()
        msg_text = str(data.get('message', '')).strip()
        target = str(data.get('target', 'all')).strip().lower()
        target_param = str(data.get('target_param', '')).strip() or None
        btn_text = str(data.get('btn_text', '')).strip()
        btn_url = str(data.get('btn_url', '')).strip()

        if not msg_text:
            return web.json_response({"success": False, "error": "Xabar matni kiritilmagan!"}, status=400)

        # Inline tugma agar mavjud bo'lsa
        reply_markup = None
        if btn_text and btn_url:
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=btn_text, url=btn_url)]
            ])

        target_user_ids = await asyncio.to_thread(test_db.get_broadcast_target_users, target, target_param)
        target_count = len(target_user_ids)

        if target_count == 0:
            return web.json_response({
                "success": False,
                "error": "Tanlangan guruhda foydalanuvchilar topilmadi!"
            }, status=400)

        target_desc = target
        if target == 'test' and target_param:
            target_desc = f"test:{target_param}"

        log_id = await asyncio.to_thread(
            test_db.create_broadcast_log,
            title or "Ommaviy Xabar",
            msg_text,
            target_desc,
            target_count,
            "in_progress"
        )

        asyncio.create_task(_dispatch_broadcast_task(log_id, target_user_ids, msg_text, reply_markup))

        return web.json_response({
            "success": True,
            "log_id": log_id,
            "target_count": target_count,
            "message": f"Xabar {target_count} nafar foydalanuvchiga yuborish navbatiga qo'yildi!"
        })
    except Exception as e:
        log.error(f"Dashboard broadcast send error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)}, status=500)


async def create_web_app():
    app = web.Application()
    app.router.add_post('/api/admin/clean-blocked-users', handle_clean_blocked_users)
    app.router.add_get('/api/admin/clean-blocked-users', handle_clean_blocked_users)
    app.router.add_post('/api/admin/notify-inactive-users', handle_notify_inactive_users)
    app.router.add_get('/api/admin/notify-inactive-users', handle_notify_inactive_users)
    app.router.add_get('/', handle_index)
    app.router.add_get('/index.html', handle_index)
    app.router.add_get('/admin.html', handle_admin)
    app.router.add_get('/app.html', handle_app)
    app.router.add_get('/user-chat/{id}', handle_user_chat_redirect)
    
    # MacBook Desktop Dashboard
    app.router.add_get('/dashboard', handle_dashboard)
    app.router.add_get('/dashboard.html', handle_dashboard)
    app.router.add_get('/api/dashboard/overview', handle_dashboard_overview)
    app.router.add_get('/api/dashboard/submissions', handle_dashboard_submissions)
    app.router.add_get('/api/dashboard/submission/{id}', handle_dashboard_submission_detail)
    app.router.add_get('/api/dashboard/users', handle_dashboard_users)
    app.router.add_get('/api/dashboard/user-submissions/{tg_id}', handle_dashboard_user_submissions)
    app.router.add_get('/api/dashboard/tests', handle_dashboard_tests)
    app.router.add_get('/api/dashboard/logs', handle_dashboard_logs)
    app.router.add_post('/api/dashboard/user-action', handle_dashboard_user_action)
    app.router.add_post('/api/dashboard/late-action', handle_dashboard_late_action)
    app.router.add_post('/api/dashboard/submissions/cancel', handle_dashboard_cancel_submission)
    app.router.add_post('/api/dashboard/test-toggle', handle_dashboard_test_toggle)
    app.router.add_post('/api/dashboard/test-publish', handle_dashboard_test_publish)
    app.router.add_post('/api/dashboard/query', handle_dashboard_query)
    app.router.add_post('/api/dashboard/warn-user', handle_dashboard_warn_user)
    app.router.add_post('/api/dashboard/warn-users-batch', handle_dashboard_warn_users_batch)
    app.router.add_get('/api/dashboard/broadcast/history', handle_dashboard_broadcast_history)
    app.router.add_get('/api/dashboard/broadcast/audience-count', handle_dashboard_broadcast_audience_count)
    app.router.add_post('/api/dashboard/broadcast/send', handle_dashboard_broadcast_send)

    app.router.add_get('/api/rasch/{test_id}', handle_rasch_evaluate_api)
    app.router.add_post('/api/submit-test', handle_submit_test_api)
    app.router.add_post('/api/create-test', handle_create_test_api)
    app.router.add_get('/api/admin/get-test-keys', handle_admin_get_test_keys)
    app.router.add_post('/api/admin/update-test-keys', handle_admin_update_test_keys)
    app.router.add_post('/api/scan-keys', handle_scan_keys_api)
    app.router.add_post('/api/set-gemini-key', handle_set_gemini_key_api)
    # Asosiy Mini App API
    app.router.add_get('/api/app/profile', handle_app_profile)
    app.router.add_post('/api/app/update-profile', handle_app_update_profile)
    app.router.add_post('/api/app/delete-my-account', handle_app_delete_my_account)
    app.router.add_get('/api/app/active-tests', handle_app_active_tests)
    app.router.add_get('/api/app/test-submissions/{test_id}', handle_app_test_submissions)
    app.router.add_get('/api/app/my-results', handle_app_my_results)
    app.router.add_get('/api/app/trigger-solve', handle_app_trigger_solve)
    app.router.add_post('/api/app/trigger-solve', handle_app_trigger_solve)
    app.router.add_get('/api/app/users', handle_app_users)
    app.router.add_post('/api/app/update-user-status', handle_app_update_user_status)
    app.router.add_post('/api/app/restrict-all-users', handle_app_restrict_all_users)
    app.router.add_post('/api/app/broadcast', handle_app_broadcast)
    app.router.add_post('/api/app/broadcast/delete', handle_app_broadcast_delete)
    app.router.add_get('/api/next-test-code', handle_next_test_code_api)
    app.router.add_get('/api/app/status', handle_app_status)
    app.router.add_get('/healthz', handle_app_status)
    app.router.add_get('/ping', handle_app_status)
    app.router.add_post('/api/app/compare-keys', handle_app_compare_keys)
    app.router.add_post('/api/app/set-pin', handle_app_set_pin)
    app.router.add_post('/api/app/verify-pin', handle_app_verify_pin)
    # Universal Static Route
    app.router.add_get('/css/{path:.*}', handle_static_file)
    app.router.add_get('/js/{path:.*}', handle_static_file)
    app.router.add_get('/img/{path:.*}', handle_static_file)
    app.router.add_get('/{path:[^/]+\\.(?:css|js|png|jpg|jpeg|svg|ico|json|webp|mp4)}', handle_static_file)

    return app

# keep_alive_pinger main() ichida qayta yoqildi (KEEP_ALIVE=0 bilan o'chirish mumkin).
# Tashqi Cron-job (UptimeRobot, cron-job.org) orqali /healthz yoki /ping endpointiga
# ertalab 07:00 dan 23:00 gacha so'rov yuboring. Bu bot o'z-o'zini ping qilmaydi.

# ── AVTOMATIK HTTPS TUNNEL (OGOHLANTIRISHLARSIZ / TO'G'RIDAN-TO'G'RI OCHILUVCHI) ──
async def maintain_tunnel(local_port: int):
    """Telegram Mini App uchun tunnel yoki Railway doimiy HTTPS manzilini sozlaydi."""
    global WEBAPP_URL
    import re

    # Agar Render.com yoki Railway yoki boshqa doimiy domenda ishlayotgan bo'lsa
    render_domain = os.getenv("RENDER_EXTERNAL_URL")
    is_render = os.getenv("RENDER") == "true" or bool(os.getenv("RENDER_SERVICE_ID")) or bool(os.getenv("RENDER_INSTANCE_ID"))
    if render_domain or is_render:
        if not render_domain:
            render_domain = os.getenv("WEBAPP_URL") or "https://fizika-bot-t560.onrender.com"
        WEBAPP_URL = (render_domain if render_domain.startswith("http") else f"https://{render_domain}").rstrip("/")
        log.info(f"🚀 Render.com Production muhiti aniqlandi: {WEBAPP_URL}")
        try:
            with open("tunnel_url.txt", "w") as f:
                f.write(WEBAPP_URL)
            menu_btn = MenuButtonWebApp(text="Profil 👤", web_app=WebAppInfo(url=f"{WEBAPP_URL}/app.html"))
            await bot.set_chat_menu_button(menu_button=menu_btn)
            log.info("✅ Bot menyu tugmasi 'Profil 👤' Render.com URL ga ulandi!")
        except Exception as e:
            log.error(f"Menu tugmasini yangilashda xatolik: {e}")
        return

    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")
    if railway_domain:
        WEBAPP_URL = f"https://{railway_domain}"
        log.info(f"🚂 Railway Production muhiti aniqlandi: {WEBAPP_URL}")
        try:
            with open("tunnel_url.txt", "w") as f:
                f.write(WEBAPP_URL)
            menu_btn = MenuButtonWebApp(text="Profil 👤", web_app=WebAppInfo(url=f"{WEBAPP_URL}/app.html"))
            await bot.set_chat_menu_button(menu_button=menu_btn)
            log.info("✅ Bot menyu tugmasi 'Profil 👤' Railway URL ga ulandi!")
        except Exception as e:
            log.error(f"Menu tugmasini yangilashda xatolik: {e}")
        return

    env_url = os.getenv("WEBAPP_URL", "")
    if env_url and not any(k in env_url for k in [".lhr.life", ".trycloudflare.com", ".serveo.net", "serveousercontent.com", "localhost", "127.0.0.1"]):
        WEBAPP_URL = env_url.rstrip("/")
        log.info(f"🌐 Doimiy WEBAPP_URL sozlamasi aniqlandi: {WEBAPP_URL}")
        try:
            with open("tunnel_url.txt", "w") as f:
                f.write(WEBAPP_URL)
            menu_btn = MenuButtonWebApp(text="Profil 👤", web_app=WebAppInfo(url=f"{WEBAPP_URL}/app.html"))
            await bot.set_chat_menu_button(menu_button=menu_btn)
            log.info("✅ Bot menyu tugmasi 'Profil 👤' env URL ga ulandi!")
        except Exception as e:
            log.error(f"Menu tugmasini yangilashda xatolik: {e}")
        return

    providers = [
        ("Cloudflare", ["cloudflared", "tunnel", "--url", f"http://localhost:{local_port}"], r'https://[a-zA-Z0-9\-\.]+\.trycloudflare\.com'),
        ("LocalhostRun", ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30", "-R", f"80:localhost:{local_port}", "nokey@localhost.run"], r'https://[a-zA-Z0-9\-\.]+\.lhr\.life')
    ]

    while True:
        for name, cmd, pattern in providers:
            try:
                log.info(f"🔌 HTTPS Tunnelga ulanmoqda ({name})...")
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    decoded = line.decode('utf-8', errors='ignore')
                    match = re.search(pattern, decoded)
                    if match:
                        new_url = match.group(0)
                        WEBAPP_URL = new_url
                        log.info(f"✨ JONLI HTTPS MINI APP URL ({name}): {WEBAPP_URL}")
                        try:
                            with open("tunnel_url.txt", "w") as f:
                                f.write(WEBAPP_URL)
                            # Update Bot Menu Button automatically
                            menu_btn = MenuButtonWebApp(text="Profil 👤", web_app=WebAppInfo(url=f"{WEBAPP_URL}/app.html"))
                            await bot.set_chat_menu_button(menu_button=menu_btn)
                            log.info("✅ Bot menyu tugmasi 'Profil 👤' Mini App URL ga ulandi!")
                        except Exception as e:
                            log.error(f"Menu tugmasini yangilashda xatolik: {e}")
                await proc.wait()
                log.warning(f"⚠️ {name} aloqasi uzildi. Qayta ulanmoqda...")
            except Exception as e:
                log.error(f"Tunnel xatoligi ({name}): {e}")
            await asyncio.sleep(2)
        await asyncio.sleep(3)

# ── TEST JADVAL VAQT HANDLERLARI ───────────────────────────

@router.callback_query(F.data.startswith("adm_schedule_"))
async def adm_schedule_start(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[2])
    test = test_db.get_test_by_id(test_id)
    if not test:
        await call.answer("Test topilmadi!", show_alert=True)
        return

    sched_date = test.get('scheduled_date') or ''
    sched_start = test.get('scheduled_start') or ''
    sched_end = test.get('scheduled_end') or ''

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Yangi vaqt belgilash", callback_data=f"adm_sched_set_{test_id}")],
        [InlineKeyboardButton(text="🗑 Jadval vaqtini bekor qilish", callback_data=f"adm_sched_clear_{test_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"adm_tstat_{test_id}")],
    ])

    cur_sched = f"⏰ {sched_date} | {sched_start}–{sched_end}" if (sched_start and sched_end) else "➖ Belgilanmagan"
    text = (
        f"⏰ <b>Avtomatik vaqt boshqaruvi</b>\n\n"
        f"📖 <b>Test:</b> {test['title']}\n"
        f"🕐 <b>Hozirgi jadval:</b> {cur_sched}\n\n"
        f"<i>Test belgilangan vaqtda avtomatik <b>faollashadi</b> (boshlanish vaqti kelganda)\n"
        f"va belgilangan vaqtda avtomatik <b>to'xtatiladi</b> (tugash vaqti kelganda).\n"
        f"Siz hech narsa qilmasangiz ham bot o'zi boshqaradi.</i>"
    )
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm_sched_clear_"))
async def adm_sched_clear(call: CallbackQuery):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    test_db.clear_test_schedule(test_id)
    await call.answer("✅ Jadval vaqti bekor qilindi!", show_alert=True)
    # test boshqaruv sahifasiga qaytish
    call.data = f"adm_tstat_{test_id}"
    await admin_test_stats_detail(call)


@router.callback_query(F.data.startswith("adm_sched_set_"))
async def adm_sched_set_start(call: CallbackQuery, state: FSMContext):
    if not test_db.is_admin(call.from_user.id, ADMIN_ID):
        return
    test_id = int(call.data.split("_")[3])
    await state.update_data(schedule_test_id=test_id)
    await state.set_state(ScheduleState.waiting_date)

    now_uzb = datetime.now(UZB_TZ)
    today = now_uzb.strftime("%d.%m.%Y")
    tomorrow = (now_uzb + timedelta(days=1)).strftime("%d.%m.%Y")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 Bugun ({today})", callback_data=f"sched_date_{today}_{test_id}")],
        [InlineKeyboardButton(text=f"📅 Ertaga ({tomorrow})", callback_data=f"sched_date_{tomorrow}_{test_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"adm_schedule_{test_id}")],
    ])
    try:
        await call.message.edit_text(
            "📅 <b>Test o'tkaziladigan sanani tanlang yoki kiriting:</b>\n\n"
            "<i>Format: <code>26.09.2026</code></i>",
            reply_markup=kb
        )
    except Exception:
        await call.message.answer(
            "📅 <b>Sanani tanlang yoki kiriting (26.09.2026 formatida):</b>",
            reply_markup=kb
        )
    await call.answer()


@router.callback_query(F.data.startswith("sched_date_"))
async def adm_sched_date_chosen(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    # sched_date_DD.MM.YYYY_testid
    chosen_date = parts[2]
    test_id = int(parts[3])
    await state.update_data(schedule_date=chosen_date, schedule_test_id=test_id)
    await state.set_state(ScheduleState.waiting_start)
    await call.message.edit_text(
        f"✅ Sana: <b>{chosen_date}</b>\n\n"
        f"🕐 <b>Test boshlanish vaqtini kiriting</b> (UZB vaqti):\n"
        f"<i>Format: <code>19:30</code></i>"
    )
    await call.answer()


@router.message(ScheduleState.waiting_date)
async def adm_sched_date_text(message: Message, state: FSMContext):
    import re
    text = message.text.strip()
    if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', text):
        await message.answer("❌ Noto'g'ri format. Iltimos: <code>26.09.2026</code>")
        return
    data = await state.get_data()
    test_id = data.get('schedule_test_id')
    await state.update_data(schedule_date=text)
    await state.set_state(ScheduleState.waiting_start)
    await message.answer(
        f"✅ Sana: <b>{text}</b>\n\n"
        f"🕐 <b>Boshlanish vaqtini kiriting</b> (UZB):\n"
        f"<i>Format: <code>19:30</code></i>"
    )


@router.message(ScheduleState.waiting_start)
async def adm_sched_start_time(message: Message, state: FSMContext):
    import re
    text = message.text.strip()
    if not re.match(r'^\d{1,2}:\d{2}$', text):
        await message.answer("❌ Noto'g'ri format. Iltimos: <code>19:30</code>")
        return
    # HH:MM formatga keltirish
    h, m = text.split(":")
    text = f"{int(h):02d}:{m}"
    await state.update_data(schedule_start=text)
    await state.set_state(ScheduleState.waiting_end)
    await message.answer(
        f"✅ Boshlanish: <b>{text}</b>\n\n"
        f"🕕 <b>Tugash vaqtini kiriting</b> (UZB):\n"
        f"<i>Format: <code>22:00</code></i>"
    )


@router.message(ScheduleState.waiting_end)
async def adm_sched_end_time(message: Message, state: FSMContext):
    import re
    text = message.text.strip()
    if not re.match(r'^\d{1,2}:\d{2}$', text):
        await message.answer("❌ Noto'g'ri format. Iltimos: <code>22:00</code>")
        return
    h, m = text.split(":")
    text = f"{int(h):02d}:{m}"

    data = await state.get_data()
    test_id = data.get('schedule_test_id')
    schedule_date = data.get('schedule_date', '')
    schedule_start = data.get('schedule_start', '')

    await state.clear()

    # Saqlash
    test_db.set_test_schedule(test_id, schedule_date, schedule_start, text)

    test = test_db.get_test_by_id(test_id)
    test_name = test['title'] if test else f"Test #{test_id}"

    await message.answer(
        f"✅ <b>Avtomatik jadval saqlandi!</b>\n\n"
        f"📖 <b>Test:</b> {test_name}\n"
        f"📅 <b>Sana:</b> {schedule_date}\n"
        f"🕐 <b>Boshlanadi:</b> {schedule_start} (UZB)\n"
        f"🕕 <b>Tugaydi:</b> {text} (UZB)\n\n"
        f"<i>Bot belgilangan vaqtda testni avtomatik faollashtiradi va to'xtatadi.</i>"
    )


# ── BACKGROUND SCHEDULER (har 60 soniyada tekshiradi) ──────

async def schedule_checker():
    """Har 60 soniyada testlarning avtomatik vaqtini tekshiradi va rejalashtirilgan xabarlarni tarqatadi hamda faollashtiradi/to'xtatadi."""
    log.info("⏰ Schedule Checker ishga tushdi")
    while True:
        try:
            now_uzb = datetime.now(UZB_TZ)
            today_iso = now_uzb.strftime("%Y-%m-%d")
            today_dot = now_uzb.strftime("%d.%m.%Y")
            now_minutes = now_uzb.hour * 60 + now_uzb.minute

            tests = test_db.get_scheduled_tests()
            for t in tests:
                sdate = str(t.get('scheduled_date') or '').strip()
                sstart = str(t.get('scheduled_start') or '').strip()
                send = str(t.get('scheduled_end') or '').strip()
                test_id = t['id']
                test_code = t.get('test_code') or str(test_id)
                code_display = f"#{test_code}" if not str(test_code).startswith("#") else str(test_code)
                test_title = t.get('title') or "Fizika Testi"
                is_active = (t.get('is_active', 1) == 1)
                notified = str(t.get('auto_notified') or '')

                if not sdate or not sstart or not send:
                    continue

                # Sana tekshiruvi (YYYY-MM-DD yoki DD.MM.YYYY)
                date_match = (sdate == today_iso or sdate == today_dot)
                if not date_match:
                    if "-" in sdate:
                        parts = sdate.split("-")
                        if len(parts) == 3 and len(parts[0]) == 4:
                            date_match = (f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}" == today_iso)
                    elif "." in sdate:
                        parts = sdate.split(".")
                        if len(parts) == 3 and len(parts[2]) == 4:
                            date_match = (f"{int(parts[2]):04d}-{int(parts[1]):02d}-{int(parts[0]):02d}" == today_iso)

                if not date_match:
                    continue

                try:
                    sh, sm = map(int, sstart.split(":"))
                    eh, em = map(int, send.split(":"))
                    start_minutes = sh * 60 + sm
                    end_minutes = eh * 60 + em
                except Exception:
                    continue

                # 1. ⏳ 30 daqiqa qoldi ogohlantirishi (start - 30 daqiqadan start - 10 daqiqagacha)
                if (start_minutes - 30) <= now_minutes < (start_minutes - 10) and "30m" not in notified:
                    test_db.mark_test_auto_notified(test_id, "30m")
                    clean_title = re.sub(r'\s*#[\w\d]+\s*$', '', test_title).strip() or test_title
                    msg_30m = (
                        "⏳ <b>Diqqat! Test boshlanishiga 30 daqiqa qoldi!</b>\n\n"
                        "Internet aloqangizni tekshirib, qoralama qog'ozlarni tayyorlab oling.\n\n"
                        f"📖 <b>Test:</b> {clean_title}\n"
                        f"🕐 <b>Boshlanish vaqti:</b> {sstart} (UZB)"
                    )
                    await send_broadcast_to_users(message_text=msg_30m)
                    log.info(f"⏰ Test #{test_id} uchun 30 daqiqa qoldi xabari tarqatildi")

                # 2. ⚠️ 10 daqiqa qoldi ogohlantirishi (start - 10 daqiqadan start gacha)
                if (start_minutes - 10) <= now_minutes < start_minutes and "10m" not in notified:
                    test_db.mark_test_auto_notified(test_id, "10m")
                    clean_title = re.sub(r'\s*#[\w\d]+\s*$', '', test_title).strip() or test_title
                    msg_10m = (
                        "⚠️ <b>Test boshlanishiga 10 daqiqa qoldi!</b>\n\n"
                        "Mini ilovaga kirib, tayyor bo'lib turing.\n\n"
                        f"📖 <b>Test:</b> {clean_title}\n"
                        f"🕐 <b>Boshlanish vaqti:</b> {sstart} (UZB)"
                    )
                    await send_broadcast_to_users(message_text=msg_10m)
                    log.info(f"⏰ Test #{test_id} uchun 10 daqiqa qoldi xabari tarqatildi")

                # 3. 🚀 Boshlanish vaqti keldi (start dan end gacha)
                if start_minutes <= now_minutes < end_minutes:
                    # Testni faollashtirish
                    if not is_active:
                        test_db.set_test_active_status(test_id, 1)
                        is_active = True
                        log.info(f"⏰ Test #{test_id} avtomatik faollashtirildi ({sstart})")

                    # Avtomatik "🚀 Test boshlandi!" xabarini barcha o'quvchilarga tarqatish
                    if "started" not in notified:
                        test_db.mark_test_auto_notified(test_id, "started")
                        msg_started = (
                            "🚀 <b>Test boshlandi! Barchaga omad tilaymiz.</b>\n"
                            "Belgilangan vaqt ichida javoblarni topshirishni unutmang.\n\n"
                            f"📖 <b>Test nomi:</b> {test_title}\n"
                            f"📌 <b>Test kodi:</b> <code>{code_display}</code>\n"
                            f"⏰ <b>Test vaqti:</b> {sstart} – {send} (UZB)\n\n"
                            "<i>Mini ilovaga kirib, test topshirishingiz mumkin 👇</i>"
                        )
                        sent, fail, _ = await send_broadcast_to_users(message_text=msg_started)
                        log.info(f"⏰ Test #{test_id} boshlanganlik xabari {sent} nafar o'quvchiga avtomat tarqatildi")
                        try:
                            await bot.send_message(
                                chat_id=ADMIN_ID,
                                text=(
                                    f"⏰ <b>Avtomatik: Test boshlandi va o'quvchilarga e'lon qilindi!</b>\n\n"
                                    f"📖 <b>{test_title}</b>\n"
                                    f"📌 Test kodi: <code>{code_display}</code>\n"
                                    f"🕐 Vaqti: <b>{sstart}–{send}</b> (UZB)\n"
                                    f"📨 <b>O'quvchilarga tarqatildi:</b> {sent} ta\n\n"
                                    f"✅ Test faol — o'quvchilar javob topshirishi mumkin."
                                )
                            )
                        except Exception:
                            pass

                # 4. ⏰ 15 daqiqa qoldi ogohlantirishi (end - 15 daqiqadan end gacha)
                if (end_minutes - 15) <= now_minutes < end_minutes and "15m" not in notified and "started" in notified:
                    test_db.mark_test_auto_notified(test_id, "15m")
                    msg_15m = (
                        "⏰ <b>Diqqat, test yakunlanishiga 15 daqiqa qoldi!</b>\n\n"
                        "Qolgan javoblarni tekshirib, topshirishga shoshiling.\n\n"
                        f"📖 <b>Test:</b> {test_title}\n"
                        f"📌 <b>Test kodi:</b> <code>{code_display}</code>\n"
                        f"🕕 <b>Tugash vaqti:</b> {send} (UZB)"
                    )
                    await send_broadcast_to_users(message_text=msg_15m)
                    log.info(f"⏰ Test #{test_id} yakunlanishiga 15 daqiqa qolganligi xabari tarqatildi")

                # 5. 🔴 Tugash vaqti keldi va test hali faol bo'lsa
                if now_minutes >= end_minutes and is_active:
                    test_db.set_test_active_status(test_id, 0)
                    test_db.clear_test_schedule(test_id)
                    log.info(f"⏰ Test #{test_id} avtomatik to'xtatildi ({send})")

                    # Barcha o'quvchilarga test yakunlanganligi haqida avtomatik xabar tarqatish
                    msg_ended = (
                        "🛑 <b>Test yakunlandi!</b>\n\n"
                        "Javoblarni qabul qilish to'xtatildi. Ishtirok etgan barcha o'quvchilarga minnatdorchilik bildiramiz.\n\n"
                        f"📖 <b>Test:</b> {test_title}\n"
                        f"📌 <b>Test kodi:</b> <code>{code_display}</code>\n"
                        f"🕕 <b>Tugash vaqti:</b> {send} (UZB)\n\n"
                        "📊 <i>Tez orada to'liq tahlil va rasmiy natijalar e'lon qilinadi! Mini ilovaga kirib yangiliklarni kuzatib boring.</i>"
                    )
                    sent, fail, _ = await send_broadcast_to_users(message_text=msg_ended)
                    log.info(f"⏰ Test #{test_id} yakunlanganlik xabari {sent} nafar o'quvchiga tarqatildi")

                    try:
                        await bot.send_message(
                            chat_id=ADMIN_ID,
                            text=(
                                f"⏰ <b>Avtomatik: Test yakunlandi!</b>\n\n"
                                f"📖 <b>{test_title}</b>\n"
                                f"📌 Test kodi: <code>{code_display}</code>\n"
                                f"🕕 Tugash vaqti: <b>{send}</b>\n\n"
                                f"🛑 Test to'xtatildi va barcha o'quvchilarga yakunlanganlik xabari tarqatildi ({sent} ta).\n"
                                f"📊 Natijalarni hisoblash va e'lon qilish uchun: <b>/admin</b> → Testlar"
                            )
                        )
                    except Exception:
                        pass

        except Exception as e:
            log.error(f"Schedule checker xatosi: {e}")

        await asyncio.sleep(60)



# ── ASOSIY ISHGA TUSHIRISH (MAIN) ─────────────────────
async def main():
    global WEBAPP_URL

    # 1. aiohttp serverini DARHOL ishga tushirish (Render /healthz tekshiruvidan darhol o'tishi uchun)
    app = await create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    current_port = PORT
    site = None
    for attempt in range(10):
        try:
            site = web.TCPSite(runner, '0.0.0.0', current_port)
            await site.start()
            log.info(f"🌐 Mini App Server ishga tushdi: http://localhost:{current_port}")
            break
        except OSError as e:
            if e.errno == 48: # Address already in use
                current_port += 1
            else:
                raise e

    # 2. Orqa fonda bazani tozalash (Server javob berishini to'xtatib qo'ymaslik uchun)
    async def run_startup_db_tasks():
        try:
            await asyncio.to_thread(test_db.init_db)
            cleaned = await asyncio.to_thread(test_db.delete_all_blocked_users)
            if cleaned:
                log.info(f"🧹 Bot ishga tushganda {len(cleaned)} ta oldindan bloklangan foydalanuvchi bazadan o'chirildi")
        except Exception as ex:
            log.warning(f"Startup clean blocked xatolik: {ex}")

    asyncio.create_task(run_startup_db_tasks())

    # 2. Fon rejimida HTTPS Tunnelni boshlash
    asyncio.create_task(maintain_tunnel(current_port))

    # 2b. Avtomatik jadval tekshiruvchisini ishga tushirish
    asyncio.create_task(schedule_checker())

    # 2c. Render bepul rejimida 15 daqiqa harakatsizlikdan keyin server uxlab qoladi va
    # polling to'xtaydi. Har 10 daqiqada o'z public URL'ini ping qilib uyg'oq ushlaymiz.
    # (Workspace'da faqat 1 ta xizmat ishlasa ~744 soat/oy — 750 soatlik limitga sig'adi.)
    async def keep_alive_pinger():
        import aiohttp
        await asyncio.sleep(60)
        while True:
            url = (os.getenv("RENDER_EXTERNAL_URL") or WEBAPP_URL or os.getenv("WEBAPP_URL") or "").rstrip("/")
            if url.startswith("http"):
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
                        async with s.get(f"{url}/healthz") as r:
                            log.debug(f"keep-alive ping: {r.status}")
                except Exception as ex:
                    log.warning(f"keep-alive ping xatolik: {ex}")
            await asyncio.sleep(600)

    if os.getenv("KEEP_ALIVE", "1") != "0":
        asyncio.create_task(keep_alive_pinger())

    # 3. Telegram Botni ishga tushirish
    log.info("🤖 Telegram Bot Polling rejimida ishga tushmoqda...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        # Telegram rasmiy menyu buyruqlarini ro'yxatdan o'tkazish
        try:
            await bot.set_my_commands([
                BotCommand(command="start", description="🚀 Botni ishga tushirish"),
                BotCommand(command="app", description="📱 Test topshirish (Mini App)"),
                BotCommand(command="results", description="📊 Mening natijalarim"),
                BotCommand(command="profile", description="👤 Shaxsiy profilim"),
                BotCommand(command="help", description="ℹ️ Qo'llanma va yordam"),
            ])
            log.info("✅ Telegram Bot rasmiy buyruqlar menyusi o'rnatildi (/start, /app, ...)")

            # Telegram pastki chat menyu tugmasini doimiy ravishda "Profil 👤" qilib o'rnatish
            try:
                app_url = WEBAPP_URL
                if not app_url and os.path.exists("tunnel_url.txt"):
                    try:
                        with open("tunnel_url.txt", "r") as f:
                            app_url = f.read().strip()
                    except Exception:
                        pass
                if not app_url:
                    app_url = os.getenv("WEBAPP_URL") or "https://fizika-bot-t560.onrender.com"
                if "/dashboard" in app_url:
                    app_url = app_url.split("/dashboard")[0]
                menu_btn = MenuButtonWebApp(text="Profil 👤", web_app=WebAppInfo(url=f"{app_url.rstrip('/')}/app.html"))
                await bot.set_chat_menu_button(menu_button=menu_btn)
                log.info("✅ Telegram Bot pastki menyu tugmasi 'Profil 👤' qilib sozlandi!")
            except Exception as me:
                log.warning(f"Bot chat menyu tugmasini o'rnatishda ogohlantirish: {me}")
        except Exception as ce:
            log.warning(f"Bot buyruqlarini o'rnatishda ogohlantirish: {ce}")

        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        if runner:
            await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi.")
