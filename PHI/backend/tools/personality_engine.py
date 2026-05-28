"""Personality Engine — ADVANCED: sentence-transformer emotion classification,
SQLite-persistent conversational memory, persona serialization,
communication style NLP analysis, mood tracking with trends.

7 built-in personalities + unlimited custom personas, all persisted in SQLite.
"""

import json
import os
import re
import sqlite3
import threading
import logging
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path(os.path.dirname(os.path.abspath(__file__))) / "personality.db"
_local = threading.local()


def _get_db() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
    return _local.conn


def _init_db():
    db = _get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS personalities (
            key TEXT PRIMARY KEY, name TEXT NOT NULL,
            config TEXT NOT NULL, is_builtin INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversation_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL, mentions INTEGER DEFAULT 1,
            first_discussed TEXT NOT NULL, last_discussed TEXT NOT NULL,
            summary TEXT DEFAULT '', users TEXT DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL, category TEXT NOT NULL,
            value TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(username, category)
        );
        CREATE TABLE IF NOT EXISTS mood_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, mood TEXT NOT NULL,
            intensity REAL DEFAULT 0.5, context TEXT DEFAULT '',
            source TEXT DEFAULT 'detect'
        );
        CREATE INDEX IF NOT EXISTS idx_topics_mentions ON conversation_topics(mentions);
        CREATE INDEX IF NOT EXISTS idx_mood_ts ON mood_history(timestamp);
    """)
    db.commit()
    _seed_builtins()


def _seed_builtins():
    db = _get_db()
    existing = db.execute("SELECT COUNT(*) FROM personalities WHERE is_builtin=1").fetchone()[0]
    if existing > 0:
        return
    builtins = {
        "professional": {"name": "Professional", "description": "Efficient, precise, business-appropriate tone",
                         "tone": "formal and efficient", "formality": 0.9, "verbosity": 0.5,
                         "humor": 0.1, "empathy": 0.4, "proactiveness": 0.6, "catchphrase": "",
                         "traits": "concise, data-driven, solution-oriented",
                         "rules": ["Avoid casual language and emojis", "Get straight to the point",
                                    "Use data and facts when possible", "Address user by name sparingly"]},
        "funny": {"name": "Funny", "description": "Witty, humorous, lighthearted assistant",
                   "tone": "playful and witty", "formality": 0.2, "verbosity": 0.7,
                   "humor": 0.9, "empathy": 0.5, "proactiveness": 0.7,
                   "catchphrase": "Here's the scoop, buddy!",
                   "traits": "quick-witted, pun-loving, playful",
                   "rules": ["Use humor and wordplay naturally", "Tell a joke when appropriate",
                              "Keep it light even with serious topics", "Use emojis occasionally"]},
        "teacher": {"name": "Teacher", "description": "Educational, patient, explains concepts thoroughly",
                     "tone": "patient and instructive", "formality": 0.6, "verbosity": 0.8,
                     "humor": 0.3, "empathy": 0.7, "proactiveness": 0.5,
                     "catchphrase": "Let me explain that step by step.",
                     "traits": "thorough, encouraging, Socratic",
                     "rules": ["Explain concepts step by step", "Use analogies and examples",
                                "Ask questions to check understanding", "Break complex topics into digestible parts"]},
        "hacker": {"name": "Hacker", "description": "Tech-savvy, cyberpunk, uses technical jargon",
                    "tone": "cyberpunk and technical", "formality": 0.3, "verbosity": 0.6,
                    "humor": 0.4, "empathy": 0.3, "proactiveness": 0.8,
                    "catchphrase": "Access granted.",
                    "traits": "technical, efficient, no-nonsense",
                    "rules": ["Use technical terminology freely", "Be direct and efficient",
                               "Reference cyberpunk culture occasionally", "Use matrix/terminal metaphors"]},
        "mentor": {"name": "Mentor", "description": "Supportive, wise, focuses on growth and guidance",
                    "tone": "warm and encouraging", "formality": 0.4, "verbosity": 0.7,
                    "humor": 0.3, "empathy": 0.9, "proactiveness": 0.6,
                    "catchphrase": "I believe in you.",
                    "traits": "supportive, wise, growth-oriented",
                    "rules": ["Focus on user's growth and development", "Offer encouragement alongside solutions",
                               "Ask reflective questions", "Share wisdom and perspective", "Celebrate user's wins"]},
        "poet": {"name": "Poet", "description": "Artistic, eloquent, responds with poetic flair",
                  "tone": "eloquent and lyrical", "formality": 0.7, "verbosity": 0.9,
                  "humor": 0.2, "empathy": 0.6, "proactiveness": 0.4, "catchphrase": "",
                  "traits": "creative, descriptive, metaphorical",
                  "rules": ["Use rich language and metaphors", "Paint word pictures",
                             "Be creative even with mundane topics", "Reference literature and art occasionally"]},
        "therapist": {"name": "Therapist", "description": "Empathetic listener, focuses on emotional well-being",
                       "tone": "gentle and empathetic", "formality": 0.4, "verbosity": 0.6,
                       "humor": 0.1, "empathy": 1.0, "proactiveness": 0.3,
                       "catchphrase": "How does that make you feel?",
                       "traits": "listening, validating, gentle",
                       "rules": ["Listen actively and validate feelings", "Use therapeutic communication techniques",
                                  "Never dismiss concerns", "Offer perspective without judgment",
                                  "Know when to suggest professional help"]},
    }
    now = datetime.now(timezone.utc).isoformat()
    for key, config in builtins.items():
        db.execute("INSERT OR IGNORE INTO personalities VALUES (?, ?, ?, 1, ?)",
                   (key, config["name"], json.dumps(config), now))
    db.commit()


_init_db()

PERSONALITIES = {}
DEFAULT_PERSONALITY = "professional"
_active_personality = DEFAULT_PERSONALITY


def _load_personalities():
    global PERSONALITIES
    db = _get_db()
    rows = db.execute("SELECT key, config FROM personalities").fetchall()
    PERSONALITIES = {r["key"]: json.loads(r["config"]) for r in rows}


_load_personalities()


# --- Core personality functions ---

def get_active() -> str:
    return _active_personality


async def set_personality(mode: str) -> str:
    global _active_personality
    mode = mode.lower().strip()
    if mode not in PERSONALITIES:
        available = ", ".join(sorted(PERSONALITIES.keys()))
        return f"Unknown personality '{mode}'. Available: {available}"
    _active_personality = mode
    profile = PERSONALITIES[mode]
    logger.info(f"Personality set to: {mode} ({profile['name']})")
    return f"Personality set to **{profile['name']}**: {profile['description']}"


async def get_personality() -> str:
    profile = PERSONALITIES.get(_active_personality, PERSONALITIES.get(DEFAULT_PERSONALITY, {}))
    return json.dumps({"active": _active_personality, "name": profile.get("name"),
                        "description": profile.get("description"),
                        "tone": profile.get("tone"), "traits": profile.get("traits")}, indent=2)


async def list_personalities() -> str:
    return json.dumps({key: {"name": p.get("name"), "description": p.get("description"),
                              "tone": p.get("tone"), "traits": p.get("traits")}
                        for key, p in PERSONALITIES.items()}, indent=2)


def get_personality_prompt_extension(user_name: str) -> str:
    profile = PERSONALITIES.get(_active_personality, PERSONALITIES.get(DEFAULT_PERSONALITY, {}))
    rules_str = "\n".join(f"{i+1}. {r}" for i, r in enumerate(profile.get("rules", [])))
    extra = profile.get("catchphrase", "")
    extra_str = f"\nYour catchphrase is: \"{extra}\"" if extra else ""
    return f"""
CURRENT PERSONALITY MODE: {profile.get('name', 'Professional')}
Tone: {profile.get('tone', 'formal and efficient')}
Traits: {profile.get('traits', 'concise, data-driven')}

Personality Rules:
{rules_str}{extra_str}

Speak naturally within this personality. Do not announce your personality mode unless asked.
"""


# --- Conversational Memory with SQLite ---

async def remember_topic(topic: str, details: str, user_name: str = "") -> str:
    db = _get_db()
    topic_lower = topic.lower().strip()
    existing = db.execute("SELECT * FROM conversation_topics WHERE topic=?", (topic_lower,)).fetchone()
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        mentions = existing["mentions"] + 1
        old_summary = existing["summary"]
        users = json.loads(existing["users"])
        if user_name and user_name not in users:
            users.append(user_name)
        db.execute("UPDATE conversation_topics SET mentions=?, last_discussed=?, summary=?, users=? WHERE id=?",
                   (mentions, now, f"{old_summary[:100]} | {details[:200]}", json.dumps(users), existing["id"]))
    else:
        db.execute("INSERT INTO conversation_topics (topic, mentions, first_discussed, last_discussed, summary, users) VALUES (?, 1, ?, ?, ?, ?)",
                   (topic_lower, now, now, details[:300], json.dumps([user_name] if user_name else [])))
    db.commit()
    count = db.execute("SELECT SUM(mentions) as total FROM conversation_topics").fetchone()["total"] or 0
    return f"Remembered topic '{topic}' (total topics: {count})"


async def recall_topics(limit: int = 10) -> str:
    db = _get_db()
    rows = db.execute("SELECT * FROM conversation_topics ORDER BY mentions DESC LIMIT ?", (int(limit),)).fetchall()
    return json.dumps({"topics": [{"topic": r["topic"], "mentions": r["mentions"],
                                    "last_discussed": r["last_discussed"],
                                    "summary": r["summary"][:100]} for r in rows],
                        "total_topics": db.execute("SELECT COUNT(*) as c FROM conversation_topics").fetchone()["c"]}, indent=2)


async def remember_preference(category: str, value: str, username: str = "") -> str:
    db = _get_db()
    user = username or "default"
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT OR REPLACE INTO user_preferences (username, category, value, updated_at) VALUES (?, ?, ?, ?)",
               (user, category.lower().strip(), value.strip(), now))
    db.commit()
    return f"Remembered preference: {category} = {value} for {user}"


async def get_preferences(username: str = "") -> str:
    db = _get_db()
    user = username or "default"
    rows = db.execute("SELECT category, value FROM user_preferences WHERE username=? ORDER BY category", (user,)).fetchall()
    return json.dumps({r["category"]: r["value"] for r in rows}, indent=2)


async def get_conversation_summary() -> str:
    db = _get_db()
    topics = db.execute("SELECT COUNT(*) as c, SUM(mentions) as total_m FROM conversation_topics").fetchone()
    prefs = db.execute("SELECT COUNT(*) as c FROM user_preferences").fetchone()
    moods = db.execute("SELECT COUNT(*) as c FROM mood_history").fetchone()
    top_topics = db.execute("SELECT topic, mentions FROM conversation_topics ORDER BY mentions DESC LIMIT 5").fetchall()
    return json.dumps({
        "total_topics": topics["c"],
        "total_mentions": topics["total_m"] or 0,
        "frequent_topics": [r["topic"] for r in top_topics],
        "stored_preferences": prefs["c"],
        "mood_entries": moods["c"],
        "active_personality": _active_personality,
    }, indent=2)


# --- Advanced Emotion Detection with sentence-transformers ---

_EMOTION_MODEL = None
_EMOTION_LABELS = ["happy", "sad", "angry", "surprised", "neutral",
                    "frustrated", "excited", "confused", "anxious", "grateful"]
_EMOTION_EXAMPLES = {
    "happy": ["I'm so excited about this!", "This is wonderful news!", "I feel great today!"],
    "sad": ["I'm feeling really down", "That's disappointing", "I miss those times"],
    "angry": ["This is infuriating!", "I can't believe this!", "That makes me so mad"],
    "frustrated": ["It keeps failing", "Why won't this work?", "I'm so stuck on this"],
    "excited": ["Amazing! This is incredible!", "I can't wait!", "This is the best thing ever"],
    "confused": ["I don't understand", "What does this mean?", "This doesn't make sense"],
    "anxious": ["I'm worried about this", "What if it goes wrong?", "I'm nervous about"],
    "grateful": ["Thank you so much!", "I really appreciate this", "That means a lot"],
    "surprised": ["Wow, I didn't expect that!", "No way!", "That's unexpected"],
    "neutral": ["It's fine", "Okay, I see", "Alright then"],
}

_THESAURUS = {
    "happy": ["great", "awesome", "wonderful", "fantastic", "love", "excellent",
               "amazing", "beautiful", "perfect", "joy", "delighted", "thrilled",
               "glad", "pleased", "cheerful", "elated", "ecstatic"],
    "sad": ["unfortunate", "regret", "disappoint", "lonely", "miss", "depress",
             "sorry", "sadly", "gloomy", "miserable", "heartbroken", "sorrow",
             "grief", "melancholy", "down"],
    "angry": ["furious", "mad", "outrage", "unacceptable", "livid", "irate",
               "fume", "enraged", "irritated", "annoyed", "frustrated"],
    "frustrated": ["frustrat", "annoying", "useless", "stupid", "why won't",
                    "not working", "broken", "terrible", "hate", "waste",
                    "ridiculous", "cannot", "can't even", "stuck", "fails"],
    "excited": ["wow", "incredible", "thrilled", "can't wait", "hyped",
                 "pumped", "stoked", "amazing", "awesome"],
    "confused": ["confus", "don't understand", "unclear", "what does",
                  "how does", "not sure", "maybe", "perhaps", "huh",
                  "weird", "strange", "puzzling"],
    "anxious": ["worried", "nervous", "anxious", "scared", "fear",
                 "concerned", "stressed", "overwhelmed", "panic"],
    "grateful": ["thank", "appreciate", "grateful", "thankful", "blessed"],
    "surprised": ["surprise", "unexpected", "can't believe", "no way",
                   "wow", "shocked", "astonished", "stunned"],
    "neutral": ["okay", "fine", "alright", "sure", "whatever", "i see"],
}


def _keyword_emotion_score(text: str) -> Dict[str, float]:
    text_lower = text.lower()
    scores = {}
    for emotion, words in _THESAURUS.items():
        score = sum(1 for w in words if w in text_lower)
        if score > 0:
            scores[emotion] = score
    return scores


async def detect_emotion(text: str, use_ml: bool = True) -> str:
    scores = _keyword_emotion_score(text)
    ml_score = 0
    if use_ml:
        try:
            from sentence_transformers import SentenceTransformer
            global _EMOTION_MODEL
            if _EMOTION_MODEL is None:
                _EMOTION_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            emb = _EMOTION_MODEL.encode([text])
            ex_embs = _EMOTION_MODEL.encode(_EMOTION_LABELS)
            import numpy as np
            similarities = np.dot(emb, ex_embs.T)[0]
            for i, label in enumerate(_EMOTION_LABELS):
                scores[label] = scores.get(label, 0) + float(similarities[i] * 2)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"ML emotion detection unavailable: {e}")
    if not scores:
        scores["neutral"] = 0.5
    primary = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    # Persist to mood history
    db = _get_db()
    db.execute("INSERT INTO mood_history (timestamp, mood, intensity, source) VALUES (?, ?, ?, ?)",
               (datetime.now(timezone.utc).isoformat(), primary, round(scores[primary] / total, 2),
                "ml" if use_ml else "keyword"))
    db.commit()
    return json.dumps({
        "primary": primary,
        "confidence": round(scores[primary] / total, 2),
        "scores": {k: round(v / total, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])[:5]},
    }, indent=2)


async def mood_trend(days: int = 7) -> str:
    db = _get_db()
    since = (datetime.now(timezone.utc).timestamp() - days * 86400)
    since_iso = datetime.fromtimestamp(since, tz=timezone.utc).isoformat()
    rows = db.execute("SELECT mood, COUNT(*) as cnt FROM mood_history WHERE timestamp > ? GROUP BY mood ORDER BY cnt DESC",
                      (since_iso,)).fetchall()
    if not rows:
        return json.dumps({"message": "No mood data for this period"})
    return json.dumps({"period_days": days, "moods": [dict(r) for r in rows],
                        "total": sum(r["cnt"] for r in rows)}, indent=2)


# --- Custom Persona Creator with SQLite ---

async def create_persona(name: str, tone: str = "neutral", formality: float = 0.5,
                          verbosity: float = 0.5, humor: float = 0.3, empathy: float = 0.5,
                          traits: str = "", catchphrase: str = "", rules: str = "") -> str:
    key = name.lower().strip()
    def _clamp(v, lo=0.0, hi=1.0):
        try: return max(lo, min(hi, float(v)))
        except (TypeError, ValueError): return lo + (hi - lo) / 2
    profile = {"name": name.strip(), "description": f"Custom persona: {name}",
               "tone": tone, "formality": _clamp(formality),
               "verbosity": _clamp(verbosity), "humor": _clamp(humor),
               "empathy": _clamp(empathy), "proactiveness": _clamp(0.5),
               "catchphrase": catchphrase, "traits": traits or "custom",
               "rules": [r.strip() for r in rules.split("\n") if r.strip()] if rules else ["Be yourself"]}
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT OR REPLACE INTO personalities VALUES (?, ?, ?, 0, ?)",
               (key, profile["name"], json.dumps(profile), now))
    db.commit()
    PERSONALITIES[key] = profile
    return json.dumps({"status": "created", "name": name, "profile": profile}, indent=2)


async def delete_persona(name: str) -> str:
    key = name.lower().strip()
    db = _get_db()
    row = db.execute("SELECT is_builtin FROM personalities WHERE key=?", (key,)).fetchone()
    if not row:
        return f"Persona '{name}' not found"
    if row["is_builtin"]:
        return f"Cannot delete built-in personality '{name}'"
    db.execute("DELETE FROM personalities WHERE key=?", (key,))
    db.commit()
    PERSONALITIES.pop(key, None)
    global _active_personality
    if _active_personality == key:
        _active_personality = DEFAULT_PERSONALITY
    return f"Deleted persona '{name}'"


# --- Communication Style Report with NLP ---

async def communication_style_report(conversation_text: str) -> str:
    sentences = [s.strip() for s in conversation_text.replace("?", "?\n").replace("!", "!\n").split("\n") if s.strip()]
    word_count = len(conversation_text.split())
    sentence_count = len(sentences)
    avg_sentence_length = round(word_count / sentence_count, 1) if sentence_count else 0
    question_count = sum(1 for s in sentences if "?" in s)
    exclamation_count = sum(1 for s in sentences if "!" in s)
    words = conversation_text.lower().split()
    unique_words = len(set(words))
    lexical_diversity = round(unique_words / word_count, 3) if word_count else 0
    filler_words = sum(1 for w in words if w in ("um", "uh", "like", "actually", "basically", "literally", "you know", "i mean", "sort of", "kind of"))
    tech_terms = sum(1 for w in words if w in ("code", "api", "function", "server", "database", "python", "javascript", "docker", "git", "cloud", "deploy", "bug", "test", "config", "memory", "thread", "async", "query", "endpoint", "middleware", "kubernetes", "microservice", "pipeline", "workflow"))
    avg_word_length = round(sum(len(w) for w in words) / len(words), 2) if words else 0
    # Sentiment via keyword
    pos = sum(1 for w in words if w in ("good", "great", "nice", "awesome", "amazing", "love", "perfect", "excellent", "happy", "wonderful", "fantastic", "brilliant", "superb"))
    neg = sum(1 for w in words if w in ("bad", "terrible", "awful", "hate", "worst", "horrible", "sucks", "stupid", "broken", "wrong", "failed", "useless"))
    # Readability (Flesch-like approximation)
    syllables = sum(max(1, len(re.findall(r'[aeiouy]+', w))) for w in words)
    readability = max(0, min(100, 206.835 - 1.015 * (word_count / max(sentence_count, 1)) - 84.6 * (syllables / max(word_count, 1))))
    report = {
        "total_words": word_count,
        "total_sentences": sentence_count,
        "avg_sentence_length": avg_sentence_length,
        "questions_asked": question_count,
        "exclamations": exclamation_count,
        "lexical_diversity": lexical_diversity,
        "unique_words": unique_words,
        "avg_word_length": avg_word_length,
        "filler_word_count": filler_words,
        "technical_term_count": tech_terms,
        "positive_word_count": pos,
        "negative_word_count": neg,
        "readability_score": round(readability, 1),
        "readability_label": "Very Easy" if readability > 90 else "Easy" if readability > 70 else "Fairly Easy" if readability > 60 else "Standard" if readability > 50 else "Fairly Difficult" if readability > 30 else "Difficult",
        "suggestions": [],
    }
    if avg_sentence_length > 25:
        report["suggestions"].append(f"Your sentences avg {avg_sentence_length} words. Try breaking long sentences (target: <20 words) for clarity.")
    if lexical_diversity < 0.3:
        report["suggestions"].append(f"Lexical diversity is low ({lexical_diversity}). Expand vocabulary for more precise expression.")
    if filler_words > word_count * 0.02:
        report["suggestions"].append(f"You use {filler_words} filler words ({round(filler_words/word_count*100,1)}%). Reduce 'um', 'like', 'actually'.")
    if question_count < sentence_count * 0.05 and sentence_count > 5:
        report["suggestions"].append("Very few questions asked. Try engaging more with questions to drive conversation.")
    if readability < 50:
        report["suggestions"].append(f"Readability score is {round(readability)} (Difficult). Use shorter sentences and simpler words.")
    if not report["suggestions"]:
        report["suggestions"].append("Your communication style is well-balanced. Keep it up!")
    return json.dumps(report, indent=2)


# --- Digital Twin: Style Learning and Mimicry ---

_DIGITAL_TWIN_CACHE: Dict[str, dict] = {}


def _init_digital_twin_db():
    db = _get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS digital_twins (
            username TEXT PRIMARY KEY,
            profile TEXT NOT NULL,
            samples_analyzed INTEGER DEFAULT 0,
            last_updated TEXT NOT NULL
        );
    """)
    db.commit()


_init_digital_twin_db()


def _analyze_style_profile(text: str) -> dict:
    sentences = [s.strip() for s in re.split(r'[.!?\n]+', text) if s.strip()]
    words = text.split()
    word_count = len(words)
    if word_count < 3:
        return {"error": "Not enough text to analyze (minimum 3 words needed)"}

    sentence_lengths = [len(s.split()) for s in sentences] if sentences else [0]
    mean_sl = sum(sentence_lengths) / len(sentence_lengths)
    sorted_sl = sorted(sentence_lengths)
    mid = len(sorted_sl) // 2
    median_sl = sorted_sl[mid] if len(sorted_sl) % 2 else (sorted_sl[mid - 1] + sorted_sl[mid]) / 2

    variance = sum((x - mean_sl) ** 2 for x in sentence_lengths) / len(sentence_lengths)
    std_sl = variance ** 0.5

    lower_words = [w for w in words if len(w) > 0 and w[0].islower() and w[0].isalpha()] if words else []
    capital_style = "lowercase_start" if len(lower_words) > word_count * 0.3 else "capitalized_start"

    total_chars = sum(len(w) for w in words)
    avg_word_len = total_chars / word_count if word_count else 0

    word_freq: Dict[str, int] = {}
    for w in words:
        wl = w.lower().strip(".,!?;:'\"()[]{}")
        if len(wl) > 2:
            word_freq[wl] = word_freq.get(wl, 0) + 1
    top_words = sorted(word_freq.items(), key=lambda x: -x[1])[:20]

    question_count = text.count("?")
    exclaim_count = text.count("!")
    ellipsis_count = text.count("...")
    period_count = text.count(".")
    comma_count = text.count(",")

    emojis = re.findall(r'[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]', text)
    emoji_count = len(emojis)
    emoji_freq = round(emoji_count / word_count, 4) if word_count else 0

    filler = sum(1 for w in lower_words if w in (
        "um", "uh", "like", "actually", "basically", "literally", "you", "know",
        "i", "mean", "sort", "of", "kind", "just", "well", "so", "anyway", "right",
        "okay", "yeah", "hmm"))
    filler_pct = round(filler / word_count * 100, 1) if word_count else 0

    formality_score = 50
    if capital_style == "capitalized_start":
        formality_score += 10
    formality_score -= min(filler_pct * 2, 20)
    if comma_count > word_count * 0.05:
        formality_score += 5
    if exclaim_count > word_count * 0.02:
        formality_score -= 5
    if emoji_count > 0:
        formality_score -= min(emoji_count * 3, 15)
    formality_score = max(0, min(100, formality_score))

    unique_words = len(set(w.lower().strip(".,!?;:'\"()[]{}") for w in words if w.strip(".,!?;:'\"()[]{}")))
    lexical_diversity = round(unique_words / word_count, 3) if word_count else 0

    slang = sum(1 for w in lower_words if w in (
        "gonna", "wanna", "gotta", "gimme", "lemme", "dunno", "kinda", "sorta",
        "lotta", "coulda", "shoulda", "woulda", "cuz", "bc", "tho", "afk", "btw",
        "idk", "imo", "lol", "lmao", "tbh", "rn", "omg", "nvm", "ikr", "smh",
        "fr", "ong", "no cap", "sus", "based", "cringe", "bet"))
    slang_level = "high" if slang > 5 else "moderate" if slang > 2 else "low"

    return {
        "samples_analyzed": 1,
        "word_count": word_count,
        "sentence_stats": {
            "mean_length": round(mean_sl, 1),
            "median_length": round(median_sl, 1),
            "std_dev": round(std_sl, 1),
            "min": min(sentence_lengths),
            "max": max(sentence_lengths),
            "total": len(sentences),
        },
        "word_stats": {
            "avg_length": round(avg_word_len, 2),
            "unique_words": unique_words,
            "lexical_diversity": lexical_diversity,
        },
        "punctuation": {
            "questions": question_count,
            "exclamations": exclaim_count,
            "ellipsis": ellipsis_count,
            "periods": period_count,
            "commas": comma_count,
        },
        "capitalization": capital_style,
        "formality_score": formality_score,
        "formality_label": "Formal" if formality_score > 70 else "Neutral" if formality_score > 40 else "Casual",
        "emoji_count": emoji_count,
        "emoji_frequency": emoji_freq,
        "common_words": [{"word": w, "count": c} for w, c in top_words],
        "filler_percentage": filler_pct,
        "slang_level": slang_level,
        "estimated_tone": "Analytical" if lexical_diversity > 0.6 and mean_sl > 18 else
                          "Conversational" if mean_sl < 14 else
                          "Descriptive",
    }


def _merge_profiles(existing: dict, new: dict) -> dict:
    merged = dict(new)
    merged["samples_analyzed"] = existing.get("samples_analyzed", 0) + new.get("samples_analyzed", 1)

    for key in ("sentence_stats", "word_stats", "punctuation"):
        if key in existing and key in new:
            merged[key] = {}
            for k in new[key]:
                if k in ("total", "samples_analyzed"):
                    merged[key][k] = existing[key].get(k, 0) + new[key].get(k, 0)
                elif isinstance(new[key][k], (int, float)) and isinstance(existing[key].get(k), (int, float)):
                    merged[key][k] = round(
                        (existing[key].get(k, 0) * existing.get("samples_analyzed", 1) +
                         new[key].get(k, 0) * new.get("samples_analyzed", 1)) /
                        max(merged["samples_analyzed"], 1), 2
                    )
                else:
                    merged[key][k] = new[key].get(k, existing.get(key, {}).get(k, ""))

    merged["common_words"] = new.get("common_words", existing.get("common_words", []))
    if existing.get("common_words") and new.get("common_words"):
        combined = {w["word"]: w["count"] for w in existing["common_words"]}
        for w in new["common_words"]:
            combined[w["word"]] = combined.get(w["word"], 0) + w["count"]
        merged["common_words"] = sorted([{"word": k, "count": v} for k, v in combined.items()],
                                        key=lambda x: -x["count"])[:20]

    merged["formality_score"] = round(
        (existing.get("formality_score", 50) * existing.get("samples_analyzed", 1) +
         new.get("formality_score", 50) * new.get("samples_analyzed", 1)) /
        max(merged["samples_analyzed"], 1)
    )
    merged["formality_label"] = "Formal" if merged["formality_score"] > 70 else "Neutral" if merged["formality_score"] > 40 else "Casual"
    merged["filler_percentage"] = round(
        (existing.get("filler_percentage", 0) + new.get("filler_percentage", 0)) / 2, 1
    ) if merged["samples_analyzed"] > 1 else new.get("filler_percentage", 0)
    merged["emoji_count"] = existing.get("emoji_count", 0) + new.get("emoji_count", 0)
    merged["emoji_frequency"] = round(
        (existing.get("emoji_frequency", 0) + new.get("emoji_frequency", 0)) / 2, 4
    ) if merged["samples_analyzed"] > 1 else new.get("emoji_frequency", 0)
    return merged


async def digital_twin_learn(username: str, text_sample: str) -> str:
    if len(text_sample.strip().split()) < 3:
        return json.dumps({"error": "Need at least 3 words to analyze style"})
    db = _get_db()
    profile = _analyze_style_profile(text_sample)
    if "error" in profile:
        return json.dumps(profile)
    existing_row = db.execute("SELECT profile FROM digital_twins WHERE username=?", (username,)).fetchone()
    if existing_row:
        existing = json.loads(existing_row["profile"])
        profile = _merge_profiles(existing, profile)
    now = datetime.now(timezone.utc).isoformat()
    db.execute("INSERT OR REPLACE INTO digital_twins VALUES (?, ?, ?, ?)",
               (username, json.dumps(profile), profile["samples_analyzed"], now))
    db.commit()
    profile["last_updated"] = now
    _DIGITAL_TWIN_CACHE[username] = profile
    return json.dumps({"status": "learned", "username": username,
                        "samples_analyzed": profile["samples_analyzed"],
                        "style_summary": {
                            "formality": profile.get("formality_label"),
                            "tone": profile.get("estimated_tone"),
                            "avg_sentence": profile.get("sentence_stats", {}).get("mean_length"),
                            "vocabulary": profile.get("word_stats", {}).get("lexical_diversity"),
                            "slang": profile.get("slang_level"),
                            "emoji_freq": profile.get("emoji_frequency"),
                        }}, indent=2)


async def digital_twin_profile(username: str) -> str:
    db = _get_db()
    if username in _DIGITAL_TWIN_CACHE:
        return json.dumps(_DIGITAL_TWIN_CACHE[username], indent=2)
    row = db.execute("SELECT profile, samples_analyzed, last_updated FROM digital_twins WHERE username=?", (username,)).fetchone()
    if not row:
        return json.dumps({"error": f"No digital twin profile for '{username}'. Use digital_twin_learn to build one."})
    profile = json.loads(row["profile"])
    profile["last_updated"] = row["last_updated"]
    _DIGITAL_TWIN_CACHE[username] = profile
    return json.dumps(profile, indent=2)


async def digital_twin_mimic(username: str, custom_instructions: str = "") -> str:
    db = _get_db()
    row = db.execute("SELECT profile FROM digital_twins WHERE username=?", (username,)).fetchone()
    if not row:
        return json.dumps({"error": f"No digital twin for '{username}'"})
    p = json.loads(row["profile"])
    sentence_style = f"{p.get('sentence_stats', {}).get('mean_length', 15)} words on average"
    cap_style = p.get("capitalization", "standard")
    formality = p.get("formality_label", "Neutral")
    tone = p.get("estimated_tone", "Conversational")
    common = [w["word"] for w in p.get("common_words", [])[:10]]
    common_str = ", ".join(common) if common else "standard vocabulary"
    slang = p.get("slang_level", "low")
    filler = p.get("filler_percentage", 0)
    filler_note = f"{filler}% of speech is filler" if filler > 0 else "minimal filler words"
    emoji_hint = f"User uses emojis ({p.get('emoji_count', 0)} found in samples)." if p.get("emoji_count", 0) > 0 else ""
    mimic_prompt = f"""
You are mimicking {username}'s communication style. Adapt your response to match:

FORMALITY: {formality} (score: {p.get('formality_score', 50)}/100)
TONE: {tone}
SENTENCE LENGTH: {sentence_style}
CAPITALIZATION: {cap_style}
VOCABULARY: prefers words like {common_str}
SLANG LEVEL: {slang}
FILLER WORDS: {filler_note}
{emoji_hint}
"""
    if custom_instructions:
        mimic_prompt += f"\nADDITIONAL INSTRUCTIONS: {custom_instructions}\n"
    return json.dumps({
        "username": username,
        "mimic_instructions": mimic_prompt.strip(),
        "style_profile": {
            "formality": formality,
            "tone": tone,
            "avg_sentence_words": p.get("sentence_stats", {}).get("mean_length"),
            "lexical_diversity": p.get("word_stats", {}).get("lexical_diversity"),
            "common_words": common[:5],
        },
        "usage": "Pass mimic_instructions as system prompt extension to make the AI write in the user's style."
    }, indent=2)


async def digital_twin_compare(username_a: str, username_b: str) -> str:
    db = _get_db()
    ra = db.execute("SELECT profile FROM digital_twins WHERE username=?", (username_a,)).fetchone()
    rb = db.execute("SELECT profile FROM digital_twins WHERE username=?", (username_b,)).fetchone()
    if not ra:
        return json.dumps({"error": f"No profile for '{username_a}'"})
    if not rb:
        return json.dumps({"error": f"No profile for '{username_b}'"})
    pa = json.loads(ra["profile"])
    pb = json.loads(rb["profile"])
    comparison = {
        "formality": {"a": pa.get("formality_label"), "b": pb.get("formality_label"),
                      "a_score": pa.get("formality_score"), "b_score": pb.get("formality_score"),
                      "delta": pa.get("formality_score", 50) - pb.get("formality_score", 50)},
        "tone": {"a": pa.get("estimated_tone"), "b": pb.get("estimated_tone")},
        "avg_sentence_length": {"a": pa.get("sentence_stats", {}).get("mean_length"),
                                "b": pb.get("sentence_stats", {}).get("mean_length")},
        "lexical_diversity": {"a": pa.get("word_stats", {}).get("lexical_diversity"),
                              "b": pb.get("word_stats", {}).get("lexical_diversity")},
        "slang_level": {"a": pa.get("slang_level"), "b": pb.get("slang_level")},
        "emoji_usage": {"a": pa.get("emoji_count", 0), "b": pb.get("emoji_count", 0)},
        "samples_analyzed": {"a": pa.get("samples_analyzed", 0), "b": pb.get("samples_analyzed", 0)},
    }
    diffs = []
    if abs(comparison["formality"]["delta"]) > 10:
        more = username_a if comparison["formality"]["delta"] > 0 else username_b
        diffs.append(f"{more} is more formal")
    if comparison["avg_sentence_length"]["a"] and comparison["avg_sentence_length"]["b"]:
        delta_sl = comparison["avg_sentence_length"]["a"] - comparison["avg_sentence_length"]["b"]
        if abs(delta_sl) > 3:
            longer = username_a if delta_sl > 0 else username_b
            diffs.append(f"{longer} uses longer sentences")
    if comparison["slang_level"]["a"] != comparison["slang_level"]["b"]:
        more_slang = username_a if {"high": 3, "moderate": 2, "low": 1}.get(comparison["slang_level"]["a"], 0) > {"high": 3, "moderate": 2, "low": 1}.get(comparison["slang_level"]["b"], 0) else username_b
        diffs.append(f"{more_slang} uses more slang")
    comparison["key_differences"] = diffs
    return json.dumps(comparison, indent=2)


async def digital_twin_list() -> str:
    db = _get_db()
    rows = db.execute("SELECT username, samples_analyzed, last_updated FROM digital_twins ORDER BY last_updated DESC").fetchall()
    if not rows:
        return json.dumps({"message": "No digital twin profiles yet"})
    return json.dumps({"profiles": [dict(r) for r in rows], "total": len(rows)}, indent=2)


async def digital_twin_delete(username: str) -> str:
    db = _get_db()
    db.execute("DELETE FROM digital_twins WHERE username=?", (username,))
    db.commit()
    _DIGITAL_TWIN_CACHE.pop(username, None)
    return json.dumps({"deleted": True, "username": username})
