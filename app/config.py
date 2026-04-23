import os
import sys
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from groq import Groq

STATIONS = {
    "Band_FM": "https://stm.alphanetdigital.com.br:7040/band",
    "Ondas_Verdes": "https://live3.livemus.com.br:6922/stream",
    "Vox_FM": "https://streaming.inweb.com.br/vox-catanduva",
    "Clube_FM": "https://8157.brasilstream.com.br/stream?1776957572681",
    "Vida_FM": "https://streaming.inweb.com.br/vox-vida",
    "Nativa_FM": "https://s41.maxcast.com.br:8172/live",
    "Atividade": "https://streaming.inweb.com.br/atividade",
}

RECORD_DURATION = 60
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"
GROQ_LLM_MODEL = "llama-3.1-8b-instant"
MIN_SPEECH_RATIO = 0.40
MIN_SPEECH_SEGS = 3
TRANSCRIPTION_CAP = 3000
AD_COOLDOWN_SECONDS = 90

RETAIL_KEYWORDS = [
    "supermercado", "mercado", "atacado", "atacarejo", "hipermercado",
    "mercadão", "sacolão", "empório", "mercearia", "distribuidora",
    "magazine", "shopping", "loja", "lojas", "clube", "fair", "feira",
    "armazém", "cooperativa", "hortifruti", "quitanda",
]

def _load_env_files() -> list[str]:
    """Load .env from common source and frozen-app locations."""
    loaded: list[str] = []
    candidates: list[str] = []

    # When frozen, data files are extracted under _MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, ".env"))

    # Next to the executable for portable deployment scenarios.
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, ".env"))

    # Project root during development.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates.append(os.path.join(project_root, ".env"))

    seen = set()
    for env_path in candidates:
        if env_path in seen:
            continue
        seen.add(env_path)
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
            loaded.append(env_path)

    return loaded


_LOADED_ENV_PATHS = _load_env_files()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    searched = ", ".join(_LOADED_ENV_PATHS) if _LOADED_ENV_PATHS else "nenhum .env encontrado"
    raise ValueError(f"❌ GROQ_API_KEY não encontrada! Caminhos verificados: {searched}")

groq_client = Groq(api_key=GROQ_API_KEY)
TZ_BR = ZoneInfo("America/Sao_Paulo")
