from pathlib import Path
import time
import pandas as pd

from config import A_SHARES, START_DATE, END_DATE
from baostock_batch import fetch_baostock_batch
from validate import validate_a_share

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
RESULTS = BASE / "results"
DATA.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)

PCB_STOCKS = ["002916", "002463", "600183", "002938", "603228", "300476"]
INDEX = "000001.SH"


def save(df, path):
    if df is not None and not df.empty:
        df.to_csv(path, index=False)


def fetch_stocks_with_retry(attempts=4):
    symbols = {s: A_SHARES[s]["sina"] for s in PCB_STOCKS}
    last = None
    for attempt in range(1, attempts + 1):
        try:
            out = fetch_baostock_batch(symbols, START_DATE, END_DATE)
            if all(len(out.get(s, pd.DataFrame())) > 0 for s in PCB_STOCKS):
                return out
            last = RuntimeError("one or more empty Baostock symbols")
        except Exception as e:
            last = e
        print("BAOSTOCK_BATCH_RETRY", attempt, repr(last))
        time.sleep(attempt * 3)
    raise RuntimeError(f"Baostock batch failed: {last!r}")


def fetch_index_pytdx():
    from pytdx.hq import TdxHq_API
    try:
        from pytdx.config.hosts import hq_hosts
        servers = [(x[1], x[2]) for x in hq_hosts]
    except Exception:
        servers = []
    servers += [
        ("180.153.18.170", 7709),
        ("119.97.185.59", 7709), ("124.70.133.119", 7709),
        ("116.205.183.150", 7709), ("123.60.73.44", 7709),
        ("116.205.163.254", 7709), ("121.36.225.169", 7709),
        ("123.60.70.228", 7709), ("124.71.9.153", 7709),
    ]
    servers = list(dict.fromkeys(servers))
    api = None
    for ip, port in servers:
        a = None
        try:
            a = TdxHq_API(heartbeat=False, auto_retry=False, raise_exception=True)
            if not a.connect(ip, port, time_out=2):
                continue
            test = a.get_index_bars(0, 1, "000001", 0, 10) or []
            if len(test) >= 5:
                t = a.to_df(test)
                if "datetime" in t.columns and t["datetime"].notna().any():
                    print("INDEX_SERVER_OK", ip, port)
                    api = a
                    break
        except Exception as e:
            print("INDEX_SERVER_FAIL", ip, port, repr(e))
        if a is not None:
            try:
                a.disconnect()
            except Exception:
                pass
    if api is None:
        raise RuntimeError("no working TDX index server")
    try:
        parts = []
        for page in range(8):
            rows = api.get_index_bars(0, 1, "000001", page * 800, 800) or []
            if not rows:
                break
            x = api.to_df(rows)
            parts.append(x)
            ts = pd.to_datetime(x["datetime"], errors="coerce")
            print("INDEX_PAGE", page, len(x), ts.min(), ts.max())
            if ts.min() <= pd.Timestamp(START_DATE):
                break
        if not parts:
            return pd.DataFrame()
        z = pd.concat(parts, ignore_index=True)
        z["ts"] = pd.to_datetime(z["datetime"], errors="coerce")
        z = z.dropna(subset=["ts"]).drop_duplicates("ts").sort_values("ts")
        z = z[(z.ts >= pd.Timestamp(START_DATE)) &
              (z.ts < pd.Timestamp(END_DATE) + pd.Timedelta(days=1))]
        # normalize to common schema
        for col in ["open", "high", "low", "close", "vol", "amount"]:
            if col in z.columns:
                z[col] = pd.to_numeric(z[col], errors="coerce")
        return pd.DataFrame({
            "ts": z.ts,
            "open": z.open,
            "high": z.high,
            "low": z.low,
            "close": z.close,
            "volume": z["vol"] if "vol" in z.columns else 0,
            "amount": z["amount"] if "amount" in z.columns else None,
            "source": "pytdx_index",
        }).dropna(subset=["ts", "close"])
    finally:
        api.disconnect()


def assert_exact(df, symbol):
    _, sm = validate_a_share(df, symbol)
    r = sm.iloc[0]
    print("CORE_CHECK", symbol, r.to_dict())
    if int(r["expected_days"]) != 39 or int(r["days"]) != 39 or int(r["bars"]) != 1872:
        raise RuntimeError(f"{symbol} is not exact 39x48")
    if int(r["missing_days"]) != 0 or int(r["incomplete_days"]) != 0 or float(r["completeness"]) != 1.0:
        raise RuntimeError(f"{symbol} completeness failed")
    return sm


def main():
    stock_data = fetch_stocks_with_retry()
    summaries = []
    for symbol in PCB_STOCKS:
        x = stock_data[symbol].copy()
        x["ts"] = pd.to_datetime(x["ts"])
        x = x[(x.ts >= pd.Timestamp(START_DATE)) &
              (x.ts < pd.Timestamp(END_DATE) + pd.Timedelta(days=1))]
        sm = assert_exact(x, symbol)
        sm["primary_source"] = "baostock"
        summaries.append(sm)
        save(x.assign(symbol=symbol), DATA / f"a_{symbol}_baostock.csv")

    idx = fetch_index_pytdx()
    sm = assert_exact(idx, INDEX)
    sm["primary_source"] = "pytdx_index"
    summaries.append(sm)
    save(idx.assign(symbol=INDEX), DATA / "a_000001_SH_pytdx_index.csv")

    report = pd.concat(summaries, ignore_index=True)
    report.to_csv(RESULTS / "completeness.csv", index=False)
    print("CORE_OOS_DATA_EXACT_OK")
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
