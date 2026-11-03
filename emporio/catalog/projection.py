"""Project bounded customer-safe catalog facts from ORM products."""

from typing import Any

from emporio.catalog.models import Product

PUBLIC_SPEC_KEYS = {
    "top",
    "back_sides",
    "neck",
    "strings",
    "scale",
    "electronics",
    "color",
    "body",
    "shells",
    "pieces",
    "hardware",
    "keys",
    "type",
    "polyphony",
}


def money_text(cents: int) -> str:
    """Format integer cents as a two-decimal BRL amount without floats."""
    return f"{cents // 100}.{cents % 100:02d}"


def project_product(product: Product, payment: str) -> dict[str, Any]:
    """Return only the documented public fields for one catalog product."""
    description, truncated = _description(product.description)
    specs, truncated_specs = _specifications(product.specs)
    truncated.extend(truncated_specs)
    promotion = _promotion(product)
    payable = product.pix_payable_cents if payment == "pix" else product.standard_payable_cents
    condition = _payment_condition(payment, product.pricing_state)
    return {
        "name": product.name,
        "description": description,
        "category": product.category.name,
        "specs": specs,
        "base_price_brl": money_text(product.base_cents),
        "payable_price_brl": money_text(payable),
        "payment_condition": condition,
        "availability": _availability(product.status, product.stock_quantity),
        "promotion": promotion,
        "truncated_fields": truncated,
    }


def _description(value: str) -> tuple[str, list[str]]:
    """Bound a customer-facing description and mark truncation."""
    return (value[:600], ["description"]) if len(value) > 600 else (value, [])


def _specifications(values: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    """Allowlist and bound the public specification projection."""
    specs = {}
    truncated = []
    for key, value in values.items():
        if key in PUBLIC_SPEC_KEYS and isinstance(value, str):
            specs[key] = value[:80]
            if len(value) > 80:
                truncated.append(f"specs.{key}")
    return specs, truncated


def _promotion(product: Product) -> dict[str, Any]:
    """Project active promotion state without disclosing internal keys."""
    active = _active_promotions(product)
    if len(active) > 1 or product.pricing_state == "ambiguous":
        return {"state": "ambiguous", "description": None, "discount_percent": None}
    if not active:
        return {"state": "none", "description": None, "discount_percent": None}
    item = active[0]
    percent = item.discount_basis_points
    return {
        "state": "active",
        "description": item.description,
        "discount_percent": f"{percent // 100}.{percent % 100:02d}",
    }


def _active_promotions(product: Product) -> list[Any]:
    """Select active promotions from the ORM-prefetched relation."""
    return [item for item in product.promotions.all() if item.is_active]


def _availability(status: str, quantity: int) -> str:
    """Derive sellability from both recorded status and stock."""
    if type(quantity) is not int or quantity < 0:
        return "unknown"
    return _known_availability(status, quantity)


def _known_availability(status: str, quantity: int) -> str:
    """Return a known catalog status only for valid integer stock."""
    if status == "active":
        return "available" if quantity > 0 else "temporarily_unavailable"
    if status in {"coming_soon", "discontinued"}:
        return status
    return "unknown"


def _payment_condition(payment: str, pricing_state: str) -> str:
    """Describe the payment basis represented by the selected price."""
    payment_labels = {
        "pix": "pagamento integral via PIX",
        "credit": "pagamento no crédito",
        "debit": "pagamento no débito",
        "boleto": "pagamento por boleto",
        "mixed": "pagamento combinado",
        "unspecified": "forma de pagamento não informada",
    }
    if pricing_state == "ambiguous":
        return f"preço base; promoção ativa ambígua; {payment_labels[payment]}"
    if pricing_state == "promotion":
        return f"promoção do catálogo; {payment_labels[payment]}; não cumulativa com PIX"
    if payment == "pix":
        return f"preço para {payment_labels[payment]}"
    return f"preço registrado; {payment_labels[payment]}"
