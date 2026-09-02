import pandas as pd

A_SESSIONS = [("09:30", "11:30"), ("13:00", "15:00")]
EXPECTED_BARS = 48


def normalize_a_share(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    x = df.copy()
    x["ts"] = pd.to_datetime(x["ts"])
    if getattr(x["ts"].dt, "tz", None) is not None:
        x["ts"] = x["ts"].dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    x = x.sort_values("ts").drop_duplicates("ts", keep="last")
    return x


def validate_a_share(df: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = normalize_a_share(df)
    if x.empty:
        return pd.DataFrame(), pd.DataFrame([{"symbol": symbol, "status": "empty"}])
    x["date"] = x["ts"].dt.date.astype(str)
    daily = x.groupby("date").agg(
        bars=("ts", "count"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        amount=("amount", "sum"),
    ).reset_index()
    daily["symbol"] = symbol
    daily["complete"] = daily["bars"].between(46, 48)
    daily["bar_gap"] = EXPECTED_BARS - daily["bars"]
    summary = pd.DataFrame([{
        "symbol": symbol,
        "days": len(daily),
        "complete_days": int(daily["complete"].sum()),
        "incomplete_days": int((~daily["complete"]).sum()),
        "bars": len(x),
        "expected_bars_if_full": len(daily) * EXPECTED_BARS,
        "missing_bar_estimate": int((daily["bar_gap"].clip(lower=0)).sum()),
        "completeness": float(daily["bars"].sum() / max(1, len(daily) * EXPECTED_BARS)),
    }])
    return daily, summary


def compare_sources(primary: pd.DataFrame, secondary: pd.DataFrame, symbol: str) -> pd.DataFrame:
    a, b = normalize_a_share(primary), normalize_a_share(secondary)
    if a.empty or b.empty:
        return pd.DataFrame([{"symbol": symbol, "overlap": 0}])
    cols = ["ts", "open", "high", "low", "close", "volume"]
    z = a[cols].merge(b[cols], on="ts", suffixes=("_a", "_b"))
    if z.empty:
        return pd.DataFrame([{"symbol": symbol, "overlap": 0}])
    for c in ["open", "high", "low", "close"]:
        denom = z[f"{c}_a"].abs().replace(0, pd.NA)
        z[f"{c}_pct_diff"] = ((z[f"{c}_a"] - z[f"{c}_b"]).abs() / denom).astype(float)
    return pd.DataFrame([{
        "symbol": symbol,
        "overlap": len(z),
        "median_close_pct_diff": z["close_pct_diff"].median(),
        "p99_close_pct_diff": z["close_pct_diff"].quantile(0.99),
        "max_close_pct_diff": z["close_pct_diff"].max(),
    }])
