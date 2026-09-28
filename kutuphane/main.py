"""Dedplay Kütüphane: kitap arama, ekleme, EPUB üretme (ve ileride okuma/düzeltme)."""
import os
from urllib.parse import quote

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from . import depo, epubcheck, katalog
from . import kitap as K

SURUM = "0.1.0"
STATIK = os.path.join(os.path.dirname(__file__), "static")
HOST = "http://host.docker.internal"
SERVISLER = {
    "Stüdyo": os.environ.get("STUDYO_URL", f"{HOST}:8070") + "/api/services",
    "Translate": os.environ.get("TRANSLATE_URL", f"{HOST}:8060") + "/api/status",
    "Osmanlıca": os.environ.get("OSMANLICA_URL", f"{HOST}:8089") + "/",
}

app = FastAPI(title="Dedplay Kütüphane", version=SURUM)


@app.on_event("startup")
def _basla():
    os.makedirs(depo.KITAPLAR, exist_ok=True)
    depo.baslat()


@app.get("/", response_class=HTMLResponse)
def ana():
    return open(os.path.join(STATIK, "index.html"), encoding="utf-8").read()


@app.get("/api/durum")
def durum():
    s = {}
    for ad, url in SERVISLER.items():
        try:
            s[ad] = requests.get(url, timeout=3).status_code < 500
        except Exception:
            s[ad] = False
    kat = os.path.join(depo.VERI, "openiti", "katalog.csv")
    return {"surum": SURUM, "epubcheck": epubcheck.var_mi(), "servisler": s,
            "katalog": os.path.exists(kat), "katalog_tarih": int(os.path.getmtime(kat)) if os.path.exists(kat) else None}


# ---------------- OpenITI katalogu ----------------
@app.get("/api/katalog/ara")
def katalog_ara(q: str, azami: int = 50):
    try:
        sonuc = katalog.ara(depo.VERI, q, min(max(azami, 1), 200))
    except Exception as e:
        raise HTTPException(503, f"Katalog yüklenemedi: {e}")
    ekli = {k["kimlik"] for k in depo.liste()}
    for s in sonuc:
        s["ekli"] = s["versionUri"] in ekli
    return sonuc


@app.post("/api/katalog/yenile")
def katalog_yenile():
    try:
        katalog.indir(depo.VERI)
        return {"ok": True, "eser": len(katalog.yukle(depo.VERI, indirmeye_izin=False))}
    except Exception as e:
        raise HTTPException(503, f"Katalog indirilemedi: {e}")


class OpenitiEkle(BaseModel):
    version_uri: str


@app.post("/api/kitaplar/openiti")
def openiti_ekle(g: OpenitiEkle):
    satir = katalog.bul(depo.VERI, g.version_uri)
    if not satir:
        raise HTTPException(404, "Katalogda böyle bir eser yok")
    kid = g.version_uri
    depo.klasor(kid)  # kimlik denetimi
    import time
    ilk = depo.durum_oku(kid)
    depo.is_ekle("openiti", kid, g.version_uri, tur="openiti", kaynak_kimlik=g.version_uri,
                 baslik=ilk.get("baslik") or satir["title_ar"].split("::")[0].strip(),
                 baslik_asil=satir["title_ar"].split("::")[0].strip(),
                 yazar=ilk.get("yazar") or satir["author_ar"].split("::")[0].strip(),
                 eklendi=ilk.get("eklendi") or int(time.time()))
    return {"ok": True, "kimlik": kid}


# ---------------- Kitaplar ----------------
@app.get("/api/kitaplar")
def kitaplar():
    return depo.liste()


def _kitap(kid):
    try:
        yol = depo.kitap_yolu(kid)
    except ValueError:
        raise HTTPException(400, "Geçersiz kitap kimliği")
    if not os.path.exists(yol):
        raise HTTPException(404, "Kitap henüz hazır değil")
    return K.yukle(yol)


@app.get("/api/kitaplar/{kid}")
def kitap_ayrinti(kid: str):
    d = depo.durum_oku(kid) if depo.KIMLIK.match(kid) else None
    if not d:
        raise HTTPException(404, "Böyle bir kitap yok")
    out = {"kimlik": kid, "durum": d}
    if os.path.exists(depo.kitap_yolu(kid)):
        kit = K.yukle(depo.kitap_yolu(kid))
        bl = kit["bloklar"]
        out["kunye"] = kit["kunye"]
        out["diller"] = K.diller(kit)
        out["fihrist"] = [{"id": b["id"], "seviye": b.get("seviye", 1), "metin": b["metin"]}
                          for b in bl if b["tur"] == "baslik"]
        out["istatistik"] = {"blok": len(bl), "baslik": len(out["fihrist"]),
                             "sayfa": sum(len(b.get("sayfalar", [])) for b in bl),
                             "kelime": sum(len((b["metin"].get(kit["kunye"].get("asil_dil", "ar")) or "").split())
                                           for b in bl)}
    return out


class Kunye(BaseModel):
    baslik_tr: str | None = None
    yazar_tr: str | None = None


@app.patch("/api/kitaplar/{kid}/kunye")
def kunye_duzelt(kid: str, k: Kunye):
    kit = _kitap(kid)
    if k.baslik_tr is not None:
        kit["kunye"]["baslik"]["tr"] = k.baslik_tr.strip()
    if k.yazar_tr is not None:
        kit["kunye"]["yazar"]["tr"] = k.yazar_tr.strip()
    K.kaydet(kit, depo.kitap_yolu(kid))
    depo.is_ekle("epub", kid, tur="epub")
    return {"ok": True}


@app.post("/api/kitaplar/{kid}/yeniden")
def yeniden(kid: str):
    _kitap(kid)
    depo.is_ekle("epub", kid, tur="epub")
    return {"ok": True}


@app.get("/api/kitaplar/{kid}/epub/{dosya}")
def epub_indir(kid: str, dosya: str):
    d = depo.durum_oku(kid) if depo.KIMLIK.match(kid) else {}
    if dosya not in {e["dosya"] for e in d.get("epublar") or []}:
        raise HTTPException(404, "Böyle bir EPUB yok")
    yol = os.path.join(depo.klasor(kid), "epub", dosya)
    if not os.path.exists(yol):
        raise HTTPException(404, "Dosya bulunamadı (yeniden üretiliyor olabilir)")
    return FileResponse(yol, media_type="application/epub+zip",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(dosya)}"})


@app.delete("/api/kitaplar/{kid}")
def kitap_sil(kid: str):
    d = depo.durum_oku(kid) if depo.KIMLIK.match(kid) else None
    if not d:
        raise HTTPException(404, "Böyle bir kitap yok")
    if d.get("asama") not in ("hazır", "hata"):
        raise HTTPException(409, "Kitap şu an işleniyor; bitince silebilirsiniz")
    depo.sil(kid)
    return {"ok": True}


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)
