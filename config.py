"""Centralna konfiguracja bota - wczytywanie zmiennych srodowiskowych i stalych."""
import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    """Pobiera zmienna srodowiskowa jako int. Pusta lub brak -> wartosc domyslna."""
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default


# ===== Sekrety / srodowisko =====
TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GUILD_ID = os.getenv("GUILD_ID") or None  # opcjonalne - dla szybkiego syncu na jednym serwerze

# ===== Jezyk bota: "pl" albo "en" =====
LANGUAGE = (os.getenv("LANGUAGE") or "pl").strip().lower()
if LANGUAGE not in ("pl", "en"):
    LANGUAGE = "pl"

# ===== Kolory embedow (spojny wyglad) =====
COLOR_PRIMARY = 0x5865F2   # Discord blurple
COLOR_SUCCESS = 0x57F287   # zielony
COLOR_ERROR = 0xED4245     # czerwony
COLOR_WARNING = 0xFEE75C   # zolty
COLOR_INFO = 0x5865F2

# ===== Ekonomia (mozna nadpisac przez zmienne srodowiskowe) =====
DAILY_AMOUNT = _int_env("DAILY_AMOUNT", 250)
WORK_MIN = _int_env("WORK_MIN", 50)
WORK_MAX = _int_env("WORK_MAX", 300)
WORK_COOLDOWN = _int_env("WORK_COOLDOWN", 3600)        # sekundy
DAILY_COOLDOWN = _int_env("DAILY_COOLDOWN", 86400)     # sekundy
START_BALANCE = _int_env("START_BALANCE", 0)
CURRENCY_SYMBOL = "\U0001FA99"  # monety

# ===== Leveling (mozna nadpisac przez zmienne srodowiskowe) =====
XP_PER_MESSAGE_MIN = _int_env("XP_PER_MESSAGE_MIN", 15)
XP_PER_MESSAGE_MAX = _int_env("XP_PER_MESSAGE_MAX", 25)
XP_COOLDOWN = _int_env("XP_COOLDOWN", 60)              # sekundy miedzy zliczaniem XP


def xp_needed(level: int) -> int:
    """Ile XP potrzeba aby osiagnac dany poziom (od 0)."""
    return 5 * (level ** 2) + 50 * level + 100


def validate() -> list[str]:
    """Zwraca liste brakujacych WYMAGANYCH zmiennych srodowiskowych."""
    missing = []
    if not TOKEN:
        missing.append("DISCORD_TOKEN")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    return missing
