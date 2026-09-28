"""Elindeki kitaplar (0.2) gerileme testleri: PDF (katman/taranmış/bozuk katman), EPUB, DOCX, TXT, Osmanlıca parçalama.
Stüdyo'nun kodu (app.textsrc, app.duzelt), Tesseract (tur) ve PyMuPDF gerekir: Kütüphane imajında hepsi var.
Çalıştırma (sunucuda, kod klasöründe):
  docker run --rm -v "$PWD":/k -w /k -e PYTHONPATH=/app:/k berzahbey/dedplay-kutuphane:latest python tests/test_kaynak.py"""
import os, sys, tempfile, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kutuphane import depo, epub, epubcheck, kaynak, osmanlica
from kutuphane import kitap as K
import fixtur_uret

BASARI = []


def ok(kosul, ad):
    BASARI.append(bool(kosul))
    print(("GECTI " if kosul else "KALDI ") + ad)


klasor = tempfile.mkdtemp()
fixtur_uret.hepsini_uret(klasor)
BEKLENEN_FIHRIST = ["ÖNSÖZ", "BİRİNCİ BÖLÜM", "İlmin Şerefi", "İKİNCİ BÖLÜM", "Kelâmın Önemi", "SONUÇ"]
for tur in ("katman", "tarama", "bozuk"):
    kit = kaynak.cevir(os.path.join(klasor, f"deneme_{tur}.pdf"))
    bl = kit["bloklar"]
    ok(K.denetle(kit) == [], f"PDF {tur}: yapısal denetim")
    ok([b["metin"]["tr"] for b in bl if b["tur"] == "baslik"] == BEKLENEN_FIHRIST, f"PDF {tur}: fihrist")
    ok([b["seviye"] for b in bl if b["tur"] == "baslik"] == [1, 1, 2, 1, 2, 1], f"PDF {tur}: başlık seviyeleri")
    ok([s["no"] for b in bl for s in b.get("sayfalar", [])] == ["5", "6", "7", "8", "9", "10"], f"PDF {tur}: basılı sayfa numaraları")
    s8 = next((b, s) for b in bl for s in b.get("sayfalar", []) if s["no"] == "8")
    ok(s8[0]["metin"]["tr"][s8[1]["konum"]["tr"]:].startswith("zorunlu"), f"PDF {tur}: sayfa geçişinde bölünen kelime birleşti")
    ok(len(kit["dipnotlar"]) == 2 and all("sahiptir.{{" in b["metin"]["tr"] for b in bl if "{{" in b["metin"]["tr"]),
       f"PDF {tur}: iki dipnot doğru yere bağlı")
    ok(kit["kunye"]["baslik"]["tr"] == "İtikadda Orta Yol", f"PDF {tur}: eser adı kapaktan")
    ok(not any("ISBN" in b["metin"]["tr"] or "İÇİNDEKİLER" in b["metin"]["tr"] for b in bl), f"PDF {tur}: künye ve içindekiler atıldı")
    ok(kit["kunye"]["cikarma"]["bozuk_katman"] == (tur == "bozuk"), f"PDF {tur}: bozuk katman tespiti")

kit = kaynak.cevir(os.path.join(klasor, "Erzurumlu Ibrahim Hakki - Marifetname.epub"))
bl = kit["bloklar"]
ok(K.denetle(kit) == [] and len(kit["dipnotlar"]) == 2, "EPUB: iki dipnot bağlı")
ok([b["metin"]["tr"] for b in bl if b["tur"] == "baslik"] == ["Mukaddime", "Birinci Bâb", "Birinci Fasıl"], "EPUB: içindekiler ve Notlar atıldı, başlıklar")
ok(bl[1]["metin"]["tr"].startswith("Hamd") and [s["no"] for b in bl for s in b.get("sayfalar", [])] == ["3", "5", "6"], "EPUB: ilk paragraf ve sayfa işaretleri")
ok(kit["kunye"]["baslik"]["tr"] == "Mârifetnâme" and kit["kunye"]["yazar"]["tr"] == "Erzurumlu İbrahim Hakkı", "EPUB: künye")
kit = kaynak.cevir(os.path.join(klasor, "deneme.docx"))
ok([(b["metin"]["tr"], b.get("seviye")) for b in kit["bloklar"] if b["tur"] == "baslik"] == [("Birinci Kısım", 1), ("İlmin Tarifi", 2)], "DOCX: başlıklar (kitap adı metne girmedi)")
kit = kaynak.cevir(os.path.join(klasor, "deneme.txt"))
ok([b["metin"]["tr"] for b in kit["bloklar"]] == ["MUKADDİME", "Bu metin düz yazı dosyasıdır.", "BİRİNCİ BÖLÜM",
                                                   "İkinci paragraf burada başlar ve sonra devam eder."], "TXT: paragraflar")

# Osmanlıca parçalama: dipnot işaretleri çeviriciye gitmez, geri takılır
sablon, parcalar = osmanlica._parcala("Birinci cümle.{{n0001}} İkinci cümle {{n0002}}")
ok(parcalar == ["Birinci cümle.", "İkinci cümle"], "Osmanlıca: işaretler parçalara girmez")
ok(osmanlica._birlestir(sablon, ["A.", "B"]) == "A.{{n0001}} B {{n0002}}", "Osmanlıca: işaretler geri takılır")

# Türkçe asıllı kitap: sürümler ve EPUB (sahte Osmanlıca ile)
kit = kaynak.cevir(os.path.join(klasor, "deneme_katman.pdf"))
for b in kit["bloklar"]:
    b["metin"]["osm"] = "عثمانلیجه " + " ".join("{{" + g + "}}" for g in K.NOT_ISARETI.findall(b["metin"]["tr"]))
for n in kit["dipnotlar"].values():
    n["metin"]["osm"] = "حاشیه"
ok([e for e, _ in depo.surumler(kit)] == ["turkce", "osmanlica", "turkce-osmanlica"], "Türkçe asıllı kitap: üç sürüm")
for ek, diller in depo.surumler(kit):
    yol = os.path.join(klasor, ek + ".epub")
    epub.uret(kit, diller, yol)
    if epubcheck.var_mi():
        d = epubcheck.denetle(yol)
        ok(d["hata"] == 0 and d["uyari"] == 0, f"EPUB {ek}: epubcheck 0 hata 0 uyarı {d['mesajlar'][:2]}")
kunye = zipfile.ZipFile(os.path.join(klasor, "turkce-osmanlica.epub")).read("OEBPS/metin/kunye.xhtml").decode()
ok("kişisel kopya" in kunye and "otomatik harf çevirisidir" in kunye, "Künye: kaynak ve Osmanlıca notu")
ok(kaynak.turkce_baslik("İTİKADDA ORTA YOL VE İLİM") == "İtikadda Orta Yol ve İlim", "Türkçe büyük/küçük harf")

print("SONUC:", "HEPSI GECTI" if all(BASARI) else f"{BASARI.count(False)} TEST KALDI")
sys.exit(0 if all(BASARI) else 1)
