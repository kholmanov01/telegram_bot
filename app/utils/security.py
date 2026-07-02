"""Security and input-validation helpers.

These are intentionally dependency-free and synchronous so they can be reused
from any layer (handlers, services, repositories) without import cycles.
"""

from __future__ import annotations

import re
import secrets
from typing import Final

# Compiled patterns are module-level for reuse and speed.
_EMPLOYEE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^EMP\d{3,}$", re.IGNORECASE)
_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")


def validate_employee_code(code: str) -> bool:
    """Return ``True`` when ``code`` matches ``EMP`` + 3+ digits.

    Matching is case-insensitive (``emp001`` is also accepted).

    :param code: The candidate code string.
    :returns: ``True`` if valid, ``False`` otherwise.
    """
    if not isinstance(code, str):
        return False
    return bool(_EMPLOYEE_CODE_RE.match(code.strip()))


def sanitize_text(text: str, max_length: int = 1000) -> str:
    """Strip, collapse internal whitespace and truncate ``text``.

    HTML escaping is intentionally NOT performed here — escaping is the
    responsibility of the formatting layer so it can be done at the moment
    of building the final HTML message.

    :param text: Raw user input.
    :param max_length: Maximum allowed length (in characters) of the result.
    :returns: Cleaned text.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    cleaned = _WHITESPACE_RE.sub(" ", text).strip()
    if max_length > 0 and len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
    return cleaned


def generate_secure_token(length: int = 32) -> str:
    """Return a URL-safe random token.

    Uses :func:`secrets.token_urlsafe`. The ``length`` parameter is the
    requested number of bytes of entropy; the resulting string is longer
    (about 4/3 of ``length``) due to base64 encoding.

    :param length: Bytes of entropy.
    :returns: URL-safe random string.
    """
    if length <= 0:
        raise ValueError("Token length must be positive")
    return secrets.token_urlsafe(length)


def mask_phone(phone: str) -> str:
    """Mask a phone number, keeping only the country code and last 2 digits.

    Examples::

        "+998901234567" -> "+998•••••67"
        "998901234567"  -> "998•••••67"
        "12345"         -> "•••45"

    Non-string inputs are stringified first.

    :param phone: Phone number string.
    :returns: Masked phone string.
    """
    if not phone:
        return ""
    s = str(phone).strip()
    if len(s) <= 4:
        return "•" * len(s)

    # Try to keep a leading "+" plus up to 3 digits as the visible prefix.
    prefix_end = 1 if s.startswith("+") else 0
    # Walk past the plus and the first 3 digits to find the prefix boundary.
    digits_seen = 0
    while prefix_end < len(s) and digits_seen < 3:
        ch = s[prefix_end]
        if ch.isdigit():
            digits_seen += 1
        prefix_end += 1
    # If we never saw any digits, just mask everything but the last 2.
    if digits_seen == 0:
        prefix_end = max(0, len(s) - 2)

    suffix_len = min(2, max(0, len(s) - prefix_end))
    prefix = s[:prefix_end]
    middle_len = max(0, len(s) - prefix_end - suffix_len)
    # Guarantee masking is visible for short inputs: if the middle section
    # would be too short, fall back to masking everything except the last 2
    # characters (plus a leading "+" if present).
    if middle_len < 3 and len(s) > 4:
        prefix = "+" if s.startswith("+") else ""
        suffix_len = 2
        middle_len = max(0, len(s) - len(prefix) - suffix_len)
    suffix = s[len(s) - suffix_len:] if suffix_len else ""
    return f"{prefix}{'•' * middle_len}{suffix}"


def is_safe_int(s: str) -> bool:
    """Return ``True`` when ``s`` is a string that safely parses as an int.

    Whitespace is stripped. Negatives are accepted, floats are not.

    :param s: Candidate string.
    :returns: ``True`` if ``int(s)`` would succeed.
    """
    if not isinstance(s, str):
        return False
    s = s.strip()
    if not s:
        return False
    try:
        int(s)
        return True
    except ValueError:
        return False
