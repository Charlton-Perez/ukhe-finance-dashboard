# UK HE Pound for Pound

Dashboard showing where each £1 of income goes across UK HE providers, benchmarked against the University of Reading.

**Live dashboard:** https://charlton-perez.github.io/ukhe-finance-dashboard/

Built from public HESA open data (CC BY 4.0). Not an official University of Reading publication.

## Getting the raw data
The raw HESA files (~5GB) are not in the repo. Download them from hesa.ac.uk into `data/raw/`:
- Finance tables: `https://www.hesa.ac.uk/data-and-analysis/finances/table-N` for N = 1, 5, 6, 7, 8, 9, 12, 14 (save as `hesa-fin-table-N.csv`, or unzip `table-N.zip` into `hesa-fin-table-N/`)
- Students: `https://www.hesa.ac.uk/data-and-analysis/students/table-49.zip`, unzipped into `hesa-stu-table-49/`

## Rebuild

```bash
python3 scripts/extract_students.py  # only when Table 49 changes (~5GB raw) -> data/students_cah1.csv
python3 scripts/build_data.py   # data/raw/*.csv -> data/dashboard_data.json
python3 scripts/build_html.py   # -> docs/index.html (GitHub Pages) and dist/dashboard.html (Claude artifact)
```

## Files
- `data/raw/` – HESA Finance open data (Tables 1, 5, 6, 7, 8, 9, 12, 14), CC BY 4.0, downloaded 2026-10-03 (last updated May-26).
- `data/raw/hesa-stu-table-49/` – HESA Student Table 49 (enrolments by provider and CAH subject), downloaded 2026-10-03.
- `data/students_cah1.csv` – extracted student headcounts by provider, CAH level 1 and mode.
- `data/mission_groups.csv` – mission group membership (edit to change groups or the "Reading comparators" peer set).
- `scripts/build_data.py` – cleans and joins the HESA tables.
- `src/dashboard.template.html` – the dashboard (vanilla JS + SVG, no dependencies).

## Category mapping (HESA Table 8 activities)
| Dashboard heading | HESA activity |
|---|---|
| Academic delivery | Academic departments (101–145) + Research grants & contracts (207) |
| Support services | Academic services (201) + General education (203) + Staff & student facilities (204) |
| Management & admin | Central administration & services (202) |
| Estates | Premises (205) |
| Residences & other | Residences & catering (206) + Other expenditure (208, excl. pension cost adjustment) |
| Pension adjustment | Pension cost adjustment (in 208); excluded by default |
| Capital investment | Table 9: Buildings vs Equipment & intangible assets |

## Tabs
1. **Overview** – the five headings per £1 of income, with all peer-group, year and filter options.
2. **Institution detail** – each heading broken into Table 8 activity lines and cost types; research cost recovery; residences and catering net of income (Table 7); whole-institution staff ratios.
3. **Subjects** – nine broad subject areas (cost centres matched to CAH level 1): spend per student FTE, academic staff cost per FTE, other costs per FTE, research income per £1 of departmental spend. FTE = full-time + 0.5 × part-time.
