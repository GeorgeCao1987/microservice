import socket
import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}


def _to_dt(s):
    return pd.to_datetime(s, errors="coerce")


def _tdx_frame(df, source="mootdx"):
    if df is None or len(df) == 0:
        return pd.DataFrame()
    x = df.reset_index() if getattr(df.index, "name", None) in ("datetime", "date") else df.copy()
    dt_col = "datetime" if "datetime" in x.columns else ("date" if "date" in x.columns else None)
    if dt_col is None:
        return pd.DataFrame()
    vol_col = "vol" if "vol" in x.columns else ("volume" if "volume" in x.columns else None)
    amt_col = "amount" if "amount" in x.columns else None
    out = pd.DataFrame({
        "ts": pd.to_datetime(x[dt_col], errors="coerce"),
        "open": pd.to_numeric(x["open"], errors="coerce"),
        "high": pd.to_numeric(x["high"], errors="coerce"),
        "low": pd.to_numeric(x["low"], errors="coerce"),
        "close": pd.to_numeric(x["close"], errors="coerce"),
        "volume": pd.to_numeric(x[vol_col], errors="coerce") if vol_col else 0,
        "amount": pd.to_numeric(x[amt_col], errors="coerce") if amt_col else None,
        "source": source,
    })
    return out.dropna(subset=["ts", "close"])


def fetch_mootdx_5m(symbol: str, start: str, end: str, is_index: bool = False, pages: int = 5) -> pd.DataFrame:
    """Paged public TongdaXin 5m bars. frequency=0 is 5-minute; max 800 bars/page."""
    from mootdx.quotes import Quotes
    from mootdx.consts import MARKET_SH, MARKET_SZ
    code = symbol[-6:]
    market = MARKET_SH if symbol.startswith("sh") or code.startswith(("5", "6", "9")) else MARKET_SZ
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(8)
    client = None
    try:
        client = Quotes.factory(market="std", multithread=False, heartbeat=False, timeout=8)
        parts = []
        for page in range(pages):
            start_pos = page * 800
            if is_index:
                raw = client.index(symbol=code, frequency=0, market=market, start=start_pos, offset=800)
            else:
                raw = client.bars(symbol=code, frequency=0, start=start_pos, offset=800)
            part = _tdx_frame(raw)
            if part.empty:
                break
            parts.append(part)
            oldest = part["ts"].min()
            if pd.notna(oldest) and oldest <= pd.Timestamp(start):
                break
        if not parts:
            return pd.DataFrame()
        x = pd.concat(parts, ignore_index=True).sort_values("ts").drop_duplicates("ts")
        return x[(x.ts >= pd.Timestamp(start)) & (x.ts < pd.Timestamp(end) + pd.Timedelta(days=1))].copy()
    finally:
        if client is not None:
            try: client.close()
            except Exception: pass
        socket.setdefaulttimeout(old_timeout)


def fetch_baostock_5m(symbol: str, start: str, end: str) -> pd.DataFrame:
    import baostock as bs
    market = "sh" if symbol.startswith("sh") else "sz"
    code = symbol[-6:]
    bs_code = f"{market}.{code}"
    old_timeout = socket.getdefaulttimeout(); socket.setdefaulttimeout(10)
    try:
        lg = bs.login()
        if lg.error_code != "0": raise RuntimeError(f"baostock login {lg.error_code}: {lg.error_msg}")
        try:
            rs = bs.query_history_k_data_plus(bs_code,
                "date,time,code,open,high,low,close,volume,amount,adjustflag",
                start_date=start, end_date=end, frequency="5", adjustflag="3")
            if rs.error_code != "0": raise RuntimeError(f"baostock query {bs_code} {rs.error_code}: {rs.error_msg}")
            rows = []
            while rs.next():
                p = dict(zip(rs.fields, rs.get_row_data()))
                ts = pd.to_datetime((p.get("time") or "")[:14], format="%Y%m%d%H%M%S", errors="coerce")
                if pd.isna(ts): continue
                rows.append({"ts": ts, "open": float(p["open"]), "high": float(p["high"]), "low": float(p["low"]),
                             "close": float(p["close"]), "volume": float(p["volume"] or 0), "amount": float(p["amount"] or 0),
                             "source": "baostock"})
            return pd.DataFrame(rows)
        finally: bs.logout()
    finally: socket.setdefaulttimeout(old_timeout)


def fetch_eastmoney_5m(secid: str, start: str, end: str) -> pd.DataFrame:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {"secid": secid, "klt": 5, "fqt": 1, "beg": start.replace("-", ""), "end": end.replace("-", ""), "lmt": 100000,
              "fields1": "f1,f2,f3,f4,f5,f6", "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"}
    r = requests.get(url, params=params, headers=HEADERS, timeout=10); r.raise_for_status()
    klines = (((r.json().get("data") or {}).get("klines")) or [])
    rows = []
    for v in klines:
        p = v.split(",")
        if len(p) >= 7:
            rows.append({"ts": _to_dt(p[0]), "open": float(p[1]), "close": float(p[2]), "high": float(p[3]), "low": float(p[4]),
                         "volume": float(p[5]), "amount": float(p[6]), "source": "eastmoney"})
    return pd.DataFrame(rows)


def fetch_sina_5m(symbol: str, count: int = 1023) -> pd.DataFrame:
    url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
    params = {"symbol": symbol, "scale": 5, "ma": "no", "datalen": min(count, 1023)}
    r = requests.get(url, params=params, headers=HEADERS, timeout=10); r.raise_for_status()
    arr = r.json()
    rows = []
    for p in arr if isinstance(arr, list) else []:
        rows.append({"ts": _to_dt(p.get("day")), "open": float(p.get("open", 0)), "close": float(p.get("close", 0)),
                     "high": float(p.get("high", 0)), "low": float(p.get("low", 0)), "volume": float(p.get("volume", 0)),
                     "amount": None, "source": "sina"})
    return pd.DataFrame(rows)


def fetch_yahoo_5m(ticker: str, start: str, end: str) -> pd.DataFrame:
    p1 = int(pd.Timestamp(start, tz="UTC").timestamp()); p2 = int((pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"period1": p1, "period2": p2, "interval": "5m", "includePrePost": "false", "events": "div,splits"}
    r = requests.get(url, params=params, headers=HEADERS, timeout=10); r.raise_for_status()
    result = ((r.json().get("chart") or {}).get("result") or [])
    if not result: return pd.DataFrame()
    res = result[0]; ts = res.get("timestamp") or []; q = (((res.get("indicators") or {}).get("quote") or [{}])[0])
    rows = []
    for i, unix_ts in enumerate(ts):
        vals = {k: (q.get(k) or [None] * len(ts))[i] for k in ["open", "high", "low", "close", "volume"]}
        if vals["close"] is not None:
            rows.append({"ts": pd.to_datetime(unix_ts, unit="s", utc=True), "open": vals["open"], "high": vals["high"], "low": vals["low"],
                         "close": vals["close"], "volume": vals["volume"], "amount": None, "source": "yahoo"})
    return pd.DataFrame(rows)


def fetch_yahoo_recent_5m(ticker: str, start: str, end: str) -> pd.DataFrame:
    now_utc = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    s, e = pd.Timestamp(start), pd.Timestamp(end); s = max(s, now_utc - pd.Timedelta(days=59))
    if s > e: return pd.DataFrame()
    return fetch_yahoo_5m(ticker, s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d"))
