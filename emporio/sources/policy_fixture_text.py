"""Public section selection and bounded segmentation for the known policy PDF."""

import re

from emporio.catalog.normalize import normalize_text

_SECTION = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(.+?)\s*$")
_PUBLIC_TOPICS = {
    "1": "scope",
    "1.2": "contact",
    "2": "hours",
    "3": "payment",
    "3.1": "payment",
    "4.1": "returns",
    "4.2": "returns",
    "4.3": "returns",
    "4.4": "returns",
    "5.1": "delivery",
    "5.2": "delivery",
    "5.3": "delivery",
    "6.1": "promotions",
    "6.2": "promotions",
    "7": "contact",
    "8.1": "warranty",
    "8.2": "warranty",
    "8.3": "warranty",
    "9": "privacy",
}


def extract_fixture_passages(pages: list[str]) -> list[dict[str, object]]:
    """Return only passages selected by the reviewed initial-source map."""
    passages: list[dict[str, object]] = []
    current: str | None = None
    lines: list[tuple[int, str]] = []
    for page_number, page in enumerate(pages, 1):
        for line in page.splitlines():
            current, lines, flushed = _section_line(page_number, line, current, lines)
            passages.extend(flushed)
    passages.extend(_initial_section(current, lines))
    return passages


def _section_line(
    page: int,
    line: str,
    current: str | None,
    lines: list[tuple[int, str]],
) -> tuple[str | None, list[tuple[int, str]], list[dict[str, object]]]:
    match = _SECTION.match(line)
    if _is_nested_list_item(match, current):
        lines.append((page, line.strip()))
        return current, lines, []
    if not match:
        if current:
            lines.append((page, line.strip()))
        return current, lines, []
    return match.group(1), [(page, line.strip())], _initial_section(current, lines)


def _is_nested_list_item(match, current):
    return bool(
        match
        and current
        and "." in current
        and "." not in match.group(1)
        and int(match.group(1)) < int(current.split(".", 1)[0])
    )


def _initial_section(section: str | None, lines: list[tuple[int, str]]) -> list[dict[str, object]]:
    if section not in _PUBLIC_TOPICS:
        return []
    text, pages = _section_text(section, lines)
    return _passage_records(section, pages, _chunks(text))


def _section_text(section, lines):
    kept = _usable_section_lines(_approved_lines(section, lines))
    pages = _pages_for_lines(kept)
    source = _join_lines(kept)
    return _section_specific_text(section, source), pages


def _usable_section_lines(selected):
    return [(page, line) for page, line in selected if _usable_line(line)]


def _pages_for_lines(kept):
    return sorted({page for page, _ in kept})


def _join_lines(kept):
    return " ".join(line for _, line in kept)


def _section_specific_text(section, source):
    if section == "9":
        source = _privacy_text(source)
    if section == "7":
        source = _contact_text(source)
    return source


def _approved_lines(section, lines):
    if section == "1":
        return _approved_scope_lines(lines)
    if section == "1.2":
        return _approved_contact_lines(lines)
    return lines


def _approved_scope_lines(lines):
    return [pair for pair in lines if "exclusivamente" in normalize_text(pair[1])]


def _approved_contact_lines(lines):
    selected, include_next = [], False
    for pair in lines:
        normalized = normalize_text(pair[1])
        if _approved_contact_line(normalized, include_next):
            selected.append(pair)
        include_next = _contact_has_continuation(normalized)
    return selected


def _usable_line(line):
    return bool(line) and not _boilerplate(line)


def _approved_contact_line(normalized, include_next):
    allowed = ("razao social", "nome fantasia", "endereco", "telefone", "whatsapp", "e mail")
    return include_next or any(label in normalized for label in allowed)


def _contact_has_continuation(normalized):
    return "telefone" in normalized or "whatsapp" in normalized


def _privacy_text(source):
    start = re.search(r"dados pessoais coletados", source, re.IGNORECASE)
    return "Os " + source[start.start() :] if start else source


def _contact_text(source):
    return " ".join(
        sentence
        for sentence in re.split(r"(?<=[.!?])\s+", source)
        if "whatsapp" in normalize_text(sentence) and re.search(r"\(\d{2}\)", sentence)
    )


def _chunks(source):
    sentences = re.split(r"(?<=[.!?])\s+|\s+•\s+", re.sub(r"\s+", " ", source))
    chunks, current = [], ""
    for sentence in filter(None, sentences):
        current, previous = _next_chunk(current, sentence)
        if previous:
            chunks.append(previous)
    if current:
        chunks.append(current)
    return chunks


def _next_chunk(current, sentence):
    combined = f"{current} {sentence}".strip()
    if len(combined) <= 400:
        return combined, ""
    return (sentence if len(sentence) <= 400 else ""), current


def _passage_records(section: str, pages: list[int], chunks: list[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    if pages:
        for index, text in enumerate(chunks):
            records.append(
                {
                    "id": f"{pages[0]}:{section}:{index}",
                    "page": pages[0],
                    "pages": pages,
                    "section": f"§{section}",
                    "topic": _PUBLIC_TOPICS[section],
                    "audience": "public",
                    "conflict": False,
                    "text": text,
                }
            )
    return records


def _boilerplate(line):
    normalized = normalize_text(line)
    return "manual de politicas e procedimentos" in normalized or bool(
        re.fullmatch(r"pagina\s+\d+", normalized)
    )
