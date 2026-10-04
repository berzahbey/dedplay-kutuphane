"""0.5.11 gerileme testi: Surya satırları (İki Madnun'dan alınmış gerçek örnekler). OCR çalıştırmaz, hızlıdır."""
import os, sys, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kutuphane import kaynak as S

kalan = []


def dene(ad, kosul):
    print(("GECTI " if kosul else "KALDI ") + ad)
    if not kosul:
        kalan.append(ad)


def satir(metin, x0, y0, x1, y1):
    return types.SimpleNamespace(text=metin, bbox=(x0, y0, x1, y1))


def satirlar(liste):
    return [r["text"] for r in S._surya_satirlari(liste, 72 / 200, None)]


# 1) aralıklı başlığın Kiril okunan ilk harfi birleşir: "т" + "AKDIM" -> "TAKDIM"
t = satirlar([satir("AKDIM", 389, 401, 557, 429), satir("т", 367, 406, 387, 426),
              satir("Vakfımızca, merhum D. Sâbit Ünal'ın Gazâlî'den ter-", 128, 487, 856, 514)])
dene("Aralıklı başlık tek satır olur (TAKDIM)", t[0] == "TAKDIM")
dene("TAKDIM içerik başlığı sayılır", bool(S.TS.ICERIK_BASLIK.match(t[0])))
# 2) madde harfi ve başlık aynı satırda: "A —" + "ZAMAN"
t = satirlar([satir("ZAMAN", 211, 522, 395, 550), satir("A —", 143, 530, 210, 548),
              satir("Zaman mahdut olmaz (sınırlanmaz), zaman içinde za-", 143, 598, 869, 625)])
dene("Madde harfi başlığın önüne gelir (A — ZAMAN)", t[0] == "A — ZAMAN")
# 3) Surya harf karışıklıkları
dene("ș -> ş, å/ä -> â", S._surya_harfleri("geniș misål müntehä") == "geniş misâl müntehâ")
dene("Kiril metin (Latin azsa) değişmez", S._surya_harfleri("Москва") == "Москва")
# 4) uydurma süzgeci: Çince harfli sayfada anlamsız satırlar atılır, başlık ve Arapça kalır
t = satirlar([satir("1. KİTAP", 300, 500, 600, 530), satir("BÜYÜK MADNÛN", 280, 560, 640, 590),
              satir("( كتاب المضنون الكبير )", 280, 610, 640, 650), satir("不可 province.", 100, 900, 400, 930),
              satir("Contract", 100, 1000, 300, 1030), satir("an CarthairCarthair", 100, 1100, 400, 1130)])
dene("Uydurma satırlar atılır, başlık ve Arapça kalır", t == ["1. KİTAP", "BÜYÜK MADNÛN", "( كتاب المضنون الكبير )"])
t = satirlar([satir("Contract", 100, 1000, 300, 1030), satir("Maurice Bauyges", 100, 1100, 400, 1130)])
dene("Çince yoksa hiçbir satır atılmaz", len(t) == 2)
# 5) harfli ara başlıklar
for b in ("A — ZAMAN", "C - RIZIK MESELESİ", "B — İRTİKÂ (Yücelme) TABİRİ", "D - ALLAH'IN VE PEYGAMBER'İN RÜYÂDA GÖRÜLMESİ"):
    dene("Ara başlık: " + b, S._harfli_madde_basligi(b) and S.anlamli_baslik(b))
for b in ("A — Su küresi : (denizler)", "B - bu bir cümledir.", "1 — Ateş küresi"):
    dene("Ara başlık değil: " + b, not S._harfli_madde_basligi(b))
dene("Büyük harfli dini terimli başlık (RUBÛBİYYETİ BİLMEK)", S.anlamli_baslik("RUBÛBİYYETİ BİLMEK"))
dene("Karışık büyük-küçük çöp yine başlık değil", not S.anlamli_baslik("PAS TAİ Kan yay"))
# 6) Arapçalı yüksek satır başlık sayılmaz
r = {"text": "Yine Hak Teâlâ ( بيوم نطوي السماء )", "h": 15, "top": 100, "bot": 115, "x0": 40, "x1": 300,
     "n": 7, "kalin": False, "ocr": True}
dene("Arapçalı yüksek satır başlık değil", not S._baslik_mi(r, 10, 340, 0.0))
dene("Arapçasız yüksek satır yine başlık", S._baslik_mi(dict(r, text="Yeni Bölümün Adı"), 10, 340, 0.0))
# 7) Arapça ibareli kısa paragraf çöp diye silinmez; gerçek çöp silinir
og = [{"tur": "p", "metin": "Nitekim Hak Celle ve Âlâ Kur'an'ında :"},
      {"tur": "p", "metin": "( وإن الى ربك المنتهى ) «Muhakkak ki"},
      {"tur": "p", "metin": "xq zzv kkr pp"}]
kit = S.kitaba_cevir(og, {}, {"baslik": {"tr": "D"}, "yazar": {"tr": ""}, "asil_dil": "tr"})
metinler = [b["metin"]["tr"] for b in kit["bloklar"]]
dene("Arapça ibareli kısa paragraf kalır", any("المنتهى" in m for m in metinler))
dene("Arapçasız çöp paragraf silinir", not any("zzv" in m for m in metinler))
# 8) Surya üst simgesi dipnot atfı sayılır
dene("Üst simge atıf: \\ue0002\\ue001", S._atif_var("ayırdık.» demiştir.\ue0002\ue001 Evvelki", 2))
# 9) Türkçe cümle içindeki Arapça ibare paragrafı bölmez; tamamen Arapça paragraf ayrı kalır
og = [{"tur": "p", "metin": "Allah'ın günleri ise, Hak Teâlânın; ( وذكرهم بأيام الله )"},
      {"tur": "p", "metin": "«Onlara Allah'ın günlerini hatırlat!» dediği yerde"},
      {"tur": "p", "metin": "( وفي السماء رزقكم وما توعدون )"},
      {"tur": "p", "metin": "«Gökte rızkınız vardır.»"}]
S._kopuk_paragraflari_birlestir(og)
dene("Karışık satır + «meal» birleşir", og[0]["metin"].endswith("dediği yerde") and len(og) == 3)
dene("Tamamen Arapça paragraf ayrı kalır", og[1]["metin"].startswith("( وفي"))

print("SONUC: HEPSI GECTI" if not kalan else f"SONUC: {len(kalan)} TEST KALDI")
sys.exit(1 if kalan else 0)
