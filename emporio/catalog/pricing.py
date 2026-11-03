"""Pure integer-cent pricing calculations for imported catalog rows."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def cents(value: str) -> int:
    """Parse nonnegative source money with at most two decimal places."""
    amount = _parse_decimal(value, "invalid money")
    if not _valid_amount(amount, Decimal("92233720368547758.07")):
        raise ValueError("invalid money")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def discounted_cents(base: int, basis_points: int) -> int:
    """Apply one percentage with decimal half-up rounding to cents."""
    amount = Decimal(base) * (Decimal(10_000 - basis_points) / Decimal(10_000))
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def percentage_basis_points(value: str) -> int:
    """Parse a source percentage to basis points."""
    percent = _parse_decimal(value, "invalid percentage")
    if not _valid_amount(percent, Decimal("100")):
        raise ValueError("invalid percentage")
    return int(percent * 100)


def _parse_decimal(value: str, message: str) -> Decimal:
    """Parse a source decimal and normalize malformed input errors."""
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError(message) from error


def _valid_amount(amount: Decimal, maximum: Decimal) -> bool:
    """Check finite nonnegative decimal bounds and at most two fraction digits."""
    if not amount.is_finite():
        return False
    if amount < 0 or amount > maximum:
        return False
    exponent = amount.as_tuple().exponent
    return isinstance(exponent, int) and exponent >= -2
