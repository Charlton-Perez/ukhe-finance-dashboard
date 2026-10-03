"""Inline data/dashboard_data.json into the dashboard template.

Writes:
  dist/dashboard.html - body-only page for the Claude artifact (the host adds the document skeleton)
  docs/index.html     - standalone page for GitHub Pages
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tpl = (ROOT / "src" / "dashboard.template.html").read_text()
data = (ROOT / "data" / "dashboard_data.json").read_text().replace("</", "<\\/")
body = tpl.replace("__DATA__", data, 1)

dist = ROOT / "dist" / "dashboard.html"
dist.parent.mkdir(exist_ok=True)
dist.write_text(body)

# Standalone page: add the skeleton the artifact host would normally provide
head, sep, rest = body.partition("</style>")
standalone = (
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    "<style>html{color-scheme:light}body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
    + head + sep + "\n</head>\n<body>\n" + rest + "\n</body>\n</html>\n"
)
docs = ROOT / "docs" / "index.html"
docs.parent.mkdir(exist_ok=True)
docs.write_text(standalone)
for p in (dist, docs):
    print(f"wrote {p} ({p.stat().st_size / 1e6:.1f} MB)")
