import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from groq import Groq

STATIONS = {
    "Band_FM": "https://stm.alphanetdigital.com.br:7040/band",
    "Ondas_Verdes": "https://live3.livemus.com.br:6922/stream",
    "Nativa_FM": "https://s41.maxcast.com.br:8172/live",
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

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("❌ GROQ_API_KEY não encontrada!")

groq_client = Groq(api_key=GROQ_API_KEY)
TZ_BR = ZoneInfo("America/Sao_Paulo")
