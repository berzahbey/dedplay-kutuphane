"""Kütüphane gerileme testleri (internet gerekmez). Çalıştırma: python tests/test_temel.py
Konteynerde: docker exec dedplay-kutuphane python /app/tests/test_temel.py  (imaja tests kopyalanmaz;
sunucuda kod klasöründen: docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kutuphane:latest python tests/test_temel.py)"""
import copy, io, os, re, sys, tempfile, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kutuphane import epub, epubcheck, katalog, openiti
from kutuphane import kitap as K

ORNEK = """######OpenITI#
#META# 000.SortField :: Shamela_0000001
#META# 016.BookTITLE :: كتاب التجربة
#META#Header#End#
# | خطبة الكتاب
# الحمد لله رب العالمين ، والصلاة على رسوله . PageV01P010 هذا أول الصفحة الحادية عشرة
~~ وتتمة السطر ms001 هنا .
# PageV01P011 صفحة فارغة PageV01P012
# | القطب الأول في الذات
# | الدعوى الأولى وجود الله
# نبين فيه وجوده ( تعالى ) وأنه قديم . PageV01P013
# | الدعوى الثانية قدمه
# والقديم لا أول له .
"""
BASARI = []


def ok(kosul, ad):
    BASARI.append(bool(kosul))
    print(("GECTI " if kosul else "KALDI ") + ad)


kit = openiti.cevir(ORNEK, {"title_ar": "كتاب التجربة", "author_ar": "المؤلف", "date": "505",
                            "versionUri": "0505Test.Tecrube.X-ara1", "url": "https://example.org/x"})
bl = kit["bloklar"]
ok(K.denetle(kit) == [], "örnek kitap yapısal olarak sağlam")
ok([b["seviye"] for b in bl if b["tur"] == "baslik"] == [1, 1, 2, 2], "başlık seviyeleri (Hutbe, Kutup, Dava, Dava)")
p1 = bl[1]
ok(bl[0]["sayfalar"][0]["no"] == "10", "ilk sayfa = ilk işaretin sayfası (ilk başlıkta)")
k11 = next(s for s in p1["sayfalar"] if s["no"] == "11")["konum"]["ar"]
ok(p1["metin"]["ar"][k11:].startswith("هذا أول"), "paragraf içi sayfa konumu kelimenin başında")
ok("ms001" not in p1["metin"]["ar"] and "~~" not in p1["metin"]["ar"], "ms ve ~~ temizlendi")
ok("العالمين، والصلاة" in p1["metin"]["ar"] and "(تعالى)" in bl[4]["metin"]["ar"], "Arapça noktalama boşlukları")
ok([s["no"] for s in bl[2]["sayfalar"]] == ["12", "13"], "boş sayfa (12) ve 13 sonraki başlığa geçti")
ok([s["no"] for s in bl[5].get("sayfalar", [])] == ["14"], "paragraf sonundaki işaret sonraki bloğa geçti")

# iki dilli + dipnot
t = copy.deepcopy(kit)
for b in t["bloklar"]:
    b["metin"]["tr"] = "Türkçe " + b["id"] + (" {{n0001}}" if b["id"] == "b00002" else "") + ". İkinci cümle burada."
    b["metin"]["osm"] = "عثمانلیجه " + b["id"] + (" {{n0001}}" if b["id"] == "b00002" else "")
t["dipnotlar"] = {"n0001": {"metin": {"tr": "Dipnot metni.", "osm": "حاشیه"}}}
t["kunye"]["baslik"]["tr"] = "Tecrübe Kitabı"
ok(K.denetle(t) == [], "iki dilli kitap sağlam")
gecici = tempfile.mkdtemp()
for diller in (["ar"], ["tr"], ["osm"], ["tr", "osm"], ["ar", "tr"]):
    yol = os.path.join(gecici, "_".join(diller) + ".epub")
    epub.uret(t, diller, yol)
    z = zipfile.ZipFile(yol)
    ok(z.namelist()[0] == "mimetype" and z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED, f"{diller}: mimetype ilk ve sıkıştırmasız")
    nav = z.read("OEBPS/nav.xhtml").decode()
    ok('epub:type="page-list"' in nav and nav.count("<li><a href=\"metin/bolum_") >= 4, f"{diller}: fihrist ve sayfa listesi")
    if epubcheck.var_mi():
        d = epubcheck.denetle(yol)
        ok(d["hata"] == 0 and d["uyari"] == 0, f"{diller}: epubcheck 0 hata 0 uyarı {d['mesajlar'][:2]}")
h = zipfile.ZipFile(os.path.join(gecici, "tr_osm.epub")).read("OEBPS/metin/bolum_001.xhtml").decode()
ok(h.count('epub:type="noteref"') == 2 and h.count('epub:type="footnote"') == 1, "iki dilli dipnot: 2 atıf, 1 not")
opf = zipfile.ZipFile(os.path.join(gecici, "osm.epub")).read("OEBPS/content.opf").decode()
ok('page-progression-direction="rtl"' in opf, "Osmanlıca sağdan sola")
spine = opf.split("<spine")[1].split("</spine>")[0]
ok(spine.strip().splitlines()[-1].strip() == '<itemref idref="nav"/>' and spine.index('"kapak"') < spine.index('"b001"'),
   "okuma sırası: kapak, künye, metin, fihrist en sonda")

# düzeltme
ok(K.duzelt(t, "b00002", "tr", "Düzeltilmiş metin {{n0001}}.") and t["bloklar"][1]["elle"]["tr"], "düzeltme kaydı ve 'elle' işareti")
ok(t["bloklar"][1]["gecmis"][-1]["eski"].startswith("Türkçe"), "eski hâl geçmişte")
t2 = copy.deepcopy(t); t2["dipnotlar"]["n0099"] = {"metin": {"tr": "x"}}
ok(any("n0099" in e for e in K.denetle(t2)), "boşta dipnot yakalanır")

# Türkçe arama sadeleştirmesi
ok(katalog.sade("gazzâlî iktisad").split() == katalog.sade("al-Ġazālī Iqtisad").split(), "gazzâlî iktisad = al-Ġazālī Iqtisad")
ok("fusus" in katalog.sade("Fusûsu'l-Hikem") and katalog.sade("İbnü'l-Arabî").strip() != "", "şapka ve kesme işareti")

# düzeltilmemiş OCR (AOCP) artıkları: resim bağlantısı, varak, naşir dipnot numaraları (yıllar korunur)
OCR_ORNEK = """######OpenITI#
#META#Header#End#
# | باب
# الحمد لله فهو(24) لما يرى ![image file](./0638X_0024.png) تعالى [135 و)، والثاني [136ظ] قال (ما يأتيهم محدث)8)، وحديثا)((12) أي
~~ وتدبير8(220) والله ليلة0(405) هذا مشركون}58)، و الله) 279) وأما المقدسة  (185) من توفي سنة (505) هـ وفي (1111 م) كان.
# قال(1) وقال(2) وقال(3) وقال(4) وقال(5) تم. PageV01P010
"""
k = openiti.cevir(OCR_ORNEK, {"versionUri": "0638Test.Ornek.AOCP1-ara1"})
tum = " ".join(b["metin"]["ar"] for b in k["bloklar"])
ok(k["kunye"]["ocr"], "OCR kaynak işaretlenir (AOCP)")
ok(not re.search(r"image|png|\[\s*\d|\(\d{1,4}\)|\d\)", tum.replace("(505)", "").replace("(1111 م)", "")), f"OCR artıkları temizlenir: {tum[:200]}")
ok("(505) هـ" in tum and "(1111 م)" in tum, "Yıllar (505 هـ, 1111 م) korunur")
k2 = openiti.cevir(ORNEK, {})
ok(k2 == kit or [b["metin"]["ar"] for b in k2["bloklar"]] == [b["metin"]["ar"] for b in kit["bloklar"]], "Temiz metin değişmez")

print("SONUC:", "HEPSI GECTI" if all(BASARI) else f"{BASARI.count(False)} TEST KALDI")
sys.exit(0 if all(BASARI) else 1)
