"""PostCard / PostList views — the one card every post listing renders (S152-06b).

A port of the computed values of fe-user ``PostCard.vue`` (+ ``PostList.vue``,
``utils/archiveDisplay.ts``, ``utils/timeAgo.ts``). The three archive toggles
default ON and own the category eyebrow, the tag chips and the reading time.
Dates are formatted en-US in UTC: the SPA uses the browser's locale and zone.
"""
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence
from urllib.parse import quote

from markupsafe import Markup

DEFAULT_LEAD_WIDTH = 1200
DEFAULT_LEAD_HEIGHT = 675
WORDS_PER_MINUTE = 200
TOGGLE_OWNED_META_FIELDS = ("tags", "reading_time")
READING_TIME_FIELD = "reading_time"
CATEGORY_MODE = "category"
EXCERPT_MODES = ("excerpt", "full")
FULL_MODE = "full"
PAGE_TYPE = "page"
# ``encodeURIComponent`` leaves exactly these unescaped.
URI_COMPONENT_SAFE_CHARACTERS = "-_.!~*'()"
_HTML_TAG = re.compile(r"<[^>]*>")
MONTH_ABBREVIATIONS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = SECONDS_PER_MINUTE * 60
SECONDS_PER_DAY = SECONDS_PER_HOUR * 24
SECONDS_PER_WEEK = SECONDS_PER_DAY * 7
SECONDS_PER_MONTH = SECONDS_PER_DAY * 30
SECONDS_PER_YEAR = SECONDS_PER_DAY * 365
# ``Intl.RelativeTimeFormat('en', {numeric: 'auto'})`` words for -1 / 0 / +1.
_RELATIVE_WORDS = {
    ("second", 0): "now",
    ("day", -1): "yesterday",
    ("day", 1): "tomorrow",
    ("week", -1): "last week",
    ("week", 1): "next week",
    ("month", -1): "last month",
    ("month", 1): "next month",
    ("year", -1): "last year",
    ("year", 1): "next year",
}
_RELATIVE_UNITS = (
    (SECONDS_PER_MINUTE, "second", 1),
    (SECONDS_PER_HOUR, "minute", SECONDS_PER_MINUTE),
    (SECONDS_PER_DAY, "hour", SECONDS_PER_HOUR),
    (SECONDS_PER_WEEK, "day", SECONDS_PER_DAY),
    (SECONDS_PER_MONTH, "week", SECONDS_PER_WEEK),
    (SECONDS_PER_YEAR, "month", SECONDS_PER_MONTH),
)


def encode_uri_component(value: Any) -> str:
    return quote(str(value), safe=URI_COMPONENT_SAFE_CHARACTERS)


def js_round(value: float) -> int:
    """``Math.round``: halves round towards +infinity."""
    return math.floor(value + 0.5)


def parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def time_ago(value: Any, now: Optional[datetime] = None) -> str:
    """``utils/timeAgo.ts`` in English."""
    then = parse_timestamp(value)
    if then is None:
        return ""
    delta_seconds = js_round(
        (then - (now or datetime.now(timezone.utc))).total_seconds()
    )
    unit, amount = "year", js_round(delta_seconds / SECONDS_PER_YEAR)
    for limit, candidate_unit, unit_seconds in _RELATIVE_UNITS:
        if abs(delta_seconds) < limit:
            unit, amount = candidate_unit, js_round(delta_seconds / unit_seconds)
            break
    if (unit, amount) in _RELATIVE_WORDS:
        return _RELATIVE_WORDS[(unit, amount)]
    plural = "" if abs(amount) == 1 else "s"
    if amount < 0:
        return f"{-amount} {unit}{plural} ago"
    return f"in {amount} {unit}{plural}"


def short_date(value: Any) -> str:
    """``toLocaleDateString(undefined, {year, month: 'short', day})`` → ``Oct 3, 2026``."""
    parsed = parse_timestamp(value)
    if parsed is None:
        return ""
    utc = parsed.astimezone(timezone.utc)
    return f"{MONTH_ABBREVIATIONS[utc.month - 1]} {utc.day}, {utc.year}"


def numeric_date(value: Any) -> str:
    """``toLocaleDateString()`` → ``10/3/2026``."""
    parsed = parse_timestamp(value)
    if parsed is None:
        return ""
    utc = parsed.astimezone(timezone.utc)
    return f"{utc.month}/{utc.day}/{utc.year}"


def archive_display(
    config: Mapping[str, Any],
    default_mode: str,
    meta: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """The PostList ``display`` of a widget: mode, meta and the three toggles."""
    mode = config.get("mode")
    return {
        "mode": default_mode if mode is None else mode,
        "meta": list(meta if meta is not None else config.get("meta") or []),
        "show_categories": config.get("show_categories") is not False,
        "show_tags": config.get("show_tags") is not False,
        "show_article_size": config.get("show_article_size") is not False,
    }


def _reading_time_minutes(post: Mapping[str, Any]) -> int:
    text = _HTML_TAG.sub(" ", str(post.get("content_html") or "")).strip()
    words = len(text.split()) if text else 0
    return max(1, js_round(words / WORDS_PER_MINUTE))


def _meta_value(field: str, post: Mapping[str, Any], now: Optional[datetime]) -> str:
    if field == "author":
        return str(post.get("author_name") or post.get("author_id") or "")
    if field == "time_ago":
        return time_ago(post.get("published_at"), now)
    if field == "published_at":
        return numeric_date(post.get("published_at"))
    if field == READING_TIME_FIELD:
        return f"{_reading_time_minutes(post)} min"
    return ""


def _meta_items(
    post: Mapping[str, Any], display: Mapping[str, Any], now: Optional[datetime]
) -> List[Dict[str, str]]:
    fields = [
        field for field in display["meta"] if field not in TOGGLE_OWNED_META_FIELDS
    ]
    if display["show_article_size"]:
        fields.append(READING_TIME_FIELD)
    return [
        {"field": field, "value": _meta_value(field, post, now)} for field in fields
    ]


def _tag_chip(tag: Any) -> Optional[Dict[str, str]]:
    if isinstance(tag, str):
        return (
            {"name": tag, "href": f"/tag/{encode_uri_component(tag)}"} if tag else None
        )
    name = tag.get("name") if tag.get("name") is not None else tag.get("slug") or ""
    if not name:
        return None
    if tag.get("archive_url"):
        href = f"/{tag['archive_url']}"
    else:
        href = f"/tag/{encode_uri_component(tag.get('slug') or name)}"
    return {"name": name, "href": href}


def _tag_chips(
    post: Mapping[str, Any], display: Mapping[str, Any]
) -> List[Dict[str, str]]:
    tags = post.get("tags")
    if not display["show_tags"] or not isinstance(tags, list):
        return []
    return [chip for chip in (_tag_chip(tag) for tag in tags) if chip]


def _category(
    post: Mapping[str, Any], display: Mapping[str, Any], detail_path: str
) -> Optional[Dict[str, str]]:
    category = post.get("primary_category") or {}
    name = category.get("name") or ""
    if not name or not display["show_categories"]:
        return None
    if category.get("archive_url"):
        href = f"/{category['archive_url']}"
    elif category.get("slug"):
        href = f"/category/{category['slug']}"
    else:
        href = detail_path
    return {"name": name, "href": href}


def _type_badge(post: Mapping[str, Any]) -> Optional[Dict[str, str]]:
    post_type = str(post.get("type") or "").strip()
    if not post_type:
        return None
    kind = PAGE_TYPE if post_type == PAGE_TYPE else "post"
    return {"kind": kind, "label": post_type[0].upper() + post_type[1:]}


def _first_present(post: Mapping[str, Any], *keys: str) -> Any:
    """``post[a] ?? post[b] ?? …``: the first value that is not null."""
    for key in keys:
        if post.get(key) is not None:
            return post[key]
    return None


def _image(url: Any, post: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    if not url:
        return None
    return {
        "url": url,
        "width": post.get("og_image_width") or DEFAULT_LEAD_WIDTH,
        "height": post.get("og_image_height") or DEFAULT_LEAD_HEIGHT,
    }


def post_card_view(
    post: Mapping[str, Any],
    display: Mapping[str, Any],
    detail_base: Optional[str],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """What ``_post_card.html.j2`` renders for one post."""
    mode = display["mode"]
    slug = post.get("slug") or ""
    detail_path = f"{detail_base}{slug}" if detail_base else f"/{slug}"
    return {
        "mode": mode,
        "title": post.get("title") or "",
        "detail_path": detail_path,
        "category": _category(post, display, detail_path),
        "type_badge": _type_badge(post),
        "date_label": short_date(post.get("published_at")),
        "meta": _meta_items(post, display, now),
        "tags": _tag_chips(post, display),
        "category_excerpt": _first_present(post, "excerpt_effective", "excerpt") or "",
        "excerpt": post.get("excerpt") if mode in EXCERPT_MODES else None,
        "body_html": (
            Markup(post["content_html"])
            if mode == FULL_MODE and post.get("content_html")
            else None
        ),
        "thumb": _image(
            _first_present(post, "featured_image_url", "og_image_url"), post
        ),
        "lead_image": _image(post.get("og_image_url"), post),
    }


def post_list_view(
    posts: Sequence[Mapping[str, Any]],
    display: Mapping[str, Any],
    detail_base: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """What ``_post_list.html.j2`` renders: the mode and one card view per post."""
    return {
        "mode": display["mode"],
        "cards": [post_card_view(post, display, detail_base, now) for post in posts],
    }
