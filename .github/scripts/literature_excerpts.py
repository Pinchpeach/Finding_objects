#!/usr/bin/env python3
"""Print the lines of arXiv papers that match regex patterns (literature checks).

The cloud session cannot reach arXiv; this runs on GitHub Actions and the
excerpts are read from the job log.  Only short matched passages are printed
(2 lines of context, at most MAX_HITS per pattern); no paper text is stored.

    python .github/scripts/literature_excerpts.py SPEC.json
SPEC: {"arXiv id": ["regex", ...], ...}
"""
import json
import random
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_HITS = 6
UA = {"User-Agent": "Finding_objects literature check (GitHub Actions)"}


def get(url):
    time.sleep(random.uniform(3, 5))  # arXiv asks for >= 3 s between requests
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def meta(aid):
    x = ET.fromstring(get(f"https://export.arxiv.org/api/query?id_list={aid}"))
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    e = x.find("a:entry", ns)
    if e is None:
        return "no metadata"
    title = " ".join((e.findtext("a:title", "", ns) or "").split())
    authors = [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)]
    jref = e.findtext("x:journal_ref", "", ns) or "-"
    doi = e.findtext("x:doi", "", ns) or "-"
    year = (e.findtext("a:published", "", ns) or "")[:4]
    au = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
    return f"{au} ({year}) {title} | journal_ref: {jref} | doi: {doi}"


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    for aid, pats in spec.items():
        print(f"\n######## arXiv:{aid}")
        try:
            print("META:", meta(aid))
            pdf = get(f"https://export.arxiv.org/pdf/{aid}")
        except Exception as exc:  # keep going: one failure must not hide the others
            print("FETCH FAILED:", exc)
            continue
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "p.pdf"
            p.write_bytes(pdf)
            subprocess.run(["pdftotext", "-layout", str(p), str(Path(d) / "p.txt")], check=False)
            t = (Path(d) / "p.txt").read_text(errors="ignore") if (Path(d) / "p.txt").exists() else ""
        lines = [" ".join(x.split()) for x in t.splitlines()]
        print(f"text lines: {len(lines)}")
        for pat in pats:
            rx = re.compile(pat, re.I)
            hits = [i for i, x in enumerate(lines) if rx.search(x)]
            print(f"--- /{pat}/ : {len(hits)} hits")
            for i in hits[:MAX_HITS]:
                ctx = " ⏎ ".join(x for x in lines[max(0, i - 2) : i + 3] if x)
                print(f"  L{i}: {ctx[:600]}")


if __name__ == "__main__":
    main()
