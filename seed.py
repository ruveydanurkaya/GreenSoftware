"""Demo/benchmark için sentetik aday üretir."""
import datetime
import random
import uuid

PROFILES = {
    "Yazılım Geliştirici": ["python", "sql", "git", "docker", "linux", "javascript", "react", "aws", "problem-cozme"],
    "Veri Analisti": ["sql", "excel", "veri-analizi", "power-bi", "python", "istatistik", "tableau", "iletisim"],
    "Dijital Pazarlama Uzmanı": ["seo", "iletisim", "excel", "figma", "sosyal-medya", "icerik-yazarligi", "veri-analizi"],
    "Satış Temsilcisi": ["satis", "musteri-iliskileri", "iletisim", "excel", "sap", "takim-calismasi"],
    "Muhasebe Uzmanı": ["muhasebe", "sap", "excel", "iletisim", "takim-calismasi"],
}
FIRST = ["Ayşe", "Mehmet", "Zeynep", "Ahmet", "Elif", "Mustafa", "Defne", "Emre", "Selin", "Burak",
         "Deniz", "Can", "Ece", "Kerem", "Merve", "Oğuz", "Pelin", "Yusuf", "İrem", "Tolga"]
LAST = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Aydın", "Öztürk", "Arslan", "Doğan", "Kurt",
        "Koç", "Polat", "Erdem", "Aksoy", "Güneş"]
SCHOOLS = ["Pamukkale Üniversitesi", "Ege Üniversitesi", "ODTÜ", "İTÜ", "Dokuz Eylül Üniversitesi", "Ankara Üniversitesi"]
DEPTS = ["Bilgisayar Mühendisliği", "Endüstri Mühendisliği", "İşletme", "İstatistik", "İletişim Fakültesi", "Ekonomi"]
LEVELS = ["Lisans", "Lisans", "Lisans", "Yüksek Lisans", "Ön Lisans"]
LANGS = ["İngilizce", "Almanca", "Fransızca", "İspanyolca"]


def make_candidate(rng: random.Random, cid: str) -> dict:
    pos = rng.choice(list(PROFILES))
    core = PROFILES[pos]
    skills = {s for s in core if rng.random() < 0.7}
    from skills import ALL_SKILLS
    skills |= set(rng.sample(ALL_SKILLS, rng.randint(0, 3)))
    if not skills:
        skills = {core[0]}
    return {
        "id": cid,
        "olusturma": datetime.date.today().isoformat(),
        "ad": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "email": f"aday{cid}@ornek.com",
        "egitim": {"seviye": rng.choice(LEVELS), "bolum": rng.choice(DEPTS),
                   "okul": rng.choice(SCHOOLS), "yil": rng.randint(2012, 2026)},
        "deneyim_yil": rng.randint(0, 12),
        "son_pozisyon": pos,
        "yetenekler": sorted(skills),
        "diller": rng.sample(LANGS, rng.randint(1, 2)),
        "hakkinda": "Takım çalışmasına yatkın, öğrenmeye açık ve sonuç odaklı biriyim.",
        "durum": "yeni",
    }


def seed_store(store, n: int = 60, seed: int = 7) -> None:
    rng = random.Random(seed)
    for _ in range(n):
        store.add(make_candidate(rng, uuid.uuid4().hex[:8]))


if __name__ == "__main__":
    import sys
    from storage import Store
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    seed_store(Store(), count)
    print(f"{count} demo aday eklendi.")
