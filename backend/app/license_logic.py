from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

MESSENGER_PERCENT = Decimal("10.00")
HUNDRED = Decimal("100.00")
CENT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.01")


def _clean_producers(producers: list[dict]) -> list[dict]:
    """
    Returns all unique producers.

    External producers (user_id=None) are included in financial calculations.
    """
    clean = []
    seen = set()

    for index, producer in enumerate(producers):
        user_id = producer.get("user_id")
        display_name = (
            producer.get("display_name")
            or producer.get("username")
            or "External Producer"
        ).strip()

        # Registered users are unique by user_id.
        # External producers are unique by position/name.
        key = ("user", user_id) if user_id is not None else (
            "external",
            display_name.lower(),
            index,
        )

        if key in seen:
            continue

        seen.add(key)

        try:
            share_percent = Decimal(
                str(producer.get("share_percent") or "0")
            )
        except Exception:
            share_percent = Decimal("0")

        clean.append({
            "user_id": user_id,
            "display_name": display_name,
            "share_percent": share_percent,
        })

    return clean


def _normalise_shares(producers: list[dict]) -> list[Decimal]:
    """
    Returns producer percentages normalised to exactly 100%.

    If valid percentages are missing, producers are split equally.
    """
    if not producers:
        return []

    shares = [
        max(Decimal("0"), producer["share_percent"])
        for producer in producers
    ]

    total = sum(shares, Decimal("0"))

    if total <= 0:
        base = (
            HUNDRED / Decimal(len(producers))
        ).quantize(PERCENT_QUANT, rounding=ROUND_DOWN)

        result = [base] * len(producers)

        result[-1] = (
            HUNDRED - sum(result[:-1], Decimal("0"))
        ).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)

        return result

    result = []

    for share in shares:
        percent = (
            share / total * HUNDRED
        ).quantize(PERCENT_QUANT, rounding=ROUND_DOWN)

        result.append(percent)

    # Fix rounding difference.
    difference = HUNDRED - sum(result, Decimal("0"))

    result[-1] = (
        result[-1] + difference
    ).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)

    return result


def calculate_splits(
    price: Decimal,
    producers: list[dict],
    seller_id: int,
    messenger: dict | None = None,
) -> list[dict]:
    """
    Calculate immutable license splits.

    Rules:
    - All producer credits participate, including external producers.
    - Original producer shares are respected and normalized to 100%.
    - Messenger is explicit per license. If present, messenger receives 10%.
    - The remaining 90% is distributed proportionally among producers.
    - If no messenger is selected, producers receive 100%.
    - The returned rows are the immutable financial snapshot stored on the license.
    """

    clean = _clean_producers(producers)

    if not clean:
        return []

    # A financial Messenger split must always belong to a real account.
    # The API layer validates this too, but keeping the invariant here prevents
    # future callers from accidentally creating an unowned 10% split.
    if messenger is not None and messenger.get("user_id") is None:
        raise ValueError("Messenger must resolve to a registered user account")

    # Messenger is now an explicit role on the sale, not a property of the beat
    # and not inferred from whether the account creating the sale is a producer.
    # This keeps the financial record deterministic: a producer can sell their own
    # beat without a messenger, or another producer can record the messenger.
    messenger_percent = MESSENGER_PERCENT if messenger else Decimal("0.00")
    producer_pool_percent = HUNDRED - messenger_percent

    result = []

    if messenger_percent > 0:
        messenger_amount = (
            price * messenger_percent / HUNDRED
        ).quantize(CENT, rounding=ROUND_HALF_UP)
        result.append({
            "user_id": messenger.get("user_id"),
            "display_name": messenger.get("display_name") or "Messenger",
            "role": "messenger",
            "share_percent": messenger_percent,
            "amount": messenger_amount,
        })

    original_shares = _normalise_shares(clean)

    producer_amounts = []
    producer_percents = []

    for share in original_shares:
        final_percent = (
            share * producer_pool_percent / HUNDRED
        ).quantize(PERCENT_QUANT, rounding=ROUND_DOWN)

        final_amount = (
            price * final_percent / HUNDRED
        ).quantize(CENT, rounding=ROUND_DOWN)

        producer_percents.append(final_percent)
        producer_amounts.append(final_amount)

    # Fix percentage rounding.
    percent_difference = (
        producer_pool_percent
        - sum(producer_percents, Decimal("0"))
    )

    producer_percents[-1] += percent_difference

    # Fix money rounding.
    producer_pool_amount = (
        price * producer_pool_percent / HUNDRED
    ).quantize(CENT, rounding=ROUND_HALF_UP)

    amount_difference = (
        producer_pool_amount
        - sum(producer_amounts, Decimal("0"))
    )

    producer_amounts[-1] += amount_difference

    for producer, percent, amount in zip(
        clean,
        producer_percents,
        producer_amounts,
    ):
        result.append({
            "user_id": producer["user_id"],
            "display_name": producer["display_name"],
            "role": "producer",
            "share_percent": percent,
            "amount": amount,
        })

    return result