import re


def normalize_issn(raw: str) -> str | None:
    """Normalize to XXXX-XXXX format. Handles X check digit. Returns None if invalid."""
    if not raw or not isinstance(raw, str):
        return None
    cleaned = re.sub(r'[\s\-]', '', raw.strip()).upper()
    # ISSNs are 8 chars: 7 digits + digit or X
    if not re.fullmatch(r'[0-9]{7}[0-9X]', cleaned):
        return None
    return f"{cleaned[:4]}-{cleaned[4:]}"


def parse_issn_pair(raw: str) -> tuple[str | None, str | None]:
    """
    Scimago stores ISSNs as comma-separated: '12345678, 87654321'
    Returns (issn_print, issn_electronic). First is treated as print.
    """
    if not raw or not isinstance(raw, str):
        return None, None
    parts = [p.strip() for p in raw.split(',')]
    issn_print = normalize_issn(parts[0]) if len(parts) > 0 else None
    issn_electronic = normalize_issn(parts[1]) if len(parts) > 1 else None
    return issn_print, issn_electronic
