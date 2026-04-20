import re

from .config import RETAIL_KEYWORDS

AD_STRONG = [
    "promoção", "oferta", "desconto", "imperdível", "compre", "aproveite",
    "garanta", "só hoje", "últimos dias", "parcel", "sem juros", "cupom",
    "por apenas", "a partir de", "r$", "reais",
]

AD_BUSINESS = [
    "farmácia", "drogaria", "autoescola", "supermercado", "clínica",
    "laboratório", "ótica", "academia", "concessionária", "pizzaria",
    "restaurante", "seguro", "consórcio", "financiamento", "imobiliária",
    "hospital", "posto", "faculdade", "curso", "aplicativo", "frete",
    "delivery", "whatsapp", "site", ".com", ".br",
]

EXPLICIT_CTA = [
    "ligue", "acesse", "compre", "whatsapp", "zap", "visite", "peça já",
    "clique", "baixe", "chame no", "manda mensagem", "fale com",
    "entre em contato", "vá ao site", "pelo site", "no instagram",
    "no aplicativo", "mande um", "encomende",
]

NON_AD_PHRASES = [
    "segundo informações", "de acordo com", "o governador", "o prefeito",
    "a polícia", "os bombeiros", "o presidente", "a secretaria",
    "boa tarde", "bom dia", "boa noite", "você está ouvindo",
    "eu sinto falta", "lembro quando", "antigamente", "era melhor",
    "quando eu era", "que saudade", "minha avó", "meu pai", "minha mãe",
    "hoje em dia", "mudou muito", "apoio de", "com o apoio",
    "transmissão oficial", "patrocínio de", "parceiro oficial",
    "nas redes sociais", "nosso instagram", "nosso facebook",
    "siga a gente", "nos siga", "acompanhe a gente",
    "você está ouvindo a", "aqui é a", "essa é a",
    "nossa programação", "nossa rádio", "pelo nosso aplicativo",
    "fone whats", "fone e whats", "fone zap",
    "pony watts", "pony wats", "ponywatts",
]

PRICE_RE = re.compile(r"r\$\s*\d+([.,]\d{2})?|\d+\s*reais", re.IGNORECASE)
PHONE_RE = re.compile(r"(\(?\d{2}\)?\s*)?\d{4,5}[-\s]?\d{4}")
VINHETA_RE = re.compile(
    r"(oficial (da|do|de)|parceiro oficial|só (da|do)|"
    r"apresenta(do por)?|uma realização|com o apoio|apoio (da|do)|"
    r"patrocínio (da|do)|transmissão oficial)",
    re.IGNORECASE,
)
FIRST_PERSON_RE = re.compile(
    r"\b(eu |a gente |nós |minha |meu |nossa |nosso )"
    r"(sinto|lembro|acho|gosto|quero|fazia|comia|ia|era|fui|vim|tenho|tinha)\b",
    re.IGNORECASE,
)


def heuristic_score(text: str) -> dict:
    t = text.lower()
    return {
        "ad_score": (
            sum(2 for k in AD_STRONG if k in t)
            + sum(1 for k in AD_BUSINESS if k in t)
            + (3 if PRICE_RE.search(t) else 0)
            + (2 if PHONE_RE.search(t) else 0)
            + (2 if any(k in t for k in EXPLICIT_CTA) else 0)
        ),
        "nonad_score": (
            sum(1 for k in NON_AD_PHRASES if k in t)
            + (3 if FIRST_PERSON_RE.search(text) else 0)
            + (4 if VINHETA_RE.search(text) and not any(k in t for k in EXPLICIT_CTA)
               and not PRICE_RE.search(t) else 0)
        ),
        "has_price": bool(PRICE_RE.search(t)),
        "has_phone": bool(PHONE_RE.search(t)),
        "has_cta": any(k in t for k in EXPLICIT_CTA),
        "is_vinheta": bool(VINHETA_RE.search(text)),
        "is_fp_chat": bool(FIRST_PERSON_RE.search(text)),
    }


def should_skip(heur: dict, station_name: str = "", text: str = "") -> str | None:
    if heur["ad_score"] < 2 and heur["nonad_score"] >= 2:
        return "conteúdo não-publicitário"
    if heur["is_vinheta"] and not heur["has_cta"] and not heur["has_price"]:
        return "vinheta/patrocínio sem CTA ou preço"
    if heur["is_fp_chat"] and not heur["has_price"] and not heur["has_cta"]:
        return "conversa em 1ª pessoa sem preço/CTA"
    if station_name and text and name_in_text(station_name, text) and not heur["has_price"]:
        return "auto-promoção da rádio"
    return None


def name_in_text(name: str, text: str) -> bool:
    if not name or not text:
        return False
    tokens = [w for w in re.split(r"\W+", name.lower()) if len(w) >= 3]
    t_lower = text.lower()
    if not tokens:
        return bool(re.search(r"\b" + re.escape(name.lower()) + r"\b", t_lower))
    matched = sum(1 for tok in tokens if tok in t_lower)
    return matched >= max(1, round(len(tokens) * 0.6))


def is_retail_anchor(anunciante: str, text: str) -> bool:
    if not anunciante:
        return False
    combined = (anunciante + " " + text[:500]).lower()
    return any(kw in combined for kw in RETAIL_KEYWORDS)
