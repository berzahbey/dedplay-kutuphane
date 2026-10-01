"""Dedplay Kütüphane simgesi: ailenin düzeni (üstte "dedplay", ortada kırmızı sembol, altta uygulama adı);
sembol oynat düğmesi yerine açık kitap. Çalıştırma: python make_icon.py <çıktı.png>"""
import os
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

YAZI_TIPI = "https://raw.githubusercontent.com/google/fonts/main/ofl/firasanscondensed/"
RED, AD_RENK = (224, 38, 43), (176, 106, 20)  # ailenin kırmızısı; "kütüphane" koyu kehribar (studio yeşil, translate mavi)


def font(ad, boy):
    yol = f"/tmp/{ad}.ttf"
    if not os.path.exists(yol):
        urllib.request.urlretrieve(YAZI_TIPI + ad + ".ttf", yol)
    return ImageFont.truetype(yol, boy)


def egri(p0, k, p1, n=40):
    """İkinci derece Bézier eğrisi noktaları."""
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * k[0] + t ** 2 * p1[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * k[1] + t ** 2 * p1[1]) for t in (i / n for i in range(n + 1))]


k = 2
S = 1024 * k
img = Image.new("RGB", (S, S), "white")
d = ImageDraw.Draw(img)
d.text((S / 2, 350 * k), "dedplay", font=font("FiraSansCondensed-SemiBold", 192 * k), fill="black", anchor="ms")

cx, ust, alt, gen = 512, 455, 675, 255  # açık kitap: ortası (sırt), üst/alt kenar, bir sayfanın genişliği
cizgi = 18
for yon in (-1, 1):  # sol ve sağ sayfa
    dis = cx + yon * gen
    kapak = egri((cx, alt + 26), (cx + yon * gen * 0.5, alt - 4), (dis + yon * 14, alt + 6))
    d.polygon([(x * k, y * k) for x, y in [(cx, alt - 10)] + kapak + [(dis + yon * 14, ust + 30)]], fill=RED)
    ustk = egri((cx, ust + 22), (cx + yon * gen * 0.45, ust - 30), (dis, ust))
    altk = egri((dis, alt - 18), (cx + yon * gen * 0.45, alt - 52), (cx, alt))
    sayfa = [(x * k, y * k) for x, y in ustk + altk]
    d.polygon(sayfa, fill="white")
    d.line(sayfa + [sayfa[0]], fill=RED, width=cizgi * k, joint="curve")
    for n in range(1, 5):  # yazı satırları: üst kenara koşut
        dy = n * 36
        sat = egri((cx + yon * 34, ust + 22 + dy), (cx + yon * gen * 0.45, ust - 30 + dy * 0.98), (dis - yon * 34, ust + dy - 4))
        d.line([(x * k, y * k) for x, y in sat], fill=RED, width=9 * k, joint="curve")
d.line([(cx * k, (ust + 20) * k), (cx * k, alt * k)], fill=RED, width=cizgi * k)  # sırt

d.text((S / 2, 820 * k), "kütüphane", font=font("FiraSansCondensed-Medium", 104 * k), fill=AD_RENK, anchor="ms")
img.resize((512, 512), Image.LANCZOS).save(sys.argv[1] if len(sys.argv) > 1 else "icon.png")
print("simge hazır")
