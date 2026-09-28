"""Deneme kitapları: gerçek Türkçe kitaplardaki sorunları taşıyan PDF'ler (metin katmanlı, taranmış, bozuk katmanlı)."""
import fitz  # PyMuPDF

import os
SERIF = next(f for f in ([] if os.environ.get("FIXTUR_DEJAVU") else ["/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf"]) + ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"] if os.path.exists(f))
SERIF_B = next(f for f in ([] if os.environ.get("FIXTUR_DEJAVU") else ["/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf"]) + ["/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"] if os.path.exists(f))
W, H = 420, 640          # sayfa (pt)
SOL, SAG, UST = 50, 370, 70
GOVDE, DIP, BAS1, BAS2 = 11, 8, 16, 13

P1 = ("Bu kitapta ele alınan meseleler, itikadın temel esaslarına dairdir. Müellif, akıl ile naklin "
      "birbirine zıt olmadığını göstermek için delilleri tertip etmiş ve her meseleyi kendi yerinde açıklamıştır.")
P2 = ("İlmin şerefi, konusunun şerefine bağlıdır. Allah Teâlâ'nın zâtı, sıfatları ve fiilleri hakkındaki bilgi, "
      "bütün bilgilerin en yücesidir. Bu sebeple kelâm ilmi, dinî ilimler arasında müstesna bir yere sahiptir.")
P3 = ("Şunu bilmek gerekir ki, her müslümanın bu ilmin bütün inceliklerini öğrenmesi farz değildir; fakat "
      "şüpheye düşen kimsenin şüphesini giderecek kadar bilgiye sahip olması lazımdır.")

def satirlar(metin, font, boy, genislik):
    kel, out, cur = metin.split(), [], ""
    for k in kel:
        d = (cur + " " + k).strip()
        if fitz.get_text_length(d, fontname="F", fontfile=font, fontsize=boy) if False else font_w(d, font, boy) <= genislik or not cur:
            cur = d
        else:
            out.append(cur); cur = k
    if cur: out.append(cur)
    return out

_f = {}
def font_w(s, font, boy):
    if font not in _f: _f[font] = fitz.Font(fontfile=font)
    return _f[font].text_length(s, fontsize=boy)

class Kitap:
    def __init__(self):
        self.sayfalar = []  # her sayfa: [(x, y, metin, font, boy)]
        self.yeni()
    def yeni(self):
        self.s = []; self.sayfalar.append(self.s); self.y = UST
    def yaz(self, x, metin, font=SERIF, boy=GOVDE):
        self.s.append((x, self.y, metin, font, boy)); self.y += boy * 1.45

def kitap():
    k = Kitap()
    # 1 kapak
    k.y = 250; k.yaz(90, "İTİKADDA ORTA YOL", SERIF_B, 20); k.y += 20; k.yaz(140, "İmam Gazzâlî", SERIF, 14)
    # 2 künye
    k.yeni()
    for s in ["Deneme Yayınları: 12", "ISBN 978-975-0000-00-0", "Baskı: Örnek Matbaası, İstanbul 1998",
              "Tüm hakları saklıdır. Tel: 0212 000 00 00", "www.ornekyayin.com.tr"]:
        k.yaz(SOL, s, SERIF, 9)
    # 3 içindekiler
    k.yeni(); k.yaz(150, "İÇİNDEKİLER", SERIF_B, BAS2)
    for s in ["ÖNSÖZ ........................ 5", "BİRİNCİ BÖLÜM ................ 6", "İKİNCİ BÖLÜM ................. 7",
              "Kelâmın Önemi ................ 7", "SONUÇ ........................ 8"]:
        k.yaz(SOL, s)
    return k

def govde_sayfalari():
    """Asıl metin: (tür, metin) listesi; 'b1','b2' başlık, 'p' paragraf, 'kes' sayfa sonu."""
    return [
        ("b1", "ÖNSÖZ"), ("p", P1), ("p", P2 + "¹ " + P3),
        ("kes", None),
        ("b1", "BİRİNCİ BÖLÜM"), ("b2", "İlmin Şerefi"), ("p", P2 + "² Bu konuda icmâ vardır."), ("p", P3 + " " + P1 + " " + P2 + " " + P3 + " " + P1),
        ("kes", None),
        ("tire", ("Bu ilmin öğrenilmesi, şüphe ortaya çıktığında zorun", "lu hâle gelir ve âlimler bunu açıkça ifade etmişlerdir.")), ("kes", None), ("b1", "İKİNCİ BÖLÜM"), ("b2", "Kelâmın Önemi"), ("p", P1 + " " + P2),
        ("p", "1. Birinci madde: aklın hükmü."), ("p", "2. İkinci madde: naklin hükmü."),
        ("kes", None),
        ("b1", "SONUÇ"), ("p", P3),
    ]

NOTLAR = {1: "Gazzâlî, el-İktisâd, s. 4.", 2: "Bu konudaki ihtilaflar için bkz. İbn Haldun, Mukaddime."}

def dizgi():
    k = kitap()
    k.yeni()
    basli = 5  # ilk metin sayfasının basılı numarası
    sayfa_no = {len(k.sayfalar) - 1: basli}
    notlar_sayfa = {}
    def sayfa_kes():
        k.yeni(); sayfa_no[len(k.sayfalar) - 1] = sayfa_no[len(k.sayfalar) - 2] + 1
    for tur, metin in govde_sayfalari():
        if tur == "kes":
            sayfa_kes(); continue
        if tur == "tire":
            k.yaz(SOL + 18, metin[0] + "-"); sayfa_kes(); k.yaz(SOL, metin[1]); continue
        if tur == "b1":
            k.y += 10; k.yaz(SOL + (SAG - SOL - font_w(metin, SERIF_B, BAS1)) / 2, metin, SERIF_B, BAS1); k.y += 6; continue
        if tur == "b2":
            k.yaz(SOL + (SAG - SOL - font_w(metin, SERIF_B, BAS2)) / 2, metin, SERIF_B, BAS2); k.y += 4; continue
        ilk = True
        for sat in satirlar(metin, SERIF, GOVDE, SAG - SOL - 18):
            if k.y > H - 130:  # sayfa taşması: paragraf sonraki sayfada sürer
                sayfa_kes()
            x = SOL + (18 if ilk else 0); ilk = False
            for n in (1, 2):
                if "¹²"[n - 1] in sat:
                    notlar_sayfa.setdefault(len(k.sayfalar) - 1, []).append(n)
            k.yaz(x, sat)
    return k, sayfa_no, notlar_sayfa

def pdf_yaz(yol, kip):
    """kip: 'katman' (metin), 'tarama' (resim), 'bozuk' (resim + bozuk görünmez katman)"""
    k, sayfa_no, notlar_sayfa = dizgi()
    tmp = fitz.open()
    for i, s in enumerate(k.sayfalar):
        p = tmp.new_page(width=W, height=H)
        p.insert_font(fontname="F", fontfile=SERIF); p.insert_font(fontname="B", fontfile=SERIF_B)
        if i in sayfa_no:  # üst bilgi + alt sayfa numarası
            p.insert_text((SOL, 40), "İTİKADDA ORTA YOL", fontname="F", fontsize=8)
            p.insert_text((W / 2 - 6, H - 30), str(sayfa_no[i]), fontname="F", fontsize=9)
        for x, y, metin, font, boy in s:
            fn = "B" if font == SERIF_B else "F"
            parca = metin.split("¹") if "¹" in metin else metin.split("²") if "²" in metin else [metin]
            if len(parca) == 2:
                n = "1" if "¹" in metin else "2"
                p.insert_text((x, y), parca[0], fontname=fn, fontsize=boy)
                x2 = x + font_w(parca[0], font, boy)
                p.insert_text((x2, y - 4), n, fontname=fn, fontsize=boy * 0.6)
                p.insert_text((x2 + font_w(n, font, boy * 0.6), y), parca[1], fontname=fn, fontsize=boy)
            else:
                p.insert_text((x, y), metin, fontname=fn, fontsize=boy)
        yd = H - 110
        for n in notlar_sayfa.get(i, []):  # dipnotlar
            p.draw_line((SOL, yd - 10), (SOL + 100, yd - 10), width=0.5)
            p.insert_text((SOL, yd), f"{n} {NOTLAR[n]}", fontname="F", fontsize=DIP); yd += 12
    if kip == "katman":
        tmp.save(yol); return
    out = fitz.open()
    for i, p in enumerate(tmp):
        pix = p.get_pixmap(dpi=200)
        yeni = out.new_page(width=W, height=H)
        yeni.insert_image(yeni.rect, stream=pix.tobytes("png"))
        if kip == "bozuk":  # eski OCR katmanı: Türkçe harfler kaybolmuş, görünmez (render_mode=3)
            bozuk = p.get_text().translate(str.maketrans("şŞğĞıİ", "  g I "))
            yeni.insert_font(fontname="F", fontfile=SERIF)
            yeni.insert_textbox(fitz.Rect(SOL, UST, SAG, H - 40), bozuk, fontname="F", fontsize=9, render_mode=3)
    out.save(yol)



def hepsini_uret(klasor):
    """Deneme dosyalarını klasöre yazar: üç PDF türü, EPUB, DOCX, TXT."""
    os.makedirs(klasor, exist_ok=True)
    for kip in ("katman", "tarama", "bozuk"):
        pdf_yaz(os.path.join(klasor, f"deneme_{kip}.pdf"), kip)
    from ebooklib import epub
    import docx
    b = epub.EpubBook(); b.set_identifier("x1"); b.set_title("Mârifetnâme"); b.set_language("tr"); b.add_author("Erzurumlu İbrahim Hakkı")
    ic = epub.EpubHtml(title="İçindekiler", file_name="ic.xhtml", lang="tr")
    ic.content = "<html><body><h1>İçindekiler</h1><p>Mukaddime .......... 3</p><p>Birinci Bâb .......... 5</p><p>Yayınevi: Deneme · ISBN 000</p></body></html>"
    c1 = epub.EpubHtml(title="Mukaddime", file_name="c1.xhtml", lang="tr")
    c1.content = ('<html><body><h1>Mukaddime</h1><p><span epub:type="pagebreak" id="page3" title="3"/>Hamd, âlemlerin Rabbi olan Allah\'adır. '
                  'Bu kitap, marifetin yollarını beyan eder.<a href="notlar.xhtml#fn1" id="r1">[1]</a> İnsan kendini bilmekle Rabbini bilir.</p></body></html>')
    c2 = epub.EpubHtml(title="Birinci Bâb", file_name="c2.xhtml", lang="tr")
    c2.content = ('<html><body><h1>Birinci Bâb</h1><h2>Birinci Fasıl</h2><p><span epub:type="pagebreak" id="page5" title="5"/>'
                  'Göklerin ve yerin yaratılışı hakkındadır.<sup><a href="notlar.xhtml#fn2">2</a></sup></p>'
                  '<p>Yıldızların hareketi, bir nizam üzere cereyan eder; <span epub:type="pagebreak" id="page6" title="6"/>bu nizam hikmete delildir.</p></body></html>')
    n = epub.EpubHtml(title="Notlar", file_name="notlar.xhtml", lang="tr")
    n.content = ('<html><body><h1>Notlar</h1><ol><li id="fn1"><a href="c1.xhtml#r1">[1]</a> Hadis-i şerif olarak rivayet edilir.</li>'
                 '<li id="fn2">2. Bkz. Mârifetnâme, s. 12.</li></ol></body></html>')
    for x in (ic, c1, c2, n):
        b.add_item(x)
    b.toc = [c1, c2]; b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav()); b.spine = [ic, c1, c2, n]
    epub.write_epub(os.path.join(klasor, "Erzurumlu Ibrahim Hakki - Marifetname.epub"), b)
    d = docx.Document()
    d.add_heading("Risale-i Deneme", 0)
    d.add_heading("Birinci Kısım", 1); d.add_paragraph("Bu risale, ilmin fazileti hakkındadır.")
    d.add_heading("İlmin Tarifi", 2); d.add_paragraph("İlim, bir şeyi olduğu gibi bilmektir.")
    d.core_properties.title = "Risale-i Deneme"
    d.save(os.path.join(klasor, "deneme.docx"))
    open(os.path.join(klasor, "deneme.txt"), "w", encoding="utf-8").write(
        "MUKADDİME\n\nBu metin düz yazı dosyasıdır.\n\nBİRİNCİ BÖLÜM\n\nİkinci paragraf burada başlar ve sonra\ndevam eder.\n")
