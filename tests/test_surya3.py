"""0.5.14 gerileme testi: sunucudaki Tesseract çıktısı ve önbellek satırlarıyla (OCR çalıştırmaz)."""
import os, sys, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kutuphane import kaynak as S
import pytesseract
from PIL import Image

kalan = []


def dene(ad, kosul):
    print(("GECTI " if kosul else "KALDI ") + ad)
    if not kosul:
        kalan.append(ad)


# 1) "Âdemi" satırı: sunucudaki Tesseract'ın gerçek kelimeleri (Arapça bölgesi çöp okunmuş, "ADİ" yanlış aday)
TK = [(10, 107, "Caöiymo"), (132, 45, "eds"), (193, 41, "gol"), (247, 38, "ADİ"), (306, 53, "Giz."), (378, 8, ")"),
      (409, 62, "«Hak"), (499, 67, "Teâlâ"), (590, 82, "Âdemi")]
eski = pytesseract.image_to_data
pytesseract.image_to_data = lambda *a, **k: {"left": [x for x, _, _ in TK], "width": [w for _, w, _ in TK],
                                             "text": [t for _, _, t in TK]}
sonuc = S._karisik_satiri_diz("Hak Teala Ademi» ( خلق الله آدم على صورته )", Image.new("L", (681, 54), 255))
pytesseract.image_to_data = eski
dene("Karışık satır: Arapça solda, Türkçe sağda (sunucu Tesseract'ı)", sonuc == "( خلق الله آدم على صورته ) «Hak Teala Ademi")


def satirlar(liste):
    return [r["text"] for r in S._surya_satirlari([types.SimpleNamespace(text=t, bbox=b) for t, b in liste], 72 / 200, None)]


# 2) boş sayfa 6'nın gerçek Surya satırları: yalnız üstteki "18" kalır
SAYFA6 = [("", (286, 1140, 927, 1368)), ("18", (134, 1198, 166, 1216)), ("", (104, 1226, 287, 1370)),
          ("机动物", (46, 1330, 105, 1361)), ("", (223, 1344, 365, 1410)), ("", (632, 1345, 846, 1403)),
          ("<b>Carl</b>", (630, 1353, 665, 1370)), ("", (124, 1361, 562, 1460)), ("A.", (596, 1374, 621, 1391)),
          ("30", (3, 1381, 23, 1394)), ("an Carthair<br>Carthair", (646, 1384, 795, 1425)),
          ("<b>Contract</b>", (6, 1420, 52, 1436))]
dene("Boş sayfadaki uydurmalar (Carl, Contract, A., 30) atılır", satirlar(SAYFA6) == ["18"])
# 3) yıldızlı dipnot
n = S._notlari_bol(["(*) Bu tercüme, İzmir İlâhiyat Fakültesi Vakfı yayınlarının 2. kitabı olarak «Halkın Kelâmî "
                    "Tartışmalardan Korunması» adı ile İzmir 1987'de yayınlanmıştır."])
dene("'(*)' dipnotu tek not, içindeki '2. kitabı' yeni not değil", len(n) == 1 and n[0][0] == 901 and "2. kitabı" in n[0][1])
rows = [{"text": t, "h": 10, "top": y, "bot": y + 10, "x0": 30, "x1": 300, "n": 3, "kalin": False, "ocr": True}
        for t, y in (("bir şey yazılmamıştır.(*)", 100), ("Allah'tan hepimize tevfik ederim.", 140),
                     ("(*) Bu tercüme, İzmir İlâhiyat Fakültesi Vakfı yayınlarının 2. kitabı", 420),
                     ("olarak yayınlanmıştır.", 432))]
ana, dip = S._dipnot_ayir(rows, 500, 10)
dene("'(*)' ile başlayan sayfa altı satırları dipnot bölgesi", len(dip) == 2 and len(ana) == 2)
# 4) harfli ara başlıklar aynı seviye
og = [{"tur": "baslik", "metin": "BİRİNCİ KISIM", "seviye": 1}, {"tur": "baslik", "metin": "A — ZAMAN", "seviye": 2},
      {"tur": "p", "metin": "Metin."}, {"tur": "baslik", "metin": "B — İRTİKÂ (Yücelme) TABİRİ", "seviye": 3},
      {"tur": "p", "metin": "Metin."}, {"tur": "baslik", "metin": "C - RIZIK MESELESİ", "seviye": 2}, {"tur": "p", "metin": "Metin."}]
S._seviyeler = lambda o: None  # yazı boyu tahmini bu testte devre dışı (seviyeler verildiği gibi)
kit = S.kitaba_cevir(og, {}, {"baslik": {"tr": "D"}, "yazar": {"tr": ""}, "asil_dil": "tr"})
sev = [b.get("seviye") for b in kit["bloklar"] if b["tur"] == "baslik"]
dene("Harfli ara başlıklar aynı seviyede", sev[1:] == [2, 2, 2])

print("SONUC: HEPSI GECTI" if not kalan else f"SONUC: {len(kalan)} TEST KALDI")
sys.exit(1 if kalan else 0)
