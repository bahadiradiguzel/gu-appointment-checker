"""
Slot Checker Bot
================
Monitors a scheduling API for earlier available slots and sends a Telegram
notification when one appears.

Usage: python checker.py
Scheduling: GitHub Actions cron or any scheduler.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# YAPILANDIRMA SABİTLERİ
# ---------------------------------------------------------------------------

BASE_URL = "https://afspraak.utrecht.nl/qmaticwebbooking/rest/schedule"

# Branch ve servis ID'leri (URL'den alındı)
BRANCH_ID = "6799b9a23eb23e3be8cff82b78da95d10503b9057b8cf48bc34c4bc47f0"
SERVICE_ID = "2d7f771f9554b048625e837f7f0c8936b1993136558d7625d59c48846473c44d"
CUSTOM_SLOT_LENGTH = 25  # dakika

SERVICE_NAME = os.environ.get("SERVICE_NAME", "Target Service")

# Bu tarihten (dahil) önceki slotları yoksay — Format: YYYY-MM-DD
MIN_DATE = "2026-03-01"

# Bu tarihten sonraki yeni erken slotlar için bildirim gönderme — Format: YYYY-MM-DD
MAX_NOTIFY_DATE = "2026-05-02"

# Telegram — GitHub Secrets veya ortam değişkenlerinden okunur
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "")

BOOKING_URL = "https://afspraak.utrecht.nl/qmaticwebbooking/"

# HTTP istek zaman aşımı (saniye)
REQUEST_TIMEOUT = 15

# State dosyasının yolu
STATE_FILE = "state.json"

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API YARDIMCI FONKSİYONLARI
# ---------------------------------------------------------------------------

# Parametre string'i tekrarlanıyor — merkezi tanım
_PARAMS = f"servicePublicId={SERVICE_ID};customSlotLength={CUSTOM_SLOT_LENGTH}"

DATES_URL = f"{BASE_URL}/branches/{BRANCH_ID}/dates;{_PARAMS}"
TIMES_URL_TEMPLATE = f"{BASE_URL}/branches/{BRANCH_ID}/dates/{{date}}/times;{_PARAMS}"

_SESSION = requests.Session()
_SESSION.headers.update({
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; slot-checker/1.0)",
})


def _get_json(url: str) -> list | None:
    """URL'ye GET isteği atar, JSON listesi döndürür. Hata olursa None."""
    try:
        resp = _SESSION.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        log.error("HTTP hatası [%s]: %s", url, exc)
    except requests.RequestException as exc:
        log.error("İstek hatası [%s]: %s", url, exc)
    except ValueError as exc:
        log.error("JSON parse hatası [%s]: %s", url, exc)
    return None


# ---------------------------------------------------------------------------
# 1. UYGUN SLOTLARI ÇEKME
# ---------------------------------------------------------------------------

def get_available_slots() -> list[dict]:
    """Uygun tarih + saat slotlarını API'den çeker.

    Dönüş formatı:
        [{"date": "2026-04-30", "times": ["14:50"]}, ...]
    """
    min_date = datetime.strptime(MIN_DATE, "%Y-%m-%d").date()

    log.info("Uygun günler sorgulanıyor: %s", DATES_URL)
    dates_data = _get_json(DATES_URL)
    if dates_data is None:
        log.error("Tarihler alınamadı.")
        return []

    log.info("API'den %d tarih döndü.", len(dates_data))

    slots: list[dict] = []
    for entry in dates_data:
        date_str = entry.get("date", "")
        if not date_str:
            continue

        try:
            slot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            log.warning("Geçersiz tarih atlandı: %s", date_str)
            continue

        if slot_date < min_date:
            log.debug("MIN_DATE öncesi tarih atlandı: %s", date_str)
            continue

        times = _get_times_for_date(date_str)
        slots.append({"date": date_str, "times": times})
        log.info("  %s → %s", date_str, times if times else "(saat bilgisi yok)")

    return slots


def _get_times_for_date(date_str: str) -> list[str]:
    """Belirtilen tarih için saat slotlarını döndürür."""
    url = TIMES_URL_TEMPLATE.format(date=date_str)
    data = _get_json(url)
    if not data:
        return []

    times = [entry["time"] for entry in data if "time" in entry]
    return sorted(set(times))


# ---------------------------------------------------------------------------
# 2. STATE YÖNETİMİ
# ---------------------------------------------------------------------------

def load_previous_state() -> list[dict]:
    """state.json'u okur; yoksa veya geçersizse boş liste döndürür."""
    if not os.path.exists(STATE_FILE):
        log.info("state.json bulunamadı — ilk çalışma kabul ediliyor.")
        return []
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            log.info("Önceki state yüklendi: %d kayıt.", len(data))
            return data
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("state.json okunamadı (%s) — sıfırlanıyor.", exc)
    return []


def save_state(state: list[dict]) -> None:
    """Güncel slot listesini state.json'a yazar."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        log.info("State kaydedildi: %d kayıt → %s", len(state), STATE_FILE)
    except OSError as exc:
        log.error("State kaydedilemedi: %s", exc)


def diff_states(old_state: list[dict], new_state: list[dict]) -> list[dict]:
    """Mevcut en erken tarihten daha erken yeni slotları döndürür.

    Mantık:
    - old_state boşsa (ilk çalışma): bildirim yok, sadece kaydet.
    - Aksi halde old_state'deki en erken tarihi bul.
    - new_state'de bu tarihten önce olan herhangi bir tarih → bildirim.
    - Aynı tarihe yeni saat eklendiyse → bildirim.
    """
    if not old_state:
        # İlk çalışma: referans tarihi kaydet, bildirim gönderme.
        return []

    old_earliest = min(
        datetime.strptime(e["date"], "%Y-%m-%d").date() for e in old_state
    )
    log.info("Mevcut en erken tarih: %s", old_earliest)

    old_map: dict[str, set[str]] = {
        e["date"]: set(e.get("times", [])) for e in old_state
    }

    new_slots: list[dict] = []
    for entry in new_state:
        d = entry["date"]
        slot_date = datetime.strptime(d, "%Y-%m-%d").date()
        new_times = set(entry.get("times", []))
        old_times = old_map.get(d)

        if slot_date < old_earliest:
            # Daha erken yeni bir tarih açıldı
            new_slots.append({"date": d, "times": sorted(new_times)})
        elif slot_date == old_earliest and old_times is not None:
            # Mevcut en erken tarihe yeni saat eklendi
            added = new_times - old_times
            if added:
                new_slots.append({"date": d, "times": sorted(added)})

    return new_slots


# ---------------------------------------------------------------------------
# 3. TELEGRAM BİLDİRİMİ
# ---------------------------------------------------------------------------

def send_telegram_message(text: str) -> None:
    """Telegram Bot API ile mesaj gönderir (HTML parse_mode)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Telegram mesajı gönderildi.")
    except requests.RequestException as exc:
        log.error("Telegram mesajı gönderilemedi: %s", exc)


def format_notification(new_slots: list[dict], old_earliest: str) -> str:
    """Yeni slotlar için bildirim metni üretir."""
    lines = [
        "🔔 <b>Daha Erken Slot Açıldı!</b>",
        f"<b>Hizmet:</b> {SERVICE_NAME}",
        f"<b>Önceki en erken tarih:</b> {old_earliest}",
        "",
    ]
    for slot in sorted(new_slots, key=lambda s: s["date"]):
        d = slot["date"]
        times = slot.get("times", [])
        times_str = ", ".join(times) if times else "—"
        lines.append(f"📅 <b>{d}</b>  →  {times_str}")

    lines += [
        "",
        f'🔗 <a href="{BOOKING_URL}">Hemen randevu al</a>',
        f"🕐 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. ANA AKIŞ
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 60)
    log.info("Utrecht Randevu Takip Botu başlatıldı.")
    log.info("Hizmet: %s | Min. Tarih: %s", SERVICE_NAME, MIN_DATE)
    log.info("=" * 60)

    if TELEGRAM_BOT_TOKEN == "BURAYA_TOKEN_GELECEK":
        log.warning("TELEGRAM_BOT_TOKEN ayarlanmamış!")

    old_state = load_previous_state()
    current_slots = get_available_slots()

    if not current_slots and not old_state:
        log.info("Hiç uygun slot bulunamadı.")
        save_state([])
        return

    new_slots = diff_states(old_state, current_slots)

    if new_slots:
        max_notify = datetime.strptime(MAX_NOTIFY_DATE, "%Y-%m-%d").date()
        notifiable = [s for s in new_slots if datetime.strptime(s["date"], "%Y-%m-%d").date() <= max_notify]
        if notifiable:
            log.info("DAHA ERKEN SLOT(LAR): %d tarih.", len(notifiable))
            old_earliest = min(e["date"] for e in old_state) if old_state else "-"
            send_telegram_message(format_notification(notifiable, old_earliest))
        else:
            log.info("Yeni erken slotlar MAX_NOTIFY_DATE sonrasında — bildirim gönderilmedi.")
    else:
        log.info("Yeni slot yok — değişiklik yok.")

    save_state(current_slots)
    log.info("Tamamlandı.")


if __name__ == "__main__":
    main()
