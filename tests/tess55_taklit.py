"""Tesseract 5.5 taklidi: yan yana iki kitap sayfasında aynı yükseklikteki satırlar tek satır olarak verilir.
TESS55_KIP=satir: sağ yarının bütün satırı sol satıra katılır (sunucuda görülen); kelime: kelimeler tek tek dağıtılır."""
import os
import pytesseract
_asil = pytesseract.image_to_data


def _birlestiren(img, *a, **k):
    d = _asil(img, *a, **k)
    W = img.size[0]
    if W < img.size[1] * 1.1 or not isinstance(d, dict):
        return d
    n = len(d["text"])
    dolu = [j for j in range(n) if (d["text"][j] or "").strip()]
    anahtar = lambda j: (d["block_num"][j], d["par_num"][j], d["line_num"][j])
    sol = [j for j in dolu if d["left"][j] + d["width"][j] / 2 < W / 2]
    sag = [j for j in dolu if d["left"][j] + d["width"][j] / 2 >= W / 2]
    if os.environ.get("TESS55_KIP", "satir") == "kelime":
        gruplar = [[j] for j in sag]
    else:
        gruplar = {}
        for j in sag:
            gruplar.setdefault(anahtar(j), []).append(j)
        gruplar = list(gruplar.values())
    for g in gruplar:
        top = min(d["top"][j] for j in g)
        yakin = min(sol, key=lambda s: abs(d["top"][s] - top), default=None)
        if yakin is not None and abs(d["top"][yakin] - top) < d["height"][g[0]] * 0.6:
            for j in g:
                d["block_num"][j], d["par_num"][j], d["line_num"][j] = anahtar(yakin)
    return d




def kur(kip="satir"):
    os.environ["TESS55_KIP"] = kip
    pytesseract.image_to_data = _birlestiren


def kaldir():
    pytesseract.image_to_data = _asil
