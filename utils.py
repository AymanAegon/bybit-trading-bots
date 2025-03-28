

def get_total_ballance(session, symbol: str=None) -> dict:
    """Gets total ballace and a coin.
    if a Symbol is None, it return all coins. """
    if symbol=="": symbol = None
    res = session.get_wallet_balance(
        accountType="UNIFIED",
        coin=symbol,
    )
    dic = {
        "totalEquity": res["result"]["list"][0]["totalEquity"],
        "coins": []
    }
    for c in res["result"]["list"][0]["coin"]:
        dic["coins"].append({"coin": c["coin"], "equity": c["equity"], "usdValue": c["usdValue"]})

    return dic

def get_position_info(session, symbol: str) -> dict:
    """Gets position info of a coin."""
    if symbol=="": return None
    res = session.get_positions(
        category="linear",
        symbol=symbol,
    )["result"]["list"][0]
    dic = {
        "coin": res["symbol"],
        "leverage": res["leverage"],
    }
    return dic