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

STRIKE_INTERVAL = 100
STRIKE_DISTANCE = 500
ORDER_SIZE = 2
CHECK_INTERVAL = 5
PRICE_OFFSET = 50
MIN_MARK_PRICE = 500
# =========================================

delta_client = DeltaRestClient(
    base_url=BASE_URL,
    api_key=API_KEY,
    api_secret=API_SECRET
)

IST = timezone(timedelta(hours=5, minutes=30))


# ---------- HELPERS ----------

def get_far_expiry():
    expiry = datetime(2026, 4, 24)
    return expiry.strftime("%d%m%y")


def get_next_day_expiry():
    tomorrow = datetime.now(IST) + timedelta(days=2)
    return tomorrow.strftime("%d%m%y")


def get_atm_strike(spot):
    return int(round(float(spot) / STRIKE_INTERVAL) * STRIKE_INTERVAL)


def get_product_id(symbol):
    return delta_client.get_product(symbol)["id"]


def position_exists(product_id):
    pos = delta_client.get_position(product_id)
    if not pos:
        return False
    return abs(float(pos.get("size", 0))) > 0


# ---------- MAIN ----------
print("🚀 DIAGONAL CALL SPREAD BOT STARTED")

while True:
    try:
        far_expiry = get_far_expiry()
        next_expiry = get_next_day_expiry()

        ticker = delta_client.get_ticker("ETHUSD")
        spot = float(ticker["spot_price"])
        atm = get_atm_strike(spot)

        print(f"\n🔁 Spot {spot} | ATM {atm}")

        # ================= BUY DEEP ITM CALL =================
        long_strike = atm - STRIKE_DISTANCE
        long_symbol = f"C-ETH-{long_strike}-{far_expiry}"
        print(f"📌 LONG CALL {long_strike} | Expiry {far_expiry}")

        long_id = get_product_id(long_symbol)

        if not position_exists(long_id):
            long_ticker = delta_client.get_ticker(long_symbol)
            long_mark = float(long_ticker["mark_price"])

            if long_mark >= MIN_MARK_PRICE:
                long_price = round_by_tick_size(long_mark + PRICE_OFFSET, 0.5)

                long_order = create_order_format(
                    product_id=long_id,
                    size=ORDER_SIZE,
                    side="buy",
                    price=long_price
                )

                delta_client.batch_create(long_id, [long_order])
                print(f"✅ BOUGHT LONG CALL @ {long_price}")
            else:
                print(f"⚠️ Long skipped (mark {long_mark} too low)")
        else:
            print("⏭️ Long call already exists")

        # ================= SELL ATM CALL (NEXT DAY) =================
        short_strike = atm
        short_symbol = f"C-ETH-{short_strike}-{next_expiry}"
        print(f"📌 SHORT CALL {short_strike} | Expiry {next_expiry}")

        short_id = get_product_id(short_symbol)

        if position_exists(long_id) and not position_exists(short_id):

            short_ticker = delta_client.get_ticker(short_symbol)
            short_mark = float(short_ticker["mark_price"])

            short_price = round_by_tick_size(short_mark - PRICE_OFFSET, 0.5)

            short_order = create_order_format(
                product_id=short_id,
                size=ORDER_SIZE,
                side="sell",
                price=short_price
            )

            delta_client.batch_create(short_id, [short_order])
            print(f"💰 SOLD ATM CALL @ {short_price}")

        else:
            print("⏭️ Short call exists or hedge missing")

    except Exception as e:
        print("❌ Error:", e)

    time.sleep(CHECK_INTERVAL)
