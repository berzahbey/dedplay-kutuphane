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
ok("kişisel kopya" not in kunye and "OCR" not in kunye and "İtikadda Orta Yol" in kunye, "Künye: sadece ad ve yazar")
bolum = zipfile.ZipFile(os.path.join(klasor, "turkce.epub")).read("OEBPS/metin/bolum_001.xhtml").decode()
ok('role="doc-pagebreak"' in bolum and 'aria-label="5"></span>' in bolum, "Sayfa numarası görünmez işaret olarak duruyor")
ok(kaynak._kunye_sec({"baslik": "Imam Gazali Itikatta Sozun Ozu", "yazar": "Imam Gazali Itikatta Sozun Ozu", "kapak_baslik": ""},
                     "Itikatta Sozun Ozu", "Imam Gazali", "Imam Gazali - Itikatta Sozun Ozu")[1] == "İmam Gazali",
   "Künye: dosya adının kopyası olan bilgi alanı yok sayılır")
ok(kaynak._kunye_sec({"baslik": "", "yazar": "", "kapak_baslik": "İTİKATTA SÖZÜN ÖZÜ"}, "Itikatta Sozun Ozu", "Imam Gazali",
                     "x")[0] == "İtikatta Sözün Özü", "Künye: kapaktaki başlık Türkçe harfleriyle")
ok(kaynak.turkce_baslik("İTİKADDA ORTA YOL VE İLİM") == "İtikadda Orta Yol ve İlim", "Türkçe büyük/küçük harf")

# başlık denetimi: gerçek kitaptaki OCR çöpü fihriste girmez
COP = ['Ti EAA NİL ye" sir', 'Çİ eler İLANİ JS LE Aİ Jp', 'PAS TAİ Kan yay', 'â) ş ya az Lüle WAR', 'şöyle PARA iye', 'EA Pe)', 'TIRE',
       'SURU pil sani Gİ KİSİ LA GN öl', '5) Moral YS yal iy Ol»', 'sağ LEŞ ELLİ Ği', 'EĞEN ğ', 'kB aE', 'Alü alli', 'Pat', 'haldir.',
       'vaciptir.”', '#0 O »', "“Haceru'l-Esved, yeryüzünde Cenab-ı Hakk'ın"]
IYI = ['GİRİŞ', 'BİRİNCİ BÖLÜM', 'İlmin Şerefi', 'Kelâmın Önemi', 'ÖNSÖZ', "Allah'ın Varlığı", 'Ruh ve Beden', 'Kısım II',
       'Resulullah (S.A.V.) Efendimizin Hadis-i Şerifine', "Birinci Kutup: Allah'ın Zatı Hakkında", 'II. BÖLÜM']
ok(not [t for t in COP if kaynak.anlamli_baslik(t)], "Başlık denetimi: OCR çöpü başlık sayılmaz")
ok(all(kaynak.anlamli_baslik(t) for t in IYI), "Başlık denetimi: gerçek başlıklar tanınır")

# numaralı fihrist: Bölüm 001 · 5-20 · Başlık
import io, re
kit = K.yeni({"baslik": {"tr": "Deneme"}, "yazar": {"tr": ""}, "asil_dil": "tr", "kaynak": {"tur": "dosya"}})
def _p(no):
    K.blok_ekle(kit, "p", {"tr": "Metin."}, sayfalar=[{"no": str(no), "konum": {"tr": 0}}])
_p(1); _p(4)
K.blok_ekle(kit, "baslik", {"tr": "GİRİŞ"}, seviye=1, sayfalar=[{"no": "5", "konum": {"tr": 0}}])
for n in range(6, 21):
    _p(n)
K.blok_ekle(kit, "baslik", {"tr": "BİRİNCİ BÖLÜM"}, seviye=1, sayfalar=[{"no": "21", "konum": {"tr": 0}}])
for n in range(22, 92):
    _p(n)
nav = zipfile.ZipFile(io.BytesIO(epub.uret(kit, ["tr"]))).read("OEBPS/nav.xhtml").decode().split('epub:type="toc"')[1].split("</nav>")[0]
etiketler = re.findall(r'<a href="[^"]+">([^<]+)</a>', nav)
ok(etiketler == ["Bölüm 001 (1-4)", "Bölüm 002 (5-20) GİRİŞ", "Bölüm 003 (21-38) BİRİNCİ BÖLÜM", "Bölüm 004 (39-56)",
                 "Bölüm 005 (57-74)", "Bölüm 006 (75-91)"], f"Numaralı fihrist ve uzun bölümün bölünmesi {etiketler}")
ok(not [t for t in ["TİRE", "? vâcib ola tertibi bozmuş olu”"] if kaynak.anlamli_baslik(t)], "Başlık denetimi: TİRE ve ? ile başlayan satır")
ok(kaynak._eksik_numaralari_doldur([None, None, "3", "4", "5", "6", "7", "2877", "9", "10", "11", None, "13"])
   == [str(i) for i in range(1, 14)], "Yanlış okunmuş sayfa numarası (2877) düzeltilir")
og = [{"tur": "baslik", "metin": t, "boy": b, "ocr": True} for t, b in
      [("BİRİNCİ BÖLÜM", 15), ("HAYAT SIFATI", 12), ("İKİNCİ BÖLÜM", 11), ("İRADE SIFATI", 12.5)]]
kaynak._seviyeler(og)
ok([o["seviye"] for o in og] == [1, 2, 1, 2], "Seviye: Birinci/İkinci Bölüm aynı (en üst) seviyede")

print("SONUC:", "HEPSI GECTI" if all(BASARI) else f"{BASARI.count(False)} TEST KALDI")
sys.exit(0 if all(BASARI) else 1)
