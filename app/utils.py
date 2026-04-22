import datetime
import re
import unicodedata

from .config import TZ_BR

TRANSCRIPTION_FIXES = {
    "netflix": "Netflex",
    "moresq": "Moreschi",
    "moresc": "Moreschi",
    "moresqui": "Moreschi",
    "la juma": "Lajuma",
    "lajuma": "Lajuma",
    "pony watts": "Fone Whats",
    "pony wats": "Fone Whats",
    "ponywatts": "Fone Whats",
    "Se Crede": "Sicredi",
    "Magate": "Magatti",
    "Clube do Precinho": "Antunes",
    "Presti Monte": "Prestmont",
    "WEG": "Netflex",
    
}


def br_now():
    return datetime.datetime.now(TZ_BR)


def br_timestamp():
    return br_now().strftime("%d-%m-%Y_%H-%M-%S")


def br_display():
    return br_now().strftime("%d/%m/%Y %H:%M:%S")


def safe_filename(text: str, max_len: int = 60) -> str:
    if not text:
        return "Desconhecido"
    text = unicodedata.normalize("NFKD", str(text).strip())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\- ]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text).strip("_")
    return (text or "Desconhecido")[:max_len]


def fix_transcription(text: str) -> str:
    """Substitui variações de nomes detectadas incorretamente pelo modelo."""
    t = text
    for wrong, right in TRANSCRIPTION_FIXES.items():
        t = re.sub(rf"\b{re.escape(wrong)}\b", right, t, flags=re.IGNORECASE)
    return t
