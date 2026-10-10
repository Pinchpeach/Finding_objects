#!/usr/bin/env python3
"""Finding Objects — desktop app (draft).

Tkinter front end for the v2 classifier: enter a sky position (or pick a
folder of already-collected catalogs), run, and browse/export the coarse
STAR/GALAXY/QSO classification.  Run:  python v2/app/finding_objects_app.py
"""
from __future__ import annotations
import queue, sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import Job, run_in_background  # noqa: E402


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Finding Objects — v2 classifier (draft)")
        self.geometry("1000x640")
        self.events: queue.Queue = queue.Queue()
        self.result = None
        self._build()
        self.after(100, self._poll)

    def _build(self):
        form = ttk.Frame(self, padding=8); form.pack(fill="x")
        self.vars = {k: tk.StringVar(value=v) for k, v in
                     {"ra": "245.0", "dec": "43.0", "radius": "3", "raw": "", "work": str(Path.home() / "finding_objects_runs" / "run1"), "minconf": ""}.items()}
        fields = [("RA (deg)", "ra"), ("Dec (deg)", "dec"), ("Radius (arcmin)", "radius"),
                  ("Min confidence (optional)", "minconf")]
        for i, (label, key) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=0, column=2 * i, sticky="w")
            ttk.Entry(form, textvariable=self.vars[key], width=12).grid(row=0, column=2 * i + 1, padx=4)
        ttk.Label(form, text="Raw catalog folder (optional, skips download)").grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Entry(form, textvariable=self.vars["raw"], width=50).grid(row=1, column=2, columnspan=4, sticky="we")
        ttk.Button(form, text="Browse…", command=lambda: self._pick("raw")).grid(row=1, column=6)
        ttk.Label(form, text="Output folder").grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Entry(form, textvariable=self.vars["work"], width=50).grid(row=2, column=2, columnspan=4, sticky="we")
        ttk.Button(form, text="Browse…", command=lambda: self._pick("work")).grid(row=2, column=6)
        self.run_btn = ttk.Button(form, text="Run", command=self._run); self.run_btn.grid(row=0, column=8, rowspan=2, padx=8)
        ttk.Button(form, text="Export CSV", command=self._export).grid(row=2, column=8, padx=8)

        bar = ttk.Frame(self, padding=(8, 0)); bar.pack(fill="x")
        ttk.Label(bar, text="Show class:").pack(side="left")
        self.filter = tk.StringVar(value="ALL")
        for c in ("ALL", "STAR", "GALAXY", "QSO", "UNKNOWN"):
            ttk.Radiobutton(bar, text=c, value=c, variable=self.filter, command=self._fill).pack(side="left")
        self.counts = ttk.Label(bar, text=""); self.counts.pack(side="right")

        panes = ttk.PanedWindow(self, orient="vertical"); panes.pack(fill="both", expand=True, padx=8, pady=8)
        self.table = ttk.Treeview(panes, show="headings"); panes.add(self.table, weight=3)
        self.log = tk.Text(panes, height=8); panes.add(self.log, weight=1)

    def _pick(self, key):
        path = filedialog.askdirectory()
        if path:
            self.vars[key].set(path)

    def _job(self) -> Job:
        f = lambda k: float(self.vars[k].get()) if self.vars[k].get().strip() else None
        raw = self.vars["raw"].get().strip()
        job = Job(work=Path(self.vars["work"].get()), raw_dir=Path(raw) if raw else None, min_confidence=f("minconf"))
        if job.raw_dir is None:
            job.ra, job.dec, job.radius_arcmin = f("ra"), f("dec"), f("radius")
            if None in (job.ra, job.dec, job.radius_arcmin) or job.radius_arcmin <= 0:
                raise ValueError("RA, Dec and a positive radius are required (or choose a raw catalog folder).")
        return job

    def _run(self):
        try:
            job = self._job()
        except ValueError as exc:
            messagebox.showerror("Input", str(exc)); return
        self.run_btn.state(["disabled"]); self.log.delete("1.0", "end")
        run_in_background(job, log=lambda m: self.events.put(("log", m)),
                          on_done=lambda df: self.events.put(("done", df)),
                          on_error=lambda e, tb: self.events.put(("error", tb)))

    def _poll(self):
        # Worker threads never touch Tk widgets; results arrive via the queue.
        while not self.events.empty():
            kind, payload = self.events.get()
            if kind == "log":
                self.log.insert("end", f"{payload}\n"); self.log.see("end")
            elif kind == "done":
                self.result = payload; self._fill(); self.run_btn.state(["!disabled"])
            elif kind == "error":
                self.log.insert("end", payload); self.run_btn.state(["!disabled"])
                messagebox.showerror("Run failed", payload.splitlines()[-1])
        self.after(100, self._poll)

    def _fill(self):
        if self.result is None:
            return
        df = self.result
        if self.filter.get() != "ALL":
            df = df[df.primary_class.eq(self.filter.get())]
        self.table.delete(*self.table.get_children())
        self.table["columns"] = list(df.columns)
        for c in df.columns:
            self.table.heading(c, text=c); self.table.column(c, width=110, anchor="w")
        for row in df.head(5000).itertuples(index=False):
            self.table.insert("", "end", values=[f"{v:.3f}" if isinstance(v, float) else v for v in row])
        self.counts.config(text=" · ".join(f"{k}: {v}" for k, v in self.result.primary_class.value_counts().items()))

    def _export(self):
        if self.result is None:
            messagebox.showinfo("Export", "Run a classification first."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            self.result.to_csv(path, index=False)


if __name__ == "__main__":
    App().mainloop()
