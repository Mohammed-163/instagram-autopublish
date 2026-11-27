"""Deterministic, read-only editorial recommendations from fixed-age Reel evidence."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

MIN_REACH = 100
MIN_POSTS_PER_THEME = 3
MAX_PER_THEME = 2
MAX_EVIDENCE_SLOTS = 6
WEEKLY_SLOTS = 10

# Explicit aliases from historical topics; new, unclassified topics do not earn evidence.
THEME_ALIASES = {
    "دعاء": {"certainty-in-dua", "dua-relieves-heart-stress", "power-of-dua", "prayer-changes-destiny"},
    "فرج": {"relief-after-distress", "hope-in-divine-relief", "relief-and-divine-presence", "relief-is-near",
             "optimism-and-patience", "healing-broken-hearts"},
    "رزق": {"trusting-gods-provision", "delayed-provision-and-trust", "delayed-sustenance-faith",
             "divine-trust-and-provision", "rizq-is-peace", "sustenance-and-peace", "trust-in-god-sustenance"},
    "سكينة": {"finding-peace-when-lost", "god-is-the-only-refuge", "quran-comfort-heart",
               "spiritual-seclusion-comfort", "trusting-god-in-loneliness", "trusting-god-peace",
               "inner-peace-decisions", "peace-of-mind-decisions", "heart-certainty-in-allah"},
    "سعي": {"focus-on-effort-not-outcome", "god-compensates-struggle", "trust-in-god-and-effort"},
    "رضا": {"contentment-with-gods-decree", "accepting-divine-will", "contentment-and-peace", "contentment-is-trust",
             "dont-compare-your-path", "gods-perfect-plan", "gods-perfect-timing", "trust-gods-timing"},
    "رحمة": {"divine-mercy-amidst-pain", "gods-mercy-in-despair"},
}
ALIASES = {slug: theme for theme, slugs in THEME_ALIASES.items() for slug in slugs}


@dataclass(frozen=True)
class Idea:
    slug: str
    theme: str
    situation: str
    ayah_key: str


# Human-curated thematic pairings; the exact ayah always comes from the existing
# verified catalogue. These Iraqi openers are editorial copy, not tafsir.
IDEAS = (
    Idea("audience-late-dua", "دعاء", "آخر الليل، وهالدعوة بعدها بقلبك؟", "2:186"),
    Idea("audience-dua-direction", "دعاء", "وقفت تصلّي وما عرفت شتگول؟", "2:201"),
    Idea("audience-heavy-evening", "فرج", "رجعت للبيت وحسّيت اليوم كله ثگيل؟", "94:5-6"),
    Idea("audience-waiting-with-patience", "فرج", "صارلك تنتظر وما تعرف شگد بعد؟", "2:153"),
    Idea("audience-job-reply", "رزق", "كل شوي تفتح الإيميل تنتظر جواب الوظيفة؟", "65:3"),
    Idea("audience-tomorrow", "رزق", "تطفي الضوء وتبدي تحسب هموم باچر؟", "9:51"),
    Idea("audience-quiet-home", "سكينة", "البيت هادئ، بس بالك مو هادئ؟", "13:28"),
    Idea("audience-overload", "سكينة", "ورا كل إشعار شغلة ثانية براسك؟", "2:45"),
    Idea("audience-unseen-work", "سعي", "متعب نفسك بالدراسة، وما دا تشوف نتيجة؟", "53:39"),
    Idea("audience-start-again", "سعي", "خلصت شغلة وبقيت محتار شتبدي بعدها؟", "94:7-8"),
    Idea("audience-comparing-feed", "رضا", "فرحت لصاحبك، وبنفس اللحظة قارنت نفسك بيه؟", "2:152"),
    Idea("audience-small-good", "رضا", "تتذكّر كلشي ناقص وتنسى الشي الزين اللي صار اليوم؟", "14:7"),
    Idea("audience-regret", "رحمة", "من تهدأ بالليل، ترجع ببالك غلطة قديمة؟", "39:53"),
    Idea("audience-repair", "رحمة", "غلطت وتريد تبدي تصلح بدل ما تلوم نفسك؟", "4:110"),
)
ALIASES.update({idea.slug: idea.theme for idea in IDEAS})


def _count(value: object) -> bool:
    return type(value) is int and value >= 0


def recommend(posts: list[dict], week_start: date, verse_keys: set[str]) -> dict:
    """Rank repeated audience signals and reserve room for exploration.

    Caller provides canonical, on-time 24-hour snapshots. Dedupe using media ID;
    don't use rows at/after the forecast date (safe for Sunday reruns/backtests).
    A capture must also be available before the forecast date.
    Counts are summed within a post then divided by its reach. The median is
    across posts, not pooled reach, so one large Reel cannot win the ranking.
    """

    by_theme: dict[str, list[tuple[float, float]]] = defaultdict(list)
    all_rates: list[float] = []
    seen: set[str] = set()
    lower = week_start - timedelta(days=56)
    baghdad = ZoneInfo("Asia/Baghdad")
    for post in posts:
        media = post.get("media_id")
        reach, saved, shares = (post.get(k) for k in ("reach", "saved", "shares"))
        if (not isinstance(media, str) or not media or media in seen
                or post.get("measured_24h") is not True
                or not all(_count(n) for n in (reach, saved, shares))
                or reach < MIN_REACH
                or str(post.get("raw_visual_style", "")).endswith("__opener_situation_fallback_v1")):
            continue
        try:
            published, captured = (datetime.fromisoformat(str(post.get(k)).replace("Z", "+00:00"))
                                   for k in ("published_at", "captured_at"))
        except ValueError:
            continue
        if (published.tzinfo is None or captured.tzinfo is None
                or not lower <= published.astimezone(baghdad).date() < week_start
                or captured.astimezone(baghdad).date() >= week_start
                or not timedelta(hours=24) <= captured - published <= timedelta(hours=24, minutes=30)):
            continue
        seen.add(media)
        rates = (1000 * saved / reach, 1000 * shares / reach)
        all_rates.append(sum(rates))
        theme = ALIASES.get(post.get("topic"))
        if theme:
            by_theme[theme].append(rates)
    baseline = median(all_rates) if all_rates else None
    evidence = {}
    for theme, rates in by_theme.items():
        totals = [sum(pair) for pair in rates]
        middle = median(totals)
        above = sum(rate > baseline for rate in totals)
        evidence[theme] = {
            "posts": len(rates), "above_baseline": above, "combined": round(middle, 2),
            "saves": round(median(a for a, _ in rates), 2),
            "shares": round(median(b for _, b in rates), 2),
            "eligible": len(rates) >= MIN_POSTS_PER_THEME and above >= 2 and middle > baseline,
        }
    ranked = sorted(
        (t for t, e in evidence.items() if e["eligible"]),
        key=lambda t: (-evidence[t]["combined"], -evidence[t]["posts"], t),
    )[:MAX_EVIDENCE_SLOTS // MAX_PER_THEME]

    # Rotate editorial ideas without displacing the proven ranking. Choose no
    # more than two of any theme and no more than six supported slots.
    offset = week_start.toordinal() // 7 % len(IDEAS)
    pool = [i for i in IDEAS[offset:] + IDEAS[:offset] if i.ayah_key in verse_keys]
    picked: list[tuple[Idea, bool]] = []
    count: Counter[str] = Counter()
    used: set[str] = set()

    def add(idea: Idea, supported: bool) -> None:
        picked.append((idea, supported))
        count[idea.theme] += 1
        used.add(idea.slug)

    for _ in range(MAX_PER_THEME):
        for theme in ranked:
            idea = next((i for i in pool if i.theme == theme and i.slug not in used), None)
            if idea and len(picked) < MAX_EVIDENCE_SLOTS:
                add(idea, True)
    for round_number in range(MAX_PER_THEME):
        # Only the unranked themes form exploratory slots; no misleading
        # separation where the same successful theme gets both labels.
        for idea in pool:
            if len(picked) >= WEEKLY_SLOTS:
                break
            if idea.theme not in ranked and idea.slug not in used and count[idea.theme] <= round_number:
                add(idea, False)
    return {
        "sample_size": len(seen),
        "baseline": None if baseline is None else round(baseline, 2),
        "themes": evidence,
        "ideas": [{
            "slug": idea.slug, "theme": idea.theme, "opening": idea.situation, "ayah_key": idea.ayah_key,
            "mode": "evidence" if supported else "exploration",
            "reason": evidence.get(idea.theme) if supported else None,
        } for idea, supported in picked],
    }
