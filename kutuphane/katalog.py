"""OpenITI katalogu: künye tablosunu indirir, önbelleğe alır, Türkçe yazımla arar.

Arama: yazılan ve tablodaki adlar aynı sade biçime indirilir (şapkasız; ş=sh, ç=ch, k=q, ğ=gh;
el-/ibn/ebu yok sayılır; çift harf tek; e/a, o/u, y/i eşit). Böylece "gazali iktisad" yazınca
"al-Ġazālī … Iqtisad" bulunur. Arapça harfle de aranabilir.
"""
import csv
import io
import os
import re
import threading
import time
import unicodedata

import requests

URL = ("https://raw.githubusercontent.com/OpenITI/kitab-metadata-automation/master/output/"
       "OpenITI_Github_clone_metadata_light.csv")
ESKI_SAYILIR = 30 * 24 * 3600  # 30 günden eski önbellek yenilenir
_kilit = threading.Lock()
_veri = {"satirlar": None, "zaman": 0}
ARAP = re.compile(r"[\u0600-\u06FF]")
HAREKE = re.compile(r"[\u064B-\u065F\u0670\u0640]")


def sade(s):
    s = (s or "").lower()
    for a, b in [("ı", "i"), ("ş", "s"), ("ç", "c"), ("ğ", "g"), ("ö", "o"), ("ü", "u"),
                 ("sh", "s"), ("ch", "c"), ("th", "s"), ("dh", "z"), ("kh", "h"), ("gh", "g"),
                 ("ġ", "g"), ("q", "k"), ("w", "v"), ("ʿ", ""), ("ʾ", ""), ("'", ""), ("’", ""), ("‘", "")]:
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\b(al|el|ul|il|ibn|bin|b|abu|ebu|ibni|bnt)\b", " ", s.replace("-", " "))
    s = re.sub(r"(.)\1", r"\1", s)
    s = s.replace("e", "a").replace("o", "u").replace("y", "i").replace("j", "c")
    return " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip() + " "


def sade_ar(s):
    s = HAREKE.sub("", s or "")
    return s.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"}))


def _yol(veri_klasoru):
    return os.path.join(veri_klasoru, "openiti", "katalog.csv")


def indir(veri_klasoru):
    yol = _yol(veri_klasoru)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    r = requests.get(URL, timeout=300)
    r.raise_for_status()
    with open(yol + ".tmp", "wb") as f:
        f.write(r.content)
    os.replace(yol + ".tmp", yol)
    _veri["satirlar"] = None


def yukle(veri_klasoru, indirmeye_izin=True):
    """Birincil sürüm satırlarını döndürür (bellekte tutulur)."""
    with _kilit:
        yol = _yol(veri_klasoru)
        if indirmeye_izin and (not os.path.exists(yol) or time.time() - os.path.getmtime(yol) > ESKI_SAYILIR):
            try:
                indir(veri_klasoru)
            except Exception:
                if not os.path.exists(yol):
                    raise
        if _veri["satirlar"] is not None and _veri["zaman"] == os.path.getmtime(yol):
            return _veri["satirlar"]
        csv.field_size_limit(10 ** 9)
        satirlar = []
        with open(yol, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if r.get("status") != "pri":
                    continue
                s = {k: r.get(k, "") for k in ("versionUri", "date", "author_ar", "author_lat_shuhra",
                                                "author_lat_full_name", "title_ar", "title_lat", "tok_length",
                                                "url", "tags", "book")}
                s["_lat"] = sade(" ".join([s["author_lat_shuhra"], s["author_lat_full_name"], s["title_lat"],
                                           s["book"]]))
                s["_ar"] = sade_ar(s["author_ar"] + " " + s["title_ar"])
                satirlar.append(s)
        _veri.update(satirlar=satirlar, zaman=os.path.getmtime(yol))
        return satirlar


def ara(veri_klasoru, sorgu, azami=50):
    satirlar = yukle(veri_klasoru)
    sorgu = (sorgu or "").strip()
    if not sorgu:
        return []
    if ARAP.search(sorgu):
        kel = sade_ar(sorgu).split()
        bul = [s for s in satirlar if all(k in s["_ar"] for k in kel)]
    else:
        kel = sade(sorgu).split()
        bul = [s for s in satirlar if all(k in s["_lat"] for k in kel)]

    def puan(s):
        tam = sum(1 for k in kel if f" {k} " in (s["_lat"] if not ARAP.search(sorgu) else f" {s['_ar']} "))
        try:
            uzun = int(s["tok_length"] or 0)
        except ValueError:
            uzun = 0
        return (-tam, -min(uzun, 2_000_000))
    bul.sort(key=puan)
    out = [{k: v for k, v in s.items() if not k.startswith("_")} for s in bul[:azami]]
    for s in out:  # düzeltilmemiş OCR (AOCP): metinde okuma hataları olabilir
        s["ocr"] = "AOCP" in s["versionUri"] or "OCR" in (s.get("tags") or "").upper()
    return out


def bul(veri_klasoru, version_uri):
    return next((s for s in yukle(veri_klasoru) if s["versionUri"] == version_uri), None)
