"""Kıyas yardımcıları: ölçüm sonuçlarını okuma, enerji/karbon hesabı, biçimlendirme.

Ölçümü run_benchmark.py yapar (iki sistemi AYNI sentetik adaylarla gerçekten çalıştırır).
Burada kalan TEK varsayım grubu enerji katsayılarıdır; ölçülen CPU saniyesi ve bayt sayıları bunlarla enerjiye çevrilir.

SCI = ((E x I) + M) / R   (Green Software Foundation). M (gömülü karbon) hariç, R = 1 aday.
"""
import json
from pathlib import Path

RESULTS = Path(__file__).parent / "results" / "benchmark.json"

ENERGY_DEFAULTS = dict(
    intensity=450.0,   # şebeke karbon yoğunluğu gCO2e/kWh [varsayım, bölgeye göre değişir]
    cpu_watts=20.0,    # CPU'nun ortalama gücü (W) [varsayım]
)
NETWORK_KWH_PER_GB = 0.06         # [kaba literatür değeri, varsayım]
STORAGE_KWH_PER_GB_YEAR = 0.006   # 1 yıl saklama [kaba değer, varsayım]


def load_results() -> dict | None:
    if RESULTS.exists():
        return json.loads(RESULTS.read_text("utf-8"))
    return None


def typical_pdf_bytes() -> float:
    r = load_results()
    return r["avg_pdf_bytes"] if r else 155 * 1024


def energy(system: dict, n: int, intensity: float, cpu_watts: float) -> dict:
    """system: ölçülen toplamlar (cpu_s, stored, transferred)."""
    cpu = system["cpu_s"] * cpu_watts / 3600 / 1000
    net = system["transferred"] / 1e9 * NETWORK_KWH_PER_GB
    sto = system["stored"] / 1e9 * STORAGE_KWH_PER_GB_YEAR
    kwh = cpu + net + sto
    g = kwh * intensity
    return dict(kwh_cpu=cpu, kwh_net=net, kwh_sto=sto, kwh=kwh, g=g, sci=g / n)


# ---- Biçimlendirme (şablon filtreleri) ----
def fmt_bytes(b: float) -> str:
    for unit, div in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if b >= div:
            return f"{b / div:,.1f} {unit}".replace(",", " ")
    return f"{b:,.0f} B".replace(",", " ")


def fmt_energy(kwh: float) -> str:
    wh = kwh * 1000
    if wh >= 1:
        return f"{wh:.2f} Wh"
    if wh * 1000 >= 1:
        return f"{wh * 1000:.2f} mWh"
    return f"{wh * 1e6:.2f} µWh"


def fmt_g(g: float) -> str:
    if g >= 1:
        return f"{g:.2f} g"
    if g * 1000 >= 1:
        return f"{g * 1000:.2f} mg"
    return f"{g * 1e6:.2f} µg"


def fmt_s(s: float) -> str:
    return f"{s:.2f} sn" if s >= 0.1 else f"{s * 1000:.1f} ms"
