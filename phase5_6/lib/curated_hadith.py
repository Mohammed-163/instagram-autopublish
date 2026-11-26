"""A manually reviewed, one-slot hadith exception; disabled unless explicitly enabled."""
from dataclasses import dataclass
from datetime import date

HADITH_STYLE = "curated_hadith_silent_v1"
HADITH_DAY = date(2026, 12, 1)  # Baghdad local date
HADITH_SLOT = 1


@dataclass(frozen=True)
class CuratedHadith:
    quote: str
    attribution: str
    short_reference: str
    full_reference: str
    source_url: str
    hook: str
    reflection: str

    @property
    def video_reference(self) -> str:
        return f"مقتطف من حديث: {self.attribution}\n{self.short_reference}"

    def editorial_content(self) -> dict:
        return {
            "topic_slug": "hadith-al-kafi-2-2-19-1",
            "hook_line": self.hook,
            "fact_line": self.reflection,
            "cta_line": "وقفة من حديث",
            "pixabay_query": "quiet dawn soft sky",
            "caption_arabic": (
                f"{self.hook}\n\n"
                f"«{self.quote}»\n{self.attribution}\n"
                f"مقتطف. المصدر: {self.full_reference}\n{self.source_url}\n\n"
                f"وقفة: {self.reflection}"
            ),
            "hashtags": ["#آية_وطمأنينة", "#أهل_البيت", "#الدعاء"],
        }


# Quotation follows the Arabic text on the linked page, without changing its
# orthography. It is an excerpt from a longer narrated exchange, not an ayah.
HADITH = CuratedHadith(
    quote="فَلا تَمَلَّ الدُّعَاءَ",
    attribution="عن الإمام الرضا عليه السلام",
    short_reference="الكافي، ج 2، ح 1",
    full_reference="الكافي، ج 2، كتاب الدعاء، باب من أبطأت عليه الإجابة، ح 1",
    source_url="https://thaqalayn.com/ar/hadith/2/2/19/1",
    hook="صارلك تدعي، والجواب بعده ما إجه؟",
    reflection="من يطول عليك الانتظار، مو لازم تعرف متى الفرج حتى تبقى تدعي.",
)


def selected_curated_hadith(day: date, slot: int, enabled: str | None) -> CuratedHadith | None:
    if (enabled or "").strip().casefold() == "true" and (day, slot) == (HADITH_DAY, HADITH_SLOT):
        return HADITH
    return None
