"""Render catalog availability lines for the facts a model cites by ref."""

LABELS = {
    "available": "disponível em estoque",
    "temporarily_unavailable": "sem estoque no momento",
    "coming_soon": "em breve",
    "discontinued": "fora de linha",
    "unknown": "disponibilidade não confirmada",
}


def with_facts(answer, evidence):
    """Append one availability line per fact ref; return None when a ref is unknown."""
    if answer is None or "facts" not in answer:
        return answer
    refs = [r for i in evidence for r in i.get("data", []) if isinstance(r, dict) and "ref" in r]
    rows = {r["ref"]: r for r in refs}
    if any(ref not in rows for ref in answer["facts"]):
        return None
    lines = [
        f"{rows[k]['name']}: {LABELS.get(rows[k].get('availability'), LABELS['unknown'])}."
        for k in answer["facts"]
    ]
    rendered = {k: v for k, v in answer.items() if k != "facts"}
    rendered["text"] = "\n".join([answer["text"], *lines])
    return rendered
