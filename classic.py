"""KLASİK (yeşil olmayan) işe alım sistemi: karşılaştırma için ikinci site. Adres: /klasik

Tipik mimari:
  1. Aday CV'sini (PDF) yükler.
  2. Sunucu PDF'i diske yazar ve SENKRON olarak ayrıştırır (metin çıkarma; metin yoksa OCR).
  3. Ayrıştırılan yetenekler küçük bir kayıtta tutulur, eşleştirme tüm kayıtlar üzerinde doğrusal taranır.
  4. İK uzmanı her adayı incelemek için CV dosyasını (PDF) indirir.
"""
import io
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

from flask import (Blueprint, abort, current_app, redirect, render_template, request,
                   send_file, url_for)

from skills import ALIASES, ALL_SKILLS

TOKEN_FREE = r"(?<![\w+#.\-]){}(?![\w+#])"
PATTERNS = {}
for _s in ALL_SKILLS:
    labels = {_s.replace("-", " "), _s}
    labels |= {a for a, target in ALIASES.items() if target == _s}
    PATTERNS[_s] = [re.compile(TOKEN_FREE.format(re.escape(l)), re.IGNORECASE) for l in labels]
EXP = re.compile(r"Toplam deneyim:\s*(\d+)", re.IGNORECASE)


def cpu_now() -> float:
    """Bu süreç + alt süreçler (tesseract/pdftoppm) CPU saniyesi."""
    t = os.times()
    return t.user + t.system + t.children_user + t.children_system


def extract_text(pdf: bytes) -> tuple[str, bool]:
    """(metin, ocr_kullanildi_mi)"""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    if len(text.strip()) >= 40:
        return text, False
    # Metin katmanı yok -> taranmış belge: OCR
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "cv.pdf").write_bytes(pdf)
        subprocess.run(["pdftoppm", "-r", "150", "-png", str(Path(tmp) / "cv.pdf"), str(Path(tmp) / "pg")],
                       check=True, capture_output=True)
        out = []
        for png in sorted(Path(tmp).glob("pg*.png")):
            r = subprocess.run(["tesseract", str(png), "-", "-l", "eng"], capture_output=True, text=True)
            out.append(r.stdout)
    return "\n".join(out), True


def parse_cv(pdf: bytes) -> dict:
    text, ocr = extract_text(pdf)
    skills = [s for s in ALL_SKILLS if any(p.search(text) for p in PATTERNS[s])]  # her yetenek için tam metin taraması
    m = EXP.search(text)
    return {"yetenekler": skills, "deneyim_yil": int(m.group(1)) if m else 0, "ocr": ocr}


def score(job: dict, rec: dict) -> dict:
    sk = rec["yetenekler"]  # LİSTE: üyelik testi O(n)
    z = [s for s in job["zorunlu"] if s in sk]
    t = [s for s in job["tercih"] if s in sk]
    zs = len(z) / len(job["zorunlu"])
    ts = len(t) / max(len(job["tercih"]), 1)
    es = min(rec["deneyim_yil"] / job["min_deneyim"], 1.0) if job["min_deneyim"] else 1.0
    return {"puan": round(100 * (0.7 * zs + 0.2 * ts + 0.1 * es)), "zorunlu_var": len(z),
            "eksik": [s for s in job["zorunlu"] if s not in sk]}


class ClassicStore:
    def __init__(self, base: Path):
        self.base = Path(base)
        self.pdf_dir = self.base / "uploads"
        self.db_dir = self.base / "db"
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.records: list[dict] = []
        self.lock = threading.Lock()
        self.parse_cpu = 0.0
        self.ocr_count = 0
        for p in sorted(self.db_dir.glob("*.json")):
            self.records.append(json.loads(p.read_text("utf-8")))


bp = Blueprint("classic", __name__, url_prefix="/klasik")


def _store() -> ClassicStore:
    return current_app.config["CLASSIC"]


@bp.route("/", methods=["GET", "POST"])
def apply():
    errors = []
    if request.method == "POST":
        ad, email = request.form.get("ad", "").strip(), request.form.get("email", "").strip()
        f = request.files.get("cv")
        if len(ad) < 3 or "@" not in email:
            errors.append("Ad soyad ve e-posta gerekli.")
        if not f or not f.filename.lower().endswith(".pdf"):
            errors.append("PDF özgeçmiş yükleyin.")
        if not errors:
            pdf = f.read()
            st = _store()
            cid = uuid.uuid4().hex[:8]
            c0 = cpu_now()
            parsed = parse_cv(pdf)
            with st.lock:
                st.parse_cpu += cpu_now() - c0
                st.ocr_count += int(parsed["ocr"])
                (st.pdf_dir / f"{cid}.pdf").write_bytes(pdf)
                rec = {"id": cid, "ad": ad, "email": email, "yetenekler": parsed["yetenekler"],
                       "deneyim_yil": parsed["deneyim_yil"], "son_pozisyon": "", "durum": "yeni",
                       "pdf_bayt": len(pdf)}
                (st.db_dir / f"{cid}.json").write_text(json.dumps(rec, ensure_ascii=False, separators=(",", ":")), "utf-8")
                st.records.append(rec)
            return redirect(url_for("classic.thanks", cid=cid))
    return render_template("classic_apply.html", errors=errors)


@bp.route("/tesekkurler/<cid>")
def thanks(cid):
    return render_template("classic_thanks.html", cid=cid)


@bp.route("/ik")
def panel():
    jobs = current_app.config["JOBS"]
    job = jobs.get(request.args.get("ilan", next(iter(jobs)))) or abort(404)
    rows = []
    for rec in _store().records:  # tüm kayıtlar üzerinde doğrusal tarama
        s = score(job, rec)
        rows.append({**s, "id": rec["id"], "ad": rec["ad"], "deneyim": rec["deneyim_yil"], "pdf": rec["pdf_bayt"]})
    rows.sort(key=lambda r: (-r["puan"], r["ad"]))
    return render_template("classic_panel.html", jobs=jobs.values(), job=job, rows=rows[:50], total=len(rows))


@bp.route("/ik/aday/<cid>/cv")
def cv(cid):
    path = _store().pdf_dir / f"{cid}.pdf"
    if not path.exists():
        abort(404)
    return send_file(path, mimetype="application/pdf")
