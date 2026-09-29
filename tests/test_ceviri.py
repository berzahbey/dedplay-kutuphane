"""Çeviri (0.5) testleri: Translate'e gidecek paragraflar, çevirinin kitaba yazılması. Çalıştırma:
  docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kutuphane:latest python tests/test_ceviri.py"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kutuphane import ceviri, depo
from kutuphane import kitap as K

BASARI = []


def ok(kosul, ad):
    BASARI.append(bool(kosul))
    print(("GECTI " if kosul else "KALDI ") + ad)


kit = K.yeni({"baslik": {"ar": "الاقتصاد في الاعتقاد"}, "yazar": {"ar": "الغزالي"}, "asil_dil": "ar", "kaynak": {"tur": "openiti"}})
K.blok_ekle(kit, "baslik", {"ar": "خطبة الكتاب"}, seviye=1)
K.blok_ekle(kit, "p", {"ar": "الحمد لله {{n0001}} رب العالمين"})
K.blok_ekle(kit, "p", {"ar": "سطر محذوف"})
K.blok_ekle(kit, "p", {"ar": "فقرة مصححة", "tr": "Elle düzeltilmiş Türkçe."}, elle={"tr": True})
kit["dipnotlar"] = {"n0001": {"metin": {"ar": "حاشية"}}}
K.sil(kit, "b00003")

harita, par = ceviri.cevrilecekler(kit, "ar")
ok([h for h in harita] == [["blok", "b00001"], ["blok", "b00002"], ["kunye", "baslik"], ["kunye", "yazar"], ["not", "n0001"]],
   f"Çevrilecekler: silinen ve elle düzeltilmiş atlanır, künye ve dipnot eklenir {harita}")
ok(par[0]["kind"] == "h" and par[1]["text"] == "الحمد لله رب العالمين", "Başlık 'h', dipnot işareti Translate'e gitmez")
ok(all(p["text"].strip() for p in par), "Boş paragraf gönderilmez (sıra kaymaz)")
ok(ceviri.tahmini_sure(par) > 0, "Tahmini süre hesaplanır")

klasor = tempfile.mkdtemp()
json.dump({"is": 7, "harita": harita}, open(os.path.join(klasor, "ceviri.json"), "w"))
ciktilar = [{"idx": i, "out": o} for i, o in enumerate(["Kitabın Önsözü", "Hamd âlemlerin Rabbi Allah'adır.", "İtikatta Orta Yol",
                                                         "Gazzâlî", "Dipnot."])]
kit["bloklar"][3]["metin"]["tr"] = "Elle düzeltilmiş Türkçe."
yazilan = ceviri.uygula(kit, klasor, ciktilar)
ok(yazilan == 5, f"Beş çeviri yazıldı ({yazilan})")
ok(kit["bloklar"][1]["metin"]["tr"] == "Hamd âlemlerin Rabbi Allah'adır.{{n0001}}", "Dipnot atfı Türkçede korunur")
ok(kit["bloklar"][3]["metin"]["tr"] == "Elle düzeltilmiş Türkçe.", "Elle düzeltilmiş Türkçeye dokunulmaz")
ok(kit["kunye"]["baslik"]["tr"] == "İtikatta Orta Yol" and kit["kunye"]["yazar"]["tr"] == "Gazzâlî", "Eser adı ve yazar Türkçeleşir")
ok(kit["dipnotlar"]["n0001"]["metin"]["tr"] == "Dipnot.", "Dipnot çevrilir")
ok(K.denetle(kit) == [] and "tr" in K.diller(kit), "Kitap sağlam, artık Türkçesi var")
try:
    ceviri.uygula(kit, klasor, ciktilar[:3]); ok(False, "Sayı tutmazsa yazılmaz")
except ValueError:
    ok(True, "Çeviri sayısı tutmazsa hiçbir şey yazılmaz")
ok([e for e, _ in depo.surumler(kit)] == ["turkce", "arapca-turkce", "arapca"], "Çeviriden sonra sürümler (Osmanlıca gelince o da eklenir)")
try:
    ceviri.baslat(K.yeni({"baslik": {"tr": "x"}, "yazar": {}, "asil_dil": "tr"}), klasor); ok(False, "Türkçe kitap çevrilmez")
except ValueError:
    ok(True, "Türkçe kitap çevrilmez")

print("SONUC:", "HEPSI GECTI" if all(BASARI) else f"{BASARI.count(False)} TEST KALDI")
sys.exit(0 if all(BASARI) else 1)
