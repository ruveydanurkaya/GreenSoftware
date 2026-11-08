"""Standart yetenek sözlüğü (taxonomy).
Aday serbest metin yazmaz, listeden seçer -> veri baştan temiz gelir, ayrıştırma (parsing) gerekmez."""

TAXONOMY = {
    "Yazılım": ["python", "java", "javascript", "typescript", "c#", "c++", "sql",
                "react", "node.js", "git", "docker", "kubernetes", "linux", "aws",
                "makine-ogrenmesi"],
    "Veri ve analiz": ["excel", "power-bi", "veri-analizi", "istatistik", "tableau"],
    "Tasarım ve pazarlama": ["figma", "seo", "icerik-yazarligi", "sosyal-medya", "grafik-tasarim"],
    "İş ve yönetim": ["proje-yonetimi", "muhasebe", "sap", "satis", "musteri-iliskileri"],
    "Ortak yetkinlikler": ["iletisim", "takim-calismasi", "problem-cozme"],
}

ALL_SKILLS = [s for group in TAXONOMY.values() for s in group]

ALIASES = {
    "js": "javascript", "ts": "typescript", "nodejs": "node.js", "node": "node.js",
    "k8s": "kubernetes", "ml": "makine-ogrenmesi", "csharp": "c#", "cpp": "c++",
    "powerbi": "power-bi", "python3": "python", "postgres": "sql", "mysql": "sql",
}


def normalize(skill: str) -> str:
    s = skill.strip().replace("İ", "i").lower().replace(" ", "-")
    return ALIASES.get(s, s)
