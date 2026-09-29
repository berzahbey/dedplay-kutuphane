"""Elindeki kitaplar (PDF, EPUB, DOCX, TXT) -> kitap.json (Türkçe).

Stüdyo'nun metin kodu (app.textsrc, app.duzelt) kullanılır; ondan farklı olarak burada
basılı sayfa numaraları, başlıklar (fihrist için) ve dipnot bağlantıları KORUNUR.

İç işaretler (özel kullanım alanı karakterleri):
  \\ue000n\\ue001  metindeki dipnot numarası (sayfanın dipnotuna bağlanmadan önce)
  \\ue002etiket\\ue003  basılı sayfa başlangıcı (düzeltmeden sonra konuma çevrilir)
  {{n0001}}  bağlanmış dipnot atfı (kitap.json biçimi)
"""
import collections
import hashlib
import io
import os
import re
import statistics as st
import unicodedata
from concurrent.futures import ProcessPoolExecutor

from . import kitap as K

try:  # Stüdyo'nun kodu (imajda /app/app)
    from app import duzelt as DZ
    from app import textsrc as TS
except ImportError:  # pragma: no cover
    DZ = TS = None

UST = re.compile(r"\ue000(\d{1,3})\ue001")
SAYFA_ISARET = re.compile(r"\ue002([^\ue003]{1,20})\ue003")
END_PUNCT = tuple('.!?:;"”»)]…')
YAPISIK = re.compile(r"(?<=[a-zçğıöşüâîû\.,;:])(\d{1,2})(?=[\s.,;:!?”\"')]|$)")
BOLUM_NO = re.compile(r"^(birinci|ikinci|üçüncü|dördüncü|beşinci|altıncı|yedinci|sekizinci|dokuzuncu|onuncu|"
                      r"\d{1,2}\.?|[ivxlc]{1,6}\.?)\s+(bölüm|kısım|fasıl|bab|kitap|makale|mektup|risale)[.:]?$", re.I)
OCR_DPI = 300


def _gerekli():
    if TS is None or DZ is None:
        raise RuntimeError("Stüdyo'nun metin kodu (app.textsrc, app.duzelt) bulunamadı")


def _harf(s):
    return sum(1 for c in s if c.isalpha())


def _rakam(s):
    return s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))


# ======================= PDF: satırlar =======================
def _katman_satirlari(page):
    rows = []
    for b in page.get_text("dict").get("blocks", []):
        for ln in b.get("lines", []):
            spans = [s for s in ln.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            boy = [s["size"] for s in spans if any(c.isalpha() for c in s["text"])]
            h = st.median(boy) if boy else (spans[0]["size"] if spans else 0)
            parca = []
            for k, s in enumerate(spans):
                t = s["text"]
                ust = (s.get("flags", 0) & 1) or (h and s["size"] < h * 0.78)
                if k > 0 and ust and re.fullmatch(r"\s*[\d٠-٩]{1,3}\s*", t):
                    parca.append("\ue000" + _rakam(t.strip()) + "\ue001")
                    continue
                if k > 0 and ust and re.fullmatch(r"[\d\s\W]+", t):
                    continue
                parca.append(t)
            metin = TS.norm("".join(parca))
            if not metin:
                continue
            harfli = [s for s in spans if any(c.isalpha() for c in s["text"])]
            kalin = bool(harfli) and all(("bold" in s.get("font", "").lower() or s.get("flags", 0) & 16) for s in harfli)
            x0, y0, x1, y1 = ln["bbox"]
            rows.append({"text": metin, "h": h, "top": y0, "bot": y1, "x0": x0, "x1": x1,
                         "n": len(metin.split()), "kalin": kalin, "blok": b.get("number", 0), "ocr": False})
    return rows


def _ocr_sayfa(args):
    """Taranmış sayfa: (i, satırlar, genişlik, yükseklik). Satır ölçüleri PDF birimine çevrilir."""
    os.environ["OMP_THREAD_LIMIT"] = "1"
    import fitz
    import pytesseract
    from PIL import Image, ImageOps
    yol, i, dil = args
    page = fitz.open(yol)[i]
    olcek = 72 / OCR_DPI
    pix = page.get_pixmap(dpi=OCR_DPI)
    img = ImageOps.autocontrast(Image.open(io.BytesIO(pix.tobytes("png"))).convert("L"))
    try:
        d = pytesseract.image_to_data(img, lang=dil, output_type=pytesseract.Output.DICT)
    except Exception:
        d = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    satir, sira = {}, []
    for k in range(len(d["text"])):
        t = (d["text"][k] or "").strip()
        if not t:
            continue
        key = (d["block_num"][k], d["par_num"][k], d["line_num"][k])
        if key not in satir:
            satir[key] = []
            sira.append(key)
        satir[key].append((d["left"][k], t, d["height"][k], d["top"][k], d["width"][k]))
    rows = []
    for key in sira:
        ws = sorted(satir[key])
        hs = [h for _, t, h, _, _ in ws if any(c.isalpha() for c in t)]
        lh = st.median(hs) if hs else 0
        parca = []
        for k, (_, t, h, _, _) in enumerate(ws):
            if k > 0 and lh and h < lh * 0.62 and re.fullmatch(r"[\d]{1,3}", t):
                parca.append("\ue000" + t + "\ue001")  # küçük (üst simge) dipnot numarası
            elif k > 0 and lh and h < lh * 0.6 and re.fullmatch(r"[\d\W]+", t):
                continue
            else:
                parca.append((" " if parca else "") + t)
        metin = TS.norm("".join(parca))
        if metin:
            rows.append({"text": metin, "h": lh * olcek, "top": min(w[3] for w in ws) * olcek,
                         "bot": max(w[3] + w[2] for w in ws) * olcek, "x0": ws[0][0] * olcek,
                         "x1": max(w[0] + w[4] for w in ws) * olcek, "n": len(metin.split()), "kalin": False,
                         "blok": key[0] * 1000 + key[1], "ocr": True})
    rows += _kenar_numarasi(img, rows, olcek, dil)
    return i, rows, page.rect.width, page.rect.height


def _kenar_numarasi(img, rows, olcek, dil):
    """Tesseract tek başına duran sayfa numarasını çoğu zaman görmez: üst ve alt şeritler sadece rakamla okunur."""
    import pytesseract
    W, H = img.size
    kenar = [r for r in rows if (r["top"] / olcek < H * 0.12 or r["bot"] / olcek > H * 0.88)
             and TS.PAGE_NUM.match(r["text"].strip())]
    if kenar:
        return []
    out = []
    for y0, y1 in ((0, int(H * 0.10)), (int(H * 0.90), H)):
        serit = img.crop((0, y0, W, y1))
        try:
            d = pytesseract.image_to_data(serit, lang=dil, config="--psm 6", output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        for k, t in enumerate(d["text"]):
            t = (t or "").strip()
            if re.fullmatch(r"\d{1,4}", t) and float(d["conf"][k]) > 60:
                top = (y0 + d["top"][k]) * olcek
                out.append({"text": t, "h": d["height"][k] * olcek, "top": top, "bot": top + d["height"][k] * olcek,
                            "x0": d["left"][k] * olcek, "x1": (d["left"][k] + d["width"][k]) * olcek, "n": 1,
                            "kalin": False, "blok": -1, "ocr": True})
    return out[:1]


def pdf_sayfalari(yol, ilerleme=None):
    """[(satırlar, genişlik, yükseklik, ocr_mu)] ve bilgi sözlüğü."""
    import fitz
    doc = fitz.open(yol)
    n = len(doc)
    sayfalar, ocr = [None] * n, []
    for i, page in enumerate(doc):
        try:
            rows = _katman_satirlari(page)
        except Exception:
            rows = []
        if sum(_harf(r["text"]) for r in rows) < 40:
            ocr.append(i)
        else:
            sayfalar[i] = (rows, page.rect.width, page.rect.height, False)
    bilgi = {"sayfa": n, "ocr": 0, "bozuk_katman": False}
    katman = "\n".join(r["text"] for s in sayfalar if s for r in s[0])
    if TS.katman_bozuk_mu(katman):
        bilgi["bozuk_katman"] = True
        sayfalar, ocr = [None] * n, list(range(n))
    if ocr:
        bilgi["ocr"] = len(ocr)
        dil = os.environ.get("OCR_LANG", "tur")
        with ProcessPoolExecutor(max_workers=max(1, os.cpu_count() or 1)) as ex:
            for k, (i, rows, w, h) in enumerate(ex.map(_ocr_sayfa, [(yol, i, dil) for i in ocr], chunksize=1)):
                sayfalar[i] = (rows, w, h, True)
                if ilerleme:
                    ilerleme(f"OCR: sayfa {k + 1}/{len(ocr)}")
    meta = doc.metadata or {}
    bilgi["baslik"] = (meta.get("title") or "").strip()
    bilgi["yazar"] = (meta.get("author") or "").strip()
    return sayfalar, bilgi


# ======================= PDF: sayfa düzeyinde ayıklama =======================
_UST_BILGI_NO = re.compile(r"^(\d{1,4})\s+\S.{0,70}$|^.{1,70}\S\s+(\d{1,4})$")


def _sayfa_no_ve_kenar(rows, h):
    """Basılı sayfa numarasını bulur, sayfa numarası satırlarını çıkarır. (no, kalan satırlar)"""
    no, kalan = None, []
    for r in rows:
        kenar = r["top"] < h * 0.12 or r["bot"] > h * 0.88
        t = _rakam(r["text"].strip())
        if kenar and TS.PAGE_NUM.match(t):
            no = no or re.sub(r"[^\divxlcdm]", "", t.lower())
            continue
        if kenar and r["n"] <= 12:
            m = _UST_BILGI_NO.match(t)
            if m and no is None:
                no = m.group(1) or m.group(2)
        kalan.append(r)
    return no, kalan


def _tekrar_edenleri_at(sayfa_satirlari):
    """Sayfaların ilk/son satırlarında tekrar eden üst/alt bilgiler (kitap adı, bölüm adı)."""
    anahtar = lambda t: re.sub(r"[\d\W]+", " ", t).strip().lower()
    sayac = collections.Counter()
    for rows in sayfa_satirlari:
        for r in rows[:2] + rows[-2:]:
            if len(r["text"]) < 90:
                sayac[anahtar(r["text"])] += 1
    esik = max(3, int(len(sayfa_satirlari) * 0.3))
    tekrar = {k for k, c in sayac.items() if c >= esik and k}
    out = []
    for rows in sayfa_satirlari:
        ilk_son = {id(r) for r in rows[:2] + rows[-2:]}
        out.append([r for r in rows if not (id(r) in ilk_son and anahtar(r["text"]) in tekrar)])
    return out


def _eksik_numaralari_doldur(nolar):
    """Numarası okunamayan sayfalar: arap rakamlı sayfalardan kayma (basılı - pdf sırası) bulunup doldurulur."""
    kayma = collections.Counter(int(n) - i for i, n in enumerate(nolar) if n and n.isdigit())
    if not kayma:
        return nolar
    k, adet = kayma.most_common(1)[0]
    if adet < 2:
        return nolar
    out = []
    for i, n in enumerate(nolar):
        if n and n.isdigit():
            # yakın sayfalardaki kaymaya göre denetle (kitap ortasında boş/eksik sayfa kaymayı değiştirebilir)
            komsu = [int(m) - j for j, m in enumerate(nolar) if m and m.isdigit() and 0 < abs(j - i) <= 8]
            yerel = collections.Counter(komsu).most_common(1)[0][0] if komsu else k
            if abs(int(n) - i - yerel) > 3:
                n = None  # yanlış okunmuş (ör. 237 yerine 2877)
        out.append(n if n else (str(i + k) if i + k >= 1 else None))
    return out


# ======================= PDF: paragraflar ve başlıklar =======================
def _govde_boyu(sayfa_satirlari, ocr):
    """Gövde yazısının boyu. Katmanda en sık punto; OCR'da (yükseklik harflere göre oynar) ağırlıklı ortanca."""
    rows = [r for rs in sayfa_satirlari for r in rs if r.get("ocr") == ocr and r["n"] >= 4]
    if not rows:
        return None
    if not ocr:
        say = collections.Counter()
        for r in rows:
            say[round(r["h"] * 2) / 2] += len(r["text"])
        return say.most_common(1)[0][0]
    agir = sorted((r["h"], len(r["text"])) for r in rows)
    yari, top = sum(a for _, a in agir) / 2, 0
    for h, a in agir:
        top += a
        if top >= yari:
            return h
    return agir[-1][0]


def _baslik_mi(r, govde, genislik, kalin_oran):
    t = r["text"].strip()
    if len(t) > 90 or len(t) < 2 or t.endswith((",", ";")) or UST.search(t):
        return False
    if TS.ICERIK_BASLIK.match(t) or BOLUM_NO.match(t):
        return True
    if r["h"] >= govde * (1.4 if r.get("ocr") else 1.15):
        return True
    ortada = abs((r["x0"] + r["x1"]) / 2 - genislik / 2) < genislik * 0.08 and (r["x1"] - r["x0"]) < genislik * 0.7
    if r["kalin"] and kalin_oran < 0.3 and not t.endswith(".") and (ortada or len(t) < 60):
        return True
    harfler = [c for c in t if c.isalpha()]
    if bool(harfler) and all(c.isupper() for c in harfler) and len(t) <= 50 and ortada:
        return True
    # OCR: iki yandan da içeride, ortalanmış, noktayla bitmeyen kısa satır
    return bool(r.get("ocr")) and ortada and r["x0"] > genislik * 0.25 and len(t) <= 70 and not t.endswith(END_PUNCT) \
        and r["h"] >= govde * 1.1


def _sayfa_paragraflari(rows, genislik, govde, kalin_oran):
    """Bir sayfanın ana satırları -> [(tür, metin, boy)] (tür 'b' başlık ya da 'p')."""
    if not rows:
        return []
    govde_satir = [r for r in rows if abs(r["h"] - govde) < govde * 0.15]
    sol = collections.Counter(round(r["x0"]) for r in govde_satir).most_common(1)[0][0] if govde_satir else min(r["x0"] for r in rows)
    sag = max((r["x1"] for r in govde_satir), default=max(r["x1"] for r in rows))
    araliklar = [b["top"] - a["top"] for a, b in zip(rows, rows[1:]) if 0 < b["top"] - a["top"] < govde * 3]
    aralik = st.median(araliklar) if araliklar else govde * 1.4
    out, cur, onceki = [], [], None
    for r in rows:
        baslik = _baslik_mi(r, govde, genislik, kalin_oran)
        yeni = True
        if onceki is not None and cur:
            if baslik and cur[0][0] == "b" and r["top"] - onceki["top"] < aralik * 2.2 and abs(r["h"] - onceki["h"]) < 0.5:
                yeni = False  # iki satıra bölünmüş başlık
            elif not baslik and cur[0][0] == "p":
                girinti = r["x0"] > sol + govde * 0.6
                bosluk = r["top"] - onceki["top"] > aralik * 1.55
                kisa_son = onceki["text"].endswith(END_PUNCT) and onceki["x1"] < sag - govde * 2.5
                madde = re.match(r"^\d{1,3}[.)]\s", r["text"])
                yeni = girinti or bosluk or kisa_son or bool(madde)
        if yeni and cur:
            out.append(cur)
            cur = []
        cur.append(("b" if baslik else "p", r))
        onceki = r
    if cur:
        out.append(cur)
    paras = []
    for grup in out:
        tur = grup[0][0]
        metin = TS.join_lines("\n".join(r["text"] for _, r in grup))
        paras.append((tur, metin, max(r["h"] for _, r in grup)))
    return paras


def _dipnot_ayir(rows, h, govde):
    """Önce Stüdyo'nun punto kuralı; bulunamazsa: alt yarıda büyük boşluktan sonra rakamla başlayan satırlar."""
    if not rows:
        return [], []
    ana, dip = TS._dipnot_ayir(rows, h)
    if dip:
        return ana, dip
    for k in range(1, len(rows)):
        a, b = rows[k - 1], rows[k]
        if b["top"] > h * 0.45 and b["top"] - a["bot"] > govde * 2.5 and re.match(r"^\d{1,3}[\s.)]", b["text"]):
            return rows[:k], rows[k:]
    return rows, []


_SAHTE_UST = re.compile(r"(?<=[^\W\d_][.,;:])\s?[!|?'’”\"°](?=\s|$)")
_SON_ISARET = re.compile(r"(?<=[.!?…])\s+['’‘\"”|°]$")


def _tirnak_esli(once, k):
    """Paragraf sonundaki işaret, önceden açılmış bir tırnağın kapanışı mı (gerçek tırnak)?"""
    if k == "”":
        return once.count("“") > once.count("”")
    if k == '"':
        return once.count('"') % 2 == 1
    if k in "’'":
        return once.count("‘") > once.count("’")
    return False


def _okunamayan_ust_simge(metin, sayfa_notu, baglanan):
    """OCR üst simge numarasını çoğu zaman !, ?, ’ ya da ” okur. Noktadan sonra gelen böyle bir işaret, sayfada
    bağlanmamış tek dipnot varsa ona bağlanır. Tırnak ancak eşi yoksa (paragrafta açılmış tırnak yoksa) işaret sayılır."""
    for m in _SAHTE_UST.finditer(metin):
        k = m.group(0)
        once = metin[:m.start()]
        if k in "”\"" and (once.count("“") > once.count("”") or once.count('"') % 2 == 1):
            continue  # açılmış bir tırnağın kapanışı: gerçek tırnak
        if k in "’'" and once.count("‘") > once.count("’"):
            continue
        gid = next(g for g in sayfa_notu.values() if g not in baglanan)
        baglanan.add(gid)
        return metin[:m.start()] + "{{" + gid + "}}" + metin[m.end():]
    return metin


def _notlari_bol(dip_paras):
    """Dipnot paragrafları -> [(numara ya da None (devam), metin)]."""
    out = []
    for p in dip_paras:
        p = UST.sub(r"\1 ", p)
        for parca in re.split(r"\s(?=\d{1,3}[\s.)]+[^\W\d])", p):
            parca = parca.strip()
            if not parca:
                continue
            m = re.match(r"^(\d{1,3})[\s.)]+(.*)$", parca, re.S)
            if m:
                out.append((int(m.group(1)), m.group(2).strip()))
            elif out:
                out[-1] = (out[-1][0], out[-1][1] + " " + parca)
            else:
                out.append((None, parca))
    return out


def pdf_oku(yol, ilerleme=None):
    """PDF -> (öğeler, dipnotlar, bilgi). öğe: {'tur': 'baslik'|'p', 'metin', 'boy'} ; metinde sayfa/dipnot işaretleri."""
    _gerekli()
    sayfalar, bilgi = pdf_sayfalari(yol, ilerleme)
    if ilerleme:
        ilerleme("Sayfa yapısı çıkarılıyor")
    n = len(sayfalar)
    nolar, satirlar = [], []
    for rows, w, h, _ in sayfalar:
        no, kalan = _sayfa_no_ve_kenar(rows, h)
        nolar.append(no)
        satirlar.append(kalan)
    nolar = _eksik_numaralari_doldur(nolar)
    bilgi["kapak_baslik"] = _kapak_basligi(satirlar[:3])
    dolu = next((rows for rows in satirlar[:3] if any(_harf(r["text"]) >= 3 for r in rows)), [])
    bilgi["kapak_satirlari"] = [(r["text"], r["h"], r["top"]) for r in sorted(dolu, key=lambda r: r["top"])
                                if 2 <= len(r["text"]) <= 80 and _harf(r["text"]) >= 2]
    # ön ve son sayfalar (kapak, künye, içindekiler): Stüdyo'nun kuralı
    tut = TS.on_ve_son_sayfalari_at([[str(i)] + [r["text"] for r in satirlar[i]] for i in range(n)])
    kalan = [int(s[0]) for s in tut]
    satirlar_k = _tekrar_edenleri_at([satirlar[i] for i in kalan])
    govde_k, govde_o = _govde_boyu(satirlar_k, False), _govde_boyu(satirlar_k, True)
    govde = govde_k or govde_o or 11
    tum = [r for rows in satirlar_k for r in rows]
    kalin_oran = sum(len(r["text"]) for r in tum if r["kalin"]) / max(1, sum(len(r["text"]) for r in tum))
    ogeler, notlar, not_sayac = [], {}, [0]
    son_not = None
    for j, i in enumerate(kalan):
        rows = satirlar_k[j]
        w, h = sayfalar[i][1], sayfalar[i][2]
        g = (govde_o if sayfalar[i][3] else govde_k) or govde
        ana, dip = _dipnot_ayir(rows, h, g)
        paras = _sayfa_paragraflari(ana, w, g, kalin_oran)
        dip_paras = [TS.join_lines(r["text"]) for r in dip]
        # sayfanın dipnotları: numaralı olanlar yeni, numarasız baştaki parça önceki sayfanın notunun devamı
        sayfa_notu = {}
        for no, metin in _notlari_bol(dip_paras):
            if no is None:
                if son_not:
                    notlar[son_not] += " " + metin
                continue
            not_sayac[0] += 1
            gid = "n%04d" % not_sayac[0]
            notlar[gid] = metin
            sayfa_notu.setdefault(no, gid)
            son_not = gid
        baglanan = set()

        def bagla(m, sayfa_notu=sayfa_notu, baglanan=baglanan):
            gid = sayfa_notu.get(int(m.group(1)))
            if gid and gid not in baglanan:
                baglanan.add(gid)
                return "{{" + gid + "}}"
            return ""
        yeni_paras = []
        for tur, metin, boy in paras:
            metin = UST.sub(bagla, metin)
            if tur == "p" and sayfa_notu:  # okunamamış üst simge: kelimeye yapışık rakam, noktadan sonra "!"
                metin = YAPISIK.sub(bagla, metin)
                if sayfalar[i][3] and len(sayfa_notu) - len(baglanan) == 1:
                    metin = _okunamayan_ust_simge(metin, sayfa_notu, baglanan)
            elif tur == "p":
                metin = YAPISIK.sub("", metin)
            if tur == "p" and sayfalar[i][3]:  # bağlanamayan sahipsiz son işaret: sil
                son = _SON_ISARET.search(metin)
                if son and not _tirnak_esli(metin[:son.start()], son.group(0).strip()):
                    metin = metin[:son.start()]
            yeni_paras.append((tur, metin, boy))
        # metinde atfı bulunamayan notlar: sayfanın son paragrafının sonuna bağlanır (not kaybolmasın)
        bosta = [g for g in sayfa_notu.values() if g not in baglanan]
        if bosta:
            for k in range(len(yeni_paras) - 1, -1, -1):
                if yeni_paras[k][0] == "p":
                    tur, metin, boy = yeni_paras[k]
                    yeni_paras[k] = (tur, metin + "".join("{{" + g + "}}" for g in bosta), boy)
                    break
            else:
                yeni_paras.append(("p", "".join("{{" + g + "}}" for g in bosta), govde))
        etiket = "\ue002" + nolar[i] + "\ue003" if nolar[i] else ""
        for k, (tur, metin, boy) in enumerate(yeni_paras):
            ilk = k == 0
            onceki = ogeler[-1] if ogeler else None
            # sayfa geçişinde bölünen paragraf: öncekiyle birleştir
            if ilk and tur == "p" and onceki and onceki["tur"] == "p" and metin[:1].islower() \
                    and not onceki["metin"].endswith(END_PUNCT):
                sol = onceki["metin"]
                if sol.endswith(("-", "‐")):
                    kel_sol = re.search(r"([^\W\d_]+)[-‐]$", sol)
                    kel_sag = re.match(r"([^\W\d_]+)", metin)
                    if kel_sol and kel_sag:
                        birlesik = DZ._birlesik(kel_sol.group(1), kel_sag.group(1)) or (kel_sol.group(1) + kel_sag.group(1))
                        onceki["metin"] = sol[:kel_sol.start()] + etiket + birlesik + metin[kel_sag.end():]
                    else:
                        onceki["metin"] = sol[:-1] + etiket + metin
                else:
                    onceki["metin"] = sol + " " + etiket + metin
                continue
            ogeler.append({"tur": "baslik" if tur == "b" else "p", "metin": (etiket if ilk else "") + metin, "boy": boy,
                           "ocr": sayfalar[i][3]})
        if not yeni_paras and etiket and ogeler:
            pass  # boş sayfa: numarası atlanır
        if ilerleme and j % 20 == 0:
            ilerleme(f"Sayfa yapısı: {j + 1}/{len(kalan)}")
    bilgi["govde_boyu"] = govde
    return ogeler, notlar, bilgi


# ======================= EPUB / DOCX / TXT =======================
_NOT_BASLIK = re.compile(r"^(notlar|dipnotlar|sonnotlar|açıklamalar|notes|endnotes|footnotes)[.:]?$", re.I)
_NOKTALI = re.compile(r"(\.{3,}|…{2,}|(\. ){3,})\s*\d{0,4}\s*$|\s\d{1,4}\s*$")


def _on_temizlik(ogeler):
    """İçindekiler bölümü (noktalı/numaralı satırlar), baştaki künye satırları ve içi boş Notlar başlıkları atılır."""
    yazi = lambda o: SAYFA_ISARET.sub("", o["metin"]).strip()
    out, i, n = [], 0, len(ogeler)
    while i < n:
        o = ogeler[i]
        if o["tur"] == "baslik" and TS.ICINDEKILER.search(yazi(o)) and len(yazi(o)) < 40 and i < max(10, n * 0.3):
            j = i + 1
            while j < n and ogeler[j]["tur"] == "p" and (_NOKTALI.search(yazi(ogeler[j])) or
                                                        TS.KUNYE.search(yazi(ogeler[j])) or len(yazi(ogeler[j])) < 60):
                j += 1
            i = j
            continue
        if o["tur"] == "p" and i < max(10, n * 0.05) and TS.KUNYE.search(yazi(o)) and len(yazi(o)) < 200:
            i += 1
            continue
        if o["tur"] == "baslik" and _NOT_BASLIK.match(yazi(o)) and (i + 1 == n or ogeler[i + 1]["tur"] == "baslik"):
            i += 1
            continue
        out.append(o)
        i += 1
    return out

_BLOK = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "dd", "dt", "pre"]


def epub_oku(yol, ilerleme=None):
    """EPUB -> (öğeler, dipnotlar, bilgi). h1-h6 başlık; noteref bağlantıları dipnot; pagebreak işaretleri sayfa."""
    _gerekli()
    from bs4 import BeautifulSoup, NavigableString
    from ebooklib import ITEM_DOCUMENT, epub
    book = epub.read_epub(yol, options={"ignore_ncx": True})
    belgeler = []
    for idref, _ in book.spine:
        item = book.get_item_with_id(idref)
        if item and item.get_type() == ITEM_DOCUMENT:
            belgeler.append((os.path.basename(item.get_name()), BeautifulSoup(item.get_content(), "html.parser")))
    # 1) dipnot hedefleri: kısa (rakam, [1], *) bağlantıların gösterdiği öğeler
    hedef = {}
    for ad, soup in belgeler:
        for a in soup.find_all("a", href=True):
            yazi = a.get_text(strip=True)
            tip = (a.get("epub:type") or "") + " " + (a.get("role") or "")
            if "#" in a["href"] and ("noteref" in tip or re.fullmatch(r"[\[\(]?\d{1,3}[\]\)]?|\*{1,3}|[¹²³⁴-⁹⁰]+", yazi)):
                dosya, frag = a["href"].split("#", 1)
                hedef[(os.path.basename(dosya) or ad, frag)] = None
    notlar, not_elemanlari, gid_of = {}, set(), {}
    for ad, soup in belgeler:
        for el in soup.find_all(id=True):
            if (ad, el["id"]) in hedef and not (el.name == "a" and el.has_attr("href")):
                kap = el
                if el.name in ("a", "span", "sup"):  # hedef bağlantının kendisi: notun paragrafını al
                    kap = el.find_parent(["p", "li", "aside", "div", "dd"]) or el
                metin = kap.get_text(" ", strip=True)
                metin = re.sub(r"^[\[\(]?\d{1,3}[\]\)]?[.\s]*", "", metin).strip()
                gid = "n%04d" % (len(notlar) + 1)
                notlar[gid] = metin
                gid_of[(ad, el["id"])] = gid
                not_elemanlari.add(id(kap))
        for el in soup.find_all(["aside", "section", "div", "ol"]):
            tip = (el.get("epub:type") or "") + " " + (el.get("role") or "")
            if re.search(r"footnote|endnote|rearnote", tip):
                not_elemanlari.add(id(el))

    ogeler = []

    def metin_cikar(el, ad):
        out = []
        for c in el.descendants:
            if isinstance(c, NavigableString):
                if c.parent and c.parent.name in ("script", "style"):
                    continue
                if any(p.name == "a" and p.get("href", "").count("#") and
                       (os.path.basename(p["href"].split("#")[0]) or ad, p["href"].split("#", 1)[1]) in gid_of
                       for p in c.parents if p is not el and p.name == "a"):
                    continue
                out.append(str(c))
            elif c.name == "a" and "#" in c.get("href", ""):
                dosya, frag = c["href"].split("#", 1)
                g = gid_of.get((os.path.basename(dosya) or ad, frag))
                if g:
                    out.append("{{" + g + "}}")
            elif c.name in ("span", "a", "div") and re.search(r"pagebreak", (c.get("epub:type") or "") + (c.get("role") or "")):
                et = c.get("aria-label") or c.get("title") or c.get_text(strip=True) or re.sub(r"\D", "", c.get("id", ""))
                if et:
                    out.append("\ue002" + _rakam(et.strip()) + "\ue003")
            elif c.name == "br":
                out.append(" ")
        return TS.norm("".join(out))

    for ad, soup in belgeler:
        govde = soup.body or soup
        for el in govde.find_all(_BLOK):
            if el.find(_BLOK) or any(id(p) in not_elemanlari for p in [el] + list(el.parents)):
                continue
            metin = metin_cikar(el, ad)
            if not metin or (TS.PAGE_NUM.match(metin) and "\ue002" not in metin):
                continue
            if el.name[0] == "h" and el.name[1:].isdigit():
                ogeler.append({"tur": "baslik", "metin": metin, "boy": 7 - int(el.name[1])})
            else:
                ogeler.append({"tur": "p", "metin": metin, "boy": 0})
    # baştaki içindekiler/künye: Stüdyo'nun kuralı (ilk içerik başlığından başlat)
    yazilar = [SAYFA_ISARET.sub("", o["metin"]) for o in ogeler]
    temiz = TS.paragraflari_bastan_temizle(yazilar)
    ogeler = _on_temizlik(ogeler[len(yazilar) - len(temiz):])
    bilgi = {"baslik": (book.get_metadata("DC", "title") or [[""]])[0][0],
             "yazar": (book.get_metadata("DC", "creator") or [[""]])[0][0], "ocr": 0, "bozuk_katman": False}
    return ogeler, notlar, bilgi


def docx_oku(yol, ilerleme=None):
    _gerekli()
    import docx
    d = docx.Document(yol)
    ogeler, stil_baslik = [], ""
    for p in d.paragraphs:
        t = TS.norm(p.text)
        if not t or TS.PAGE_NUM.match(t):
            continue
        stil = (p.style.name or "").lower() if p.style is not None else ""
        m = re.search(r"(heading|başlık|baslik)\s*(\d)", stil)
        if stil in ("title", "konu başlığı", "kitap adı"):
            stil_baslik = stil_baslik or t  # kitabın adı künyeye gider, metne değil
        elif m:
            ogeler.append({"tur": "baslik", "metin": t, "boy": 7 - int(m.group(2))})
        else:
            ogeler.append({"tur": "p", "metin": t, "boy": 0})
    yazilar = [o["metin"] for o in ogeler]
    temiz = TS.paragraflari_bastan_temizle(yazilar)
    cp = d.core_properties
    return _on_temizlik(ogeler[len(yazilar) - len(temiz):]), {}, {"baslik": cp.title or stil_baslik, "yazar": cp.author or "",
                                                                  "ocr": 0, "bozuk_katman": False}


def txt_oku(yol, ilerleme=None):
    _gerekli()
    paras = TS.from_txt_bytes(open(yol, "rb").read())
    ogeler = []
    for t in TS.paragraflari_bastan_temizle(paras):  # noqa: B007
        harf = [c for c in t if c.isalpha()]
        b = len(t) <= 60 and (TS.ICERIK_BASLIK.match(t) or BOLUM_NO.match(t) or (harf and all(c.isupper() for c in harf)))
        ogeler.append({"tur": "baslik" if b else "p", "metin": t, "boy": 0})
    return _on_temizlik(ogeler), {}, {"baslik": "", "yazar": "", "ocr": 0, "bozuk_katman": False}


# ======================= ortak: düzeltme ve kitap.json =======================
def _buyuk_harfli(t):
    h = [c for c in SAYFA_ISARET.sub("", t) if c.isalpha()]
    return bool(h) and all(c.isupper() for c in h)


_COP_ISARET = re.compile(r"[#»«|<>@^~_=\\{}\[\]]")


def anlamli_baslik(t):
    """Başlık gerçekten başlık mı? OCR çöpü (Arapça satırın Türkçe OCR'ı) ve tek kalmış cümle sonları elenir."""
    t = SAYFA_ISARET.sub("", t).strip()
    if not t or len(t) > 90 or _COP_ISARET.search(t) or t[0] in "“\"'‘«(":
        return False  # tırnakla başlayan satır cümle parçasıdır
    if TS.ICERIK_BASLIK.match(t) or BOLUM_NO.match(t) or re.fullmatch(
            r"(bölüm|kısım|fasıl|bab|kitap|makale)\s+([ivxlc]{1,6}|\d{1,3})[.:]?", t, re.I):
        return True
    if not t[0].isalnum():
        return False  # ? ile başlayan vb.
    if len(t.split()) == 1 and len(re.sub(r"[^\w]", "", t)) < 5:
        return False  # tek kelimelik kısa satır (TİRE): bilinen başlıklar yukarıda kabul edildi
    if t[0].islower() or (t.endswith((".", ",", ";")) and not re.search(r"\b(vs|bkz|s|c)\.$", t, re.I)):
        return False
    kelimeler = re.findall(r"[^\W\d_]{2,}", t)
    if not kelimeler or max(len(k) for k in kelimeler) < 3:
        return False
    harf = sum(len(k) for k in kelimeler)
    if harf / max(1, len(re.sub(r"\s", "", t))) < 0.7:
        return False
    baglac = ("ve", "ile", "ki", "da", "de", "ya", "veya", "ya da")
    asil_kel = [k for k in kelimeler if k.lower() not in baglac] or kelimeler
    if sum(len(k) for k in asil_kel) / len(asil_kel) < 3.5:
        return False  # OCR çöpü: 2-3 harflik parçalar
    for parca in t.split():  # tek başına duran harf (EĞEN ğ): çöp; noktalı kısaltmalar (S.A.V.) muaf
        oz = parca.strip("()[]:;,!?\"“”'’‘")
        if len(oz) == 1 and oz.isalpha() and oz.lower() != "o" and not re.fullmatch(r"[IVXLC]", oz):
            return False
    # büyük/küçük harf düzeni: TAMAMI BÜYÜK ya da Düzgün Yazım; karışık (PAS TAİ Kan yay) başlık değildir
    buyuk = [k for k in kelimeler if len(k) >= 2 and k.isupper()]
    kucuk = [k for k in kelimeler if not k.isupper() and k.lower() not in ("ve", "ile", "ki", "da", "de", "ya", "veya")]
    if buyuk and kucuk and not all(re.search(re.escape(k) + r"\.", t) for k in buyuk):
        return False
    iyi = sum(1 for k in kelimeler if DZ.gecerli_mi(k) or DZ._kelime_mi(k))
    return iyi / len(kelimeler) >= 0.75


def _basliklari_denetle(ogeler):
    """Anlamsız başlıklar paragraf olur; küçük harfle başlayan cümle sonu önceki paragrafa eklenir."""
    out = []
    for k, o in enumerate(ogeler):
        sonraki = ogeler[k + 1] if k + 1 < len(ogeler) else None
        if o["tur"] == "baslik" and sonraki and sonraki["tur"] == "p" and \
                SAYFA_ISARET.sub("", sonraki["metin"]).lstrip()[:1].islower():
            # arkasından küçük harfle devam eden paragraf: bu satır cümlenin başıdır, başlık değil
            sonraki["metin"] = o["metin"] + " " + sonraki["metin"]
            continue
        if o["tur"] == "baslik" and not anlamli_baslik(o["metin"]):
            o = dict(o, tur="p")
            yazi = SAYFA_ISARET.sub("", o["metin"]).strip()
            onceki = out[-1] if out else None
            if onceki and onceki["tur"] == "p" and yazi[:1].islower() and not onceki["metin"].endswith(END_PUNCT):
                onceki["metin"] += " " + o["metin"]
                continue
        out.append(o)
    return out


_EK_BASLIK = re.compile(r"^(sonuç|hâtime|hatime|netice|takdim|dîbâce|dibace|kaynakça|bibliyografya|sözlük|lügatçe|"
                        r"dizin|indeks|ekler?|mukaddime|önsöz|giriş|başlangıç)[.:]?$", re.I)


def _kalip_baslik(t):
    t = SAYFA_ISARET.sub("", t).strip()
    return bool(TS.ICERIK_BASLIK.match(t) or BOLUM_NO.match(t) or _EK_BASLIK.match(t) or re.match(
        r"(bölüm|kısım|fasıl|bab|kitap|makale)\s+([ivxlc]{1,6}|\d{1,3})\b", t, re.I))


def _seviyeler(ogeler):
    _seviyeler_boy(ogeler)
    basliklar = [o for o in ogeler if o["tur"] == "baslik"]
    kalip = [o for o in basliklar if _kalip_baslik(o["metin"])]
    if len(kalip) >= 2:  # "Birinci Bölüm", "Önsöz"... her zaman en üstte; öteki başlıklar altında (en az 2. seviye)
        for o in basliklar:
            o["seviye"] = 1 if o in kalip else max(2, o["seviye"])


def _seviyeler_boy(ogeler):
    """Başlık seviyesi (en çok 3). Metin katmanında punto güvenilir: boylardan. OCR'da satır yüksekliği harflere göre
    oynar: önce yazım biçimi (TAMAMI BÜYÜK HARF üst seviye), aynı biçim içinde %20'den büyük punto farkı."""
    basliklar = [o for o in ogeler if o["tur"] == "baslik"]
    if basliklar and sum(1 for o in basliklar if o.get("ocr")) > len(basliklar) / 2:
        gruplar = []  # (büyük_harf_mı, boy eşiği)
        for buyuk in (True, False):
            boylar = sorted({o["boy"] for o in basliklar if _buyuk_harfli(o["metin"]) == buyuk and o["boy"]}, reverse=True)
            esik = []
            for b in boylar:
                if not esik or b < esik[-1] * 0.8:
                    esik.append(b)
            gruplar += [(buyuk, e) for e in esik]
        for o in basliklar:
            buyuk = _buyuk_harfli(o["metin"])
            aday = [k for k, (g, e) in enumerate(gruplar) if g == buyuk and o["boy"] >= e * 0.8]
            o["seviye"] = min((aday[0] if aday else len(gruplar) - 1) + 1, 3)
        # boşluk kalmasın: kullanılan seviyeler 1, 2, 3 diye sıkıştırılır
        kullanilan = sorted({o["seviye"] for o in basliklar})
        for o in basliklar:
            o["seviye"] = kullanilan.index(o["seviye"]) + 1
        return
    """Başlık boylarından fihrist seviyesi (en büyük = 1, en çok 3). Boy bilgisi yoksa 1."""
    boylar = sorted({o["boy"] for o in ogeler if o["tur"] == "baslik" and o["boy"]}, reverse=True)
    esikler = []  # her seviyenin en büyük boyu; %12'den fazla küçülünce yeni seviye
    for b in boylar:
        if not esikler or b < esikler[-1] * 0.88:
            esikler.append(b)
    for o in ogeler:
        if o["tur"] == "baslik":
            if o["boy"] and esikler:
                o["seviye"] = min(next((k for k, e in enumerate(esikler) if o["boy"] >= e * 0.88), len(esikler) - 1) + 1, 3)
            else:
                o["seviye"] = 1


def _basliklari_birlestir(ogeler):
    """'BİRİNCİ BÖLÜM' + hemen ardındaki aynı seviyeli başlık -> 'BİRİNCİ BÖLÜM: Başlık'."""
    out = []
    for o in ogeler:
        p = out[-1] if out else None
        if p and p["tur"] == o["tur"] == "baslik" and p["seviye"] == o["seviye"] and \
                BOLUM_NO.match(SAYFA_ISARET.sub("", p["metin"]).strip()) and not BOLUM_NO.match(o["metin"]):
            p["metin"] = p["metin"].rstrip(" .:") + ": " + SAYFA_ISARET.sub("", o["metin"]).strip()
            p["metin"] += "".join("\ue002" + e + "\ue003" for e in SAYFA_ISARET.findall(o["metin"]))
            continue
        out.append(o)
    return out


def _duzelt(metinler):
    """Stüdyo düzeltmeleri (sayfa atıfları KORUNUR: kitabın basılı sayfa numaraları EPUB'da var)."""
    basliklar = DZ.satir_ici_ust_bilgileri_bul([SAYFA_ISARET.sub(" ", t) for t in metinler])
    out = []
    for p in metinler:
        p = DZ.satir_ici_ust_bilgileri_sil(p, basliklar)
        p = DZ.cop_isaretleri_sil(p)
        p = DZ.satir_ici_tireleri_birlestir(p)
        p = DZ.harfleri_onar(p)
        p = re.sub(r"[ \t]{2,}", " ", p).replace(" ,", ",").replace(" .", ".").strip()
        p = re.sub(r"^(\d{1,3}[.)])(?=[^\s\d.)\ue002])", r"\1 ", p)
        out.append(p)
    return out


def _konumlar(metin):
    """Sayfa işaretlerini metinden çıkarır: (temiz metin, [(etiket, konum)])."""
    sayfalar, parcalar, uz = [], [], 0
    for i, parca in enumerate(SAYFA_ISARET.split(metin)):
        if i % 2:
            sayfalar.append((parca, uz))
        else:
            parcalar.append(parca)
            uz += len(parca)
    duz = "".join(parcalar)
    # baştaki/sondaki boşluk kırpılınca konumlar kayar: düzelt
    sol = len(duz) - len(duz.lstrip())
    duz = duz.strip()
    return duz, [(e, max(0, min(len(duz), k - sol))) for e, k in sayfalar]


def kitaba_cevir(ogeler, notlar, kunye):
    ogeler = _basliklari_denetle(ogeler)
    _seviyeler(ogeler)
    ogeler = _basliklari_birlestir(ogeler)
    ogeler = [o for o in ogeler if SAYFA_ISARET.sub("", o["metin"]).strip() or SAYFA_ISARET.search(o["metin"])]
    # tek başına kalmış ayet/madde numarası: sonraki paragrafa (Stüdyo kuralı)
    birlesik, bekleyen = [], None
    for o in ogeler:
        yazi = SAYFA_ISARET.sub("", o["metin"]).strip()
        if o["tur"] == "p" and re.fullmatch(r"\d{1,3}\s*[.)]", yazi):
            bekleyen = o["metin"]
            continue
        if bekleyen:
            o = dict(o, metin=bekleyen.strip() + " " + o["metin"])
            bekleyen = None
        birlesik.append(o)
    ogeler = birlesik
    duz = _duzelt([o["metin"] for o in ogeler])
    notlar = dict(zip(notlar, _duzelt(list(notlar.values())))) if notlar else {}
    kit = K.yeni(kunye)
    tasinan = []  # atılan paragraftaki sayfa işaretleri sonrakine geçer
    for o, metin in zip(ogeler, duz):
        temiz, sayfalar = _konumlar(metin)
        yazi = K.NOT_ISARETI.sub("", temiz).strip()
        if o["tur"] == "p" and not K.NOT_ISARETI.search(temiz) and (not yazi or DZ.cop_paragraf_mi(yazi)):
            tasinan += [e for e, _ in sayfalar]
            continue
        sayfa = [{"no": e, "konum": {"tr": 0}} for e in tasinan] + [{"no": e, "konum": {"tr": k}} for e, k in sayfalar]
        tasinan = []
        if o["tur"] == "baslik":
            temiz2 = turkce_onar(temiz)
            if len(temiz2) == len(temiz):  # uzunluk aynı kalır (harf değişimi): sayfa konumları geçerli
                temiz = temiz2
            K.blok_ekle(kit, "baslik", {"tr": temiz}, seviye=o.get("seviye", 1), sayfalar=sayfa)
        else:
            K.blok_ekle(kit, "p", {"tr": temiz}, sayfalar=sayfa)
    kullanilan = set()
    for b in kit["bloklar"]:
        kullanilan |= set(K.NOT_ISARETI.findall(b["metin"]["tr"]))
    kit["dipnotlar"] = {g: {"metin": {"tr": t}} for g, t in notlar.items() if g in kullanilan}
    # aynı etiketin tekrarı (ör. boş sayfa) ve sıra bozukluğu: ilk görüleni tut
    gorulen = set()
    for b in kit["bloklar"]:
        if "sayfalar" in b:
            b["sayfalar"] = [s for s in b["sayfalar"] if not (s["no"] in gorulen or gorulen.add(s["no"]))]
            if not b["sayfalar"]:
                del b["sayfalar"]
    _sirayi_duzelt(kit)
    return kit


def _sirayi_duzelt(kit):
    """Sayfa numaraları geriye gidiyorsa (yanlış okunmuş numara) o işaretler atılır."""
    onceki = None
    for b in kit["bloklar"]:
        if "sayfalar" not in b:
            continue
        tut = []
        for s in b["sayfalar"]:
            if s["no"].isdigit():
                if onceki is not None and int(s["no"]) <= onceki:
                    continue
                onceki = int(s["no"])
            tut.append(s)
        b["sayfalar"] = tut
        if not tut:
            del b["sayfalar"]


def _kapak_basligi(ilk_sayfalar):
    """İlk sayfalardaki en büyük puntolu yazı (kapak başlığı)."""
    dolu = next((rows for rows in ilk_sayfalar if any(_harf(r["text"]) >= 3 for r in rows)), [])
    aday = [r for r in dolu if 3 <= len(r["text"]) <= 80 and _harf(r["text"]) >= 3]
    if not aday:
        return ""
    en = max(r["h"] for r in aday)
    return " ".join(r["text"] for r in aday if r["h"] >= en * 0.95)[:120]


_KUCUK_KAL = {"ve", "ile", "ki", "veya", "ya", "da", "de", "fi", "min", "an", "ala", "li"}


def turkce_baslik(s):
    """'İTİKADDA ORTA YOL' -> 'İtikadda Orta Yol' (Türkçe büyük/küçük harf kurallarıyla)."""
    harf = [c for c in s if c.isalpha()]
    if not harf or not all(c.isupper() for c in harf):
        return s
    kucuk = s.replace("I", "ı").replace("İ", "i").lower()
    out = []
    for i, w in enumerate(kucuk.split()):
        if i and w in _KUCUK_KAL:
            out.append(w)
        else:
            out.append({"i": "İ", "ı": "I"}.get(w[0], w[0].upper()) + w[1:])
    return " ".join(out)


def _benzer(a, b):
    from .katalog import sade
    ka, kb = set(sade(a).split()), set(sade(b).split())
    return bool(ka and kb) and len(ka & kb) / min(len(ka), len(kb)) >= 0.5


def _kunye_sec(bilgi, ad_baslik, ad_yazar, dosya_koku):
    """Eser adı: kapaktaki başlık (Türkçe harfleriyle; dosya adıyla uyuşuyorsa) > PDF/EPUB bilgi alanı (dosya adının
    kopyası değilse) > dosya adı. Yazar: bilgi alanı (eser adıyla aynı değilse) > dosya adındaki 'Yazar - Eser'."""
    from .katalog import sade
    # bilgi alanı ancak dosya adındaki "Yazar - Eser"in birleşik kopyasıysa atılır; sadece eser adıysa (çoğu zaman
    # Türkçe harfleriyle daha doğru yazılmıştır) tercih edilir
    kopya = lambda s: bool(ad_yazar) and sade(s) == sade(ad_yazar + " " + ad_baslik)
    meta_b = bilgi.get("baslik") if _anlamli(bilgi.get("baslik")) else ""
    meta_y = bilgi.get("yazar") if _anlamli(bilgi.get("yazar")) else ""
    satirlar = bilgi.get("kapak_satirlari") or ([(bilgi["kapak_baslik"], 1, 0)] if bilgi.get("kapak_baslik") else [])
    kapak = _kapak_sec(satirlar, ad_baslik if ad_yazar else "")  # dosya adı "Yazar - Eser" değilse karşılaştırılamaz
    if kapak:
        baslik = turkce_baslik(kapak)
    elif meta_b and not kopya(meta_b):
        baslik = meta_b
    else:
        baslik = turkcelestir(ad_baslik)
    if meta_y and not kopya(meta_y) and sade(meta_y) != sade(baslik) and sade(baslik) not in sade(meta_y):
        yazar = meta_y
    else:
        yazar = turkcelestir(ad_yazar)
    return turkce_onar(baslik), turkce_onar(yazar)


def _kapak_sec(satirlar, ad_baslik):
    """Kapaktaki başlık satırları: en büyük satırdan başlayıp alttaki (ya da üstteki) büyük satırlar eklenir; dosya
    adındaki kelimelerin en az %80'ini içeren en kısa birleşim seçilir. Dosya adı yoksa en büyük satır(lar)."""
    from .katalog import sade
    if not satirlar:
        return ""
    en = max(h for _, h, _ in satirlar)
    buyuk = [(t.strip(" ,;:"), h) for t, h, _ in satirlar if h >= en * 0.5]
    hedef = set(sade(ad_baslik).split())
    if not hedef:
        return " ".join(t for t, h in buyuk if h >= en * 0.95)
    iyi, iyi_puan = "", 0
    for bas in range(len(buyuk)):
        for son in range(bas + 1, min(len(buyuk), bas + 4) + 1):
            metin = " ".join(t for t, _ in buyuk[bas:son])
            kel = set(sade(metin).split())
            kapsama = len(kel & hedef) / len(hedef)
            puan = kapsama - 0.05 * len(kel - hedef)
            if kapsama >= 0.8 and puan > iyi_puan:
                iyi, iyi_puan = metin, puan
    return iyi


_ESLER = {"o": "ö", "ö": "o", "u": "ü", "ü": "u", "s": "ş", "ş": "s", "c": "ç", "ç": "c", "g": "ğ", "ğ": "g", "i": "ı", "ı": "i"}


def _tr_kucuk(w):
    return w.replace("I", "ı").replace("İ", "i").lower()


def _tr_buyuk(w):
    return w.replace("i", "İ").replace("ı", "I").upper()


def _gecerli(w):
    kelimeler, _ = DZ._sozluk()
    return w in kelimeler or DZ.gecerli_mi(w)


def _kelime_onar(kucuk):
    """Geçersiz kelimenin noktası/şapkası kaybolmuş doğru hâli: önce kelime listesindeki iskelet eşi, yoksa Zemberek'e
    sorarak (en az değişiklikle). Bulunamazsa None."""
    if len(kucuk) < 2 or _gecerli(kucuk):
        return None
    _, iskelet = DZ._sozluk()
    aday = iskelet.get(kucuk.translate(DZ._TR_ISKELET))
    if aday and aday != kucuk:
        return aday
    yerler = [i for i, c in enumerate(kucuk) if c in _ESLER][:6]
    import itertools
    for adet in range(1, len(yerler) + 1):
        for secim in itertools.combinations(yerler, adet):
            k = list(kucuk)
            for i in secim:
                k[i] = _ESLER[k[i]]
            k = "".join(k)
            if DZ.gecerli_mi(k):
                return k
    return None


def turkce_onar(metin):
    """Başlık, kitap adı ve yazar için harf onarımı (OCR'ın kaybettiği nokta/şapka: 'SÖZÜN OZÜ' -> 'SÖZÜN ÖZÜ').
    Büyük/küçük harf düzeni korunur; karşılığı bulunamayan kelimeye (özel ad) dokunulmaz."""
    if not metin or DZ is None:
        return metin

    def onar(m):
        w = m.group(0)
        dogru = _kelime_onar(_tr_kucuk(w))
        if not dogru:
            return w
        if w.isupper():
            return _tr_buyuk(dogru)
        if w[:1].isupper():
            return _tr_buyuk(dogru[0]) + dogru[1:]
        return dogru
    return re.sub(r"[^\W\d_]+", onar, metin)


def turkcelestir(s):
    """Şapkasız/Türkçe harfsiz yazımı (dosya adı) kelime listesiyle düzeltir: 'Itikatta Sozun Ozu' -> 'İtikatta Sözün Özü'."""
    if not s or DZ is None:
        return s
    kelimeler, iskelet = DZ._sozluk()
    out = []
    for w in s.split():
        kk = DZ._kucuk(w)
        if not w.isascii() or not kk.isalpha():
            out.append(w)
            continue
        if w[:1] == "I" and (("i" + kk[1:]) in kelimeler or DZ.gecerli_mi("i" + kk[1:])):  # 'Imam' = İmam
            out.append("İ" + w[1:])
            continue
        if kk in kelimeler:
            out.append(w)
            continue
        dogru = iskelet.get(kk.translate(DZ._TR_ISKELET))
        if not dogru:
            out.append(w)
            continue
        if w[:1].isupper():
            dogru = {"i": "İ", "ı": "I"}.get(dogru[0], dogru[0].upper()) + dogru[1:]
        out.append(dogru)
    return " ".join(out)


def _dosya_adindan(yol):
    ad = os.path.splitext(os.path.basename(yol))[0]
    ad = re.sub(r"[_]+", " ", ad).strip()
    if " - " in ad:
        yazar, baslik = ad.split(" - ", 1)
        return baslik.strip(), yazar.strip()
    return ad, ""


def _anlamli(s):
    s = (s or "").strip()
    return s and not re.search(r"microsoft|word|untitled|adsız|\.docx?|\.pdf|^[\d\W]+$", s, re.I) and len(s) < 150


def cevir(yol, ilerleme=None, kaynak_bilgi=None):
    """Dosya -> kitap.json sözlüğü (Türkçe)."""
    uzanti = os.path.splitext(yol)[1].lower()
    okuyucu = {".pdf": pdf_oku, ".epub": epub_oku, ".docx": docx_oku, ".txt": txt_oku}.get(uzanti)
    if not okuyucu:
        raise ValueError("Desteklenmeyen dosya türü: " + uzanti)
    ogeler, notlar, bilgi = okuyucu(yol, ilerleme)
    if ilerleme:
        ilerleme("Metin düzeltiliyor")
    ad_baslik, ad_yazar = _dosya_adindan(yol)
    baslik, yazar = _kunye_sec(bilgi, ad_baslik, ad_yazar, os.path.splitext(os.path.basename(yol))[0])
    kunye = {
        "baslik": {"tr": baslik},
        "yazar": {"tr": yazar},
        "asil_dil": "tr",
        "kaynak": {"tur": "dosya", "ad": os.path.basename(yol), **(kaynak_bilgi or {})},
        "sayfa_kaynagi": "basılı baskı" if uzanti == ".pdf" else "",
        "cikarma": {k: bilgi.get(k) for k in ("sayfa", "ocr", "bozuk_katman")},
    }
    kit = kitaba_cevir(ogeler, notlar, kunye)
    if not any(b["tur"] == "p" for b in kit["bloklar"]):
        raise ValueError("Dosyadan metin çıkarılamadı (boş ya da okunamayan dosya)")
    return kit


def kimlik_uret(yol):
    ad = os.path.splitext(os.path.basename(yol))[0]
    ad = ad.translate(str.maketrans("İıŞşĞğÇçÖöÜü", "IiSsGgCcOoUu"))
    ad = "".join(c for c in unicodedata.normalize("NFKD", ad) if not unicodedata.combining(c))
    ad = re.sub(r"[^A-Za-z0-9]+", "-", ad).strip("-")[:60] or "kitap"
    return f"{ad}-{hashlib.sha1(yol.encode('utf-8')).hexdigest()[:6]}"
