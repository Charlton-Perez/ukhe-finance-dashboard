"""Build the compact JSON dataset used by the UK HE finance dashboard.

Inputs: HESA Finance open data (CC-BY-4.0) in data/raw/
  Table 1  - income totals and income by type
  Table 6  - tuition fees (non-EU fee income)
  Table 8  - expenditure by activity and HESA cost centre (incl. pension cost adjustment)
  Table 5  - research income by HESA cost centre (subject view)
  Table 9  - capital expenditure (estates vs equipment/digital investment)
  Table 14 - key financial indicators (context)
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
exp_rows, subj_rows, det_rows = [], [], []
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
SUBJ_ACT = {"Academic staff costs": "ac_staff", "Other staff costs": "oth_staff",
            "Other operating expenses": "opex", "Depreciation and amortisation": "dep",
            "Total expenditure": "total"}
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
    # subject (academic cost centres 101-145)
    s = d[(d["HESA cost centre"] == "Academic departments") & d["cc"].notna() & d["Activity"].isin(SUBJ_ACT)]
    s = s.assign(k=s["Activity"].map(SUBJ_ACT))
    subj_rows.append(s.pivot_table(index=["UKPRN", "Academic year", "cc"], columns="k", values="v", aggfunc="sum"))

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

# funding body grant components (England splits teaching and research; other nations report a total)
FB = {"Funding body grants": "fb_total", "Office for Students teaching grant": "fb_teach",
      "Department for Education teacher training funding": "fb_tt", "Research England research grants": "fb_qr",
      "Capital grants recognised in the year": "fb_cap"}
t7f = read(RAW / "hesa-fin-table-7.csv")
t7f = t7f[t7f["Category"].str.strip() == "Funding body grants"]
t7f = t7f.assign(k=t7f["Source of income"].str.strip().map(FB)).dropna(subset=["k"])
fbg = t7f.pivot_table(index=["UKPRN", "Academic year"], columns="k", values="v", aggfunc="sum")

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

# ---------------------------------------------------------------- Table 5: research income by subject
res_rows = []
for f in sorted(glob.glob(str(RAW / "hesa-fin-table-5" / "*.csv"))):
    d = read(f, usecols=["UKPRN", "Academic year", "HESA cost centre marker", "HESA cost centre",
                         "Source of income", "Year End Month", "Value(£000s)"])
    d = d[(d["HESA cost centre marker"] == "Academic departments") & d["Source of income"].str.strip().str.match(r"^15 Total")]
    d["cc"] = d["HESA cost centre"].map(code)
    res_rows.append(d[d["cc"].notna()].groupby(["UKPRN", "Academic year", "cc"])["v"].sum().rename("res_inc"))
subj = pd.concat(subj_rows).join(pd.concat(res_rows), how="outer")

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

# ---------------------------------------------------------------- subject areas (finance cost centres + students)
# Shared subject areas: HESA cost centres (finance) and CAH level 1 subjects (students, Table 49).
AREAS = [
    ("Medicine, health & psychology", ["101", "102", "103", "104", "105", "106", "107"], ["01", "02", "04"]),
    ("Biosciences, agriculture, vet & sport", ["108", "109", "110", "112"], ["03", "05", "06"]),
    ("Physical & environmental sciences, maths", ["111", "113", "114", "122", "124"], ["07", "09", "26"]),
    ("Engineering & computing", ["115", "116", "117", "118", "119", "120", "121"], ["10", "11"]),
    ("Architecture & built environment", ["123"], ["13"]),
    ("Social sciences & law", ["127", "128", "129", "130", "131", "132"], ["15", "16"]),
    ("Business & management", ["133", "134"], ["17"]),
    ("Education", ["135", "136"], ["22", "23"]),
    ("Arts, humanities & languages", ["125", "126", "137", "138", "139", "140", "141", "142", "143", "144", "145"], ["19", "20", "24", "25"]),
]
CC_A = {c: i for i, (_, ccs, _) in enumerate(AREAS) for c in ccs}
CAH_A = {c: i for i, (_, _, cahs) in enumerate(AREAS) for c in cahs}
subj = subj.reset_index()
subj = subj[subj["Academic year"].isin(yi)]
subj["area"] = subj["cc"].map(CC_A)
SUBJ_FIN = ["total", "ac_staff", "oth_staff", "opex", "dep", "res_inc"]
fa = subj.groupby(["UKPRN", "Academic year", "area"])[SUBJ_FIN].sum(min_count=1)
reporters = set(subj[subj["total"].fillna(0) > 0].groupby(["UKPRN", "Academic year"]).size().index)
stu = pd.read_csv(ROOT / "data" / "students_cah1.csv", dtype={"ukprn": str, "cah1": str})
stu["area"] = stu["cah1"].map(CAH_A)
sa = stu[stu["area"].notna()].groupby(["ukprn", "year", "area"])[["ft", "pt"]].sum()
sa.index = sa.index.set_names(["UKPRN", "Academic year", "area"])
sa.index = sa.index.set_levels(sa.index.levels[2].astype(int), level=2)
fa.index = fa.index.set_levels(fa.index.levels[2].astype(int), level=2)
area = fa.join(sa, how="outer").reset_index()
keep = pd.Series([(u, y) in reporters for u, y in zip(area["UKPRN"], area["Academic year"])], index=area.index)
area = area[keep & area["Academic year"].isin(yi)].copy()
area[["total", "ac_staff", "oth_staff", "opex", "dep", "res_inc", "ft", "pt"]] = \
    area[["total", "ac_staff", "oth_staff", "opex", "dep", "res_inc", "ft", "pt"]].fillna(0)

# Department income and direct cost model (all £000s), per provider-year-area:
#   teaching income = (tuition fees + teaching grant) x area share of student FTE
#   research income = research grants & contracts by cost centre (Table 5) + QR x area share of research grant income
#   other nations: recurrent funding body grants split half by FTE share, half by research share
#   direct cost = academic department spend + research grant spend (207) x area share of research grant income
area["fte"] = area["ft"] + 0.5 * area["pt"]
g = area.groupby(["UKPRN", "Academic year"])
area["fte_sh"] = area["fte"] / g["fte"].transform("sum")
res_tot = g["res_inc"].transform("sum")
spend_sh = area["total"] / g["total"].transform("sum")
area["res_sh"] = (area["res_inc"] / res_tot).where(res_tot > 0, spend_sh)
p = fin.set_index(["UKPRN", "Academic year"]).join(fbg, how="left")
cols = ["country", "inc_fees", "inc_res", "research", "research_as", "research_os", "research_op", "research_dp",
        "research_in", "research_rs", "fb_total", "fb_teach", "fb_tt", "fb_qr", "fb_cap"]
p["country"] = [providers.loc[u, "country"] if u in providers.index else "" for u, _ in p.index]
area = area.join(p[cols], on=["UKPRN", "Academic year"])
for c in cols[1:]:
    area[c] = area[c].fillna(0)
eng = area["country"] == "England"
other_fb = (area["fb_total"] - area["fb_cap"]).clip(lower=0)
area["inc_teach"] = (area["inc_fees"] + area["fb_teach"] + area["fb_tt"]) * area["fte_sh"] + \
    (~eng) * other_fb * 0.5 * area["fte_sh"]
area["inc_resx"] = area["res_inc"] + area["fb_qr"] * area["res_sh"] + (~eng) * other_fb * 0.5 * area["res_sh"]
area["c_as"] = area["ac_staff"] + area["research_as"] * area["res_sh"]
area["c_os"] = area["oth_staff"] + area["research_os"] * area["res_sh"]
area["c_op"] = area["opex"] + (area["research_op"] + area["research_in"] + area["research_rs"]) * area["res_sh"]
area["c_dp"] = area["dep"] + area["research_dp"] * area["res_sh"]
area["c_total"] = area["total"] + area["research"] * area["res_sh"]
area = area[(area["c_total"] > 0) | (area["fte"] > 0)]
SUBJ_COLS = ["inc_teach", "inc_resx", "c_total", "c_as", "c_os", "c_op", "c_dp", "res_inc", "fte"]
subj_out = [[r["UKPRN"], yi[r["Academic year"]], int(r["area"])] + [j(r[c]) for c in SUBJ_COLS]
            for _, r in area.iterrows()]
cc_names = [name for name, _, _ in AREAS]

mg = pd.read_csv(ROOT / "data" / "mission_groups.csv", dtype=str)
groups = {g: sorted(set(x["ukprn"])) for g, x in mg.groupby("group", sort=False)}

used = set(fin["UKPRN"])
out = {
    "meta": {"source": "HESA Finance open data (Tables 1, 5, 6, 8, 9, 14), CC BY 4.0. Last updated May-26.",
             "units": "£000s"},
    "years": years,
    "providers": {u: [p["name"], p["country"], p["region"]] for u, p in providers.iterrows() if u in used},
    "groups": groups,
    "fin_cols": FIN_COLS,
    "fin": fin_out,
    "subj_cols": SUBJ_COLS,
    "areas": cc_names,
    "subj": subj_out,
}
OUT.write_text(json.dumps(out, separators=(",", ":")))
print(f"providers={len(out['providers'])} fin_rows={len(fin_out)} subj_rows={len(subj_out)} "
      f"size={OUT.stat().st_size/1e6:.1f}MB years={years[0]}..{years[-1]}")
