from pathlib import Path
import pandas as pd

from config import A_SHARES, START_DATE, END_DATE, OVERSEAS
from collectors import fetch_baostock_5m, fetch_eastmoney_5m, fetch_sina_5m, fetch_yahoo_recent_5m
from validate import validate_a_share, compare_sources

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
RESULTS = BASE / "results"
DATA.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)


def save(df, path):
    if df is not None and not df.empty:
        df.to_csv(path, index=False)


def safe(call, label):
    try:
        return call()
    except Exception as e:
        print(label, "FAILED", repr(e))
        return pd.DataFrame()


def main():
    summaries, comparisons = [], []
    for symbol, cfg in A_SHARES.items():
        bs = safe(lambda: fetch_baostock_5m(cfg["sina"], START_DATE, END_DATE), f"baostock {symbol}")
        sn = safe(lambda: fetch_sina_5m(cfg["sina"], 1023), f"sina {symbol}")
        em = safe(lambda: fetch_eastmoney_5m(cfg["secid"], START_DATE, END_DATE), f"eastmoney {symbol}")
        yh = safe(lambda: fetch_yahoo_recent_5m(cfg["yahoo"], START_DATE, END_DATE), f"yahoo-cn {symbol}")
        for x in (bs, sn, yh, em):
            if not x.empty:
                x["ts"] = pd.to_datetime(x.ts)
        for x in (bs, sn, em):
            if not x.empty:
                x.drop(x[(x.ts < pd.Timestamp(START_DATE)) | (x.ts >= pd.Timestamp(END_DATE) + pd.Timedelta(days=1))].index, inplace=True)
        if not sn.empty and ("amount" not in sn.columns or sn["amount"].isna().all()):
            sn["amount"] = sn["close"] * sn["volume"]
        if not yh.empty:
            if getattr(yh.ts.dt, "tz", None) is not None:
                yh["ts"] = yh.ts.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
            yh = yh[(yh.ts >= pd.Timestamp(START_DATE)) & (yh.ts < pd.Timestamp(END_DATE) + pd.Timedelta(days=1))]
            if "amount" not in yh.columns or yh["amount"].isna().all():
                yh["amount"] = yh["close"] * yh["volume"]

        save(bs.assign(symbol=symbol), DATA / f"a_{symbol.replace('.', '_')}_baostock.csv")
        save(em.assign(symbol=symbol), DATA / f"a_{symbol.replace('.', '_')}_eastmoney.csv")
        save(sn.assign(symbol=symbol), DATA / f"a_{symbol.replace('.', '_')}_sina.csv")
        save(yh.assign(symbol=symbol), DATA / f"a_{symbol.replace('.', '_')}_yahoo.csv")

        primary = bs if not bs.empty else (sn if not sn.empty else (em if not em.empty else yh))
        source = "baostock" if not bs.empty else ("sina" if not sn.empty else ("eastmoney" if not em.empty else "yahoo"))
        daily, summary = validate_a_share(primary, symbol)
        if not summary.empty:
            summary["primary_source"] = source
        save(daily, RESULTS / f"daily_{symbol.replace('.', '_')}.csv")
        summaries.append(summary)
        if not bs.empty and not sn.empty:
            c = compare_sources(bs, sn, symbol); c["pair"] = "baostock-sina"; comparisons.append(c)
        elif not bs.empty and not yh.empty:
            c = compare_sources(bs, yh, symbol); c["pair"] = "baostock-yahoo"; comparisons.append(c)

    for ticker, name in OVERSEAS.items():
        x = safe(lambda: fetch_yahoo_recent_5m(ticker, START_DATE, END_DATE), f"overseas {ticker}")
        if not x.empty:
            x["symbol"], x["name"] = ticker, name
        save(x, DATA / ("o_" + ticker.replace("^", "IDX_").replace("=", "_").replace(".", "_") + ".csv"))

    sm = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    cp = pd.concat(comparisons, ignore_index=True) if comparisons else pd.DataFrame()
    save(sm, RESULTS / "completeness.csv")
    save(cp, RESULTS / "source_compare.csv")
    print("COMPLETENESS")
    print(sm.to_string(index=False) if not sm.empty else "none")
    print("SOURCE_COMPARE")
    print(cp.to_string(index=False) if not cp.empty else "none")
    valid = sm[sm["symbol"] != "000001.SH"] if not sm.empty and "symbol" in sm else pd.DataFrame()
    if valid.empty or "completeness" not in valid or (valid.completeness < 0.95).any():
        raise SystemExit("A-share stock primary data completeness below 95%")


if __name__ == "__main__":
    main()
