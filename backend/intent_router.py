from __future__ import annotations

import re
import unicodedata

TOPIC = "Motilal Oswal Mutual Funds"

# ---------------------------------------------------------------------------
# Greeting detection
# ---------------------------------------------------------------------------

# Collapse repeated letters: "heyyy" -> "hey", "hiii" -> "hi"
def _collapse_repeats(text: str) -> str:
    return re.sub(r"(.)\1{2,}", r"\1\1", text)


def _normalize(text: str) -> str:
    """Lowercase, strip accents, collapse repeats, remove punctuation/emojis."""
    text = text.lower().strip()
    # Remove emoji / non-ASCII symbols
    text = "".join(
        c for c in text
        if unicodedata.category(c) not in ("So", "Sk", "Sm")
        and (c.isascii() or c.isalpha())
    )
    text = _collapse_repeats(text)
    # Remove punctuation except spaces
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_GREETING_PATTERNS: list[re.Pattern] = [
    # English greetings
    re.compile(r"^h+[aeiou]*y+[aeiou]*$"),          # hey, heyy, hei
    re.compile(r"^h+[il]+[io]*$"),                   # hi, hii, hil
    re.compile(r"^hel+o+$"),                         # hello, helo, helloo
    re.compile(r"^good\s*(morning|evening|afternoon|night|day)$"),
    re.compile(r"^how\s+are\s+you"),
    re.compile(r"^how\s+r\s+u"),
    re.compile(r"^what('?s| is)\s+up"),
    re.compile(r"^sup$"),
    re.compile(r"^yo+$"),
    re.compile(r"^greetings?$"),
    re.compile(r"^namaste$"),
    re.compile(r"^namaskar$"),
    # "what can you do" variants
    re.compile(r"what\s+can\s+you\s+do"),
    re.compile(r"what\s+do\s+you\s+do"),
    re.compile(r"what\s+are\s+you\s+(capable|able)"),
    re.compile(r"tell\s+me\s+about\s+yourself"),
    re.compile(r"who\s+are\s+you"),
    # Hindi / Hinglish
    re.compile(r"^kaise\s+ho"),
    re.compile(r"^kya\s+hal"),
    re.compile(r"^kem\s+cho"),
    re.compile(r"^hello\s+bhai"),
    re.compile(r"^hii?\s+bhai"),
    re.compile(r"^hey\s+bhai"),
    re.compile(r"^bhai$"),
    re.compile(r"^yaar$"),
    re.compile(r"^hy+$"),                            # hy, hyy
]


def is_greeting(message: str) -> bool:
    """Return True if the message is a greeting or casual opener."""
    norm = _normalize(message)
    if not norm:
        return False
    for pat in _GREETING_PATTERNS:
        if pat.search(norm):
            return True
    return False


# ---------------------------------------------------------------------------
# Out-of-scope detection
# ---------------------------------------------------------------------------

_OOS_PATTERNS: list[re.Pattern] = [
    # Trivia / general knowledge unrelated to finance
    re.compile(r"\b(prime\s+minister|president|minister|government|politics|election|parliament|modi|rahul|bjp|congress)\b", re.I),
    re.compile(r"\b(joke|funny|laugh|comedy|humor)\b", re.I),
    re.compile(r"\b(weather|temperature|forecast|rain|sunny|climate)\b", re.I),
    re.compile(r"\b(movie|film|series|web\s+series|netflix|amazon\s+prime|ott|bollywood|hollywood|actor|actress)\b", re.I),
    re.compile(r"\b(cricket|football|ipl|soccer|sport|player|team|match|score)\b", re.I),
    re.compile(r"\b(recipe|cook|food|restaurant|dish|meal|calorie)\b", re.I),
    re.compile(r"\b(python|javascript|java|code|program|algorithm|sql|html|css|software|debug|error|function|class|variable)\b", re.I),
    re.compile(r"\b(translate|translation|language|grammar|spell\s+check)\b", re.I),
    re.compile(r"\b(song|music|album|singer|band|concert|artist)\b", re.I),
    re.compile(r"\b(hotel|travel|flight|trip|tourist|visa|passport|vacation|holiday)\b", re.I),
    re.compile(r"\b(doctor|medicine|health|disease|symptom|hospital|diagnosis|cure|vaccine)\b", re.I),
    re.compile(r"\b(relationship|love|girlfriend|boyfriend|marriage|dating|breakup)\b", re.I),
    re.compile(r"\b(horoscope|astrology|zodiac|tarot|numerology)\b", re.I),
    re.compile(r"\b(cryptocurrency|bitcoin|ethereum|crypto|nft|blockchain)\b", re.I),
    re.compile(r"\b(news|headline|current\s+event|latest)\b", re.I),
    re.compile(r"\b(quiz|trivia|puzzle|riddle)\b", re.I),
]

# If the message contains any of these mutual-fund anchors, it's in-scope
# even if it accidentally matches an OOS keyword.
_INSCOPE_ANCHORS: list[re.Pattern] = [
    re.compile(r"\b(mutual\s+fund|motilal|oswal|nav|sip|aum|elss|expense\s+ratio|exit\s+load|fund\s+manager|riskometer|benchmark|nifty|midcap|smallcap|large\s+cap|flexi\s+cap|multicap|index\s+fund|fof|folio|redemption|lump\s+?sum|stamp\s+duty|ltcg|stcg|capital\s+gains|groww)\b", re.I),
]


def is_out_of_scope(message: str) -> bool:
    """Return True if the message is clearly unrelated to Motilal Oswal Mutual Funds."""
    # If any in-scope anchor is present, it's NOT out of scope
    for anchor in _INSCOPE_ANCHORS:
        if anchor.search(message):
            return False
    # Check OOS keywords
    for pat in _OOS_PATTERNS:
        if pat.search(message):
            return True
    return False


# ---------------------------------------------------------------------------
# Response generators
# ---------------------------------------------------------------------------

def generate_greeting_response(message: str) -> dict:
    """Return a warm greeting response without hitting any API."""
    norm = _normalize(message)

    if re.search(r"how\s+(are|r)\s+(you|u)", norm):
        answer = (
            f"I'm doing great! 😊 I'm here to help you with {TOPIC}. "
            "What would you like to know?"
        )
    elif re.search(r"what\s+can\s+you\s+do|what\s+do\s+you\s+do|what\s+are\s+you\s+(capable|able)|tell\s+me\s+about\s+yourself|who\s+are\s+you", norm):
        answer = (
            f"I can help you answer questions related to {TOPIC}, "
            "using the information available in this chatbot."
        )
    else:
        answer = (
            f"Hey! 👋 I'm here to help you with {TOPIC}. "
            "Ask me anything related to it, and I'll help you out."
        )

    return {
        "answer": answer,
        "source_link": None,
        "last_updated_from_sources": None,
        "response_type": "greeting",
    }


def generate_out_of_scope_response() -> dict:
    """Return a polite, brief out-of-scope refusal."""
    return {
        "answer": (
            f"Sorry, I can only help with questions related to {TOPIC}. "
            "Please ask something within that area."
        ),
        "source_link": None,
        "last_updated_from_sources": None,
        "response_type": "out_of_scope",
    }
