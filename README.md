# UK HE Pound for Pound

Dashboard showing where each £1 of income goes across UK HE providers, benchmarked against the University of Reading.

**Live dashboard:** https://charlton-perez.github.io/ukhe-finance-dashboard/

Built from public HESA open data (CC BY 4.0). Not an official University of Reading publication.

## Getting the raw data
The raw HESA files (~1GB) are not in the repo. Download them from hesa.ac.uk into `data/raw/`:
- Finance tables: `https://www.hesa.ac.uk/data-and-analysis/finances/table-N` for N = 1, 6, 7, 8, 9, 14 (save as `hesa-fin-table-N.csv`, or unzip `table-N.zip` into `hesa-fin-table-N/`)

## Rebuild

```bash
python3 scripts/build_data.py   # data/raw/*.csv -> data/dashboard_data.json
python3 scripts/build_html.py   # -> docs/index.html (GitHub Pages) and dist/dashboard.html (Claude artifact)
```

## Files
- `data/raw/` – HESA Finance open data (Tables 1, 6, 7, 8, 9, 14), CC BY 4.0, downloaded 2026-10-03 (last updated May-26).
- `data/mission_groups.csv` – mission group membership (edit to change groups or the "Reading comparators" peer set).
- `scripts/build_data.py` – cleans and joins the HESA tables.
- `src/dashboard.template.html` – the dashboard (vanilla JS + SVG, no dependencies).

## Spending categories (HESA Table 8 activities)
| Dashboard category | HESA activity |
|---|---|
| Academic departments | Cost centres 101–145 |
| Research grants & contracts | 207 |
| Academic services | 201 (library, central IT, learning resources) |
| Student support & facilities | 203 general education (bursaries, scholarships, exams) + 204 staff & student facilities |
| Central administration | 202 |
| Premises | 205 |
| Residences & catering | 206 |
| Other expenditure | 208, excluding the pension cost adjustment |
| Pension adjustment | Pension cost adjustment (in 208); excluded by default |
| Capital investment | Table 9: buildings vs equipment & intangible assets |

## Default comparison set
Providers with income ≥ £100m that are publicly funded (funding council grants ≥ 1% of income), which leaves about 112 providers in 2024/25. Both filters can be changed on the page.

## Tabs
1. **Overview** – the eight HESA activities per £1 of income, with all peer-group, year and filter options.
2. **Institution detail** – each activity broken into Table 8 activity lines and cost types; research cost recovery; residences and catering net of income (Table 7); whole-institution staff ratios.

Subject-level analysis was trialled and removed: HESA doesn't publish income by subject, so per-subject efficiency relied on modelled income and was judged too uncertain to share.
