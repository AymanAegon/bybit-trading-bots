# bot.py
import os
from pybit.unified_trading import HTTP  # Updated import
from dotenv import load_dotenv
from time import time

from utils import get_position_info

# Load environment variables
load_dotenv()

# Initialize the Bybit session
session = HTTP(
    testnet=False,
    api_key=os.getenv("BYBIT_API_KEY"),
    api_secret=os.getenv("BYBIT_API_SECRET")
)

def get_last_price(symbol):
    """Fetch the last price of a symbol."""
    ticker = session.get_mark_price_kline(
        category="linear",
        symbol=symbol,
        interval=1,
    )
    return ticker['result']['list'][0][4]

def set_levrege(symbol: str, lev: str):
    if lev == get_position_info(session, symbol)["leverage"]:
        print(f"Leverage for {symbol} is already set to {lev}!")
        return None
    res = session.set_leverage(
        category="linear",
        symbol=symbol,
        buyLeverage=lev,
        sellLeverage=lev,
    )
    print(f"Leverage for {symbol} has been set to {lev}")
    return res

def place_market_order(symbol, side, qty):
    """Place a market order."""
    order = session.place_active_order(
        symbol=symbol,
        side=side,
        order_type="Market",
        qty=qty,
        time_in_force="GoodTillCancel"
    )
    return order

def place_limit_order(symbol:str, side:str, price: float, qty, lev:str, usdt: bool=False):
    """Place a market order."""
    set_levrege(symbol, lev)
    if usdt:
        x = "{:.2f}".format(qty / float(price))
        if x == "0.00": x = "{:.3f}".format(qty / float(price))
        qty = x
    order = session.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        orderType="Limit",
        qty=qty,
        price=str(price),
        timeInForce="GTC",
        isLeverage=0,
    )
    return order

def get_orders(symbol: str=None) -> list:
    """Gets all orders of a coin.
    if a Symbol is None, it return for all coins. """
    if symbol=="": symbol = None
    res = session.get_open_orders(
        category="linear",
        symbol=symbol,
        settleCoin="USDT",
        openOnly=0,
        limit=10,
    )["result"]["list"]
    
    orders = []
    for c in res:
        orders.append({
            "orderId": c["orderId"], "symbol": c["symbol"], "price": c["price"], "qty": c["qty"], "side": c["side"],
        })

    return orders

def cancel_order(symbol: str, id: str) -> dict:
    """Gets all orders of a coin.
    if a Symbol is None, it return for all coins. """
    if symbol=="": symbol = None
    res = session.cancel_order(
        category="linear",
        symbol=symbol,
        orderId=id,
    )
    return res

def main():
    symbol = "BTCUSDT"
    side = "Sell"  # "Buy" or "Sell"
    qty = "0.1"  # Amount of tokens to buy

    # Get the last price
    last_price = get_last_price(symbol)
    print(f"Last price of {symbol}: {last_price}")

    # Place a limit order
    order = place_limit_order(symbol, side, 88000, 100, "50", True)
    print(f"Order placed: {order}")

if __name__ == "__main__":
    # main()
    # set_levrege("BTCUSDT", "60")
    print(session.get_positions(category="inverse", symbol="BTCUSD"))
    # print(cancel_order("ETHUSDT", "04ecae0d-238a-4493-95d2-677be1aa42f7"))