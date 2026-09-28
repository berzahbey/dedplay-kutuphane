"""kitap.json -> EPUB 3 (fihrist, sayfa listesi, dipnot pencereleri, sağdan sola, iki dilli).

diller: gösterilecek diller sırasıyla, ör. ["tr"], ["osm"], ["tr", "osm"], ["ar", "tr"].
İlk dil ana dildir: sayfa listesi, fihrist ve okuma yönü ondan alınır.
"""
import datetime
import html
import io
import os
import re
import uuid
import zipfile

from . import kapak as KAPAK
from . import kitap as K

DIL = {"ar": ("ar", "rtl", "Arapça"), "tr": ("tr", "ltr", "Türkçe"), "osm": ("ota", "rtl", "Osmanlıca"),
       "en": ("en", "ltr", "İngilizce"), "fr": ("fr", "ltr", "Fransızca"), "fa": ("fa", "rtl", "Farsça")}
FONT_ADAY = ["/usr/share/fonts/truetype/amiri",
             os.environ.get("FONT_DIR", "/usr/share/fonts/truetype/amiri")]
X = html.escape

CSS = """@charset "utf-8";
@font-face { font-family: "Amiri"; font-weight: normal; src: url(../fonts/Amiri-Regular.ttf); }
@font-face { font-family: "Amiri"; font-weight: bold; src: url(../fonts/Amiri-Bold.ttf); }
body { margin: 0 4%; line-height: 1.55; widows: 2; orphans: 2; }
p { margin: 0; text-indent: 1.4em; text-align: justify; }
p + p { margin-top: 0.25em; }
[dir="rtl"], [lang="ar"], [lang="ota"], [lang="fa"] { font-family: "Amiri", "Scheherazade New", "Traditional Arabic", serif; line-height: 1.95;
  font-size: 1.12em; }
p[dir="rtl"] { text-indent: 1.4em; }
h1, h2, h3, h4, h5, h6 { text-align: center; line-height: 1.35; font-weight: bold; page-break-after: avoid;
  break-after: avoid; hyphens: none; -webkit-hyphens: none; text-indent: 0; }
h1 { font-size: 1.5em; margin: 2em 0 1.2em; page-break-before: always; break-before: page; }
h2 { font-size: 1.28em; margin: 1.8em 0 0.9em; }
h3 { font-size: 1.12em; margin: 1.5em 0 0.7em; }
h4, h5, h6 { font-size: 1em; margin: 1.2em 0 0.5em; }
h1 .ikinci, h2 .ikinci, h3 .ikinci, h4 .ikinci { display: block; font-size: 0.85em; margin-top: 0.3em;
  font-weight: normal; }
p[lang="tr"], p[lang="en"], p[lang="fr"] { hyphens: auto; -webkit-hyphens: auto; }
.cift { margin: 0.2em 0 0.8em; }
.cift p.ikinci { margin-top: 0.35em; padding-top: 0.3em; border-top: 1px solid #ccc; }
span.sayfa { font-size: 0.62em; color: #8a8a8a; vertical-align: super; line-height: 0; padding: 0 0.15em;
  text-indent: 0; font-family: sans-serif; }
a.notref { font-size: 0.7em; vertical-align: super; line-height: 0; text-decoration: none; }
aside.notlar-bolum { margin-top: 2em; border-top: 1px solid #999; padding-top: 0.5em; font-size: 0.85em; }
aside.dipnot p { text-indent: 0; }
aside.dipnot a.geri { text-decoration: none; }
.kunye { text-align: center; margin-top: 3em; }
.kunye p { text-indent: 0; text-align: center; margin: 0.4em 0; }
.kunye .eser { font-size: 1.6em; font-weight: bold; margin: 0.8em 0; }
.kunye .kucuk { font-size: 0.8em; color: #555; margin-top: 2em; }
.kunye [dir="ltr"], .kunye [lang="tr"] { font-family: serif; line-height: 1.5; font-size: 1em; }
nav li { margin: 0.3em 0; line-height: 1.5; }
nav ol { list-style: none; padding-left: 1.2em; } nav > ol { padding-left: 0; }
nav[dir="rtl"] ol { padding-left: 0; padding-right: 1.2em; }
nav a { text-decoration: none; }
.kapak { margin: 0; padding: 0; text-align: center; } .kapak img { max-width: 100%; max-height: 100%; }
"""


def _dil(d):
    return DIL.get(d, (d, "ltr", d))


def _attr(d):
    lang, yon, _ = _dil(d)
    return f' lang="{lang}" xml:lang="{lang}" dir="{yon}"'


def konum_tahmin(kaynak, konum, hedef):
    """Kaynak dildeki sayfa konumunun hedef dildeki yaklaşık karşılığı: oranla bulunur, en yakın
    cümle başına (yakında yoksa kelime başına) çekilir."""
    if not kaynak or not hedef or konum <= 0:
        return 0
    k = round(konum / len(kaynak) * len(hedef))
    pay = max(20, len(hedef) // 8)
    cumle = [m.end() for m in re.finditer(r"[.!?؟…:;؛]\s+", hedef)]
    yakin = [c for c in cumle if abs(c - k) <= pay]
    if yakin:
        return min(yakin, key=lambda c: abs(c - k))
    bosluk = [m.end() for m in re.finditer(r"\s+", hedef)]
    return min(bosluk, key=lambda c: abs(c - k)) if bosluk else 0


class _Uretici:
    def __init__(self, kit, diller, baslik=None):
        self.k, self.diller, self.ana = kit, diller, diller[0]
        self.rtl = _dil(self.ana)[1] == "rtl"
        self.arap_harfli = any(_dil(d)[1] == "rtl" for d in diller)
        self.baslik = baslik or self._kunye_baslik(self.ana)
        self.not_no = {}   # n0003 -> 1, 2, 3 (görünüş sırasıyla)
        self.sayfa_listesi = []  # (etiket, href)
        self.fihrist = []  # (seviye, etiket, href)

    def _kunye_baslik(self, d):
        b = self.k["kunye"]["baslik"]
        return b.get(d) or b.get("tr") or b.get(self.k["kunye"].get("asil_dil", "ar")) or "Adsız"

    # ---------- metin ----------
    def _sayfa_span(self, etiket, dosya, goster, gizli=False):
        sid = "s-" + re.sub(r"[^0-9A-Za-z]", "-", etiket)
        if goster:
            self.sayfa_listesi.append((etiket, f"{dosya}#{sid}"))
            return (f'<span class="sayfa" epub:type="pagebreak" role="doc-pagebreak" id="{sid}" '
                    f'aria-label="{X(etiket)}">{"" if gizli else X(etiket)}</span>')
        return ""

    def _metin(self, b, d, dosya, sayfa_goster):
        t = b["metin"].get(d) or ""
        # sayfa işaretleri: bu dilde konum yoksa asıl dilden tahmin edilir
        asil = self.k["kunye"].get("asil_dil", "ar")
        noktalar = []
        for s in b.get("sayfalar", []):
            kn = s.get("konum", {})
            if d in kn:
                p = kn[d]
            else:
                kd = next((x for x in kn if b["metin"].get(x)), asil)
                p = konum_tahmin(b["metin"].get(kd, ""), kn.get(kd, 0), t)
            noktalar.append((min(p, len(t)), s["no"]))
        noktalar.sort(key=lambda x: x[0])
        out, onceki = [], 0
        for j, (p, no) in enumerate(noktalar):
            out.append(self._satir_ici(t[onceki:p], d, b))
            # aynı noktada birden çok sayfa başlıyorsa (boş sayfa): hepsi listede, ekranda sonuncusu
            gizli = j + 1 < len(noktalar) and noktalar[j + 1][0] == p
            out.append(self._sayfa_span(no, dosya, sayfa_goster, gizli))
            onceki = p
        out.append(self._satir_ici(t[onceki:], d, b))
        return "".join(out).strip()

    def _satir_ici(self, parca, d, b):
        def _not(m):
            n = m.group(1)
            if n not in self.not_no:
                self.not_no[n] = len(self.not_no) + 1
            no = self.not_no[n]
            rid = f"r-{d}-{n}"
            self.bolum_notlari.setdefault(n, rid)
            return (f'<a class="notref" epub:type="noteref" role="doc-noteref" id="{rid}" '
                    f'href="#{n}">{no}</a>')
        return K.NOT_ISARETI.sub(_not, X(parca, quote=False))

    # ---------- bölümler ----------
    def bolumler(self):
        """Bloklar 1. seviye başlıklardan dosyalara bölünür."""
        gruplar, cur = [], []
        for b in self.k["bloklar"]:
            if b["tur"] == "baslik" and b.get("seviye", 1) == 1 and cur:
                gruplar.append(cur)
                cur = []
            cur.append(b)
        if cur:
            gruplar.append(cur)
        return gruplar

    def bolum_xhtml(self, bloklar, dosya):
        self.bolum_notlari = {}
        govde, onceki_seviye, ilk_baslik = [], 0, None
        for b in bloklar:
            if b["tur"] == "baslik":
                seviye = min(b.get("seviye", 1), onceki_seviye + 1) if self.fihrist else 1
                onceki_seviye = seviye
                hid = "h-" + b["id"]
                parcalar = []
                for i, d in enumerate(self.diller):
                    if not b["metin"].get(d):
                        continue
                    ic = self._metin(b, d, dosya, i == 0)
                    parcalar.append(ic if i == 0 else f'<span class="ikinci"{_attr(d)}>{ic}</span>')
                etiket = b["metin"].get(self.ana) or next((v for v in b["metin"].values() if v), "")
                etiket = K.NOT_ISARETI.sub("", etiket).strip()
                self.fihrist.append((seviye, etiket, f"{dosya}#{hid}"))
                ilk_baslik = ilk_baslik or etiket
                hs = min(seviye, 6)
                govde.append(f'<h{hs} id="{hid}">{"".join(parcalar)}</h{hs}>')
            else:
                ps = []
                for i, d in enumerate(self.diller):
                    if not b["metin"].get(d):
                        continue
                    sinif = ' class="ikinci"' if i else ""
                    ps.append(f'<p id="{b["id"]}-{d}"{sinif}{_attr(d)}>{self._metin(b, d, dosya, i == 0)}</p>')
                if len(ps) > 1:
                    govde.append(f'<div class="cift" id="{b["id"]}">' + "".join(ps) + "</div>")
                elif ps:
                    govde.append(ps[0])
        if self.bolum_notlari:
            notlar = []
            for n, rid in self.bolum_notlari.items():
                icerik = []
                for d in self.diller:
                    t = self.k["dipnotlar"][n]["metin"].get(d)
                    if t:
                        icerik.append(f"<p{_attr(d)}>{X(t, quote=False)}</p>")
                no = self.not_no[n]
                notlar.append(f'<aside class="dipnot" epub:type="footnote" role="doc-footnote" id="{n}">'
                              f'<p><a class="geri" href="#{rid}">{no}.</a></p>{"".join(icerik)}</aside>')
            govde.append('<section class="notlar-bolum" epub:type="footnotes">' + "".join(notlar) + "</section>")
        return self._sayfa(ilk_baslik or self.baslik, "\n".join(govde), govde_sinif=self.ana)

    def _sayfa(self, baslik, govde, govde_sinif="", ek_bas=""):
        return (f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
                f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"'
                f'{_attr(self.ana)}>\n<head><meta charset="utf-8"/><title>{X(baslik)}</title>'
                f'<link rel="stylesheet" type="text/css" href="../css/kitap.css"/>{ek_bas}</head>\n'
                f'<body class="{govde_sinif}">\n{govde}\n</body>\n</html>\n')

    # ---------- ön sayfalar ----------
    def kunye_xhtml(self):
        ku = self.k["kunye"]
        asil = ku.get("asil_dil", "ar")
        satir = [f'<p class="eser">{X(self.baslik)}</p>']
        for d in self.diller + [asil]:
            b = ku["baslik"].get(d)
            if b and b != self.baslik:
                satir.append(f"<p{_attr(d)}>{X(b)}</p>")
                break
        yazar = ku.get("yazar", {})
        y = yazar.get(self.ana) or yazar.get("tr") or yazar.get(asil) or yazar.get("lat")
        if y:
            yd = self.ana if yazar.get(self.ana) else ("tr" if yazar.get("tr") else asil)
            satir.append(f"<p{_attr(yd) if yazar.get(yd) == y else ''}>{X(y)}</p>")
        if ku.get("vefat_hicri"):
            satir.append(f"<p{_attr('tr')}>(v. {ku['vefat_hicri']} h.)</p>")
        kucuk = []
        kay = ku.get("kaynak", {})
        diller_ad = ", ".join(_dil(d)[2] for d in self.diller)
        kucuk.append(f"Bu sürüm: {X(diller_ad)}")
        if kay.get("tur") == "openiti":
            kucuk.append("Asıl metin: Open Islamicate Texts Initiative (OpenITI), " + X(kay.get("kimlik", "")))
        if kay.get("tur") == "dosya":
            kucuk.append("Kaynak: kişisel kopya (" + X(kay.get("ad", "")) + ")")
            cik = ku.get("cikarma") or {}
            if cik.get("ocr"):
                kucuk.append(f"Metin OCR ile okundu ({cik['ocr']}/{cik.get('sayfa') or cik['ocr']} sayfa); "
                             "okuma hataları kalmış olabilir.")
        if kay.get("baski"):
            kucuk.append(f"Kaynak baskı: <span{_attr(asil)}>{X(kay['baski'])}</span>")
        if ku.get("sayfa_kaynagi"):
            if asil == "tr":
                kucuk.append("Sayfa numaraları basılı baskıya göredir" +
                             ("; Osmanlıcada yaklaşık yerdedir." if "osm" in self.diller else "."))
            else:
                kucuk.append("Sayfa numaraları bu baskıya göredir; çeviride yaklaşık yerdedir.")
        if asil == "tr" and "osm" in self.diller:
            kucuk.append("Osmanlıca metin, Türkçeden otomatik harf çevirisidir.")
        if kay.get("lisans"):
            kucuk.append("Lisans: " + X(kay["lisans"]) + " — ticari olmayan kişisel kullanım içindir.")
        if any(d != asil for d in self.diller) and asil in ("ar", "en", "fr", "fa"):
            kucuk.append("Türkçe ve Osmanlıca metin makine çevirisidir; ilmî alıntıda asıl metne başvurunuz.")
        kucuk.append("Dedplay Kütüphane ile hazırlandı · " + datetime.date.today().isoformat())
        satir.append(f'<div class="kucuk"{_attr("tr")}>' + "".join(f"<p>{k}</p>" for k in kucuk) + "</div>")
        return self._sayfa("Künye", '<section class="kunye" epub:type="frontmatter">' + "".join(satir) + "</section>")

    def kapak_xhtml(self):
        return self._sayfa("Kapak", '<div class="kapak" epub:type="cover"><img src="../resim/kapak.png" '
                                    f'alt="{X(self.baslik)}"/></div>', govde_sinif="kapak")

    def nav_xhtml(self):
        ol, seviye = [], 0
        for sv, etiket, href in self.fihrist:
            if sv > seviye:
                ol.append("<ol>" * (sv - seviye))
            else:
                ol.append("</li>" + "</ol></li>" * (seviye - sv))
            ol.append(f'<li><a href="metin/{href}">{X(etiket)}</a>')
            seviye = sv
        ol.append("</li>" + "</ol></li>" * (seviye - 1) + "</ol>")
        fihrist = "".join(ol) if self.fihrist else '<ol><li><a href="metin/kunye.xhtml">Künye</a></li></ol>'
        sayfalar = "".join(f'<li><a href="metin/{h}">{X(e)}</a></li>' for e, h in self.sayfa_listesi)
        ilk = self.fihrist[0][2] if self.fihrist else "kunye.xhtml"
        govde = (f'<nav epub:type="toc" id="toc" role="doc-toc"{_attr(self.ana)}><h1>{X(self._fihrist_adi())}</h1>{fihrist}</nav>\n'
                 + (f'<nav epub:type="page-list" id="page-list" hidden="hidden"><h2>Sayfalar</h2><ol>{sayfalar}</ol></nav>\n'
                    if sayfalar else "")
                 + '<nav epub:type="landmarks" id="landmarks" hidden="hidden"><h2>Yer imleri</h2><ol>'
                 '<li><a epub:type="cover" href="metin/kapak.xhtml">Kapak</a></li>'
                 '<li><a epub:type="toc" href="nav.xhtml">Fihrist</a></li>'
                 f'<li><a epub:type="bodymatter" href="metin/{ilk}">Metin</a></li></ol></nav>')
        return (self._sayfa(self._fihrist_adi(), govde)
                .replace('href="../css/kitap.css"', 'href="css/kitap.css"'))

    def _fihrist_adi(self):
        return {"ar": "الفهرس", "osm": "فهرست"}.get(self.ana, "Fihrist")


def uret(kit, diller, cikti_yolu=None, baslik=None, kapak_png=None):
    """EPUB baytlarını döndürür (cikti_yolu verilirse oraya da yazar)."""
    u = _Uretici(kit, diller, baslik)
    kimlik = kit["kunye"].get("kaynak", {}).get("kimlik") or u.baslik
    uid = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "dedplay-kutuphane/" + kimlik + "/" + "-".join(diller)))
    dosyalar = []  # (arşivdeki yol, içerik, medya türü, manifest id, özellikler)
    bolumler = u.bolumler()
    icerik = []
    for i, grup in enumerate(bolumler, 1):
        ad = f"bolum_{i:03d}.xhtml"
        icerik.append((f"OEBPS/metin/{ad}", u.bolum_xhtml(grup, ad), f"b{i:03d}"))
    ku = kit["kunye"]
    yazar = ku.get("yazar", {})
    if kapak_png is None:
        asil = ku.get("asil_dil", "ar")
        alt = ku["baslik"].get(asil) if ku["baslik"].get(asil) != u.baslik else ""
        kapak_png = KAPAK.uret(u.baslik, yazar.get(u.ana) or yazar.get("tr") or yazar.get(asil, ""), alt=alt or "")
    dosyalar.append(("OEBPS/resim/kapak.png", kapak_png, "image/png", "kapak-resmi", "cover-image"))
    dosyalar.append(("OEBPS/css/kitap.css", CSS if u.arap_harfli else re.sub(r"@font-face[^}]*}\n", "", CSS),
                     "text/css", "css", None))
    if u.arap_harfli:
        fdir = next((f for f in FONT_ADAY if os.path.exists(os.path.join(f, "Amiri-Regular.ttf"))), None)
        if not fdir:
            raise FileNotFoundError("Amiri yazı tipi bulunamadı")
        for ad in ("Amiri-Regular.ttf", "Amiri-Bold.ttf"):
            dosyalar.append((f"OEBPS/fonts/{ad}", open(os.path.join(fdir, ad), "rb").read(), "font/ttf",
                             ad.split(".")[0].lower(), None))
    dosyalar.append(("OEBPS/metin/kapak.xhtml", u.kapak_xhtml(), "application/xhtml+xml", "kapak", None))
    dosyalar.append(("OEBPS/metin/kunye.xhtml", u.kunye_xhtml(), "application/xhtml+xml", "kunye", None))
    dosyalar.append(("OEBPS/nav.xhtml", u.nav_xhtml(), "application/xhtml+xml", "nav", "nav"))
    for yol, xh, mid in icerik:
        dosyalar.append((yol, xh, "application/xhtml+xml", mid, None))

    lang = _dil(u.ana)[0]
    simdi = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = [f'<dc:identifier id="kimlik">{uid}</dc:identifier>', f"<dc:title>{X(u.baslik)}</dc:title>"]
    for d in dict.fromkeys(diller):
        meta.append(f"<dc:language>{_dil(d)[0]}</dc:language>")
    y = yazar.get(u.ana) or yazar.get("tr") or yazar.get(ku.get("asil_dil", "ar")) or yazar.get("lat")
    if y:
        meta.append(f"<dc:creator>{X(y)}</dc:creator>")
    kay = ku.get("kaynak", {})
    if kay.get("adres"):
        meta.append(f"<dc:source>{X(kay['adres'])}</dc:source>")
    if kay.get("lisans"):
        meta.append(f"<dc:rights>{X(kay['lisans'])}</dc:rights>")
    meta.append("<dc:publisher>Dedplay Kütüphane</dc:publisher>")
    meta.append(f'<meta property="dcterms:modified">{simdi}</meta>')
    meta.append('<meta name="cover" content="kapak-resmi"/>')
    manifest = [f'<item id="{mid}" href="{yol[6:]}" media-type="{mt}"' + (f' properties="{oz}"' if oz else "") + "/>"
                for yol, _, mt, mid, oz in dosyalar]
    spine = ['<itemref idref="kapak" linear="yes"/>', '<itemref idref="kunye"/>']
    spine += [f'<itemref idref="{mid}"/>' for _, _, mid in icerik]
    spine.append('<itemref idref="nav"/>')  # fihrist sayfası kitabın sonunda (liste düğmesi yine çalışır)
    ppd = ' page-progression-direction="rtl"' if u.rtl else ""
    opf = (f'<?xml version="1.0" encoding="utf-8"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
           f'unique-identifier="kimlik" xml:lang="{lang}" dir="{"rtl" if u.rtl else "ltr"}">\n'
           f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n' + "\n".join(meta) + "\n</metadata>\n"
           f"<manifest>\n" + "\n".join(manifest) + f"\n</manifest>\n<spine{ppd}>\n" + "\n".join(spine)
           + "\n</spine>\n</package>\n")
    container = ('<?xml version="1.0" encoding="utf-8"?>\n<container version="1.0" '
                 'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                 '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles></container>\n')
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        for yol, veri, *_ in dosyalar:
            z.writestr(yol, veri, compress_type=zipfile.ZIP_DEFLATED)
    veri = b.getvalue()
    if cikti_yolu:
        with open(cikti_yolu, "wb") as f:
            f.write(veri)
    return veri
