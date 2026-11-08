"""Sentetik CV PDF'leri üretir (yalnızca KARŞILAŞTIRMA için; klasik sistemin girdisi).
Gerçek bir CV gibi: gömülü font, profil fotoğrafı, çok paragraflı anlatı.
Aynı aday kaydından (seed.make_candidate) üretildiği için iki sistem birebir aynı veriyi işler."""
import io
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("CVSans", FONT_DIR + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("CVSans-Bold", FONT_DIR + "DejaVuSans-Bold.ttf"))

FILLER = [
    "Kurumsal projelerde görev alarak ekip içi koordinasyonu sağladım ve süreçleri iyileştirdim.",
    "Haftalık raporlama sürecini otomatikleştirerek zamandan tasarruf sağladım.",
    "Yeni başlayan ekip arkadaşlarına eğitim verdim ve dokümantasyon hazırladım.",
    "Müşteri geri bildirimlerini analiz ederek ürün geliştirme önceliklerine katkı sundum.",
    "Birden fazla paydaşla çalışarak teslim tarihlerine uygun çıktılar ürettim.",
    "Departmanlar arası toplantılara katılarak ortak hedeflerin belirlenmesine destek oldum.",
]


def skill_label(slug: str) -> str:
    return slug.replace("-", " ")


def cv_lines(rec: dict, rng: random.Random, paragraphs: int = 14) -> list[tuple[str, str]]:
    """(bölüm başlığı, metin) listesi. Yetenekler okunabilir etiketlerle yazılır."""
    e = rec["egitim"]
    out = [
        ("Özgeçmiş", f"{rec['ad']} · {rec['email']}"),
        ("Eğitim", f"{e['seviye']}, {e['bolum']}, {e['okul']} ({e['yil']})"),
        ("Deneyim", f"Toplam deneyim: {rec['deneyim_yil']} yıl. Son pozisyon: {rec['son_pozisyon']}."),
        ("Yetenekler", ", ".join(skill_label(s) for s in rec["yetenekler"])),
        ("Diller", ", ".join(rec["diller"])),
        ("Hakkımda", rec["hakkinda"]),
    ]
    out.append(("İş deneyimi ayrıntıları", " ".join(rng.choice(FILLER) for _ in range(paragraphs))))
    return out


def _photo(px: int, rng: random.Random) -> bytes:
    """Gradyan + gürültü: gerçek fotoğrafa benzer sıkıştırma davranışı."""
    nrng = np.random.default_rng(rng.randint(0, 2**31))
    y, x = np.mgrid[0:px, 0:px]
    base = np.stack([(x / px) * 200, (y / px) * 180, ((x + y) / (2 * px)) * 220], axis=-1)
    img = np.clip(base + nrng.normal(0, 14, base.shape), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, "JPEG", quality=88)
    return buf.getvalue()


def make_text_pdf(rec: dict, rng: random.Random, photo_px: int = 500) -> bytes:
    """Metin katmanlı PDF (çoğu modern CV böyle)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    h = ParagraphStyle("h", fontName="CVSans-Bold", fontSize=13, spaceBefore=10, spaceAfter=3)
    b = ParagraphStyle("b", fontName="CVSans", fontSize=10.5, leading=15)
    flow = []
    lines = cv_lines(rec, rng)
    head = Paragraph(f"<font name='CVSans-Bold' size='20'>{rec['ad']}</font><br/>{rec['email']}", b)
    photo = RLImage(io.BytesIO(_photo(photo_px, rng)), width=3.5 * cm, height=3.5 * cm)
    flow.append(Table([[head, photo]], colWidths=[13 * cm, 4 * cm]))
    flow.append(Spacer(1, 10))
    for title, text in lines[1:]:
        flow += [Paragraph(title, h), Paragraph(text, b)]
    doc.build(flow)
    return buf.getvalue()


def make_scan_pdf(rec: dict, rng: random.Random) -> bytes:
    """Metin katmanı OLMAYAN (taranmış) PDF: sayfa bir görüntü, ayrıştırma için OCR gerekir."""
    W, H = 1240, 1754  # A4 ~150 dpi
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    f_b = ImageFont.truetype(FONT_DIR + "DejaVuSans-Bold.ttf", 30)
    f = ImageFont.truetype(FONT_DIR + "DejaVuSans.ttf", 24)
    y = 80
    d.text((80, y), rec["ad"], font=f_b, fill=0)
    y += 50
    for title, text in cv_lines(rec, rng, paragraphs=6)[1:]:
        d.text((80, y), title, font=f_b, fill=0)
        y += 44
        words, line = text.split(), ""
        for w in words:
            if d.textlength(line + " " + w, font=f) > W - 160:
                d.text((80, y), line, font=f, fill=0)
                y += 34
                line = w
            else:
                line = (line + " " + w).strip()
        d.text((80, y), line, font=f, fill=0)
        y += 56
    arr = np.asarray(img).astype("int16") + np.random.default_rng(rng.randint(0, 2**31)).normal(0, 6, (H, W)).astype("int16")
    img = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
    jpg = io.BytesIO()
    img.save(jpg, "JPEG", quality=80)
    jpg.seek(0)
    buf = io.BytesIO()
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(buf, pagesize=A4)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(jpg), 0, 0, width=A4[0], height=A4[1])
    c.save()
    return buf.getvalue()
