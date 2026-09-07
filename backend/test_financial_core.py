from decimal import Decimal
from app.license_logic import calculate_splits

def amounts(rows):
    return {r["display_name"]: (r["role"], r["share_percent"], r["amount"]) for r in rows}

def test_two_registered_producers_plus_messenger():
    rows=calculate_splits(Decimal("30"), [
        {"user_id":1,"display_name":"SLV","share_percent":Decimal("50")},
        {"user_id":2,"display_name":"DeddyCar","share_percent":Decimal("50")},
    ], seller_id=3, messenger={"user_id":3,"display_name":"ThePlugg"})
    assert sum(r["share_percent"] for r in rows) == Decimal("100.00")
    assert sum(r["amount"] for r in rows) == Decimal("30.00")
    a=amounts(rows)
    assert a["ThePlugg"] == ("messenger", Decimal("10.00"), Decimal("3.00"))
    assert a["SLV"][2] == Decimal("13.50")
    assert a["DeddyCar"][2] == Decimal("13.50")

def test_external_producer_still_gets_share():
    rows=calculate_splits(Decimal("30"), [
        {"user_id":1,"display_name":"SLV","share_percent":Decimal("50")},
        {"user_id":None,"display_name":"External","share_percent":Decimal("50")},
    ], seller_id=1, messenger={"user_id":2,"display_name":"ThePlugg"})
    assert sum(r["share_percent"] for r in rows) == Decimal("100.00")
    assert sum(r["amount"] for r in rows) == Decimal("30.00")
    a=amounts(rows)
    assert a["External"][2] == Decimal("13.50")

def test_no_messenger_keeps_100_percent_for_producers():
    rows=calculate_splits(Decimal("100"), [
        {"user_id":1,"display_name":"A","share_percent":Decimal("50")},
        {"user_id":2,"display_name":"B","share_percent":Decimal("50")},
    ], seller_id=1)
    assert sum(r["share_percent"] for r in rows) == Decimal("100.00")
    assert sum(r["amount"] for r in rows) == Decimal("100.00")
