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


def calibre_epub(yol):
    """Calibre'nin ürettiği tipteki EPUB (Işık Doğudan Gelir yapısı): başlıklar sınıflı <p>, fihrist NCX'te,
    satırlar ya dosya başını ya başlığın id'sini gösterir; ön sayfalar; bozuk başlık yazısı; ' ’ ' boşlukları."""
    from ebooklib import epub
    b = epub.EpubBook(); b.set_identifier("calibre1"); b.set_title("Işık Doğudan Gelir"); b.set_language("tr")
    b.add_author("Cemil Meriç")
    def belge(ad, govde):
        d = epub.EpubHtml(title=ad, file_name=ad, lang="tr"); d.content = "<html><body>" + govde + "</body></html>"; b.add_item(d); return d
    kapak = belge("titlepage.xhtml", '<div><p> </p></div>')
    s0 = belge("index_split_000.html", '<p class="block_1">IŞIK DOĞUDAN GELİR</p><p class="block_2">(EX ORİENTE LUX)</p>'
               '<p class="block_1">CEMİL MERİÇ</p><p class="block_4">PINAR YAY I NLAR I</p>')
    s1 = belge("index_split_001.html", '<p class="block_7">İçindekiler</p>'
               '<p class="block_8"><a href="index_split_002.html#id_Toc1">MEDENİYETLERİN DEFTER-İ AMALİ: ANSİKLOPEDİLER</a></p>'
               '<p class="block_9"><a href="index_split_002.html#id_Toc2">BİR TÜRÜN TARİH ÖNCESİ</a></p>'
               '<p class="block_8"><a href="index_split_003.html#id_Toc3">II — İSLÂM’DA ANSİKLOPEDİ</a></p>')
    s2 = belge("index_split_002.html", '<p class="block_11" id="id_Toc1">MEDENİYETLERİN DEFTER-İ AMALİ: ANSİKLOPEDİLER</p>'
               '<p class="block_12"></p><p class="block_13" id="id_Toc2">I-BATIDA ANSİKLOPEDİ</p>'
               '<p class="block_14" id="id_Toc3">BİR TÜRÜN TARİH ÖNCESİ</p>'
               '<p class="block_15">Dilimize Fransızcadan aktarılmış ansiklopedi… Önce lisan iffetimizi korumaya çalışmışız.</p>'
               '<p class="block_15">Yunanca aslı: «enkuklios paideia» yani bütün ilimleri kucaklayan eğitim.</p>'
               '<p class="block_14" id="id_Toc4">BELGELER TEORİSİ.</p><p class="block_15">1) Birinci madde burada.</p>')
    s3 = belge("index_split_003.html", '<p class="block_16" id="id_Toc5">II — İSLÂM ’ DA ANSİKLOPEDİ</p>'
               '<p class="block_15">Onsekizinci Asır Ansiklopedisi üzerinde çok durduk.</p>')
    s4 = belge("index_split_004.html", '<p class="block_18" id="id_Toc6">İ SLÂMIN KOZMOLOJİK DOKTRİNLE R İ</p>'
               '<p class="block_15">Hüseyin Nasır ’ ın <a href="index_split_013.html#note_2">( 2 )</a> tezini okurken bunu anladım.</p>')
    s5 = belge("index_split_005.html", '<p class="block_15">Doğu kütüphanesi hakkında bir giriş paragrafı, başlıksız.</p>')
    n = belge("index_split_013.html", '<p class="block_20" id="note_2"><a href="index_split_004.html">2</a> The Cosmological Doctrines, 1964.</p>')
    L = lambda h, t: epub.Link(h, t, h)
    b.toc = [L("index_split_002.html", "MEDENİYETLERİN DEFTER-İ AMALİ: ANSİKLOPEDİLER"),
             (epub.Section("I-BATIDA ANSİKLOPEDİ", "index_split_002.html#id_Toc2"),
              [L("index_split_002.html#id_Toc3", "BİR TÜRÜN TARİH ÖNCESİ"), L("index_split_002.html#id_Toc4", "BELGELER TEORİSİ.")]),
             (epub.Section("II — İSLÂM’DA ANSİKLOPEDİ", "index_split_003.html"),
              [L("index_split_004.html", "İSLÂMIN KOZMOLOJİK DOKTRİNLERİ")]),
             L("index_split_005.html", "DOĞU KÜTÜPHANESİ")]
    b.add_item(epub.EpubNcx()); b.add_item(epub.EpubNav())
    b.spine = [kapak, s0, s1, s2, s3, s4, s5, n]
    epub.write_epub(yol, b)


# ---- Basılı içindekilerden fihrist (Klasik Mantık tipi): başlıklar gövdeyle aynı puntoda (kalın), içindekiler iki
# sayfa, girintili alt başlıklar, numarasız "BİRİNCİ BÖLÜM" satırı, iki satıra bölünmüş girdi, sayfa ortasında başlık
M1 = ("Mantık, doğru düşünmenin kurallarını inceleyen bir ilimdir. Zihnin bilinenden bilinmeyene nasıl geçtiğini "
      "gösterir ve bu geçişte yapılabilecek yanlışlardan korunmanın yollarını öğretir.")
M2 = ("Her ilmin bir konusu, bir de gayesi vardır. Mantığın konusu malum kavramlar ve önermelerdir; gayesi ise "
      "düşünceyi hatadan korumaktır. Bu sebeple eskiler ona alet ilmi adını vermişlerdir.")
M3 = ("Kavram, bir şeyin zihindeki tasavvurudur. Kavramlar kelimelerle ifade edilir; fakat kelime ile kavram aynı "
      "şey değildir, zira bir kavram farklı dillerde farklı kelimelerle anlatılabilir.")
TOC_SAYFA1 = [(0, "ÖNSÖZ", "7"), (0, "GİRİŞ", "8"), (0, "BİRİNCİ BÖLÜM", None), (0, "KAVRAMLAR", "9"),
              (1, "Kavramın Tanımı", "9"), (1, "Kavramların Birbirine Göre Durumları ve Beş Tümel", None), (1, "Meselesi", "11")]
TOC_SAYFA2 = [(0, "İKİNCİ BÖLÜM", None), (0, "ÖNERMELER", "12"), (1, "Önermenin Tanımı", "12"),
              (1, "Karşıt Önermeler", "13"), (0, "SONUÇ", "14")]
MANTIK_GOVDE = [  # her öğe bir basılı sayfa (7'den başlar): ("ob", orta başlık) ("b", sol başlık) ("p", paragraf) ("k", kalın satır)
    [("ob", "ÖNSÖZ"), ("p", M1), ("p", M2)],
    [("ob", "GİRİŞ"), ("p", M2), ("p", M3)],
    [("ob", "BİRİNCİ BÖLÜM"), ("ob", "KAVRAMLAR"), ("p", M1), ("b", "Kavramın Tanımı"), ("p", M3), ("k", "Örnek"), ("p", M2)],
    [("p", M1 + " " + M2), ("p", M3)],
    [("b", "Kavramların Birbirine Göre Durumları"), ("b", "ve Beş Tümel Meselesi"), ("p", M3), ("p", M1)],
    [("ob", "İKİNCİ BÖLÜM"), ("ob", "ÖNERMELER"), ("b", "Önermenin Tanımı"), ("p", M2), ("p", M3)],
    [("p", M1), ("b", "Karşıt Önermeler"), ("p", M2)],
    [("ob", "SONUÇ"), ("p", M3)],
]


ACILIS_LISTE = (["Eski mantıkçılar bu konuyu uzun uzun tartışmıştır.", "Meseleyi bir misal ile açalım.",
               "Burada dikkat edilecek nokta şudur.", "Bu bahis kitabın temelini teşkil eder.",
               "Konuya başka bir yönden de bakılabilir.", "Şimdi asıl meseleye geçebiliriz.",
               "Farabi bu hususta şöyle bir ayrım yapar.", "İbn Sina aynı görüşü daha açık ifade etmiştir.",
               "Bu görüş sonraki asırlarda da kabul görmüştür.", "Kısaca söylemek gerekirse durum budur.",
               "Bir örnek vermek faydalı olacaktır.", "Şu itiraz akla gelebilir.", "Cevabı açıktır.",
               "Bu noktada iki görüş vardır.", "Birinci görüşe göre mesele basittir.", "İkinci görüş daha inceliklidir.",
               "Netice itibarıyla ikisi de aynı yere varır.", "Bunu ileride tekrar ele alacağız."])


def mantik_pdf(yol, kip="katman"):
    tmp = fitz.open()
    acilis = iter(list(ACILIS_LISTE))

    def sayfa():
        p = tmp.new_page(width=W, height=H)
        p.insert_font(fontname="F", fontfile=SERIF); p.insert_font(fontname="B", fontfile=SERIF_B)
        return p
    p = sayfa(); p.insert_text((80, 250), "KLASİK MANTIK DENEMESİ", fontname="B", fontsize=18)
    p = sayfa(); p.insert_text((SOL, UST), "Deneme Yayınları · ISBN 978-000-0000-00-0", fontname="F", fontsize=9)
    for k, girdiler in enumerate((TOC_SAYFA1, TOC_SAYFA2)):
        p = sayfa(); y = UST
        if k == 0:
            p.insert_text((150, y), "İÇİNDEKİLER", fontname="B", fontsize=BAS2); y += 30
        for girinti, bas, no in girdiler:
            x = SOL + 15 * girinti
            p.insert_text((x, y), bas, fontname="F", fontsize=GOVDE)
            if no:
                bas_son = x + font_w(bas, SERIF, GOVDE) + 4
                no_x = SAG - font_w(no, SERIF, GOVDE)
                nokta = "." * int((no_x - bas_son - 4) / font_w(".", SERIF, GOVDE))
                p.insert_text((bas_son, y), nokta, fontname="F", fontsize=GOVDE)
                p.insert_text((no_x, y), no, fontname="F", fontsize=GOVDE)
            y += GOVDE * 1.8
    for n, ogeler in enumerate(MANTIK_GOVDE):
        p = sayfa(); y = UST
        p.insert_text((W / 2 - 6, H - 30), str(7 + n), fontname="F", fontsize=9)
        for tur, metin in ogeler:
            if tur == "ob":
                p.insert_text((SOL + (SAG - SOL - font_w(metin, SERIF_B, GOVDE)) / 2, y), metin, fontname="B", fontsize=GOVDE)
                y += GOVDE * 1.9
            elif tur in ("b", "k"):
                y += 4
                p.insert_text((SOL, y), metin, fontname="B", fontsize=GOVDE); y += GOVDE * 1.7
            else:
                metin = next(acilis) + " " + metin  # tekrar eden satır üst bilgi sanılmasın
                for j, sat in enumerate(satirlar(metin, SERIF, GOVDE, SAG - SOL - 18)):
                    p.insert_text((SOL + (18 if j == 0 else 0), y), sat, fontname="F", fontsize=GOVDE); y += GOVDE * 1.45
                y += 2
    if kip == "katman":
        tmp.save(yol); return
    out = fitz.open()
    for p in tmp:
        yeni = out.new_page(width=W, height=H)
        yeni.insert_image(yeni.rect, stream=p.get_pixmap(dpi=200).tobytes("png"))
    out.save(yol)


# ---- Klasik Mantık'ın gerçek içindekiler biçimi: eski OCR katmanlı PDF. Başlık bozuk ("iONDEKİ LER"), nokta dizisi
# yok, sayfa numarası sağda AYRI satır (daha büyük), bölüm başlıkları ortada numarasız iki satır ("Birinci Bölüm" /
# "Kavram ve Treim"), OCR hataları ("Mantık nedir 9" aslı 1, "özelliğı"), numarasız girdi, roma rakamlı önsöz
KM_TOC = [("sol", "Önsöz", "v"), ("orta", "GİRİŞ", None), ("sol", "Mantık nedir", "9küçük"), ("sol", "Tarihsel bilgi", "3"),
          ("orta", "Birinci Bölüm", None), ("orta", "Kavram ve Treim", None), ("sol", "Kavramın tanımı", "5"),
          ("sol", "Kavramın özelliğı", "6"), ("sol", "Önerme çeşitleri", None), ("sol", "Yüklemli önermeler", "7"),
          ("orta", "İkinci Bölüm", None), ("orta", "Önerme", None), ("sol", "Önermenin tanımı", "8"), ("sol", "Karşı olma", "9"),
          ("sol", "Kıyas", "10"), ("sol", "Kıyasın tanımı", "10"), ("sol", "Kıyasın çeşitleri", "10"),
          ("sol", "Döndürme", "11"),
          ("sol", "Tümevarım", "11")]
KM_GOVDE = [  # (basılı no, öğeler)
    ("v", [("ob", "ÖNSÖZ"), ("p", M1)]), ("vi", [("p", M2)]),
    ("1", [("og", "G İ R İ Ş"), ("b", "I. Mantık Nedir?"), ("p", M1)]), ("2", [("p", M2)]),
    ("3", [("b", "II. Tarihsel Bilgi"), ("p", M3)]), ("4", [("p", M1)]),
    ("5", [("ob", "BİRİNCİ BÖLÜM"), ("ob", "KAVRAM VE TERİM"), ("b", "Kavramın tanımı"), ("p", M2)]),
    ("6", [("p", M3), ("b", "KAVRAMIN ÖZELLİĞİ"), ("p", M1)]),
    ("7", [("b", "Önerme çeşitleri"), ("b", "Yüklemli önermeler"), ("p", M2), ("k", "Düz döndürme:"), ("p", M3)]),
    ("8", [("ob", "İKİNCİ BÖLÜM"), ("ob", "ÖNERME"), ("b", "Önermenin tanımı"), ("p", M1)]),
    ("9", [("p", M2), ("b", "Karşı olma"), ("p", M3), ("b", "Bu kısımda ele alınan meseleler"),
           ("b", "üç ana başlık altında toplanır"), ("p", M1)]),
    ("10", [("b", "Kıyasm tanımı :"), ("p", M1), ("b", "Kıyas çeşitleri:"), ("p", M2)]),
    ("11", [("k", "Düz döndürme:"), ("p", M3), ("b", "TUMEVAR1M"), ("b", "Bu mesele eskiden beri tartışılan"),
            ("p0", "bir konudur ve burada kısaca ele alınır.")]),
]


def klasik_mantik_pdf(yol):
    tmp = fitz.open()
    acilis = iter(list(ACILIS_LISTE) * 2)

    def sayfa():
        p = tmp.new_page(width=W, height=H)
        p.insert_font(fontname="F", fontfile=SERIF); p.insert_font(fontname="B", fontfile=SERIF_B)
        return p
    p = sayfa(); p.insert_text((80, 250), "KLASIK MANTIK", fontname="B", fontsize=22)
    p = sayfa(); y = UST
    p.insert_text((135, y), "iONDEKİ LER", fontname="B", fontsize=16); y += 30
    for yer, bas, no in KM_TOC:
        x = SOL + 10 if yer == "sol" else SOL + (SAG - SOL - font_w(bas, SERIF, GOVDE)) / 2
        p.insert_text((x, y), bas, fontname="F", fontsize=GOVDE)
        if no and no.endswith("küçük"):  # başlığa yapışık küçük puntolu numara (dipnot işareti sanılır)
            p.insert_text((x + font_w(bas, SERIF, GOVDE) + 1, y - 3), no[:-5], fontname="F", fontsize=7)
        elif no:  # ayrı ve büyük yazılmış numara (eski OCR katmanı böyle bölmüş)
            p.insert_text((SAG - 25, y + 1.5), no, fontname="F", fontsize=15)
        y += GOVDE * 1.9
    for no, ogeler in KM_GOVDE:
        p = sayfa(); y = UST
        p.insert_text((W / 2 - 6, H - 30), no, fontname="F", fontsize=9)
        for tur, metin in ogeler:
            if tur == "ob":
                p.insert_text((SOL + (SAG - SOL - font_w(metin, SERIF_B, GOVDE)) / 2, y), metin, fontname="B", fontsize=GOVDE)
                y += GOVDE * 1.9
            elif tur == "og":  # büyük ilk harf ayrı parça (eski OCR katmanı "G" ve "İ R İ Ş"i ayrı yazmış)
                x = SOL + (SAG - SOL - font_w(metin, SERIF_B, GOVDE)) / 2
                p.insert_text((x, y + 1), metin[0], fontname="B", fontsize=GOVDE + 2)
                p.insert_text((x + 20, y), metin[1:].strip(), fontname="B", fontsize=GOVDE)
                y += GOVDE * 1.9
            elif tur in ("b", "k"):
                y += 4
                p.insert_text((SOL, y), metin, fontname="B", fontsize=GOVDE); y += GOVDE * 1.7
            elif tur == "p0":  # önceki (kalın) satırın devamı: girintisiz
                y -= GOVDE * 0.25
                for sat in satirlar(metin, SERIF, GOVDE, SAG - SOL):
                    p.insert_text((SOL, y), sat, fontname="F", fontsize=GOVDE); y += GOVDE * 1.45
            else:
                metin = next(acilis) + " " + metin
                for j, sat in enumerate(satirlar(metin, SERIF, GOVDE, SAG - SOL - 18)):
                    p.insert_text((SOL + (18 if j == 0 else 0), y), sat, fontname="F", fontsize=GOVDE); y += GOVDE * 1.45
                y += 2
    tmp.save(yol)
