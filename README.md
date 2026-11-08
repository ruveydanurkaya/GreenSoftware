# Yeşil İşe Alım: Form Tabanlı Sıfır Atık Veri Mimarisi

İki site, aynı sentetik adaylar, gerçek ölçüm.

- **Yeşil sistem (`/`)**: Aday CV yüklemez, formu doldurur. Veri birkaç yüz baytlık JSON olur, eşleştirme Set mantığıyla yapılır.
  CV yalnızca ilk elemeyi geçen adaydan istenir, ayrıştırılmaz.
- **Klasik sistem (`/klasik`)**: Aday PDF CV yükler. Sunucu PDF'i saklar ve senkron ayrıştırır (metin çıkarma, metin yoksa OCR).
  İK her adayı incelemek için PDF'i indirir.

## Çalıştırma
```
pip install -r requirements.txt     # flask, reportlab, pypdf, pillow, numpy
python app.py                       # http://127.0.0.1:5000
python run_benchmark.py --n 200     # ölçümü terminalden yeniden çalıştır
python run_benchmark.py --n 200 --scan-ratio 0.1   # CV'lerin %10'u taranmış (OCR gerekir)
```
OCR için sistemde `tesseract` ve `pdftoppm` (poppler) kurulu olmalı. Taranmış CV kullanmayacaksanız gerekmez.

## Sayfalar
| Adres | Ne yapar |
|---|---|
| `/` | Yeşil başvuru formu |
| `/ik` | Yeşil İK paneli (Set eşleştirme, ekranın taşıdığı veri) |
| `/ik/aday/<id>` | Aday detayı, "CV iste" / "Ele", gelen CV'yi indirme |
| `/cv-yukle/<id>` | "CV istendi" durumundaki adayın CV yükleme sayfası |
| `/klasik/` | Klasik CV yükleme (PDF) |
| `/klasik/ik` | Klasik İK paneli (tüm kayıtlarda doğrusal tarama, PDF indirme) |
| `/kiyas` | Kayıtlı ölçüm sonuçları, enerji katsayılarını değiştirme, ölçümü yeniden başlatma |

## Ölçüm senaryosu (`run_benchmark.py`)
Her iki sistem de aynı süreçte, boş bir veri klasöründe, aynı `seed.make_candidate` kayıtlarıyla çalışır.
1. n aday başvurur (yeşil: form, klasik: aynı adaydan üretilmiş PDF yükleme + ayrıştırma).
2. İK her ilan için sıralı listeyi açar.
3. İK her adayı `views` kez inceler (yeşil: hafif sayfa, klasik: PDF indirir).
4. Yeşil sistemde en iyi %10 aday CV yükler, İK bunları `views` kez indirir.

Ölçülenler: sunucu CPU saniyesi (alt süreçler dahil), diskteki bayt, yüklenen + indirilen bayt, istek süreleri, ayrıştırma doğruluğu.

## Dürüstlük notu
- **Varsayım olarak kalanlar:** Enerji katsayıları (CPU gücü, şebeke yoğunluğu, ağ 0,06 kWh/GB, depolama 0,006 kWh/GB/yıl). Kaynaklarını sunumdan önce doğrulayın.
- **Sentetik PDF boyutu** `pdfgen.py` üretecine bağlıdır (gömülü font, 500 px fotoğraf, tek sayfa, ort. ~155 KB). Gerçek CV'ler daha küçük veya çok daha büyük olabilir. `--photo-px` ile oynayın.
- **OCR** yalnızca İngilizce modelle çalışır, taranmış CV oranı varsayılan olarak 0'dır.
- Klasik ayrıştırıcı anahtar kelime eşleştirir, bu yüzden bölüm adı gibi bağlamdan yanlış yetenek yakalayabilir (ör. bölüm "İstatistik").
- SCI = ((E x I) + M) / R. Gömülü karbon M dahil değil, R = 1 aday.
- Ölçüm tek makinede alınır, CPU süreleri makineye göre değişir.

## Dosyalar
```
app.py            Flask uygulaması (yeşil + klasik blueprint)
classic.py        klasik sistem (PDF yükle, ayrıştır, doğrusal eşleştir)
skills.py         standart yetenek sözlüğü
storage.py        JSON depolama + ters indeks
matcher.py        Set tabanlı puanlama
pdfgen.py         sentetik CV PDF üreteci
run_benchmark.py  gerçek ölçüm
benchmark.py      enerji/SCI hesabı, biçimlendirme
compare_view.py   /kiyas
seed.py           demo veri
results/benchmark.json   örnek ölçüm (n=200)
```
