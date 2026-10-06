"""Build the compact JSON dataset used by the UK HE finance dashboard.

Inputs: HESA Finance open data (CC-BY-4.0) in data/raw/
  Table 1  - income totals and income by type
  Table 6  - tuition fees (non-EU fee income)
  Table 7  - residences and catering income
  Table 8  - expenditure by activity and HESA cost centre (incl. pension cost adjustment)
  Table 9  - capital expenditure (estates vs equipment/digital investment)
  Table 14 - key financial indicators (context)
  Table 12 - staff FTE, salaries and staff earning over £100k (staffing tab)
  Staff Table 7 - academic staff by contract level, function, terms and mode (staffing tab)
  Staff Table 1 - all staff by occupation (SOC), incl. managers and non-academic staff mix (staffing tab)
Plus data/mission_groups.csv (editable membership list).

All money values are £000s. Output: data/dashboard_data.json
"""
import glob
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "dashboard_data.json"


def read(path, usecols=None):
    df = pd.read_csv(path, skiprows=10, dtype=str, encoding="utf-8-sig", usecols=usecols)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"HE Provider": "HE provider", "Academic Year": "Academic year"})
    df = df[df["Year End Month"] == "All"].copy()  # one row per provider/year
    val = [c for c in df.columns if c.startswith("Value") or c == "Number/value"][0]
    s = df[val].fillna("").str.replace(",", "").str.strip()
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    df["v"] = pd.to_numeric(s, errors="coerce")
    return df


def code(label):
    m = re.match(r"^(\d{3})\b", str(label).strip())
    return m.group(1) if m else None


# ---------------------------------------------------------------- Table 1: income
t1 = read(RAW / "hesa-fin-table-1.csv")
providers = (t1.sort_values("Academic year")
             .groupby("UKPRN")
             .agg(name=("HE provider", "last"), country=("Country of HE provider", "last"),
                  region=("Region of HE provider", "last")))
inc = t1[t1["Category marker"] == "Income"]
inc_map = {
    "Total income": "inc",
    "Tuition fees and education contracts": "inc_fees",
    "Funding body grants": "inc_fbg",
    "Research grants and contracts": "inc_res",
    "Other income": "inc_oth",
    "Investment income": "inc_invest",
    "Donations and endowments": "inc_don",
}
inc = inc[inc["Category"].isin(inc_map)].assign(k=lambda d: d["Category"].map(inc_map))
fin = inc.pivot_table(index=["UKPRN", "Academic year"], columns="k", values="v", aggfunc="sum")

# ---------------------------------------------------------------- Table 8: expenditure
exp_rows, det_rows = [], []
ADM, RES, RCO = "Administration & central services", "Research grants and contracts", \
    "Residences and catering operations (including conferences)"
DET_LINES = {
    (ADM, "National Bursaries"): "ge_nat",
    (ADM, "Provider specific (including departmental) bursaries and scholarships"): "ge_prov",
    (ADM, "Other general expenditure"): "ge_oth",
    ("Premises", "Repairs and maintenance"): "pr_rm",
    ("Premises", "Other expenditure"): "pr_oth",
    (RCO, "Residences operations"): "rc_res",
    (RCO, "Catering operations"): "rc_cat",
    (RES, "Total BEIS Research Councils, The Royal Society, British Academy and The Royal Society of Edinburgh"): "rs_rc",
    (RES, "UK-based charities (open competitive process)"): "rs_char",
    (RES, "UK-based charities (other)"): "rs_char",
    (RES, "UK central government bodies/local authorities, health and hospital authorities"): "rs_gov",
    (RES, "UK industry, commerce and public corporations"): "rs_ind",
    (RES, "UK other sources"): "rs_ukoth",
    (RES, "EU government bodies"): "rs_eu",
    (RES, "EU-based charities (open competitive process)"): "rs_eu",
    (RES, "EU industry, commerce and public corporations"): "rs_eu",
    (RES, "EU (excluding UK) other"): "rs_eu",
    (RES, "Non-EU-based charities (open competitive process)"): "rs_noneu",
    (RES, "Non-EU industry, commerce and public corporations"): "rs_noneu",
    (RES, "Non-EU other"): "rs_noneu",
}
DET_HEADS = {("Academic departments", "Total academic departments"): "acad",
             ("Other expenditure", "Pension cost adjustment"): "pen"}
HEAD_CC = {"201": "acserv", "202": "admin", "203": "gen_ed", "204": "facilities",
           "205": "premises", "206": "resid", "207": "research", "208": "other"}
NATURE = {"Academic staff costs": "as", "Other staff costs": "os", "Restructuring costs": "rs",
          "Other operating expenses": "op", "Depreciation and amortisation": "dp",
          "Interest and other finance costs": "in"}
for f in sorted(glob.glob(str(RAW / "hesa-fin-table-8" / "*.csv"))):
    d = read(f)
    d["cc"] = d["Academic departments"].map(code)
    tot = d[d["Activity"] == "Total expenditure"]
    sub = d["Academic departments"].str.strip()
    pick = {
        "acad": tot[sub.loc[tot.index] == "Total academic departments"],
        "pension_adj": tot[sub.loc[tot.index] == "Pension cost adjustment"],
        "exp": tot[(tot["HESA cost centre"] == "Total expenditure")],
    }
    for c, k in {"201": "acserv", "202": "admin", "203": "gen_ed", "204": "facilities",
                 "205": "premises", "206": "resid", "207": "research", "208": "other"}.items():
        pick[k] = tot[tot["cc"] == c]
    for k, df in pick.items():
        exp_rows.append(df.groupby(["UKPRN", "Academic year"])["v"].sum().rename(k).to_frame())
    # detail: sub-lines (totals) and type-of-cost split for each heading
    key = list(zip(d["HESA cost centre"].str.strip(), sub))
    line = pd.Series([DET_LINES.get(k) for k in key], index=d.index)
    head = pd.Series([DET_HEADS.get(k) for k in key], index=d.index).fillna(d["cc"].map(HEAD_CC))
    a = d["Activity"].str.strip()
    t = d[(a == "Total expenditure") & line.notna()].assign(k=line)
    n = d[a.isin(NATURE) & head.notna()].assign(k=head + "_" + a.map(NATURE))
    det_rows.append(pd.concat([t, n]).pivot_table(index=["UKPRN", "Academic year"], columns="k", values="v", aggfunc="sum"))

exp = pd.concat(exp_rows).groupby(level=[0, 1]).sum(min_count=1)
fin = fin.join(exp, how="outer")
fin["pension_adj"] = fin["pension_adj"].fillna(0)
fin["other_ex_pen"] = fin["other"] - fin["pension_adj"]
det = pd.concat(det_rows).groupby(level=[0, 1]).sum(min_count=1)
DET_COLS = sorted(det.columns)
fin = fin.join(det, how="left")

# ---------------------------------------------------------------- Table 9: capital expenditure
t9 = read(RAW / "hesa-fin-table-9.csv")
t9 = t9[t9["Source of funds"] == "Total actual spend"]
asset = t9["Type of asset"].str.strip()
capex_total = t9[asset == "Total capital expenditure"].groupby(["UKPRN", "Academic year"])["v"].sum()
capex_build = t9[asset == "Buildings"].groupby(["UKPRN", "Academic year"])["v"].sum()
# equipment + intangibles (software/digital) = total less buildings (asset split changed in 2020/21)
capex_equip = capex_total - capex_build.reindex(capex_total.index).fillna(0)
fin = fin.join(pd.concat([capex_total.rename("capex"), capex_build.rename("capex_build"),
                          capex_equip.rename("capex_equip")], axis=1), how="left")

# ---------------------------------------------------------------- Table 7: residences & catering income
t7 = read(RAW / "hesa-fin-table-7.csv")
t7 = t7[t7["Category"].str.strip() == "Residences, conferences and catering operations"]
src = t7["Source of income"].str.strip()
fin = fin.join(pd.concat([
    t7[src == "Residences operations"].groupby(["UKPRN", "Academic year"])["v"].sum().rename("inc_resid"),
    t7[src == "Catering and Conference operations"].groupby(["UKPRN", "Academic year"])["v"].sum().rename("inc_cater"),
], axis=1), how="left")

# ---------------------------------------------------------------- Table 6: non-EU fee income
fee_rows = []
for f in sorted(glob.glob(str(RAW / "hesa-fin-table-6" / "*.csv"))):
    d = read(f)
    c = d["Tuition fees and education contracts"].str.strip()
    fee_rows.append(d[c.isin(["Total Non-EU fees", "Total Non-UK fees"])].groupby(["UKPRN", "Academic year"])["v"].sum())
fin = fin.join(pd.concat(fee_rows).rename("fees_nonEU"), how="left")

# ---------------------------------------------------------------- Table 14: KFIs
t14 = read(RAW / "hesa-fin-table-14.csv")
kfi_map = {
    "Unrestricted reserves as a % of total income": "kfi_reserves",
    "External borrowing as a % of total income": "kfi_borrowing",
    "Net liquidity days excl. pension adjustment": "kfi_liquidity",
}
k = t14[t14["KFI ratio title"].isin(kfi_map)].assign(k=lambda d: d["KFI ratio title"].map(kfi_map))
fin = fin.join(k.pivot_table(index=["UKPRN", "Academic year"], columns="k", values="v", aggfunc="first"), how="left")

# ---------------------------------------------------------------- assemble
fin = fin[fin["inc"].notna() & (fin["inc"] > 0) & fin["exp"].notna()].reset_index()
years = sorted(fin["Academic year"].unique())
yi = {y: i for i, y in enumerate(years)}

FIN_COLS = ["inc", "inc_fees", "inc_fbg", "inc_res", "inc_oth", "inc_invest", "inc_don",
            "exp", "acad", "research", "acserv", "admin", "gen_ed", "facilities", "premises",
            "resid", "other_ex_pen", "pension_adj", "capex", "capex_build", "capex_equip",
            "fees_nonEU", "inc_resid", "inc_cater", "kfi_reserves", "kfi_borrowing", "kfi_liquidity"] + DET_COLS


def j(x, dp=0):
    if pd.isna(x):
        return None
    return round(float(x), dp) if dp else int(round(float(x)))


fin_out = [[r["UKPRN"], yi[r["Academic year"]]] +
           [j(r[c], 1 if c.startswith("kfi") else 0) for c in FIN_COLS] for _, r in fin.iterrows()]

# ---------------------------------------------------------------- staffing (Finance Table 12 + Staff Table 7)
t12 = read(RAW / "hesa-fin-table-12.csv")
T12 = {"Salaries and wages academic staff": "sal_ac", "Salaries and wages non-academic staff": "sal_na",
       "Average academic staff numbers (FTE)": "fte_ac", "Average non-academic staff numbers (FTE)": "fte_na",
       "FTE (England only)": "hi_fte", "Headcount (Northern Ireland and Wales only)": "hi_hc"}
t12 = t12[t12["Staff costs"].isin(T12)].assign(k=lambda x: x["Staff costs"].map(T12))
staff = t12.pivot_table(index=["UKPRN", "Academic year"], columns="k", values="v", aggfunc="first")
T7 = {("Contract levels", "Professor"): "st_prof", ("Contract levels", "Other senior academic"): "st_sen",
      ("Contract levels", "Other contract level"): "st_oth",
      ("Academic employment function", "Both teaching and research"): "st_tr",
      ("Academic employment function", "Research only"): "st_ro", ("Academic employment function", "Teaching only"): "st_to",
      ("Terms of employment", "Fixed-term"): "st_fixed", ("Sex", "Female"): "st_fem",
      ("Total academic staff", "Total academic staff"): "st_tot"}
t7rows = []
for f in sorted(glob.glob(str(RAW / "hesa-staff-table-7" / "*.csv"))):
    lines = Path(f).read_text(encoding="utf-8-sig").splitlines()
    hdr = next(i for i, l in enumerate(lines[:40]) if l.startswith("UKPRN"))
    t = pd.read_csv(f, skiprows=hdr, dtype=str, encoding="utf-8-sig")
    t = t[(t["Country of HE provider"] == "All") & (t["Region of HE provider"] == "All")
          & (t["Activity standard occupational classification"] == "All")]
    t["v"] = pd.to_numeric(t["Number"].str.replace(",", ""), errors="coerce")
    a = t[t["Mode of employment"] == "All"]
    a = a.assign(k=[T7.get((m, c)) for m, c in zip(a["Category marker"], a["Category"])]).dropna(subset=["k"])
    m = t[(t["Mode of employment"] == "Part-time") & (t["Category"] == "Total academic staff")].assign(k="st_pt")
    t7rows.append(pd.concat([a, m]).rename(columns={"Academic Year": "Academic year"}))
t7 = pd.concat(t7rows).pivot_table(index=["UKPRN", "Academic year"], columns="k", values="v", aggfunc="first")
# Staff Table 1: headcount by occupation (non-academic data is suppressed for providers that opted out)
T1 = {("Non-academic", "Managers, directors and senior officials"): "na_mgr", ("Academic", "Managers, directors and senior officials"): "ac_mgr",
      ("Non-academic", "Professional occupations"): "na_prof", ("Non-academic", "Associate professional occupations"): "na_assoc",
      ("Non-academic", "Administrative and secretarial occupations"): "na_admin", ("Non-academic", "Skilled trades occupations"): "na_trades",
      ("Non-academic", "Elementary occupations"): "na_elem", ("Non-academic", "Total non-academic staff"): "na_tot",
      ("Non-academic", "Clerical and manual occupations"): "na_cler"}
f1 = RAW / "hesa-staff-table-1" / "table-1.csv"
lines = f1.read_text(encoding="utf-8-sig").splitlines()
t1 = pd.read_csv(f1, skiprows=next(i for i, l in enumerate(lines[:60]) if l.startswith("UKPRN")), dtype=str, encoding="utf-8-sig")
t1 = t1[(t1["Country of HE provider"] == "All") & (t1["Region of HE provider"] == "All")
        & (t1["Mode of employment"] == "All") & (t1["Atypical marker"] == "Non-atypical")]
t1 = t1.assign(v=pd.to_numeric(t1["Number"].str.replace(",", ""), errors="coerce"),
               k=[T1.get((a, c)) for a, c in zip(t1["Academic marker"], t1["Activity standard occupational classification"])])
t1 = t1.dropna(subset=["k"]).pivot_table(index=["UKPRN", "Academic year"], columns="k", values="v", aggfunc="first")
staff = staff.join(t7, how="outer").join(t1, how="outer").reset_index()
staff = staff[staff["Academic year"].isin(yi) & staff["UKPRN"].isin(set(fin["UKPRN"]))]
STAFF_COLS = ["st_tot", "st_prof", "st_sen", "st_oth", "st_tr", "st_ro", "st_to", "st_fixed", "st_fem", "st_pt",
              "sal_ac", "sal_na", "fte_ac", "fte_na", "hi_fte", "hi_hc",
              "na_mgr", "ac_mgr", "na_prof", "na_assoc", "na_admin", "na_trades", "na_elem", "na_cler", "na_tot"]
for c in STAFF_COLS:
    if c not in staff:
        staff[c] = None
staff_out = [[r["UKPRN"], yi[r["Academic year"]]] + [j(r[c]) for c in STAFF_COLS] for _, r in staff.iterrows()]

mg = pd.read_csv(ROOT / "data" / "mission_groups.csv", dtype=str)
groups = {g: sorted(set(x["ukprn"])) for g, x in mg.groupby("group", sort=False)}

used = set(fin["UKPRN"])
out = {
    "meta": {"source": "HESA Finance open data (Tables 1, 6, 7, 8, 9, 14), CC BY 4.0. Last updated May-26.",
             "units": "£000s"},
    "years": years,
    "providers": {u: [p["name"], p["country"], p["region"]] for u, p in providers.iterrows() if u in used},
    "groups": groups,
    "fin_cols": FIN_COLS,
    "fin": fin_out,
    "staff_cols": STAFF_COLS,
    "staff": staff_out,
}
OUT.write_text(json.dumps(out, separators=(",", ":")))
print(f"providers={len(out['providers'])} fin_rows={len(fin_out)} "
      f"size={OUT.stat().st_size/1e6:.1f}MB years={years[0]}..{years[-1]}")
