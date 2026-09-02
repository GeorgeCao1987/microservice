from pathlib import Path
import pandas as pd

from config import A_SHARES, START_DATE, END_DATE, OVERSEAS
from collectors import fetch_eastmoney_5m, fetch_sina_5m, fetch_yahoo_5m
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
        em = safe(lambda: fetch_eastmoney_5m(cfg["secid"], START_DATE, END_DATE), f"eastmoney {symbol}")
        sn = safe(lambda: fetch_sina_5m(cfg["sina"], 2400), f"sina {symbol}")
        yh = safe(lambda: fetch_yahoo_5m(cfg["yahoo"], START_DATE, END_DATE), f"yahoo-cn {symbol}")
        for x in (sn, yh):
            if not x.empty:
                x["ts"] = pd.to_datetime(x.ts)
        if not sn.empty:
            sn = sn[(sn.ts >= pd.Timestamp(START_DATE)) & (sn.ts < pd.Timestamp(END_DATE) + pd.Timedelta(days=1))]
        if not yh.empty:
            # Yahoo timestamps are UTC-aware; convert to Shanghai and strip tz for A-share joins.
            if getattr(yh.ts.dt, "tz", None) is not None:
                yh["ts"] = yh.ts.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
            yh = yh[(yh.ts >= pd.Timestamp(START_DATE)) & (yh.ts < pd.Timestamp(END_DATE) + pd.Timedelta(days=1))]

        save(em.assign(symbol=symbol), DATA / f"a_{symbol.replace('.', '_')}_eastmoney.csv")
        save(sn.assign(symbol=symbol), DATA / f"a_{symbol.replace('.', '_')}_sina.csv")
        save(yh.assign(symbol=symbol), DATA / f"a_{symbol.replace('.', '_')}_yahoo.csv")

        primary = sn if not sn.empty else (em if not em.empty else yh)
        daily, summary = validate_a_share(primary, symbol)
        if not summary.empty:
            summary["primary_source"] = "sina" if not sn.empty else ("eastmoney" if not em.empty else "yahoo")
        save(daily, RESULTS / f"daily_{symbol.replace('.', '_')}.csv")
        summaries.append(summary)
        if not sn.empty and not yh.empty:
            c = compare_sources(sn, yh, symbol); c["pair"] = "sina-yahoo"; comparisons.append(c)
        elif not em.empty and not sn.empty:
            c = compare_sources(em, sn, symbol); c["pair"] = "eastmoney-sina"; comparisons.append(c)

    for ticker, name in OVERSEAS.items():
        x = safe(lambda: fetch_yahoo_5m(ticker, START_DATE, END_DATE), f"overseas {ticker}")
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
    if sm.empty or (sm.completeness < 0.90).any():
        raise SystemExit("A-share primary data completeness below 90%")


if __name__ == "__main__":
    main()
