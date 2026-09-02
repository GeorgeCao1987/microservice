import json
from pathlib import Path
import pandas as pd

from config import A_SHARES
from collectors import fetch_eastmoney_5m, fetch_sina_5m, fetch_yahoo_5m
from validate import validate_a_share, compare_sources
from config import START_DATE, END_DATE, OVERSEAS

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
RESULTS = BASE / "results"
DATA.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)


def save(df, path):
    if df is not None and not df.empty:
        df.to_csv(path, index=False)


def main():
    summaries, comparisons = [], []
    for symbol, cfg in A_SHARES.items():
        em = fetch_eastmoney_5m(cfg["secid"], START_DATE, END_DATE)
        sn = fetch_sina_5m(cfg["sina"], 2200)
        if not sn.empty:
            sn = sn[(sn.ts >= pd.Timestamp(START_DATE)) & (sn.ts < pd.Timestamp(END_DATE) + pd.Timedelta(days=1))]
        save(em.assign(symbol=symbol), DATA / f"a_{symbol.replace('.', '_')}_eastmoney.csv")
        save(sn.assign(symbol=symbol), DATA / f"a_{symbol.replace('.', '_')}_sina.csv")
        daily, summary = validate_a_share(em, symbol)
        save(daily, RESULTS / f"daily_{symbol.replace('.', '_')}.csv")
        summaries.append(summary)
        comparisons.append(compare_sources(em, sn, symbol))

    for ticker, name in OVERSEAS.items():
        try:
            x = fetch_yahoo_5m(ticker, START_DATE, END_DATE)
            if not x.empty:
                x["symbol"], x["name"] = ticker, name
            save(x, DATA / ("o_" + ticker.replace("^", "IDX_").replace("=", "_").replace(".", "_") + ".csv"))
        except Exception as e:
            print("overseas fetch failed", ticker, repr(e))

    sm = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    cp = pd.concat(comparisons, ignore_index=True) if comparisons else pd.DataFrame()
    save(sm, RESULTS / "completeness.csv")
    save(cp, RESULTS / "source_compare.csv")
    print("COMPLETENESS")
    print(sm.to_string(index=False) if not sm.empty else "none")
    print("SOURCE_COMPARE")
    print(cp.to_string(index=False) if not cp.empty else "none")


if __name__ == "__main__":
    main()
