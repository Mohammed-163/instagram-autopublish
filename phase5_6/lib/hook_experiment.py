"""Date-bounded, deterministic opener experiment for the current Reel template."""
from datetime import date

START = date(2026, 11, 27)
END = date(2026, 12, 10)
BASE_VISUAL_STYLE = "warm_stock_photo_quranic_frame"
CONTROL = "control_v1"
SITUATION = "situation_v1"
FALLBACK = "situation_fallback_v1"


def planned_hook_variant(day: date, slot: int) -> str | None:
    if not START <= day <= END:
        return None
    if slot not in (1, 2):
        return None  # The study covers only the two existing production slots.
    elapsed = (day - START).days
    # Flip each weekday in the second week, and split double-slot days.
    week, weekday = divmod(elapsed, 7)
    return SITUATION if (week + weekday + slot - 1) % 2 == 0 else CONTROL


def experiment_style(variant: str | None) -> str:
    # Daily_Log and the 24h snapshot already carry visual_style.
    return f"{BASE_VISUAL_STYLE}__opener_{variant}" if variant else BASE_VISUAL_STYLE


def base_visual_style(style: str | None) -> str | None:
    """Avoid teaching the planner that opener variants are visual templates."""
    if style in {experiment_style(v) for v in (CONTROL, SITUATION, FALLBACK)}:
        return BASE_VISUAL_STYLE
    return style
