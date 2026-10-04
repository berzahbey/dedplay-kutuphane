"""0.5.12 gerileme testi: OCR önbelleği (Surya taklit edilir; gerçek model yüklenmez, hızlıdır)."""
import os, sys, tempfile, types, glob, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kutuphane import kaynak as S

kalan = []


def dene(ad, kosul):
    print(("GECTI " if kosul else "KALDI ") + ad)
    if not kosul:
        kalan.append(ad)


import fitz
gecici = tempfile.mkdtemp()
pdf = os.path.join(gecici, "deneme.pdf")
d = fitz.open()
for k in range(3):
    d.new_page(width=400, height=600)
d.save(pdf)

SATIRLAR = {0: [("<b>BİRİNCİ BÖLÜM</b>", (300, 200, 800, 240)), ("Bu sayfa birinci sayfadır ve metin burada.", (100, 300, 1000, 330))],
            1: [("İkinci sayfanın metni, devam ediyor ki", (100, 300, 1000, 330))],
            2: [("Üçüncü sayfa.", (100, 300, 600, 330))]}
cagri = []


def sahte_rec(resimler, det_predictor=None, **k):
    sonuc = []
    for _ in resimler:
        i = SIRA.pop(0)
        sonuc.append(types.SimpleNamespace(text_lines=[types.SimpleNamespace(text=t, bbox=b) for t, b in SATIRLAR[i]]))
    cagri.append(len(resimler))
    return sonuc


S._surya_hazir = lambda: (sahte_rec, object())
os.environ["OCR_ONBELLEK"] = os.path.join(gecici, "onbellek")

SIRA = [0, 1, 2]
ilk = S._surya_sayfalar(pdf, [0, 1, 2])
dene("İlk okumada Surya çağrılır", sum(cagri) == 3)
dosyalar = sorted(glob.glob(os.path.join(gecici, "onbellek", "*", "s*.json")))
dene("Her sayfa için önbellek dosyası yazılır", len(dosyalar) == 3)
dene("Kaynak adı not edilir", bool(glob.glob(os.path.join(gecici, "onbellek", "*", "kaynak.txt"))))

cagri.clear()
mesajlar = []
ikinci = S._surya_sayfalar(pdf, [0, 1, 2], mesajlar.append)
dene("İkinci okumada Surya hiç çağrılmaz", not cagri)
dene("Önbellekten okunan sonuç aynıdır", ikinci == ilk)
dene("İlerleme mesajı önbelleği söyler", any("önbellekten: 3/3" in m for m in mesajlar))

# bozuk dosya: yalnız o sayfa yeniden okunur
open(dosyalar[1], "w").write("{bozuk")
cagri.clear(); SIRA = [1]
ucuncu = S._surya_sayfalar(pdf, [0, 1, 2])
dene("Bozuk önbellek dosyası yeniden okunur (yalnız o sayfa)", cagri == [1] and ucuncu == ilk)

# Surya sürümü değişince eski kayıt kullanılmaz
eski = S._surya_anahtari
S._surya_anahtari = lambda: "surya-9.9-dpi200"
cagri.clear(); SIRA = [0, 1, 2]
S._surya_sayfalar(pdf, [0, 1, 2])
dene("Sürüm değişince önbellek kullanılmaz", sum(cagri) == 3)
S._surya_anahtari = eski

# farklı içerikli dosya (aynı ad) önbelleği paylaşmaz
d2 = fitz.open(); d2.new_page(width=401, height=600); d2.save(pdf + ".2")
dene("Farklı içerik farklı klasör", S._ocr_onbellek_klasoru(pdf) != S._ocr_onbellek_klasoru(pdf + ".2"))

# kapalı: hiç dosya yazılmaz
os.environ["OCR_ONBELLEK"] = "0"
cagri.clear(); SIRA = [0]
S._surya_sayfalar(pdf, [0])
dene("OCR_ONBELLEK=0 iken Surya çağrılır", cagri == [1])
dene("OCR_ONBELLEK=0 iken klasör yok", S._ocr_onbellek_klasoru(pdf) is None)

# yazılamayan klasör: çökmez, sonuç yine döner
os.environ["OCR_ONBELLEK"] = "/proc/yazilamaz"
cagri.clear(); SIRA = [0]
sonuc = S._surya_sayfalar(pdf, [0])
dene("Yazılamayan önbellek klasöründe çökmez", 0 in sonuc and cagri == [1])

# model yok, önbellek var: önbellekteki sayfalar yine döner
os.environ["OCR_ONBELLEK"] = os.path.join(gecici, "onbellek")
SIRA = [0, 1, 2]
S._surya_sayfalar(pdf, [0, 1, 2])  # sürüm denemesinin üstüne yazdığı kayıtlar geçerli anahtarla yenilenir
S._surya_hazir = lambda: None
dene("Model yüklenemese de önbellekteki sayfalar okunur", set(S._surya_sayfalar(pdf, [0, 1, 2])) == {0, 1, 2})

print("SONUC: HEPSI GECTI" if not kalan else f"SONUC: {len(kalan)} TEST KALDI")
sys.exit(1 if kalan else 0)
