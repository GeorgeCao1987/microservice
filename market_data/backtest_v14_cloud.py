import pandas as pd
from pathlib import Path
import backtest_v13 as v13
import backtest_v14 as v14

DATA = Path(__file__).resolve().parent / "data"


def load_a_cloud(symbol, source=None):
    key = symbol.replace('.', '_')
    for src in ["mootdx", "sina", "eastmoney", "yahoo"]:
        p = DATA / f"a_{key}_{src}.csv"
        if not p.exists():
            continue
        x = pd.read_csv(p)
        if x.empty:
            continue
        x["ts"] = pd.to_datetime(x["ts"])
        if getattr(x["ts"].dt, "tz", None) is not None:
            x["ts"] = x["ts"].dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
        return x.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    return pd.DataFrame()


if __name__ == "__main__":
    v13.load_a = load_a_cloud
    v14.main()
