"""OpenITI mARkdown metnini kitap.json biçimine çevirir.

Biçim notları (kaynak: OpenITI mARkdown):
- '#META#Header#End#' satırına kadar künye.
- '### | başlık' (seviye = dikey çizgi sayısı). Eski JK dosyalarında '# | başlık' (tek seviye).
- '# ' yeni paragraf, '~~' önceki satırın devamı.
- 'PageV01P027' 1. cildin 27. sayfasının SONU: işaretten sonrası 28. sayfadır.
- 'ms001' kesim işareti (atılır), '%~%' şiirde mısra ayracı.
"""
import re

from . import kitap as K

SAYFA = re.compile(r"PageV(\d+)P(\d+)")
MS = re.compile(r"\bms\d+\b")
BOS_SAYFA = re.compile(r"صفحة فارغة")
BASLIK = re.compile(r"^#{1,3} (\|+) ?(.*)$")
ISARET = "\ue000"  # sayfa işareti yer tutucu (özel kullanım alanı karakteri)
RESIM = re.compile(r"!?\[image[^\]]*\]\([^)]*\)")                  # ![image file](./..._0024.png)
# yazma varak/sayfa no: [133 و] [133ظ] [136]; OCR bozukları: [135 و) [158ظا [83 اظا]
VARAK = re.compile(r"\[\s*\d{1,4}\s*[اأ]?\s*[وظ]\s*ا?\s*[\]\)]?|\[\s*\d{1,4}\s*\]")
YAPISIK_NOT = re.compile(r"(?<=[^\s\d(\[])\(\d{1,4}\)")                # فهو(24): naşir dipnotu numarası (dipnotu dosyada yok)
BOSLUKLU_NOT = re.compile(r"(?<=\S)\s+\(\d{1,4}\)(?!\s*(?:هـ|ه|م)(?![\u0600-\u06FF]))")  # yıl (505 هـ) korunur
# OCR bozukları (sadece dipnot düzeni olan kitapta): )((12)  8(220)  0(405)  (3(6)  محدث)8)  أحسنه)29  (170،
BOZUK_NOT = re.compile(r"\(\(\d{1,4}\)|\d{1,2}\(\d{1,4}\)|\(\d\(\d{1,4}\)|(?<=[\u0600-\u06FF)}])\s?\d{1,4}\)|(?<=[)}])\d{1,4}(?=[\s،.؛:]|$)"
                       r"|\(\d{2,4}(?=[،.؛\s])(?!\s*(?:هـ|ه|م)(?![\u0600-\u06FF]))")

# Arapça yapı kelimeleri -> derece (küçük = üst seviye). Bilinmeyen başlık bir öncekinin altına girer.
DERECE = [
    (r"^(خطبة|فاتحة|مقدمة|المقدمة|خاتمة|الخاتمة|تمهيدات|أقطاب|القطب|قطب|الكتاب|كتاب)\b", 1),
    (r"^(التمهيد|تمهيد|القسم|قسم|الباب|باب|المقالة|مقالة|الفن|الجملة)\b", 2),
    (r"^(الفصل|فصل|الدعوى|دعوى|الصفة|الحكم|المسألة|مسألة|الأصل|الركن|الطرف|النوع)\b", 3),
]


def _derece(baslik):
    for kalip, d in DERECE:
        if re.match(kalip, baslik):
            return d
    return None


def _ar_noktalama(t):
    """Dijital metinlerdeki 'kelime ، kelime .' boşluklarını Arapça dizgi kuralına göre düzeltir."""
    t = re.sub(r"\s+([،؛:.!؟\)\]»،,;])", r"\1", t)
    t = re.sub(r"([\(\[«])\s+", r"\1", t)
    t = re.sub(r"([،؛.!؟:])(?=[^\s\d\)\]»" + ISARET + r"])", r"\1 ", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def _meta(bas):
    m = {}
    for satir in bas.splitlines():
        r = re.match(r"#META#\s*\d+\.(\w+)\s*::\s*(.*)", satir)
        if r and r.group(2).strip() not in ("NODATA", "NOTGIVEN", "NOCODE"):
            m[r.group(1)] = r.group(2).strip()
    return m


def _sayfa_etiketi(cilt, sayfa, cok_ciltli):
    return f"{cilt}/{sayfa}" if cok_ciltli else str(sayfa)


def cevir(metin, kunye_satiri=None):
    """metin: OpenITI dosyasının tamamı. kunye_satiri: katalog tablosundaki satır (dict), isteğe bağlı."""
    if "#META#Header#End#" not in metin:
        raise ValueError("OpenITI başlık sonu (#META#Header#End#) bulunamadı")
    bas, govde = metin.split("#META#Header#End#", 1)
    meta = _meta(bas)
    ks = kunye_satiri or {}
    ciltler = {int(c) for c, _ in SAYFA.findall(govde)}
    # düzeltilmemiş OCR metinleri (AOCP): kelimeye yapışık dipnot numaraları varsa naşirin dipnot düzeni vardır;
    # o zaman boşluklu olanlar da dipnot numarasıdır. Temiz metinlerde bunlar yoktur (sıralamalara dokunulmaz).
    not_duzeni = len(YAPISIK_NOT.findall(govde)) >= 5
    cok = len(ciltler) > 1

    baslik_ar = ks.get("title_ar", "").split("::")[0].strip() or meta.get("BookTITLE", "")
    yazar_ar = (ks.get("author_ar", "").split("::")[0].strip() or meta.get("AuthorAKA", "")
                or meta.get("AuthorNAME", ""))
    baski = " · ".join(x for x in (meta.get("EdPUBLISHER"), meta.get("EdPLACE"), meta.get("EdYEAR")) if x)
    kunye = {
        "baslik": {"ar": baslik_ar},
        "yazar": {"ar": yazar_ar, "lat": ks.get("author_lat_shuhra", "")},
        "asil_dil": "ar",
        "vefat_hicri": int(ks.get("date") or meta.get("AuthorDIED") or 0) or None,
        "kaynak": {"tur": "openiti", "kimlik": ks.get("versionUri", ""), "adres": ks.get("url", ""),
                   "baski": baski or ks.get("ed_info", ""),
                   "lisans": "CC BY-NC-SA 4.0 (OpenITI)"},
        "sayfa_kaynagi": baski,
        "ocr": "AOCP" in ks.get("versionUri", "") or "OCR" in ks.get("tags", "").upper(),
    }
    kit = K.yeni(kunye)

    # 1) satırları paragraf ve başlıklara topla
    ogeler = []  # (tur, ham_metin, derece_kaynak)
    for satir in govde.splitlines():
        if not satir.strip():
            continue
        m = BASLIK.match(satir)
        if m and satir.startswith(("### |", "# |", "## |")):
            ogeler.append(["baslik", m.group(2), len(m.group(1))])
        elif satir.startswith("~~"):
            if ogeler:
                ogeler[-1][1] += " " + satir[2:]
            else:
                ogeler.append(["p", satir[2:], 0])
        elif satir.startswith("# ") or satir.strip() == "#":
            ogeler.append(["p", satir[1:], 0])
        elif satir.startswith("#"):
            continue  # tanımadığımız etiket satırı
        else:
            if ogeler:
                ogeler[-1][1] += " " + satir
            else:
                ogeler.append(["p", satir, 0])

    # başlık seviyesi: dosyada birden çok çizgi derecesi varsa onlar; yoksa Arapça yapı kelimeleri
    cizgi_dereceleri = {o[2] for o in ogeler if o[0] == "baslik"}
    kelime_ile = len(cizgi_dereceleri) <= 1

    # 2) sayfa işaretlerini konumlarıyla birlikte işle
    ilk = SAYFA.search(govde)
    # ilk işaretten önceki metin, o işaretin sayfasıdır (işaret sayfanın sonunu gösterir)
    bekleyen = [_sayfa_etiketi(int(ilk.group(1)), int(ilk.group(2)), cok)] if ilk else []
    yigin = []  # (derece, seviye)
    for tur, ham, cizgi in ogeler:
        ham = MS.sub(" ", BOS_SAYFA.sub(" ", ham)).replace("%~%", "  ")
        ham = VARAK.sub(" ", RESIM.sub(" ", ham))
        if not_duzeni:
            ham = BOZUK_NOT.sub("", BOSLUKLU_NOT.sub("", YAPISIK_NOT.sub("", ham)))
        etiketler = []
        def _yer(m):
            c, s = int(m.group(1)), int(m.group(2))
            etiketler.append(_sayfa_etiketi(c, s + 1, cok))  # işaretten sonrası bir sonraki sayfa
            return ISARET
        ham = SAYFA.sub(_yer, ham)
        temiz = _ar_noktalama(ham)
        # işaretlerin temiz metindeki konumları (işaret kelimeler arasında durur; konum = sonraki kelimenin başı)
        parcalar = temiz.split(ISARET)
        sade, konumlar = re.sub(r"\s+", " ", parcalar[0]).strip(), []
        for pc in parcalar[1:]:
            konumlar.append(len(sade) + 1 if sade else 0)
            pc = re.sub(r"\s+", " ", pc).strip()
            sade = (sade + " " + pc).strip() if pc else sade
        if not sade:
            bekleyen += etiketler  # boş öğe (ör. yalnız sayfa işareti): sonraki bloğa geçer
            continue
        sayfalar = [{"no": e, "konum": {"ar": 0}} for e in bekleyen]
        bekleyen = []
        for e, kn in zip(etiketler, konumlar):
            if kn >= len(sade) - 1:
                bekleyen.append(e)  # paragraf sonunda: sonraki bloğun başına
            else:
                sayfalar.append({"no": e, "konum": {"ar": kn}})
        if tur == "baslik":
            sade = re.sub(r"^[.\s]+", "", sade)
            if kelime_ile:
                d = _derece(sade)
                if d is None:
                    seviye = (yigin[-1][1] + 1) if yigin else 1
                else:
                    while yigin and yigin[-1][0] >= d:
                        yigin.pop()
                    seviye = len(yigin) + 1
                    yigin.append((d, seviye))
            else:
                seviye = cizgi
            K.blok_ekle(kit, "baslik", {"ar": sade}, seviye=min(seviye, 6), sayfalar=sayfalar)
        else:
            K.blok_ekle(kit, "p", {"ar": sade}, sayfalar=sayfalar)
    return kit
