"""The S77 core tags + custom-fields block under a CMS page (fe-core ``TagChips`` +
``CustomFieldsDisplay``), as plain rows for ``cms/partials/tags_custom_fields.html.j2``.
"""
from typing import Any, Dict, List, Mapping, Optional

BOOLEAN_YES = "Yes"
BOOLEAN_NO = "No"
EMPTY_PLACEHOLDER = "-"


def _display_value(field_type: str, value: Any) -> str:
    if value is None or value == "":
        return EMPTY_PLACEHOLDER
    if field_type == "bool":
        return BOOLEAN_YES if value else BOOLEAN_NO
    if field_type == "multiselect" and isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _custom_field_rows(page: Mapping[str, Any]) -> List[Dict[str, str]]:
    values = page.get("custom_fields") or {}
    definitions = page.get("custom_field_defs") or []
    if not definitions:
        return [
            {"label": key, "display": _display_value("text", value)}
            for key, value in values.items()
        ]
    ordered = sorted(
        definitions, key=lambda definition: definition.get("sort_order") or 0
    )
    return [
        {
            "label": definition.get("label") or definition["key"],
            "display": _display_value(
                definition.get("type") or "text", values[definition["key"]]
            ),
        }
        for definition in ordered
        if definition.get("key") in values
    ]


def _tag_names(page: Mapping[str, Any]) -> List[str]:
    return [
        tag if isinstance(tag, str) else str(tag.get("name") or tag.get("slug") or "")
        for tag in page.get("tags") or []
    ]


def tags_and_custom_fields(page: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The block's tags + rows, or ``None`` when there is nothing to show (as the SPA)."""
    tags = _tag_names(page)
    has_fields = bool(page.get("custom_fields"))
    if not tags and not has_fields:
        return None
    return {
        "tags": tags,
        "custom_fields": _custom_field_rows(page) if has_fields else [],
    }
