"""Minimize clearly identified contact details while preserving other numbers."""

import re

EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
OWN_CONTACT = re.compile(
    r"(?i)(meu telefone|meu celular|meu whatsapp|meu e-mail|meu email)\s*(?:é|eh)?\s*:?\s*"
    r"(?:\+?55[\d ()-]{8,}|\(?[1-9][0-9]\)?[ -]?[0-9]{4,5}-?[0-9]{4}|[\w.+-]+@[\w.-]+\.[A-Z]{2,})"
)
PUBLIC_CONTACTS = {"6733214500", "6733414444", "556733214500", "556733414444"}
PHONE = re.compile(
    r"(?<!\w)(?:\+55[ -]?)?(?:\([1-9][0-9]\)|[1-9][0-9])[ -]?[0-9]{4,5}-[0-9]{4}(?!\w)"
)


def minimize_text(value: str) -> str | None:
    """Redact labeled personal contacts without treating numbers as identities."""
    if not isinstance(value, str) or len(value) > 2048 or len(value.encode("utf-8")) > 8192:
        return None
    result = EMAIL.sub("[contato removido]", value)
    result = OWN_CONTACT.sub(_replace_contact, result)
    result = PHONE.sub(_replace_phone, result)
    return result.strip() or None


def _replace_contact(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group())
    if any(item in digits for item in PUBLIC_CONTACTS):
        return match.group()
    return f"{match.group(1)} [contato removido]"


def _replace_phone(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group())
    return match.group() if digits in PUBLIC_CONTACTS else "[contato removido]"
