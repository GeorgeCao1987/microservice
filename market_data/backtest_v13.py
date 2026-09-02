from pathlib import Path
import json
import numpy as np
import pandas as pd

from config import PCB_MEMBERS

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
RESULTS = BASE / "results"
RESULTS.mkdir(exist_ok=True)
TARGET = "002916"


def load_a(symbol, source="eastmoney"):
    p = DATA / f"a_{symbol.replace('.', '_')}_{source}.csv"
    if not p.exists():
        return pd.DataFrame()
    x = pd.read_csv(p)
    x["ts"] = pd.to_datetime(x["ts"])
    x = x.sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    return x


def add_target_features(df):
    x = df.copy()
    # Everything below is based only on current/past bars.
    x["ret1"] = x.close.pct_change()
    x["range"] = (x.high - x.low) / x.close.shift(1)
    x["typical"] = (x.high + x.low + x.close) / 3
    x["cum_pv"] = (x.typical * x.volume).groupby(x.ts.dt.date).cumsum()
    x["cum_v"] = x.volume.groupby(x.ts.dt.date).cumsum().replace(0, np.nan)
    x["vwap"] = x.cum_pv / x.cum_v
    x["eff"] = x.ret1.abs() / x.amount.replace(0, np.nan) if "amount" in x else x.ret1.abs() / x.volume.replace(0, np.nan)
    # Rolling references explicitly shifted by one bar: current bar is never in the baseline.
    x["prior_high3"] = x.high.shift(1).rolling(3).max()
    x["prior_low3"] = x.low.shift(1).rolling(3).min()
    x["prior_eff3"] = x.eff.shift(1).rolling(3).mean()
    x["high_candidate"] = (x.high >= x.prior_high3) & (x.eff < x.prior_eff3 * 0.85)
    x["low_candidate"] = (x.low <= x.prior_low3) & (x.eff < x.prior_eff3 * 0.85)
    # trend state from last 4 completed/current bars only
    x["hh"] = x.high > x.high.shift(1)
    x["hl"] = x.low > x.low.shift(1)
    x["lh"] = x.high < x.high.shift(1)
    x["ll"] = x.low < x.low.shift(1)
    x["up_structure"] = (x.hh.astype(int).rolling(4).sum() + x.hl.astype(int).rolling(4).sum()) / 8
    x["down_structure"] = (x.lh.astype(int).rolling(4).sum() + x.ll.astype(int).rolling(4).sum()) / 8
    x["above_vwap"] = x.close > x.vwap
    return x


def build_pcb_context():
    parts = []
    for s in PCB_MEMBERS:
        x = load_a(s)
        if x.empty:
            continue
        x = x[["ts", "close"]].copy()
        x["day_open"] = x.close.groupby(x.ts.dt.date).transform("first")
        x[f"r_{s}"] = x.close / x.day_open - 1
        parts.append(x[["ts", f"r_{s}"]].set_index("ts"))
    if not parts:
        return pd.DataFrame()
    z = pd.concat(parts, axis=1).sort_index()
    z["pcb_ret"] = z.mean(axis=1, skipna=True)
    z["pcb_up_breadth"] = (z > 0).sum(axis=1) / z.notna().sum(axis=1).replace(0, np.nan)
    return z[["pcb_ret", "pcb_up_breadth"]].reset_index()


def build_index_context():
    x = load_a("000001.SH")
    if x.empty:
        return pd.DataFrame(columns=["ts", "index_ret"])
    x = x[["ts", "close"]].copy()
    x["day_open"] = x.close.groupby(x.ts.dt.date).transform("first")
    x["index_ret"] = x.close / x.day_open - 1
    return x[["ts", "index_ret"]]


def load_overseas(name_fragment):
    files = list(DATA.glob(f"o_*{name_fragment}*.csv"))
    if not files:
        return pd.DataFrame()
    x = pd.read_csv(files[0])
    x["ts"] = pd.to_datetime(x.ts, utc=True, errors="coerce").dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    x = x.sort_values("ts")
    x["day_open"] = x.close.groupby(x.ts.dt.date).transform("first")
    x["ret_from_open"] = x.close / x.day_open - 1
    return x[["ts", "ret_from_open"]]


def asof_merge(base, ctx, col):
    if ctx.empty:
        base[col] = np.nan
        return base
    return pd.merge_asof(base.sort_values("ts"), ctx.sort_values("ts"), on="ts", direction="backward")


def evaluate_future(x, idx, side):
    row = {"future_15m": np.nan, "future_30m": np.nan, "future_60m": np.nan,
           "mae_30m": np.nan, "mfe_30m": np.nan}
    px = x.loc[idx, "close"]
    for bars, label in [(3,"15m"),(6,"30m"),(12,"60m")]:
        w = x.iloc[idx+1:idx+1+bars]
        if w.empty:
            continue
        if side == "HIGH":
            favorable = (px - w.low.min()) / px
            adverse = (w.high.max() - px) / px
        else:
            favorable = (w.high.max() - px) / px
            adverse = (px - w.low.min()) / px
        row[f"future_{label}"] = favorable
        if bars == 6:
            row["mfe_30m"], row["mae_30m"] = favorable, adverse
    return row


def main():
    target = load_a(TARGET)
    if target.empty:
        raise SystemExit("missing target data")
    x = add_target_features(target)
    pcb = build_pcb_context()
    idx = build_index_context()
    x = x.merge(pcb, on="ts", how="left").merge(idx, on="ts", how="left")
    x["pcb_rel"] = x.pcb_ret - x.index_ret
    # external real-time confirmers; optional if source unavailable
    for frag, col in [("000660_KS","hynix_ret"),("005930_KS","samsung_ret"),("IDX_KS11","kospi_ret")]:
        ctx = load_overseas(frag)
        if not ctx.empty:
            ctx = ctx.rename(columns={"ret_from_open": col})
            x = asof_merge(x, ctx, col)
        else:
            x[col] = np.nan

    rows = []
    for i, r in x.iterrows():
        if i < 8:
            continue
        for side, flag in [("HIGH", r.high_candidate), ("LOW", r.low_candidate)]:
            if not bool(flag):
                continue
            # No future fields are used to form these scores.
            trend_up = float(r.up_structure) + (0.25 if r.above_vwap else 0) + (0.25 if r.pcb_rel > 0 else 0)
            trend_down = float(r.down_structure) + (0.25 if not r.above_vwap else 0) + (0.25 if r.pcb_rel < 0 else 0)
            if side == "HIGH":
                exhaustion = 1.0 + (0.5 if r.pcb_rel < x.loc[i-1, "pcb_rel"] else 0)
                if pd.notna(r.hynix_ret) and r.hynix_ret < 0: exhaustion += 0.25
                score = exhaustion - max(0, trend_up - 0.75) * 0.5
            else:
                exhaustion = 1.0 + (0.5 if r.pcb_rel > x.loc[i-1, "pcb_rel"] else 0)
                if pd.notna(r.hynix_ret) and r.hynix_ret > 0: exhaustion += 0.25
                score = exhaustion - max(0, trend_down - 0.75) * 0.5
            alert = score >= 1.0
            rec = {"ts": r.ts, "side": side, "price": r.close, "alert": alert, "score": score,
                   "trend_up": trend_up, "trend_down": trend_down, "pcb_ret": r.pcb_ret,
                   "index_ret": r.index_ret, "pcb_rel": r.pcb_rel, "hynix_ret": r.hynix_ret,
                   "samsung_ret": r.samsung_ret, "kospi_ret": r.kospi_ret}
            rec.update(evaluate_future(x, i, side))
            rows.append(rec)
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "candidates_v13.csv", index=False)
    alerts = out[out.alert].copy()
    summary = {}
    for side in ["HIGH", "LOW"]:
        a = alerts[alerts.side == side]
        summary[side] = {
            "candidates": int((out.side == side).sum()),
            "alerts": len(a),
            "win_15m_1pct": float((a.future_15m >= .01).mean()) if len(a) else None,
            "win_30m_1_5pct": float((a.future_30m >= .015).mean()) if len(a) else None,
            "median_mfe_30m": float(a.mfe_30m.median()) if len(a) else None,
            "median_mae_30m": float(a.mae_30m.median()) if len(a) else None,
        }
    (RESULTS / "summary_v13.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
