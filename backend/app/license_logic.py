from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

MESSENGER_PERCENT = Decimal("10.00")
HUNDRED = Decimal("100.00")
CENT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.01")


def _clean_registered_producers(producers: list[dict]) -> list[dict]:
    """Return unique registered producer entries only.

    Financial splits can only be assigned to real application users. External
    BeatCredit rows (user_id=None) remain credits for display elsewhere, but
    they cannot silently consume a revenue share.
    """
    clean = []
    seen_ids: set[int] = set()
    for producer in producers:
        user_id = producer.get("user_id")
        if user_id is None:
            continue
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            continue
        if uid in seen_ids:
            continue
        seen_ids.add(uid)
        clean.append({
            "user_id": uid,
            "display_name": (producer.get("display_name") or "Producer").strip() or "Producer",
        })
    return clean


def _split_amounts(price: Decimal, total_percent: Decimal, count: int) -> list[Decimal]:
    if count <= 0:
        return []
    total = (price * total_percent / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)
    base = (total / Decimal(count)).quantize(CENT, rounding=ROUND_DOWN)
    amounts = [base for _ in range(count)]
    amounts[-1] = (total - sum(amounts[:-1], Decimal("0"))).quantize(CENT, rounding=ROUND_HALF_UP)
    return amounts


def _equal_percentages(total_percent: Decimal, count: int) -> list[Decimal]:
    if count <= 0:
        return []
    base = (total_percent / Decimal(count)).quantize(PERCENT_QUANT, rounding=ROUND_DOWN)
    result = [base for _ in range(count)]
    result[-1] = (total_percent - sum(result[:-1], Decimal("0"))).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)
    return result


def calculate_splits(price: Decimal, producers: list[dict], seller_id: int) -> list[dict]:
    """Deterministically calculate immutable license splits.

    Producer shares are based only on explicit registered credits. The beat
    record owner is deliberately ignored. If the seller is one of the credited
    producers, they share 100% with the other producers. Otherwise the seller
    is the messenger and receives a fixed 10%, while the producers split 90%.

    The helper never fabricates a producer when no registered credits exist;
    callers should reject such a sale instead.
    """
    clean = _clean_registered_producers(producers)
    if not clean:
        return []

    seller_is_producer = any(p["user_id"] == seller_id for p in clean)
    messenger_percent = Decimal("0.00") if seller_is_producer else MESSENGER_PERCENT
    producer_percent = HUNDRED - messenger_percent
    percents = _equal_percentages(producer_percent, len(clean))
    amounts = _split_amounts(price, producer_percent, len(clean))

    result: list[dict] = []
    if messenger_percent > 0:
        messenger_amount = (price * messenger_percent / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)
        result.append({
            "user_id": seller_id,
            "display_name": "Messenger",
            "role": "messenger",
            "share_percent": messenger_percent,
            "amount": messenger_amount,
        })

    for producer, percent, amount in zip(clean, percents, amounts):
        result.append({
            "user_id": producer["user_id"],
            "display_name": producer["display_name"],
            "role": "producer",
            "share_percent": percent,
            "amount": amount,
        })
    return result
