"""Kitaplar klasörü ve Stüdyo'ya gönderme (0.4) testleri. Çalıştırma (sunucuda, kod klasöründe):
  docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kutuphane:latest python tests/test_studyo.py"""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kutuphane import cikti
from kutuphane import kitap as K

BASARI = []


def ok(kosul, ad):
    BASARI.append(bool(kosul))
    print(("GECTI " if kosul else "KALDI ") + ad)


kit = K.yeni({"baslik": {"tr": "İtikatta Sözün Özü", "osm": "اعتقادده سوزڭ اوزی"}, "yazar": {"tr": "İmam Gazali"},
              "asil_dil": "tr", "kaynak": {"tur": "dosya"}})
K.blok_ekle(kit, "baslik", {"tr": "GİRİŞ", "osm": "گیریش"}, seviye=1, sayfalar=[{"no": "9", "konum": {"tr": 0}}])
K.blok_ekle(kit, "p", {"tr": "Hamd Allah'adır.{{n0001}}", "osm": "حمد اللهدر.{{n0001}}"})
K.blok_ekle(kit, "p", {"tr": "Çöp satır", "osm": "چوپ"})
K.blok_ekle(kit, "p", {"tr": "Osmanlıcası olmayan satır."})
for n in range(10, 45):
    K.blok_ekle(kit, "p", {"tr": f"Paragraf {n}.", "osm": f"پاراغراف {n}"}, sayfalar=[{"no": str(n), "konum": {"tr": 0}}])
kit["dipnotlar"] = {"n0001": {"metin": {"tr": "Dipnot metni.", "osm": "حاشیه"}}}
K.sil(kit, "b00003")

p = cikti.studyo_parcalari(kit)
ok([x["name"] for x in p][-1] == "Dipnot_001" and all(x["name"].startswith("Parca_") for x in p[:-1]), "Parçalar: bölümler Parca_, dipnotlar Dipnot_")
ok(all("osm" not in x for x in p), "Stüdyo'ya sadece Türkçe gider (Osmanlıcaya Stüdyo çevirir)")
ok(p[0]["tr"].split("\n")[0] == "GİRİŞ" and "Bölüm 001" not in p[0]["tr"], "Bölüm, başlığıyla başlar (etiket seslendirmede okunmaz)")
ok("{{" not in "".join(x["tr"] for x in p), "Dipnot işaretleri gitmez")
ok("Çöp satır" not in "".join(x["tr"] for x in p), "Silinen satır gitmez")
ok("Osmanlıcası olmayan satır." in p[0]["tr"], "Osmanlıcası olmayan satır da gider")
ok(p[-1]["tr"].split("\n") == ["DİPNOTLAR", "1. Dipnot metni."], "Dipnotlar numaralı")
ar = K.yeni({"baslik": {"ar": "كتاب"}, "yazar": {"ar": ""}, "asil_dil": "ar", "kaynak": {"tur": "openiti"}})
K.blok_ekle(ar, "p", {"ar": "نص"})
try:
    cikti.studyo_parcalari(ar); ok(False, "Türkçesi olmayan kitap Stüdyo'ya gönderilmez")
except ValueError:
    ok(True, "Türkçesi olmayan kitap Stüdyo'ya gönderilmez")
ok(len(p) >= 3, f"Uzun kitap birden çok bölüm (ses parçası): {len(p) - 1} bölüm")
uzun = K.yeni({"baslik": {"tr": "Uzun"}, "yazar": {}, "asil_dil": "tr", "kaynak": {"tur": "dosya"}})
for n in range(60):
    K.blok_ekle(uzun, "p", {"tr": ("Uzun bir paragraf metni. " * 40).strip()})
pu = cikti.studyo_parcalari(uzun)
ok(len(pu) >= 4 and all(len(x["tr"]) <= cikti.PARCA_HARF + 1100 for x in pu), f"Başlıksız uzun kitap ~15.000 harflik ses parçalarına bölünür ({len(pu)} parça)")
ok(sum(x["tr"].count("\n") + 1 for x in pu) == 60, "Bölerken paragraf kaybolmaz")

# Kitaplar klasörü: dile göre, ad değişince eski dosya kalkar, başka dosyalara dokunulmaz
kok = tempfile.mkdtemp()
cikti.CIKTI = kok
epk = tempfile.mkdtemp()
epublar = []
for ad, d in (("t.epub", ["tr"]), ("o.epub", ["osm"]), ("to.epub", ["tr", "osm"])):
    open(os.path.join(epk, ad), "wb").write(b"EPUB-" + ad.encode())
    epublar.append({"dosya": ad, "diller": d})
os.makedirs(os.path.join(kok, "Türkçe"))
open(os.path.join(kok, "Türkçe", "Başka Kitap.epub"), "w").write("dokunma")
y1 = cikti.ciktiya_yaz(kit, epublar, epk)
ok(sorted(y1) == sorted(["Türkçe/İtikatta Sözün Özü - İmam Gazali.epub", "Osmanlıca/İtikatta Sözün Özü - İmam Gazali.epub",
                         "Türkçe-Osmanlıca/İtikatta Sözün Özü - İmam Gazali.epub"]), f"Dil klasörleri ve dosya adları {y1}")
kit["kunye"]["baslik"]["tr"] = "İtikatta Sözün Özü: Yeni"
y2 = cikti.ciktiya_yaz(kit, epublar, epk, y1)
ok(all(os.path.exists(os.path.join(kok, x)) for x in y2) and not any(os.path.exists(os.path.join(kok, x)) for x in y1),
   "Ad değişince eski dosyalar kaldırılır")
ok("İtikatta Sözün Özü Yeni - İmam Gazali.epub" in os.listdir(os.path.join(kok, "Türkçe")), "Dosya adında yasak karakter (:) temizlenir")
ok(open(os.path.join(kok, "Türkçe", "Başka Kitap.epub")).read() == "dokunma", "Başka dosyalara dokunulmaz")
cikti.CIKTI = os.path.join(kok, "yok")
ok(cikti.ciktiya_yaz(kit, epublar, epk) is None, "Klasör bağlı değilse sessizce atlanır")

print("SONUC:", "HEPSI GECTI" if all(BASARI) else f"{BASARI.count(False)} TEST KALDI")
sys.exit(0 if all(BASARI) else 1)
