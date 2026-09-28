"""Basit, sade kapak görseli (PNG). Arap harfli başlıklar Amiri ile, Latin harfliler serif yazı tipiyle."""
import io
import os
import re

from PIL import Image, ImageDraw, ImageFont, features

RAQM = features.check("raqm")  # Arapça harf birleştirme; yoksa Arapça satırlar kapağa basılmaz

AMIRI_ADAY = ["/usr/share/fonts/truetype/amiri/Amiri-Bold.ttf",
              os.path.join(os.environ.get("FONT_DIR", "/usr/share/fonts/truetype/amiri"), "Amiri-Bold.ttf")]
LATIN_ADAY = ["/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
              "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"]
ARAP = re.compile(r"[\u0600-\u06FF]")
W, H = 1600, 2400
ZEMIN, ALTIN, KREM = (22, 52, 45), (201, 168, 92), (242, 234, 214)


def _font(adaylar, boy):
    for y in adaylar:
        if os.path.exists(y):
            return ImageFont.truetype(y, boy, layout_engine=ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC)
    return ImageFont.load_default()


def _satirlar(ciz, metin, font, genislik, rtl):
    kelimeler, satirlar, cur = metin.split(), [], ""
    for k in kelimeler:
        dene = (cur + " " + k).strip()
        if ciz.textlength(dene, font=font, direction="rtl" if rtl else None) <= genislik or not cur:
            cur = dene
        else:
            satirlar.append(cur)
            cur = k
    if cur:
        satirlar.append(cur)
    return satirlar


def _yaz(ciz, metin, y, boy, renk, azami_satir=4):
    rtl = bool(ARAP.search(metin))
    if rtl and not RAQM:
        return y
    while boy > 30:
        font = _font(AMIRI_ADAY if rtl else LATIN_ADAY, boy)
        satirlar = _satirlar(ciz, metin, font, W - 360, rtl)
        if len(satirlar) <= azami_satir:
            break
        boy -= 8
    aralik = int(boy * (1.55 if rtl else 1.3))
    for s in satirlar:
        kw = {"direction": "rtl", "language": "ar"} if rtl else {}
        g = ciz.textlength(s, font=font, **({"direction": "rtl"} if rtl else {}))
        ciz.text(((W - g) / 2, y), s, font=font, fill=renk, **kw)
        y += aralik
    return y


def uret(baslik, yazar="", alt="", ust=""):
    img = Image.new("RGB", (W, H), ZEMIN)
    c = ImageDraw.Draw(img)
    for pay, kal in ((70, 6), (95, 2)):
        c.rectangle([pay, pay, W - pay, H - pay], outline=ALTIN, width=kal)
    c.line([(W / 2 - 160, 1190), (W / 2 + 160, 1190)], fill=ALTIN, width=3)
    if ust:
        _yaz(c, ust, 300, 64, ALTIN, 2)
    y = _yaz(c, baslik, 560, 132, KREM, 4)
    if alt:
        _yaz(c, alt, max(y + 40, 900), 70, KREM, 3)
    if yazar:
        _yaz(c, yazar, 1300, 96, ALTIN, 3)
    b = io.BytesIO()
    img.save(b, "PNG", optimize=True)
    return b.getvalue()
