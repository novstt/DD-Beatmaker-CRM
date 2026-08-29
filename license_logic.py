from decimal import Decimal, ROUND_HALF_UP

DISTRIBUTABLE = Decimal("90")
MESSENGER = Decimal("10")


def calculate_splits(price: Decimal, producers: list[dict], seller_id: int):
    """Pure, deterministic license split calculation.

    If the seller is one of the producers, no messenger share exists and producer
    shares are equal. Otherwise the seller receives a fixed 10% messenger share
    and the remaining 90% is divided equally among all producers.
    """
    clean=[]
    seen=set()
    for p in producers:
        key=(p.get("user_id"), (p.get("display_name") or "").strip().casefold())
        if key in seen: continue
        seen.add(key); clean.append(p)
    if not clean:
        clean=[{"user_id": seller_id, "display_name": "Current producer"}]
    seller_is_producer=any(p.get("user_id") == seller_id for p in clean if p.get("user_id") is not None)
    result=[]
    if seller_is_producer:
        pct=(Decimal("100")/Decimal(len(clean))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        # force exact 100.000 on the final producer to avoid rounding drift
        for i,p in enumerate(clean):
            share=(Decimal("100")-pct*Decimal(len(clean)-1)).quantize(Decimal("0.001")) if i==len(clean)-1 else pct
            result.append({"user_id":p.get("user_id"),"display_name":p.get("display_name") or "Producer","role":"producer","share_percent":share,"amount":(price*share/Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)})
    else:
        result.append({"user_id":seller_id,"display_name":"Messenger","role":"messenger","share_percent":MESSENGER,"amount":(price*MESSENGER/Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)})
        pct=(DISTRIBUTABLE/Decimal(len(clean))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        for i,p in enumerate(clean):
            share=(DISTRIBUTABLE-pct*Decimal(len(clean)-1)).quantize(Decimal("0.001")) if i==len(clean)-1 else pct
            result.append({"user_id":p.get("user_id"),"display_name":p.get("display_name") or "Producer","role":"producer","share_percent":share,"amount":(price*share/Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)})
    return result
