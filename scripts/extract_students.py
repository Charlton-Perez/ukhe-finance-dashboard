"""Extract HE student enrolments by provider, CAH level 1 subject and mode (HESA Table 49).

Output: data/students_cah1.csv  (ukprn, year, cah1, ft, pt) - headcounts, all levels of study.
The raw files are ~5GB, so this is cached separately from build_data.py.
"""
import glob
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
rows = []
for f in sorted(glob.glob(str(ROOT / "data" / "raw" / "hesa-stu-table-49" / "*.csv"))):
    for ch in pd.read_csv(f, skiprows=13, dtype=str, chunksize=2_000_000,
                          usecols=["UKPRN", "Level of study", "Mode of study", "Country of HE provider",
                                   "Region of HE provider", "CAH level subject", "Academic Year", "Number"]):
        ch = ch[(ch["Level of study"] == "All") & (ch["Country of HE provider"] == "All")
                & (ch["Region of HE provider"] == "All") & ch["Mode of study"].isin(["Full-time", "Part-time"])]
        cah1 = ch["CAH level subject"].str.extract(r"^(\d{2}) [A-Za-z]")[0]
        ch = ch.assign(cah1=cah1, n=pd.to_numeric(ch["Number"].str.replace(",", ""), errors="coerce"))
        rows.append(ch[ch["cah1"].notna()][["UKPRN", "Academic Year", "cah1", "Mode of study", "n"]])
    print("done", Path(f).name, flush=True)

d = pd.concat(rows)
out = d.pivot_table(index=["UKPRN", "Academic Year", "cah1"], columns="Mode of study", values="n", aggfunc="sum").fillna(0)
out = out.rename(columns={"Full-time": "ft", "Part-time": "pt"}).reset_index()
out.columns = ["ukprn", "year", "cah1", "ft", "pt"]
out = out[(out["ft"] + out["pt"]) > 0]
out.to_csv(ROOT / "data" / "students_cah1.csv", index=False)
print(len(out), "rows")
