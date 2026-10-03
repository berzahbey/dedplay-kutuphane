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
    ok(not any("ISBN" in b["metin"]["tr"] for b in bl)
       and not any("İÇİNDEKİLER" in b["metin"]["tr"].upper().replace("I", "İ") for b in bl),
       f"PDF {tur}: künye atıldı, basılı içindekiler kitaptan silindi (0.5.8)")
    ok(kit["kunye"]["cikarma"]["bozuk_katman"] == (tur == "bozuk"), f"PDF {tur}: bozuk katman tespiti")

kit = kaynak.cevir(os.path.join(klasor, "Erzurumlu Ibrahim Hakki - Marifetname.epub"))
bl = kit["bloklar"]
ok(K.denetle(kit) == [] and len(kit["dipnotlar"]) == 2, "EPUB: iki dipnot bağlı")
ok([b["metin"]["tr"] for b in bl if b["tur"] == "baslik"] == ["Mukaddime", "Birinci Bâb", "Birinci Fasıl"], "EPUB: Notlar atıldı, başlıklar, içindekiler sonda")
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
ok(len(etiketler) == 1 and sum(a.startswith("OEBPS/metin/bolum_") for a in
                                zipfile.ZipFile(io.BytesIO(epub.uret(kit, ["tr"]))).namelist()) == 6,
   f"EPUB'da liste yok (tek gizli bağlantı); uzun bölüm yine 6 dosyaya bölünür {etiketler}")
ok(not [t for t in ["TİRE", "? vâcib ola tertibi bozmuş olu”"] if kaynak.anlamli_baslik(t)], "Başlık denetimi: TİRE ve ? ile başlayan satır")
ok(kaynak._eksik_numaralari_doldur([None, None, "3", "4", "5", "6", "7", "2877", "9", "10", "11", None, "13"])
   == [str(i) for i in range(1, 14)], "Yanlış okunmuş sayfa numarası (2877) düzeltilir")
og = [{"tur": "baslik", "metin": t, "boy": b, "ocr": True} for t, b in
      [("BİRİNCİ BÖLÜM", 15), ("HAYAT SIFATI", 12), ("İKİNCİ BÖLÜM", 11), ("İRADE SIFATI", 12.5)]]
kaynak._seviyeler(og)
ok([o["seviye"] for o in og] == [1, 2, 1, 2], "Seviye: Birinci/İkinci Bölüm aynı (en üst) seviyede")

# başlık / kitap adı harf onarımı (OCR'ın kaybettiği nokta ve şapka)
ONAR = {"İTİKATTA SÖZÜN OZÜ": "İTİKATTA SÖZÜN ÖZÜ", "SEMİ' (İŞİTME) VE BASAR (GORME)": "SEMİ' (İŞİTME) VE BASAR (GÖRME)",
        "Allah'ın Varlıgı": "Allah'ın Varlığı", "Itikatta Sozun Ozu": "İtikatta Sözün Özü", "HAYAT SIFATI": "HAYAT SIFATI",
        "Mârifetnâme": "Mârifetnâme", "İmam Gazali": "İmam Gazali", "BİRİNCİ BÖLÜM": "BİRİNCİ BÖLÜM"}
ok(all(kaynak.turkce_onar(a) == b for a, b in ONAR.items()), f"Harf onarımı {[(a, kaynak.turkce_onar(a)) for a, b in ONAR.items() if kaynak.turkce_onar(a) != b]}")
ok(kaynak._kunye_sec({"kapak_satirlari": [("İTİKATTA,", 30, 200), ("SÖZÜN OZÜ", 24, 240)], "baslik": "", "yazar": ""},
                     "Itikatta Sozun Ozu", "Imam Gazali", "Imam Gazali - Itikatta Sozun Ozu") == ("İtikatta Sözün Özü", "İmam Gazali"),
   "Kitap adı: iki satırlı kapak + OCR nokta hatası düzeltilir")

# EPUB'un kendi fihristi (Calibre tipi: sınıflı <p> başlıklar, NCX, ön sayfalar, bozuk başlık yazısı)
fixtur_uret.calibre_epub(os.path.join(klasor, "calibre.epub"))
kit = kaynak.cevir(os.path.join(klasor, "calibre.epub"))
bl = kit["bloklar"]
ok(kit["kunye"].get("yapi") == "fihrist" and K.denetle(kit) == [], "EPUB fihristi: kitabın kendi fihristi kullanıldı")
ok([(b["metin"]["tr"], b["seviye"]) for b in bl if b["tur"] == "baslik"] == [
    ("MEDENİYETLERİN DEFTER-İ AMALİ: ANSİKLOPEDİLER", 1), ("I-BATIDA ANSİKLOPEDİ", 1), ("BİR TÜRÜN TARİH ÖNCESİ", 2),
    ("BELGELER TEORİSİ.", 2), ("II — İSLÂM’DA ANSİKLOPEDİ", 1), ("İSLÂMIN KOZMOLOJİK DOKTRİNLERİ", 2), ("DOĞU KÜTÜPHANESİ", 1),
    ],
   "EPUB fihristi: başlıklar, seviyeler ve temiz yazılar (Roma rakamı korunur)")
ok(not any(x in b["metin"]["tr"] for b in bl for x in ("CEMİL MERİÇ", "PINAR")) and bl[0]["metin"]["tr"].startswith("MEDENİYETLERİN")
   and not any(b["metin"]["tr"] == "İçindekiler" for b in bl), "EPUB fihristi: ön sayfalar atıldı, içindekiler silindi")
ok(any(b["metin"]["tr"].startswith("Doğu kütüphanesi hakkında") for b in bl), "EPUB fihristi: başlığa benzeyen paragraf kaybolmadı")
ok(any("Nasır’ın {{n0001}} tezini" in b["metin"]["tr"] for b in bl) and len(kit["dipnotlar"]) == 1, "Kesme işareti boşluğu ve ( 2 ) dipnotu")
import zipfile as _z, io as _io
_nav = _z.ZipFile(_io.BytesIO(epub.uret(kit, ["tr"]))).read("OEBPS/nav.xhtml").decode()
ok(_nav.split('epub:type="toc"')[1].split("</nav>")[0].count("<li>") == 1, "EPUB'da görünür liste yok (0.5.8)")

# PDF yer imleri (bookmarks): başlıklar oradan; sayfada bulunamayan yer imi sayfa başına eklenir
import fitz
fixtur_uret.pdf_yaz(os.path.join(klasor, "yi.pdf"), "katman")
_d = fitz.open(os.path.join(klasor, "yi.pdf"))
_sayfa = lambda y: next(i + 1 for i, pg in enumerate(_d) if i >= 3 and y in pg.get_text())  # içindekiler sayfası hariç
_d.set_toc([[1, "Önsöz", _sayfa("ÖNSÖZ")], [1, "Birinci Bölüm: İlmin Şerefi", _sayfa("BİRİNCİ BÖLÜM")],
            [2, "Şüphe ve İlim", _sayfa("zorun-")], [1, "İKİNCİ BÖLÜM", _sayfa("İKİNCİ BÖLÜM")], [2, "Kelâmın Önemi", _sayfa("Kelâmın Önemi")],
            [1, "SONUÇ", _sayfa("SONUÇ")]])
_d.save(os.path.join(klasor, "yi2.pdf"))
kit = kaynak.cevir(os.path.join(klasor, "yi2.pdf"))
bas = [(b["metin"]["tr"], b["seviye"]) for b in kit["bloklar"] if b["tur"] == "baslik"]
ok(kit["kunye"].get("yapi") == "fihrist" and K.denetle(kit) == [], "PDF yer imleri kullanıldı")
ok([x[0] for x in bas] == ["Önsöz", "Birinci Bölüm: İlmin Şerefi", "Şüphe ve İlim", "İKİNCİ BÖLÜM", "Kelâmın Önemi", "SONUÇ"]
   and [x[1] for x in bas] == [1, 1, 2, 1, 2, 1], f"PDF yer imleri: başlıklar ve seviyeler {bas}")
ok(not any(b["tur"] == "baslik" and b["metin"]["tr"] == "İlmin Şerefi" for b in kit["bloklar"]), "Yer imi yokken tanınan alt başlık paragrafa döner")

# Basılı içindekilerden fihrist (Klasik Mantık tipi): yer imi yok, başlıklar gövdeyle aynı puntoda, içindekiler iki sayfa
BEKLENEN_TOC = [("ÖNSÖZ", 1), ("GİRİŞ", 1), ("BİRİNCİ BÖLÜM: KAVRAMLAR", 1), ("Kavramın Tanımı", 2),
                ("Kavramların Birbirine Göre Durumları ve Beş Tümel Meselesi", 2), ("İKİNCİ BÖLÜM: ÖNERMELER", 1),
                ("Önermenin Tanımı", 2), ("Karşıt Önermeler", 2), ("SONUÇ", 1)]
for kip in ("katman", "tarama"):
    yol = os.path.join(klasor, f"mantik_{kip}.pdf")
    fixtur_uret.mantik_pdf(yol, kip)
    kit = kaynak.cevir(yol)
    bl = kit["bloklar"]
    bas = [(b["metin"]["tr"], b["seviye"]) for b in bl if b["tur"] == "baslik"]
    ok(K.denetle(kit) == [] and kit["kunye"].get("yapi") == "fihrist", f"İçindekiler ({kip}): yapısal denetim, kitabın fihristi")
    ok(bas == BEKLENEN_TOC, f"İçindekiler ({kip}): başlıklar ve seviyeler {bas}")
    sira = [b["metin"]["tr"][:20] for b in bl]
    k_tanim = sira.index("Kavramın Tanımı")
    ok(sira[k_tanim - 1].startswith("Konuya başka") and sira[k_tanim + 1].startswith("Şimdi asıl"),
       f"İçindekiler ({kip}): sayfa ortasındaki başlık kendi yerinde")
    govde_bl = bl
    ok(not any(b["tur"] == "p" and b["metin"]["tr"].strip() in ("KAVRAMLAR", "BİRİNCİ BÖLÜM", "ÖNERMELER", "İKİNCİ BÖLÜM",
                                                                  "Önermenin Tanımı", "ve Beş Tümel Meselesi")
               for b in govde_bl), f"İçindekiler ({kip}): başlık satırları paragraf olarak tekrar etmiyor")
    ok(any(b["tur"] == "p" and b["metin"]["tr"] == "Örnek" for b in bl), f"İçindekiler ({kip}): kalın satır başlık sanılmadı")
    ok([s["no"] for b in bl for s in b.get("sayfalar", [])] == [str(n) for n in range(7, 15)],
       f"İçindekiler ({kip}): basılı sayfa numaraları")
    son = []  # 0.5.8: basılı içindekiler kitaptan silinir
    # taranmışta tek haneli numarayı Tesseract sürümüne göre okuyamayabilir: numarasız kabul, yanlış numara hata
    dogru = ["ÖNSÖZ … 7", "GİRİŞ … 8", "BİRİNCİ BÖLÜM", "KAVRAMLAR … 9", "Kavramın Tanımı … 9",
             "Kavramların Birbirine Göre Durumları ve Beş Tümel", "Meselesi … 11", "İKİNCİ BÖLÜM", "ÖNERMELER … 12",
             "Önermenin Tanımı … 12", "Karşıt Önermeler … 13", "SONUÇ … 14"]
    uygun = len(son) == len(dogru) and all(a == b or (kip == "tarama" and a == b.split(" … ")[0]) for a, b in zip(son, dogru))
    ok(not any(b["metin"]["tr"].startswith(("ÖNSÖZ …", "SONUÇ …")) for b in bl),
       f"İçindekiler ({kip}): basılı içindekiler kitaptan silindi")
_nav = _z.ZipFile(_io.BytesIO(epub.uret(kit, ["tr"]))).read("OEBPS/nav.xhtml").decode()
ok("Kavramın Tanımı" not in _nav and _nav.split('epub:type="toc"')[1].split("</nav>")[0].count("<li>") == 1 and 'hidden="hidden"' in _nav,
   "EPUB'da görünür liste yok (0.5.8): gizli tek bağlantılı toc")
# Klasik Mantık'ın gerçek biçimi: bozuk başlık, ayrı satırda numaralar, ortada numarasız bölüm başlıkları, OCR hataları
fixtur_uret.klasik_mantik_pdf(os.path.join(klasor, "km.pdf"))
kit = kaynak.cevir(os.path.join(klasor, "km.pdf"))
bl = kit["bloklar"]
bas = [(b["metin"]["tr"], b["seviye"]) for b in bl if b["tur"] == "baslik"]
ok(K.denetle(kit) == [] and kit["kunye"].get("yapi") == "fihrist", "Klasik Mantık biçimi: içindekiler tanındı")
ok(bas == [("Önsöz", 1), ("GİRİŞ", 1), ("I. Mantık Nedir?", 2), ("II. Tarihsel Bilgi", 2), ("BİRİNCİ BÖLÜM: KAVRAM VE TERİM", 1),
           ("Kavramın tanımı", 2), ("Kavramın özelliği", 2), ("Önerme çeşitleri", 2), ("Yüklemli önermeler", 2),
           ("İKİNCİ BÖLÜM: ÖNERME", 1), ("Önermenin tanımı", 2), ("Karşı olma", 2), ("Kıyas", 2), ("Kıyasın tanımı", 2),
           ("Kıyasın çeşitleri", 2), ("Döndürme", 2), ("Tümevarım", 2)],
   f"Klasik Mantık biçimi: başlıklar (kitabın yazımıyla), seviyeler, yanlış numara ve OCR hatası {bas}")
govde_bl = bl
ok(any(b["tur"] == "p" and b["metin"]["tr"] == "Düz döndürme:" for b in govde_bl) and
   not any(b["tur"] == "p" and b["metin"]["tr"] in ("KAVRAM VE TERİM", "ÖNERME", "GİRİŞ") for b in govde_bl),
   "Klasik Mantık biçimi: içindekilerde olmayan satır paragraf, başlık satırı tekrar yok")
ok(any(b["tur"] == "p" and b["metin"]["tr"] == "Bu kısımda ele alınan meseleler üç ana başlık altında toplanır" for b in govde_bl),
   "Klasik Mantık biçimi: başlık sanılan iki satırlık blok bölünmedi")
ok(kaynak._toc_puan("Kıyasın tanımı", "Kıyas") == 0 and kaynak._toc_puan("il< I. Mantık Nedir?", "Mantık nedir") == 3,
   "Eşleşme puanı: kelime sınırı ve baştaki numara")
ok(kaynak._aralik_topla("G İ R İş") == "GİRİŞ", "Harf aralıklı başlık toplanır")
ok(sum(1 for b in govde_bl if b["tur"] == "p" and b["metin"]["tr"] == "Düz döndürme:") == 2 and
   not any("Kıyasm" in b["metin"]["tr"] for b in govde_bl),
   "Klasik Mantık biçimi: 'Düz döndürme:' paragraf kaldı, OCR hatalı gövde başlığı yerine içindekilerin yazımı")
ok(any(b["tur"] == "p" and b["metin"]["tr"] == "Bu mesele eskiden beri tartışılan bir konudur ve burada kısaca ele alınır."
       for b in govde_bl), "Klasik Mantık biçimi: kalın başlayıp küçük harfle süren cümle tek paragraf")
ok(kaynak._yazim_sec("KAVRAMIN ÖZELLİĞİ", "Kavramın özelliğı", 1) == "Kavramın özelliği",
   "Büyük harfli gövde: içindekilerin düzeni, hatalı kelime gövdeden")
ok(not kaynak._bulanik_toc("Düz döndürme:", "Döndürme") and kaynak._yazim_sec("Kıyasm tanımı :", "Kıyasın tanımı", 1) == "Kıyasın tanımı",
   "Bulanık eşleşme kelime sayısına bakar; geçersiz kelimeli yazım seçilmez")
ok(kaynak._icindekiler_basligi("iONDEKİ LER") and not kaynak._icindekiler_basligi("Kaynakça"), "Bozuk 'İÇİNDEKİLER' tanınır")
ok(not kaynak._benzer_toc("BİRİNCİ BÖLÜM", "İKİNCİ BÖLÜM") and kaynak._benzer_toc("Kavramın özelliği", "Kavramın özelliğı"),
   "Bulanık eşleşme: sıra sayısı farklıysa reddeder, harf hatasını kabul eder")

# başka baskının içindekileri (numaralar metne uymuyor): kullanılmaz, eski yol
g = [{"baslik": "Birinci Konu", "no": "40", "x0": 50}, {"baslik": "İkinci Konu", "no": "41", "x0": 50},
     {"baslik": "Üçüncü Konu", "no": "42", "x0": 50}]
ok(kaynak.icindekiler_fihristi(g, [None, "40", "41", "42"], [1, 2, 3], lambda i: [("p", "Başka bir metin", 11)]) is None,
   "Metne uymayan içindekiler kullanılmaz")
ok(kaynak.icindekiler_fihristi(g[:2], [None, "40", "41"], [1, 2], lambda i: []) is None, "İkiden az girdi: kullanılmaz")

# EPUB metninde kesme işareti ve tırnak kaçışlanmaz (yalnız & < >); bütün dosyalar geçerli XML
import re, xml.dom.minidom as _md
_k = K.yeni({"baslik": {"tr": "Aristo'nun Mantığı"}, "yazar": {"tr": "X"}, "asil_dil": "tr", "yapi": "fihrist"})
K.blok_ekle(_k, "baslik", {"tr": "Aristo'da modal önermeler & <tırnak>"}, seviye=1)
K.blok_ekle(_k, "p", {"tr": "Kant'a göre."})
_zip = _z.ZipFile(_io.BytesIO(epub.uret(_k, ["tr"])))
_dosyalar = {a: _zip.read(a).decode() for a in _zip.namelist() if a.endswith((".xhtml", ".opf"))}
for _t in _dosyalar.values():
    _md.parseString(_t.encode())
_opf = next(v for a, v in _dosyalar.items() if a.endswith(".opf"))
ok("Aristo'da modal önermeler &amp; &lt;tırnak&gt;" in _dosyalar["OEBPS/metin/bolum_001.xhtml"]
   and "&#x27;" not in re.sub(r'="[^"]*"', "", "".join(_dosyalar.values()))  # metinde; öznitelik (alt) kaçışlı kalır
   and "<dc:title>Aristo'nun Mantığı</dc:title>" in _opf,
   "Kesme işareti kaçışlanmaz (nav, başlık, künye); & ve < kaçışlı; dosyalar geçerli XML")

# Eski OCR katmanı satırı aynı yükseklikte parçalara bölmüş: parçalar birleşir, paragraf cümle ortasında bölünmez
fixtur_uret.parcali_pdf(os.path.join(klasor, "parcali.pdf"))
_ps = [b["metin"]["tr"] for b in kaynak.cevir(os.path.join(klasor, "parcali.pdf"))["bloklar"] if b["tur"] == "p"]
ok(_ps == fixtur_uret.PARCALI_METIN, f"Aynı satırdaki parçalar birleşir, paragraf bölünmez ({len(_ps)} paragraf)")

# Kitap açık taranmış PDF: her yatay sayfa cilt arasından ikiye bölünür (Ey Oğul, İlme Teşvik)
_bosluk = lambda t: re.sub(r"\s+", " ", kaynak.K.NOT_ISARETI.sub(" ", t)).strip()


def _ocr_benzer(bulunan, beklenen):
    """OCR'lı metin: paragraf sayısı birebir, sınırlar (ilk/son iki kelime) aynı, metin en az %97 benzer. Tesseract
    sürümüne göre tek harf okuma farkına izin verir (ör. dipnot işareti "1" kesme işareti okunabiliyor), sütun
    karışmasına ve paragraf bölünmesine izin vermez."""
    import difflib
    return len(bulunan) == len(beklenen) and all(
        a.split()[:2] == b.split()[:2] and a.split()[-2:] == b.split()[-2:]
        and difflib.SequenceMatcher(None, a, b).ratio() >= 0.97 for a, b in zip(bulunan, beklenen))


for _kip in ("katman", "tarama"):
    _y = os.path.join(klasor, f"cift_{_kip}.pdf")
    fixtur_uret.cift_sayfa_pdf(_y, _kip)
    _S, _b = kaynak.pdf_sayfalari(_y)
    _kit = kaynak.cevir(_y)
    _bl = _kit["bloklar"]
    ok((1, 0) in _b["kaynak_sayfa"] and (1, 1) in _b["kaynak_sayfa"] and (0, None) in _b["kaynak_sayfa"],
       f"Çift sayfa ({_kip}): yatay sayfa ikiye bölündü, dik kapak bölünmedi")
    _ps = [_bosluk(x["metin"]["tr"]) for x in _bl if x["tur"] == "p"]
    ok(_ps == fixtur_uret.CIFT_PARAGRAFLAR if _kip == "katman" else _ocr_benzer(_ps, fixtur_uret.CIFT_PARAGRAFLAR),
       f"Çift sayfa ({_kip}): paragraflar sayfa geçişlerinde bölünmeden birleşti")
    ok([sy["no"] for x in _bl for sy in x.get("sayfalar", [])] == ["1", "2", "3", "4"],
       f"Çift sayfa ({_kip}): her kitap sayfasının kendi basılı numarası")
    ok(any("Zühd 25" in d["metin"]["tr"] for d in _kit["dipnotlar"].values()) and
       any("{{n" in x["metin"]["tr"] for x in _bl if x["tur"] == "p"),
       f"Çift sayfa ({_kip}): sol sayfanın dipnotu kendi sayfasında, metne bağlı")
# Tesseract 5.5 yan yana iki sayfanın satırlarını tek satır verebiliyor (sunucuda görüldü): taklitle sınanır
import tess55_taklit
for _kip in ("satir",):  # sunucuda gözlenen davranış; "kelime" kipi gerçekte görülmeyen uydurma bir senaryoydu
    tess55_taklit.kur(_kip)
    try:
        _y = os.path.join(klasor, "cift_tarama.pdf")
        _b = kaynak.pdf_sayfalari(_y)[1]
        _kit = kaynak.cevir(_y)
    finally:
        tess55_taklit.kaldir()
    _bl = _kit["bloklar"]
    ok(sum(1 for _, y in _b["kaynak_sayfa"] if y == 0) == 2 and
       _ocr_benzer([_bosluk(x["metin"]["tr"]) for x in _bl if x["tur"] == "p"], fixtur_uret.CIFT_PARAGRAFLAR) and
       [sy["no"] for x in _bl for sy in x.get("sayfalar", [])] == ["1", "2", "3", "4"],
       f"Çift sayfa, Tesseract 5.5 taklidi ({_kip}): satırlar ayrıldı, sayfa bölündü, paragraf ve numaralar doğru")
_d = {"text": ["ÖNSÖZ", "tehlikelidir.", "Allah'ın", "Ey", "oğul"], "block_num": [1, 1, 1, 2, 2], "par_num": [1] * 5,
      "line_num": [1, 1, 1, 1, 1], "left": [350, 1020, 1300, 150, 230], "width": [160, 250, 150, 60, 80],
      "top": [90, 92, 92, 170, 170], "height": [30, 30, 30, 30, 30]}
ok([r["text"] for r in kaynak._ocr_satirlari(_d, 72 / 300)] == ["ÖNSÖZ", "tehlikelidir. Allah'ın", "Ey oğul"],
   "OCR satırı büyük boşlukta bölünür, normal kelime arasında bölünmez")
ok(all(kaynak.pdf_sayfalari(os.path.join(klasor, f))[1]["cift_sayfa"] == 0 for f in ("km.pdf", "parcali.pdf")),
   "Dik sayfalı kitaplarda sayfa bölünmez")
import fitz as _fitz
_d = _fitz.open()
_p = _d.new_page(width=700, height=400)
for _n in range(12):
    _p.insert_text((40, 40 + _n * 22), "Geniş tek sütunlu yatay sayfa: satırlar sayfanın ortasından geçer, bölünmemeli. " * 1,
                   fontsize=11)
_rows = kaynak._katman_satirlari(_d[0])
ok(kaynak._cilt_arasi(_rows, 700, 400) is None, "Tek sütunlu yatay sayfa bölünmez")

# zeyrek 0.1.3: "olmak" çözümlenince "ol-" kökü bozuluyordu ("olanlar" geçersiz sayılıyordu); düzeltme sırayı önemsizleştirir
kaynak.DZ.gecerli_mi("olmak")
kaynak.DZ._gecerli_onbellek.clear()
ok(all(kaynak.DZ.gecerli_mi(k) for k in ("olanlar", "olacak", "olacaktır", "yapılacak", "bulacak", "olmak")),
   "Zemberek: 'olmak' çözümlendikten sonra 'olanlar, olacak, yapılacak' hâlâ geçerli")

# Parantezli dipnot (Abidler Yolu): "(2)" atfı ve sayfa altında aynı puntoda "(2) … Sûresi"; numaralı madde dipnot değil
fixtur_uret.parantez_dipnot_pdf(os.path.join(klasor, "parantez_dipnot.pdf"))
_kit = kaynak.cevir(os.path.join(klasor, "parantez_dipnot.pdf"))
_t = " ".join(b["metin"]["tr"] for b in _kit["bloklar"] if b["tur"] == "p")
ok([d["metin"]["tr"] for d in _kit["dipnotlar"].values()] == fixtur_uret.PARANTEZ_DIPNOT and
   re.search(r"kaybolmaz\.\{\{n0001\}\}", _t) and re.search(r"olmaz mı\?\{\{n0002\}\}", _t),
   "Parantezli dipnot ayrılır ve metindeki atfına bağlanır")
ok("(1) Şeytanla savaşmak" in _t and "(2) Daima kötülüğe" in _t,
   "Sayfa altındaki numaralı madde (metinde atfı yok) dipnot sanılmaz")
ok(kaynak._atif_var("ibâdet edin. (İİ)", 1) and not kaynak._atif_var("(1) Şeytanla savaşmak", 1),
   "Atıf: OCR'ın harfe çevirdiği '(İİ)' tanınır, satır başındaki madde numarası atıf sayılmaz")

# Yazar: PDF bilgi alanındaki program/bilgisayar adı ("Construction.design") yerine dosya adındaki yazar
ok(kaynak._kunye_sec({"yazar": "Construction.design", "baslik": "?? ??? ????????"}, "Abidler Yolu", "Imam Gazali",
                     "Imam Gazali - Abidler Yolu") == ("Abidler Yolu", "İmam Gazali")
   and kaynak._kisi_adi_mi("Prof. Dr. Necati ÖNER") and not kaynak._kisi_adi_mi("Microsoft Word - kitap.doc"),
   "Yazar: program adı reddedilir, insan adı kabul edilir")

# İçindekiler/yer imi yoksa fihrist iskeleti metindeki "… Bölüm" başlıklarından
_og = []
for _b in ["MUKADDİME", "GİRİŞ", "BİRİNCİ BÖLÜM İLİM", "İKİNCİ BÖLÜM", "TEVBE", "ENGELLER", "Hazret-i Siner buyurur:",
           "ÜÇÜNCÜ BÖLÜM", "Tarsın!", "GÖZ VE KORUNMASI"]:
    _og.append({"tur": "baslik", "metin": _b, "boy": 12})
    if _b != "İKİNCİ BÖLÜM":
        _og.append({"tur": "p", "metin": "Metin.", "boy": 10})
ok(kaynak._bolum_iskeleti(_og) and [(o["metin"], o["seviye"]) for o in _og if o["tur"] == "baslik"] == [
    ("MUKADDİME", 1), ("GİRİŞ", 1), ("BİRİNCİ BÖLÜM İLİM", 1), ("İKİNCİ BÖLÜM: TEVBE", 1), ("ENGELLER", 2),
    ("ÜÇÜNCÜ BÖLÜM", 1), ("GÖZ VE KORUNMASI", 2)] and not kaynak._bolum_iskeleti([{"tur": "baslik", "metin": "GİRİŞ"}]),
   "Bölüm başlıklarından fihrist; ':' ve '!' ile biten satır başlık değil; bölümsüz kitaba dokunulmaz")

# Sahte başlıklar (paragrafın son satırı, tarama lekesi, "|" kalem çizgisi) paragraf olur; iskelette alt başlık büyük harfli
_og = [{"tur": "p", "metin": "Bu cümle ayrı-"}, {"tur": "baslik", "metin": "rılmıştır."}, {"tur": "baslik", "metin": "BH"},
       {"tur": "baslik", "metin": "runda değilsin. |"}, {"tur": "baslik", "metin": "BİRİNCİ BÖLÜM"},
       {"tur": "p", "metin": "Metin."}, {"tur": "baslik", "metin": "TAKVA ise dinde gâyet itiyatlı olma durumudur."},
       {"tur": "baslik", "metin": "RİYÂ"}, {"tur": "p", "metin": "Metin."}, {"tur": "baslik", "metin": "İKİNCİ BÖLÜM"},
       {"tur": "p", "metin": "Metin."}]
kaynak._sahte_basliklari_ayikla(_og)
kaynak._kopuk_paragraflari_birlestir(_og)
kaynak._bolum_iskeleti(_og)
ok([(o["metin"], o.get("seviye")) for o in _og if o["tur"] == "baslik"] == [("BİRİNCİ BÖLÜM", 1), ("RİYÂ", 2),
                                                                           ("İKİNCİ BÖLÜM", 1)]
   and _og[0]["metin"] == "Bu cümle ayrı- rılmıştır.",
   "Sahte başlıklar paragraf olur ve cümlesine döner; iskelette alt başlık büyük harfli")
ok(kaynak._ocr_satirlari({"text": ["yüz", "çevirmelisin.", "|"], "block_num": [1] * 3, "par_num": [1] * 3,
                          "line_num": [1] * 3, "left": [10, 60, 220], "width": [40, 120, 6], "top": [10] * 3,
                          "height": [30] * 3}, 1)[0]["text"] == "yüz çevirmelisin.", "OCR: tek başına '|' silinir")

# Cümlesi yarıda kalan paragrafın devamı (küçük harfle başlayan) birleşir; liste maddeleri birleşmez
_og = [{"tur": "p", "metin": "akla hayâle gelmeyen bu ni'met-"}, {"tur": "p", "metin": "leri, siz iyi kullarına."},
       {"tur": "p", "metin": "Şunlar gereklidir:"}, {"tur": "p", "metin": "a) Hor zaman için unutmamak,"},
       {"tur": "p", "metin": "b) İnsanlara iştirak etmemek."}]
kaynak._kopuk_paragraflari_birlestir(_og)
ok([o["metin"] for o in _og] == ["akla hayâle gelmeyen bu ni'met- leri, siz iyi kullarına.", "Şunlar gereklidir:",
                                 "a) Hor zaman için unutmamak,", "b) İnsanlara iştirak etmemek."],
   "Kopuk paragraf birleşir, liste maddeleri ayrı kalır")

print("SONUC:", "HEPSI GECTI" if all(BASARI) else f"{BASARI.count(False)} TEST KALDI")
sys.exit(0 if all(BASARI) else 1)
