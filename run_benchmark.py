"""İki sistemi AYNI sentetik adaylarla gerçekten çalıştırıp ölçer.

  python run_benchmark.py --n 200
  python run_benchmark.py --n 200 --scan-ratio 0.1     # CV'lerin %10'u taranmış (OCR gerekir)

Senaryo (her iki sistemde aynı):
  1. n aday başvurur.                        (yeşil: form POST | klasik: PDF yükleme + ayrıştırma)
  2. İK her ilan için sıralı listeyi açar.
  3. İK her adayı `views` kez inceler.        (yeşil: hafif sayfa | klasik: CV PDF'ini indirir)
  4. Yeşil sistemde ilk elemeyi geçenler (en iyi %shortlist) CV yükler, İK `views` kez indirir.
     (Klasik sistemde zaten herkesin CV'si var.)

Ölçülenler: sunucu CPU saniyesi (alt süreçler dahil), diskte kalan bayt, yüklenen + indirilen bayt, istek süresi.
Ölçülmeyen/varsayılan: enerji katsayıları (benchmark.py).
"""
import argparse
import json
import math
import platform
import random
import statistics
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import matcher
import pdfgen
from app import create_app
from benchmark import RESULTS
from classic import cpu_now
from seed import make_candidate


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file())


class Meter:
    """Faz bazında CPU, bayt, süre toplar."""

    def __init__(self):
        self.phases = {}

    def call(self, phase, fn, up=0):
        ph = self.phases.setdefault(phase, dict(cpu_s=0.0, up=0, down=0, wall=[], requests=0))
        c0, w0 = cpu_now(), time.perf_counter()
        resp = fn()
        ph["cpu_s"] += cpu_now() - c0
        ph["wall"].append(time.perf_counter() - w0)
        ph["up"] += up
        ph["down"] += len(resp.get_data())
        ph["requests"] += 1
        return resp

    def summary(self):
        out = {}
        for k, v in self.phases.items():
            out[k] = dict(cpu_s=v["cpu_s"], up=v["up"], down=v["down"], requests=v["requests"],
                          wall_mean_ms=1000 * statistics.mean(v["wall"]),
                          wall_p95_ms=1000 * sorted(v["wall"])[int(0.95 * (len(v["wall"]) - 1))])
        return out


def run(n=200, shortlist=0.10, views=3, scan_ratio=0.0, photo_px=500, log=print) -> dict:
    rng = random.Random(42)
    records = [make_candidate(rng, f"b{i:05d}") for i in range(n)]
    scan_idx = set(rng.sample(range(n), int(n * scan_ratio)))

    log(f"{n} sentetik CV (PDF) üretiliyor...")
    pdfs = [pdfgen.make_scan_pdf(r, rng) if i in scan_idx else pdfgen.make_text_pdf(r, rng, photo_px)
            for i, r in enumerate(records)]
    avg_pdf = statistics.mean(len(p) for p in pdfs)

    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Path(tmp), demo=False)
        client = app.test_client()
        jobs = list(app.config["JOBS"].values())
        store = app.config["STORE"]
        classic_store = app.config["CLASSIC"]

        # ================= YEŞİL =================
        g = Meter()
        log("Yeşil sistem: başvurular...")
        g_ids = []
        for r in records:
            form = {"ad": r["ad"], "email": r["email"], "seviye": r["egitim"]["seviye"], "bolum": r["egitim"]["bolum"],
                    "okul": r["egitim"]["okul"], "yil": r["egitim"]["yil"], "deneyim_yil": r["deneyim_yil"],
                    "son_pozisyon": r["son_pozisyon"], "diller": ", ".join(r["diller"]), "hakkinda": r["hakkinda"],
                    "yetenek": r["yetenekler"]}
            resp = g.call("1_basvuru", lambda: client.post("/", data=form), up=len(urlencode(form, doseq=True)))
            loc = resp.headers["Location"]
            g_ids.append(loc.rsplit("/", 1)[1])
            g.call("1_basvuru", lambda: client.get(loc))  # teşekkür sayfası
        acc_g = statistics.mean(
            len(set(store.candidates[cid]["yetenekler"]) & set(r["yetenekler"])) / len(set(r["yetenekler"]) | set(store.candidates[cid]["yetenekler"]))
            for cid, r in zip(g_ids, records))

        log("Yeşil sistem: İK listeleri ve inceleme...")
        for j in jobs:
            g.call("2_liste", lambda: client.get(f"/ik?ilan={j['id']}"))
        for cid in g_ids:
            for _ in range(views):
                g.call("3_inceleme", lambda: client.get(f"/ik/aday/{cid}"))

        k = max(1, math.ceil(shortlist * n / len(jobs)))
        short = []
        for j in jobs:
            for row in matcher.rank(j, store)[:k]:
                if row["id"] not in short:
                    short.append(row["id"])
        short = short[: max(1, int(shortlist * n))]
        id_to_i = {cid: i for i, cid in enumerate(g_ids)}
        for cid in short:
            g.call("4_cv_takip", lambda: client.post(f"/ik/aday/{cid}/durum", data={"durum": "cv_istendi"}), up=20)
            pdf = pdfs[id_to_i[cid]]
            g.call("4_cv_takip", lambda: client.post(f"/cv-yukle/{cid}", data={"cv": (__import__("io").BytesIO(pdf), "cv.pdf")},
                                                      content_type="multipart/form-data"), up=len(pdf))
            for _ in range(views):
                g.call("4_cv_takip", lambda: client.get(f"/ik/aday/{cid}/cv"))
        green_storage = dir_size(Path(tmp) / "yesil")
        green_json = dir_size(Path(tmp) / "yesil" / "adaylar")

        # ================= KLASİK =================
        c = Meter()
        log("Klasik sistem: PDF yükleme ve ayrıştırma (OCR dahil)...")
        c_ids = []
        for r, pdf in zip(records, pdfs):
            data = {"ad": r["ad"], "email": r["email"], "cv": (__import__("io").BytesIO(pdf), "cv.pdf")}
            resp = c.call("1_basvuru", lambda: client.post("/klasik/", data=data, content_type="multipart/form-data"),
                          up=len(pdf) + len(r["ad"]) + len(r["email"]))
            loc = resp.headers["Location"]
            c_ids.append(loc.rsplit("/", 1)[1])
            c.call("1_basvuru", lambda: client.get(loc))
        parse_cpu, ocr_count = classic_store.parse_cpu, classic_store.ocr_count
        by_id = {rec["id"]: rec for rec in classic_store.records}
        acc_c = statistics.mean(
            len(set(by_id[cid]["yetenekler"]) & set(r["yetenekler"])) / len(set(r["yetenekler"]) | set(by_id[cid]["yetenekler"]))
            for cid, r in zip(c_ids, records))

        log("Klasik sistem: İK listeleri ve CV indirme...")
        for j in jobs:
            c.call("2_liste", lambda: client.get(f"/klasik/ik?ilan={j['id']}"))
        for cid in c_ids:
            for _ in range(views):
                c.call("3_inceleme", lambda: client.get(f"/klasik/ik/aday/{cid}/cv"))
        classic_storage = dir_size(Path(tmp) / "klasik")

    def totals(meter, stored):
        s = meter.summary()
        return dict(phases=s, cpu_s=sum(v["cpu_s"] for v in s.values()), stored=stored,
                    transferred=sum(v["up"] + v["down"] for v in s.values()),
                    requests=sum(v["requests"] for v in s.values()))

    res = dict(
        created=datetime.now().isoformat(timespec="seconds"),
        machine=f"{platform.system()} {platform.machine()}, Python {platform.python_version()}",
        params=dict(n=n, shortlist=shortlist, views=views, scan_ratio=scan_ratio, photo_px=photo_px),
        n_jobs=len(jobs), n_shortlist=len(short),
        avg_pdf_bytes=avg_pdf, avg_json_bytes=green_json / n,
        green={**totals(g, green_storage), "accuracy": acc_g},
        classic={**totals(c, classic_storage), "accuracy": acc_c, "parse_cpu_s": parse_cpu, "ocr_count": ocr_count},
    )
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--shortlist", type=float, default=0.10)
    ap.add_argument("--views", type=int, default=3)
    ap.add_argument("--scan-ratio", type=float, default=0.0)
    ap.add_argument("--photo-px", type=int, default=500)
    a = ap.parse_args()
    res = run(a.n, a.shortlist, a.views, a.scan_ratio, a.photo_px)
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps(res, ensure_ascii=False, indent=1), "utf-8")
    print(f"Yazıldı: {RESULTS}")
    for name in ("green", "classic"):
        s = res[name]
        print(f"{name:8s} CPU {s['cpu_s']:.2f} sn | depolama {s['stored']:,} B | aktarım {s['transferred']:,} B | doğruluk {s['accuracy']:.3f}")
