from pathlib import Path
import pandas as pd

from config import A_SHARES, START_DATE, END_DATE, OVERSEAS
from collectors import fetch_mootdx_5m, fetch_sina_5m, fetch_yahoo_recent_5m, fetch_yahoo_daily
from validate import validate_a_share, compare_sources

BASE=Path(__file__).resolve().parent; DATA=BASE/"data"; RESULTS=BASE/"results"; DATA.mkdir(exist_ok=True); RESULTS.mkdir(exist_ok=True)
def save(df,path):
    if df is not None and not df.empty: df.to_csv(path,index=False)
def safe(call,label):
    try: return call()
    except Exception as e: print(label,"FAILED",repr(e)); return pd.DataFrame()

def main():
    summaries=[]; comparisons=[]
    for symbol,cfg in A_SHARES.items():
        td=safe(lambda:fetch_mootdx_5m(cfg["sina"],START_DATE,END_DATE,is_index=(symbol=="000001.SH")),f"mootdx {symbol}")
        sn=safe(lambda:fetch_sina_5m(cfg["sina"],1023),f"sina {symbol}")
        for x in (td,sn):
            if not x.empty:
                x["ts"]=pd.to_datetime(x.ts); x.drop(x[(x.ts<pd.Timestamp(START_DATE))|(x.ts>=pd.Timestamp(END_DATE)+pd.Timedelta(days=1))].index,inplace=True)
        if not sn.empty and ("amount" not in sn.columns or sn.amount.isna().all()): sn["amount"]=sn.close*sn.volume
        save(td.assign(symbol=symbol),DATA/f"a_{symbol.replace('.','_')}_mootdx.csv"); save(sn.assign(symbol=symbol),DATA/f"a_{symbol.replace('.','_')}_sina.csv")
        primary=td if not td.empty else sn; source="mootdx" if not td.empty else "sina"
        daily,summary=validate_a_share(primary,symbol)
        if not summary.empty: summary["primary_source"]=source
        save(daily,RESULTS/f"daily_{symbol.replace('.','_')}.csv"); summaries.append(summary)
        if not td.empty and not sn.empty:
            c=compare_sources(td,sn,symbol); c["pair"]="mootdx-sina"; comparisons.append(c)

    for ticker,name in OVERSEAS.items():
        x=safe(lambda t=ticker:fetch_yahoo_recent_5m(t,START_DATE,END_DATE),f"overseas {ticker}")
        if not x.empty: x["symbol"],x["name"]=ticker,name
        save(x,DATA/("o_"+ticker.replace("^","IDX_").replace("=","_").replace(".","_")+".csv"))

    macro_start=(pd.Timestamp(START_DATE)-pd.DateOffset(years=3)).strftime("%Y-%m-%d")
    for ticker,label in [("^TYX","tyx"),("CL=F","oil"),("^SOX","sox")]:
        d=safe(lambda t=ticker:fetch_yahoo_daily(t,macro_start,END_DATE),f"daily macro {ticker}"); save(d,DATA/f"macro_{label}_daily_3y.csv")

    sm=pd.concat(summaries,ignore_index=True) if summaries else pd.DataFrame(); cp=pd.concat(comparisons,ignore_index=True) if comparisons else pd.DataFrame()
    save(sm,RESULTS/"completeness.csv"); save(cp,RESULTS/"source_compare.csv")
    print("COMPLETENESS"); print(sm.to_string(index=False) if not sm.empty else "none")
    print("SOURCE_COMPARE"); print(cp.to_string(index=False) if not cp.empty else "none")
    if sm.empty or "completeness" not in sm or (sm.completeness<.95).any(): raise SystemExit("A-share/index primary data completeness below 95%")

if __name__=="__main__": main()
