import time
from datetime import datetime, timedelta, timezone

from delta_rest_client import (
    DeltaRestClient,
    create_order_format,
    round_by_tick_size
)

# ================= CONFIG =================
API_KEY = "TcwdPNNYGjjgkRW4BRIAnjL7z5TLyJ"
API_SECRET = "B5ALo5Mh8mgUREB6oGD4oyX3y185oElaz1LoU6Y3X5ZX0s8TvFZcX4YTVToJ"

BASE_URL = "https://api.india.delta.exchange"

STRIKE_INTERVAL = 200
ORDER_SIZE = 1
CHECK_INTERVAL = 5
PRICE_OFFSET = 100
MIN_SELL_PRICE = 1000
# =========================================

delta_client = DeltaRestClient(
    base_url=BASE_URL,
    api_key=API_KEY,
    api_secret=API_SECRET
)

IST = timezone(timedelta(hours=5, minutes=30))

# ---------- HELPERS ----------

def get_expiry():
    now = datetime.now(IST)
    if now.hour > 17 or (now.hour == 17 and now.minute >= 30):
        expiry = now.date() + timedelta(days=3)
    else:
        expiry = now.date() + timedelta(days=2)
    return expiry.strftime("%d%m%y")


def get_atm_strike(spot):
    return int(round(float(spot) / STRIKE_INTERVAL) * STRIKE_INTERVAL)


def get_product_id(symbol):
    return delta_client.get_product(symbol)["id"]


def position_exists(product_id):
    pos = delta_client.get_position(product_id)
    if not pos:
        return False
    return abs(float(pos.get("size", 0))) > 0


def get_straddle_status(atm, expiry):
    """
    Returns dict:
    {
        "call": True/False,
        "put":  True/False
    }
    """
    status = {"call": False, "put": False}

    call_symbol = f"C-BTC-{atm}-{expiry}"
    put_symbol  = f"P-BTC-{atm}-{expiry}"

    try:
        call_id = get_product_id(call_symbol)
        status["call"] = position_exists(call_id)
    except Exception:
        pass

    try:
        put_id = get_product_id(put_symbol)
        status["put"] = position_exists(put_id)
    except Exception:
        pass

    return status


# ---------- MAIN ----------
print("🚀 SELL STRADDLE BOT STARTED")

while True:
    try:
        # -------- MARKET DATA --------
        expiry = get_expiry()

        btc = delta_client.get_ticker("BTCUSD")
        spot = float(btc["spot_price"])
        atm = get_atm_strike(spot)

        print(f"\n🔁 Spot {spot} | ATM {atm} | Expiry {expiry}")

        # -------- CHECK STRADDLE STATUS --------
        status = get_straddle_status(atm, expiry)

        if status["call"] and status["put"]:
            print("✅ CALL & PUT already exist — skipping both")
            time.sleep(CHECK_INTERVAL)
            continue

        call_symbol = f"C-BTC-{atm}-{expiry}"
        put_symbol  = f"P-BTC-{atm}-{expiry}"

        call_id = get_product_id(call_symbol)
        put_id  = get_product_id(put_symbol)

        call_ticker = delta_client.get_ticker(call_symbol)
        put_ticker  = delta_client.get_ticker(put_symbol)

        call_price = round_by_tick_size(
            float(call_ticker["mark_price"]) - PRICE_OFFSET, 0.5
        )
        put_price = round_by_tick_size(
            float(put_ticker["mark_price"]) - PRICE_OFFSET, 0.5
        )

        # -------- PLACE CALL --------
        if not status["call"]:
            if float(call_ticker["mark_price"]) > MIN_SELL_PRICE:
                call_order = create_order_format(
                    product_id=call_id,
                    size=ORDER_SIZE,
                    side="sell",
                    price=float(call_price)
                )
                print("📉 Placing CALL order")
                delta_client.batch_create(call_id, [call_order])
                print(f"✅ CALL SOLD | {call_symbol} @ {call_price}")
            else:
                print("⚠️ CALL price too low — skipped")
        else:
            print("⏭️ CALL already exists — skipped")

        # -------- PLACE PUT --------
        if not status["put"]:
            if float(put_ticker["mark_price"]) > MIN_SELL_PRICE:
                put_order = create_order_format(
                    product_id=put_id,
                    size=ORDER_SIZE,
                    side="sell",
                    price=float(put_price)
                )
                print("📉 Placing PUT order")
                delta_client.batch_create(put_id, [put_order])
                print(f"✅ PUT SOLD | {put_symbol} @ {put_price}")
            else:
                print("⚠️ PUT price too low — skipped")
        else:
            print("⏭️ PUT already exists — skipped")

    except Exception as e:
        print("❌ Error:", e)

    time.sleep(CHECK_INTERVAL)
