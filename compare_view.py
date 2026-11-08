"""/kiyas: kayıtlı ölçüm sonuçlarını gösterir. /kiyas/calistir: ölçümü ayrı süreçte yeniden çalıştırır
(ayrı süreç, çünkü CPU ölçümü başka isteklerle karışmasın)."""
import subprocess
import sys
from pathlib import Path

from flask import redirect, render_template, request, url_for

import benchmark

_proc = {"p": None}
PHASES = {"1_basvuru": "Başvuru", "2_liste": "İK listesi", "3_inceleme": "Aday inceleme", "4_cv_takip": "CV takibi (yalnız yeşil)"}


def register(app):
    @app.route("/kiyas")
    def compare():
        res = benchmark.load_results()
        running = _proc["p"] is not None and _proc["p"].poll() is None

        def num(name, cast, lo, hi):
            try:
                return min(max(cast(request.args.get(name, benchmark.ENERGY_DEFAULTS[name])), lo), hi)
            except ValueError:
                return benchmark.ENERGY_DEFAULTS[name]

        p = dict(intensity=num("intensity", float, 1, 1500), cpu_watts=num("cpu_watts", float, 1, 400))
        ctx = dict(res=res, running=running, p=p, phases=PHASES)
        if res:
            n = res["params"]["n"]
            ctx["eg"] = benchmark.energy(res["green"], n, **p)
            ctx["ec"] = benchmark.energy(res["classic"], n, **p)
        return render_template("compare.html", **ctx)

    @app.post("/kiyas/calistir")
    def compare_run():
        if _proc["p"] is None or _proc["p"].poll() is not None:
            try:
                n = min(max(int(request.form.get("n", 200)), 20), 1000)
            except ValueError:
                n = 200
            scan = 0.1 if request.form.get("scan") else 0.0
            _proc["p"] = subprocess.Popen(
                [sys.executable, str(Path(__file__).parent / "run_benchmark.py"), "--n", str(n), "--scan-ratio", str(scan)],
                cwd=Path(__file__).parent, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return redirect(url_for("compare"))
