"""Eşleştirme: Set mantığı + ters indeks.
- Aday havuzu: ilanın istediği yeteneklerin indeks kümelerinin birleşimi (her arama O(1)).
- Puan: küme kesişimi (zorunlu & aday). Metin taraması / regex yok."""


def rank(job: dict, index) -> list[dict]:
    zor = frozenset(job["zorunlu"])
    ter = frozenset(job["tercih"])

    pool: set = set()
    for skill in zor | ter:
        pool |= index.skill_index.get(skill, set())

    rows = []
    for cid in pool:
        rec = index.candidates[cid]
        sk = index.skillsets[cid]
        z = zor & sk
        t = ter & sk
        zs = len(z) / len(zor) if zor else 1.0
        ts = len(t) / len(ter) if ter else 0.0
        es = min(rec["deneyim_yil"] / job["min_deneyim"], 1.0) if job["min_deneyim"] else 1.0
        puan = round(100 * (0.70 * zs + 0.20 * ts + 0.10 * es))
        rows.append({
            "id": cid, "ad": rec["ad"], "puan": puan, "deneyim": rec["deneyim_yil"],
            "pozisyon": rec["son_pozisyon"], "durum": rec["durum"],
            "zorunlu_var": len(z), "zorunlu_toplam": len(zor),
            "eksik": sorted(zor - sk), "eslesen": sorted(z | t),
        })
    rows.sort(key=lambda r: (-r["puan"], r["ad"]))
    return rows
