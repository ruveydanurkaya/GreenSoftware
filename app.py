"""Yeşil İşe Alım - Form Tabanlı Sıfır Atık Veri Mimarisi
Çalıştırma:  python app.py
  /         yeşil sistem (form + JSON + Set eşleştirme)
  /klasik   karşılaştırma için klasik sistem (PDF CV yükle + ayrıştır)
"""
import datetime
import re
import uuid
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_file, url_for

import benchmark
import classic
import compare_view
import matcher
import seed
from skills import ALL_SKILLS, TAXONOMY, normalize
from storage import BASE, Store, load_jobs

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STATUS_LABEL = {"yeni": "Yeni", "cv_istendi": "CV istendi", "cv_geldi": "CV geldi", "elendi": "Elendi"}


def parse_application(f):
    errors = []
    ad = f.get("ad", "").strip()
    email = f.get("email", "").strip()
    if len(ad) < 3:
        errors.append("Ad soyad en az 3 karakter olmalı.")
    if not EMAIL.match(email):
        errors.append("Geçerli bir e-posta adresi girin.")

    chosen = {normalize(s) for s in f.getlist("yetenek")} & set(ALL_SKILLS)
    extras = {normalize(x) for x in f.get("diger", "").split(",") if x.strip()}
    extras = {x for x in extras if len(x) <= 30}
    skills = chosen | set(sorted(extras)[:10])
    if not skills:
        errors.append("En az bir yetenek seçin.")

    try:
        deneyim = int(f.get("deneyim_yil", "0"))
        if not 0 <= deneyim <= 50:
            raise ValueError
    except ValueError:
        deneyim = 0
        errors.append("Deneyim yılı 0 ile 50 arasında olmalı.")

    try:
        yil = int(f.get("yil", "0"))
    except ValueError:
        yil = 0

    rec = {
        "id": uuid.uuid4().hex[:8],
        "olusturma": datetime.date.today().isoformat(),
        "ad": ad, "email": email,
        "egitim": {"seviye": f.get("seviye", "Lisans"), "bolum": f.get("bolum", "").strip()[:80],
                   "okul": f.get("okul", "").strip()[:80], "yil": yil},
        "deneyim_yil": deneyim,
        "son_pozisyon": f.get("son_pozisyon", "").strip()[:80],
        "yetenekler": sorted(skills),
        "diller": [d.strip() for d in f.get("diller", "").split(",") if d.strip()][:5],
        "hakkinda": f.get("hakkinda", "").strip()[:300],
        "durum": "yeni",
    }
    return rec, errors


def create_app(data_dir: Path | None = None, demo: bool = True) -> Flask:
    app = Flask(__name__)
    base = Path(data_dir) if data_dir else BASE
    store = Store(base / "yesil")
    jobs = {j["id"]: j for j in load_jobs()}
    app.config.update(STORE=store, JOBS=jobs, CLASSIC=classic.ClassicStore(base / "klasik"))
    app.register_blueprint(classic.bp)

    if demo and not store.candidates:
        seed.seed_store(store, 60)

    app.jinja_env.filters.update(
        etiket=lambda s: s.replace("-", " "),
        bytes=benchmark.fmt_bytes, energy=benchmark.fmt_energy,
        grams=benchmark.fmt_g, secs=benchmark.fmt_s,
        durum=lambda s: STATUS_LABEL.get(s, s),
    )
    pdf_kb = benchmark.typical_pdf_bytes() / 1024

    @app.route("/", methods=["GET", "POST"])
    def apply():
        errors = []
        if request.method == "POST":
            rec, errors = parse_application(request.form)
            if not errors:
                store.add(rec)
                return redirect(url_for("thanks", cid=rec["id"]))
        return render_template("apply.html", taxonomy=TAXONOMY, errors=errors, form=request.form)

    @app.route("/tesekkurler/<cid>")
    def thanks(cid):
        if cid not in store.candidates:
            abort(404)
        return render_template("thanks.html", size=store.size_of(cid), pdf_kb=pdf_kb, cid=cid)

    @app.route("/ik")
    def panel():
        job = jobs.get(request.args.get("ilan", next(iter(jobs)))) or abort(404)
        rows = matcher.rank(job, store)
        ctx = dict(jobs=jobs.values(), job=job, rows=rows[:50], total=len(rows),
                   pool=len(store.candidates), pdf_kb=pdf_kb, payload=0)
        ctx["payload"] = len(render_template("panel.html", **ctx).encode("utf-8"))
        return render_template("panel.html", **ctx)

    @app.route("/ik/aday/<cid>")
    def candidate(cid):
        rec = store.candidates.get(cid) or abort(404)
        job = jobs.get(request.args.get("ilan", ""))
        sk = store.skillsets[cid]
        match = None
        if job:
            match = dict(var=sorted(set(job["zorunlu"]) & sk), eksik=sorted(set(job["zorunlu"]) - sk),
                         tercih=sorted(set(job["tercih"]) & sk))
        return render_template("candidate.html", c=rec, job=job, match=match, size=store.size_of(cid),
                               pdf_kb=pdf_kb, has_cv=store.cv_path(cid).exists())

    @app.post("/ik/aday/<cid>/durum")
    def set_status(cid):
        if cid not in store.candidates:
            abort(404)
        status = request.form.get("durum")
        if status in ("yeni", "cv_istendi", "elendi"):
            store.set_status(cid, status)
        return redirect(url_for("candidate", cid=cid, ilan=request.form.get("ilan", "")))

    @app.route("/cv-yukle/<cid>", methods=["GET", "POST"])
    def upload_cv(cid):
        """Yalnızca 'CV istendi' durumundaki aday özgeçmişini yükler. Ayrıştırma YAPILMAZ, sadece saklanır."""
        rec = store.candidates.get(cid) or abort(404)
        if rec["durum"] not in ("cv_istendi", "cv_geldi"):
            abort(403)
        if request.method == "POST":
            f = request.files.get("cv")
            if f and f.filename.lower().endswith(".pdf"):
                store.save_cv(cid, f.read())
                return redirect(url_for("thanks", cid=cid))
        return render_template("cv_upload.html", c=rec)

    @app.route("/ik/aday/<cid>/cv")
    def download_cv(cid):
        if cid not in store.candidates or not store.cv_path(cid).exists():
            abort(404)
        return send_file(store.cv_path(cid), mimetype="application/pdf")

    compare_view.register(app)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
