"""0.5.17 gerileme testi: iki iş şeridi (OCR'lı PDF hafif işleri bekletmez). Gerçek OCR çalıştırmaz."""
import os, sys, tempfile, time, types, json, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
GECICI = tempfile.mkdtemp()
os.environ["DATA_DIR"] = GECICI
os.environ["OCR_ONBELLEK"] = os.path.join(GECICI, "ocr_onbellek")
os.environ["OCR_MOTORU"] = "surya"
from kutuphane import depo, kaynak

kalan = []


def dene(ad, kosul):
    print(("GECTI " if kosul else "KALDI ") + ad)
    if not kosul:
        kalan.append(ad)


# --- ocr_gerekir (gerçek fonksiyon) ---
import fitz
katmanli = os.path.join(GECICI, "katmanli.pdf")
d = fitz.open()
p = d.new_page()
metin = "Bu kitap sayfasında yeterince uzun ve düzgün bir Türkçe metin bulunmaktadır. " * 3
for k in range(12):
    p.insert_text((40, 60 + 20 * k), metin[:80])
d.save(katmanli)
bos = os.path.join(GECICI, "taranmis.pdf")
d = fitz.open(); d.new_page(); d.save(bos)
dene("ocr_gerekir: EPUB hafif", kaynak.ocr_gerekir("/yok/kitap.epub") is False)
dene("ocr_gerekir: metin katmanlı PDF hafif", kaynak.ocr_gerekir(katmanli) is False)
dene("ocr_gerekir: taranmış PDF (önbellekte yok) ağır", kaynak.ocr_gerekir(bos) is True)
kaynak._onbellek_yaz(kaynak._ocr_onbellek_klasoru(bos), 0, kaynak._surya_anahtari(),
                     [types.SimpleNamespace(text="Önbellekteki satır", bbox=(1, 2, 3, 4))])
dene("ocr_gerekir: taranmış ama önbellekte olan PDF hafif", kaynak.ocr_gerekir(bos) is False)
dene("Zemberek çağrıları kilitli", getattr(kaynak.DZ.gecerli_mi, "_kilitli", False))

# --- şeritler (işler taklit: OCR 3 sn sürer) ---
calisan, en_cok, olaylar = [0], [0], []
kl = threading.Lock()


def sahte_dosya(kid, yol):
    with kl:
        calisan[0] += 1
        en_cok[0] = max(en_cok[0], calisan[0])
    olaylar.append(("basla", kid, time.time()))
    time.sleep(3 if yol.endswith("agir.pdf") else 0.2)
    olaylar.append(("bit", kid, time.time()))
    with kl:
        calisan[0] -= 1


ayni_kitap = []


def sahte_epub(kid):
    ayni_kitap.append((kid, depo._is_kilidi(kid).locked(), time.time()))
    depo.durum_yaz(kid, asama="hazır", epublar=[{"dosya": "x.epub"}])


depo.kaynak.ocr_gerekir = lambda yol: str(yol).endswith("agir.pdf")
depo._dosya_ekle = sahte_dosya
depo.epub_uret = sahte_epub
depo.K = types.SimpleNamespace(yukle=lambda p: {"kunye": {"asil_dil": "xx"}})
osm = []
depo._osmanlica = lambda kid, zorla=False: osm.append(kid)
# yeniden başlatmada yarım kalmış Osmanlıca işi (türü saklı)
depo.durum_yaz("yarim", asama="Osmanlıca sırada", is_turu="osmanlica", is_arg=None, tur="epub")
depo.baslat()

depo.is_ekle("dosya", "a", "/x/agir.pdf", tur="dosya")
time.sleep(0.3)
depo.is_ekle("dosya", "b", "/x/hafif.epub", tur="dosya")
time.sleep(1.5)
dene("Hafif iş, ağır OCR işini beklemeden bitti", depo.durum_oku("b").get("asama") == "hazır" and
     depo.durum_oku("a").get("asama") != "hazır")
dene("Yeniden başlatmada yarım Osmanlıca işi Osmanlıca olarak sürdü", "yarim" in osm)
# aynı kitabın işi ağır şeritte sürerken gelen EPUB işi beklemeli, aynı anda çalışmamalı
depo.is_ekle("epub", "a", tur="epub")
dene("Durum yazısı: 'EPUB sırada'", depo.durum_oku("a").get("asama") == "EPUB sırada")
time.sleep(5)
dene("Ağır iş sonunda bitti", depo.durum_oku("a").get("asama") == "hazır")
dene("Her iş kitabın kilidini tutarak çalıştı", all(kilitli for _, kilitli, _ in ayni_kitap))
a_bit = max(t for o, k, t in olaylar if o == "bit" and k == "a")
a_epub = [t for k, _, t in ayni_kitap if k == "a"]
dene("Kitabın EPUB işi, OCR işi bittikten sonra çalıştı", len(a_epub) == 2 and min(a_epub) >= a_bit)
depo.is_ekle("osmanlica", "b", tur="epub")
dene("Durum yazısı: 'Osmanlıca sırada' ve işin türü saklanır",
     depo.durum_oku("b").get("asama") in ("Osmanlıca sırada", "hazır") and depo.durum_oku("b").get("is_turu") == "osmanlica")
time.sleep(1)

print("SONUC: HEPSI GECTI" if not kalan else f"SONUC: {len(kalan)} TEST KALDI")
os._exit(1 if kalan else 0)
