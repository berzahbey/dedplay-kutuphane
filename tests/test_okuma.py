"""Okuma ve düzeltme (0.3) gerileme testleri. Çalıştırma (sunucuda, kod klasöründe):
  docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kutuphane:latest python tests/test_okuma.py"""
import copy, io, os, re, sys, tempfile, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kutuphane import epub, epubcheck
from kutuphane import kitap as K

BASARI = []


def ok(kosul, ad):
    BASARI.append(bool(kosul))
    print(("GECTI " if kosul else "KALDI ") + ad)


def ornek():
    kit = K.yeni({"baslik": {"tr": "Deneme", "osm": "دنه مه"}, "yazar": {"tr": ""}, "asil_dil": "tr", "kaynak": {"tur": "dosya"}})
    K.blok_ekle(kit, "baslik", {"tr": "GİRİŞ", "osm": "گیریش"}, seviye=1, sayfalar=[{"no": "5", "konum": {"tr": 0}}])
    K.blok_ekle(kit, "p", {"tr": "Birinci paragraf.{{n0001}}", "osm": "برنجی.{{n0001}}"})
    K.blok_ekle(kit, "p", {"tr": "Çöp satır TİRE", "osm": "چوپ"}, sayfalar=[{"no": "6", "konum": {"tr": 0}}])
    K.blok_ekle(kit, "baslik", {"tr": "BİRİNCİ BÖLÜM", "osm": "برنجی بولوم"}, seviye=1, sayfalar=[{"no": "7", "konum": {"tr": 0}}])
    K.blok_ekle(kit, "p", {"tr": "İkinci bölümün metni.", "osm": "متن"})
    kit["dipnotlar"] = {"n0001": {"metin": {"tr": "Dipnot.", "osm": "حاشیه"}}}
    return kit


kit = ornek()
# tür değiştirme, silme, geri alma
ok(K.tur_degistir(kit, "b00003", "baslik", 2) and K.blok_bul(kit, "b00003")["seviye"] == 2, "Paragraf başlık yapılır")
ok(K.sil(kit, "b00003") and K.blok_bul(kit, "b00003")["silindi"], "Satır silinir (kitapta kalır)")
ok(K.duzelt(kit, "b00005", "tr", "Düzeltilmiş metin."), "Metin düzeltilir")
ok(K.geri_al(kit, "b00005") and K.blok_bul(kit, "b00005")["metin"]["tr"] == "İkinci bölümün metni." and "elle" not in K.blok_bul(kit, "b00005"),
   "Geri al: metin ve 'elle' işareti eski hâline döner")
ok(K.geri_al(kit, "b00003") and not K.blok_bul(kit, "b00003").get("silindi"), "Geri al: silme geri alınır")
ok(K.geri_al(kit, "b00003") and K.blok_bul(kit, "b00003")["tur"] == "p" and "gecmis" not in K.blok_bul(kit, "b00003"),
   "Geri al: tür eski hâline döner, geçmiş boşalır")
ok(not K.geri_al(kit, "b00003"), "Geri alınacak bir şey yoksa False")
# Türkçe düzeltmeyle otomatik yenilenen Osmanlıca, geri alınınca birlikte döner
K.duzelt(kit, "b00005", "tr", "Yeni metin.")
K.blok_bul(kit, "b00005")["gecmis"][-1]["osm_eski"] = K.blok_bul(kit, "b00005")["metin"]["osm"]
K.blok_bul(kit, "b00005")["metin"]["osm"] = "یڭی متن"
K.geri_al(kit, "b00005")
ok(K.blok_bul(kit, "b00005")["metin"] == {"tr": "İkinci bölümün metni.", "osm": "متن"}, "Geri al: otomatik yenilenen Osmanlıca da döner")

# görünür kitap: silinen satır EPUB'a girmez, sayfa işareti sonraki bloğa geçer
kit = ornek()
K.sil(kit, "b00003")
gor = K.gorunur(kit)
ok([b["id"] for b in gor["bloklar"]] == ["b00001", "b00002", "b00004", "b00005"], "Görünür kitap: silinen satır çıkar")
ok([s["no"] for s in K.blok_bul(gor, "b00004")["sayfalar"]] == ["6", "7"], "Görünür kitap: silinen satırın sayfası sonrakine geçer")
ok(K.blok_bul(kit, "b00003")["silindi"] and len(kit["bloklar"]) == 5, "Asıl kitapta silinen satır duruyor (geri alınabilir)")

# dipnotlu paragraf silinince: not düşer, EPUB hatasız
kit2 = ornek()
K.sil(kit2, "b00002")
ok(K.gorunur(kit2)["dipnotlar"] == {} and K.denetle(kit2) == [], "Dipnotlu paragraf silinince not görünürden düşer, kitap sağlam")
gecici = tempfile.mkdtemp()
for ad, k in (("silinen_dipnot", kit2), ("silinen_satir", kit)):
    for diller in (["tr"], ["tr", "osm"]):
        yol = os.path.join(gecici, f"{ad}_{'_'.join(diller)}.epub")
        epub.uret(k, diller, yol)
        if epubcheck.var_mi():
            d = epubcheck.denetle(yol)
            ok(d["hata"] == 0 and d["uyari"] == 0, f"EPUB ({ad}, {'+'.join(diller)}): epubcheck 0 hata 0 uyarı {d['mesajlar'][:2]}")
h = zipfile.ZipFile(os.path.join(gecici, "silinen_satir_tr.epub")).read("OEBPS/metin/bolum_001.xhtml").decode()
ok("Çöp satır" not in h, "Silinen satır EPUB metninde yok")

# bölüm yapısı: okuma ekranı EPUB ile aynı bölümleri görür; silinen satır yine de bir bölümde (geri getirilebilsin)
yapi = epub.bolum_yapisi(kit, "tr")
ok([b["etiket"] for b in yapi] == ["Bölüm 001 (5) GİRİŞ", "Bölüm 002 (7) BİRİNCİ BÖLÜM"], f"Bölüm yapısı {[b['etiket'] for b in yapi]}")
ok("b00003" in yapi[1]["bloklar"] or "b00003" in yapi[0]["bloklar"], "Silinen satır okuma ekranında bir bölümde")
kit3 = ornek()
K.sil(kit3, "b00004")  # bölüm başlığı silinince iki bölüm birleşir
ok(len(epub.bolum_yapisi(kit3, "tr")) == 1, "Bölüm başlığı silinince bölümler birleşir")
nav = zipfile.ZipFile(io.BytesIO(epub.uret(kit3, ["tr"]))).read("OEBPS/nav.xhtml").decode()
ok("BİRİNCİ BÖLÜM" not in nav, "Silinen başlık fihristte yok")

# bölümü açan başlıktan sonra seviyesi 3 olan alt başlık: fihrist listesi bozulmamalı (Fârâbî kitabındaki hata)
kit4 = ornek()
K.blok_ekle(kit4, "baslik", {"tr": "Derin Alt Başlık", "osm": "درین"}, seviye=3)
K.blok_ekle(kit4, "p", {"tr": "Metin.", "osm": "متن"})
kit4["bloklar"] = [kit4["bloklar"][0], kit4["bloklar"][-2], kit4["bloklar"][-1]] + kit4["bloklar"][1:-2]
yol4 = os.path.join(gecici, "seviye.epub"); epub.uret(kit4, ["tr"], yol4)
if epubcheck.var_mi():
    d = epubcheck.denetle(yol4)
    ok(d["hata"] == 0 and d["uyari"] == 0, f"Bölüm başlığından sonra derin alt başlık: fihrist geçerli {d['mesajlar'][:1]}")

print("SONUC:", "HEPSI GECTI" if all(BASARI) else f"{BASARI.count(False)} TEST KALDI")
sys.exit(0 if all(BASARI) else 1)
