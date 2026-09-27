"""EUR translation fees; provider costs remain separately denominated in USD."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import math

DEFAULT_TRANSLATION_RATE = 0.027


def nonnegative_decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite nonnegative number.")
    try:
        number = Decimal(str(value).strip().replace(",", "."))
        valid = number.is_finite() and number >= 0 and math.isfinite(float(number))
    except (InvalidOperation, ValueError, OverflowError):
        valid = False
    if not valid:
        raise ValueError(f"{label} must be a finite nonnegative number.")
    return number


def translation_fee_eur(word_count: object, rate_per_word: object) -> float:
    """Round the decimal product to cents, never a binary-float intermediate."""
    count = nonnegative_decimal(word_count, "Words")
    rate = nonnegative_decimal(rate_per_word, "Rate/word")
    if count != count.to_integral_value():
        raise ValueError("Words must be a nonnegative integer.")
    try:
        with localcontext() as context:
            context.prec = max(28, len(count.as_tuple().digits) + len(rate.as_tuple().digits) + 310)
            amount = (count * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result = float(amount)
    except (InvalidOperation, OverflowError):
        raise ValueError("Expected total must be a finite amount.") from None
    if not math.isfinite(result):
        raise ValueError("Expected total must be a finite amount.")
    return result
