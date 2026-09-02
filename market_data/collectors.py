import time
from datetime import datetime, timezone
import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _to_dt(s):
    return pd.to_datetime(s, errors="coerce")


def fetch_eastmoney_5m(secid: str, start: str, end: str) -> pd.DataFrame:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "klt": 5,
        "fqt": 1,
        "beg": start.replace("-", ""),
        "end": end.replace("-", ""),
        "lmt": 100000,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    js = r.json()
    klines = ((js.get("data") or {}).get("klines") or [])
    rows = []
    for x in klines:
        p = x.split(",")
        if len(p) < 7:
            continue
        rows.append({
            "ts": _to_dt(p[0]), "open": float(p[1]), "close": float(p[2]),
            "high": float(p[3]), "low": float(p[4]), "volume": float(p[5]),
            "amount": float(p[6]), "source": "eastmoney"
        })
    return pd.DataFrame(rows)


def fetch_sina_5m(symbol: str, count: int = 2000) -> pd.DataFrame:
    url = "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_data=/CN_MarketDataService.getKLineData"
    params = {"symbol": symbol, "scale": 5, "ma": "no", "datalen": count}
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    text = r.text
    left, right = text.find("(["), text.rfind("])" )
    if left < 0 or right < 0:
        return pd.DataFrame()
    import json
    arr = json.loads(text[left + 1:right + 1])
    rows = []
    for p in arr:
        rows.append({
            "ts": _to_dt(p.get("day")), "open": float(p.get("open", 0)),
            "close": float(p.get("close", 0)), "high": float(p.get("high", 0)),
            "low": float(p.get("low", 0)), "volume": float(p.get("volume", 0)),
            "amount": None, "source": "sina"
        })
    return pd.DataFrame(rows)


def fetch_yahoo_5m(ticker: str, start: str, end: str) -> pd.DataFrame:
    p1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    p2 = int((pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"period1": p1, "period2": p2, "interval": "5m", "includePrePost": "false", "events": "div,splits"}
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    result = ((r.json().get("chart") or {}).get("result") or [])
    if not result:
        return pd.DataFrame()
    res = result[0]
    ts = res.get("timestamp") or []
    q = (((res.get("indicators") or {}).get("quote") or [{}])[0])
    rows = []
    for i, unix_ts in enumerate(ts):
        vals = {k: (q.get(k) or [None] * len(ts))[i] for k in ["open", "high", "low", "close", "volume"]}
        if vals["close"] is None:
            continue
        rows.append({
            "ts": pd.to_datetime(unix_ts, unit="s", utc=True),
            "open": vals["open"], "high": vals["high"], "low": vals["low"],
            "close": vals["close"], "volume": vals["volume"], "amount": None,
            "source": "yahoo"
        })
    return pd.DataFrame(rows)
