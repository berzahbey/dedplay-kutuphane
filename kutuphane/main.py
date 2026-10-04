"""Dedplay Kütüphane: kitap arama, ekleme, EPUB üretme (ve ileride okuma/düzeltme)."""
import os
import re
from urllib.parse import quote

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from fastapi import File, UploadFile

from . import ceviri, cikti, depo, epub, epubcheck, katalog, kaynak, osmanlica
from . import kitap as K

KAYNAK = os.environ.get("KAYNAK_DIR", "/kaynak")
UZANTILAR = (".pdf", ".epub", ".docx", ".txt")

SURUM = "0.5.15"
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
    return {"surum": SURUM, "epubcheck": epubcheck.var_mi(), "servisler": s, "cikti": os.path.isdir(cikti.CIKTI),
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


# ---------------- Elindeki kitaplar: sunucu arşivi ve yükleme ----------------
def _guvenli(yol):
    tam = os.path.realpath(os.path.join(KAYNAK, (yol or "").lstrip("/")))
    if tam != os.path.realpath(KAYNAK) and not tam.startswith(os.path.realpath(KAYNAK) + os.sep):
        raise HTTPException(400, "Geçersiz yol")
    return tam


@app.get("/api/kaynak")
def kaynak_gez(yol: str = ""):
    tam = _guvenli(yol)
    if not os.path.isdir(tam):
        raise HTTPException(404, "Klasör bulunamadı (arşiv bağlı mı?)")
    klasor, dosya = [], []
    for ad in sorted(os.listdir(tam), key=lambda x: x.lower()):
        if ad.startswith("."):
            continue
        p = os.path.join(tam, ad)
        if os.path.isdir(p):
            klasor.append(ad)
        elif ad.lower().endswith(UZANTILAR):
            dosya.append({"ad": ad, "boyut": os.path.getsize(p)})
    ekli = {k["kimlik"] for k in depo.liste()}
    for f in dosya:
        f["ekli"] = kaynak.kimlik_uret(os.path.join(tam, f["ad"])) in ekli
    return {"yol": os.path.relpath(tam, KAYNAK) if tam != os.path.realpath(KAYNAK) else "", "klasor": klasor, "dosya": dosya}


def _dosya_isi(yol, gorunen_ad):
    import time
    kid = kaynak.kimlik_uret(yol)
    ilk = depo.durum_oku(kid)
    baslik, yazar = kaynak._dosya_adindan(gorunen_ad)
    depo.is_ekle("dosya", kid, yol, tur="dosya", kaynak_kimlik=yol, baslik=ilk.get("baslik") or baslik,
                 baslik_asil=ilk.get("baslik_asil") or baslik, yazar=ilk.get("yazar") or yazar,
                 eklendi=ilk.get("eklendi") or int(time.time()))
    return {"ok": True, "kimlik": kid}


class SunucuDosyasi(BaseModel):
    yol: str


@app.post("/api/kitaplar/sunucudan")
def sunucudan_ekle(g: SunucuDosyasi):
    tam = _guvenli(g.yol)
    if not os.path.isfile(tam) or not tam.lower().endswith(UZANTILAR):
        raise HTTPException(400, "Sadece PDF, EPUB, DOCX ve TXT dosyaları eklenebilir")
    return _dosya_isi(tam, os.path.basename(tam))


class MetinIstegi(BaseModel):
    baslik: str
    metin: str


@app.post("/api/kitaplar/metin")
def metin_ekle(g: MetinIstegi):
    """Yapıştırılan metin: TXT dosyası olarak kaydedilir, yüklenen kitap gibi işlenir (temizlik, okuma ekranı)."""
    baslik = re.sub(r"[\\/:*?\"<>|]+", " ", (g.baslik or "").strip())[:120].strip() or "Metin"
    if len(g.metin.strip()) < 20:
        raise HTTPException(400, "Metin çok kısa")
    klasor = os.path.join(depo.VERI, "yuklenen")
    os.makedirs(klasor, exist_ok=True)
    hedef = os.path.join(klasor, baslik + ".txt")
    with open(hedef, "w", encoding="utf-8") as f:
        f.write(g.metin)
    return _dosya_isi(hedef, baslik + ".txt")


@app.post("/api/kitaplar/yukle")
def yukle(dosya: UploadFile = File(...)):
    ad = os.path.basename(dosya.filename or "kitap")
    if not ad.lower().endswith(UZANTILAR):
        raise HTTPException(400, "Sadece PDF, EPUB, DOCX ve TXT dosyaları yüklenebilir")
    klasor = os.path.join(depo.VERI, "yuklenen")
    os.makedirs(klasor, exist_ok=True)
    hedef = os.path.join(klasor, ad)
    with open(hedef + ".tmp", "wb") as f:
        while True:
            parca = dosya.file.read(1024 * 1024)
            if not parca:
                break
            f.write(parca)
    os.replace(hedef + ".tmp", hedef)
    return _dosya_isi(hedef, ad)


@app.post("/api/kitaplar/{kid}/osmanlica")
def osmanlicayi_yenile(kid: str):
    kit = _kitap(kid)
    if not any(b["metin"].get("tr") for b in kit["bloklar"]):
        raise HTTPException(400, "Bu kitapta henüz Türkçe metin yok")
    depo.is_ekle("osmanlica", kid, tur="epub")
    return {"ok": True}


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
        asil = kit["kunye"].get("asil_dil", "tr")
        if asil != "tr":
            _, eksik = ceviri.cevrilecekler(kit, asil)
            out["ceviri_eksik"] = {"paragraf": len(eksik), "tahmini_sn": ceviri.tahmini_sure(eksik), "model": ceviri.MODEL}
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
    degisti = False
    for alan, deger in (("baslik", k.baslik_tr), ("yazar", k.yazar_tr)):
        if deger is not None and deger.strip() != kit["kunye"].get(alan, {}).get("tr", ""):
            kit["kunye"].setdefault(alan, {})["tr"] = deger.strip()
            kit["kunye"][alan]["elle"] = True
            kit["kunye"][alan].pop("osm", None)  # Osmanlıcası yeniden çevrilecek
            degisti = True
    K.kaydet(kit, depo.kitap_yolu(kid))
    tr_asilli = kit["kunye"].get("asil_dil") == "tr"
    depo.is_ekle("kunye" if (degisti and tr_asilli) else "epub", kid, tur="epub")
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


@app.post("/api/kitaplar/{kid}/studyo")
def studyoya_gonder(kid: str):
    kit = _kitap(kid)
    d = depo.durum_oku(kid)
    if d.get("asama") not in ("hazır", "hata") or not d.get("epublar"):
        raise HTTPException(409, "Kitap henüz hazır değil")
    if "tr" not in K.diller(kit):
        raise HTTPException(409, "Kitabın Türkçesi yok: önce Türkçeye çevrilmeli ('Türkçeye çevir ve Stüdyo'ya gönder')")
    try:
        sonuc = cikti.studyoya_gonder(kit)
    except requests.RequestException as e:
        raise HTTPException(503, f"Stüdyo'ya ulaşılamadı: {type(e).__name__}")
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    depo.durum_yaz(kid, studyo=sonuc)
    return sonuc


class CeviriIstegi(BaseModel):
    sonra_studyo: bool = False


@app.post("/api/kitaplar/{kid}/cevir")
@app.delete("/api/kitaplar/{kid}/cevir")
def cevir_kaldirildi(kid: str):
    raise HTTPException(410, "Çeviri kaldırıldı (0.5.8)")


# ---------------- Okuma ve düzeltme ----------------
@app.get("/oku/{kid}", response_class=HTMLResponse)
def oku_sayfasi(kid: str):
    return open(os.path.join(STATIK, "oku.html"), encoding="utf-8").read()


def _okuma_dili(kit):
    d = K.diller(kit)
    return "tr" if "tr" in d else (d[0] if d else kit["kunye"].get("asil_dil", "tr"))


@app.get("/api/kitaplar/{kid}/oku")
def oku_bilgi(kid: str):
    kit = _kitap(kid)
    yapi = epub.bolum_yapisi(kit, _okuma_dili(kit))
    d = depo.durum_oku(kid)
    return {"kimlik": kid, "kunye": kit["kunye"], "diller": K.diller(kit),
            "bolumler": [{"no": i, "etiket": b["etiket"], "alt": b["alt"], "blok": len(b["bloklar"])} for i, b in enumerate(yapi)],
            "konum": d.get("konum") or {"bolum": 0, "blok": None}, "asama": d.get("asama")}


def _blok_ozeti(b):
    sayfa = next((s["no"] for s in b.get("sayfalar", [])), None)
    return {"id": b["id"], "tur": b["tur"], "seviye": b.get("seviye"), "metin": b["metin"], "silindi": bool(b.get("silindi")),
            "elle": b.get("elle") or {}, "gecmis": len(b.get("gecmis", [])), "sayfa": sayfa}


@app.get("/api/kitaplar/{kid}/bolum/{no}")
def oku_bolum(kid: str, no: int):
    kit = _kitap(kid)
    yapi = epub.bolum_yapisi(kit, _okuma_dili(kit))
    if not 0 <= no < len(yapi):
        raise HTTPException(404, "Böyle bir bölüm yok")
    ids = set(yapi[no]["bloklar"])
    bloklar = [_blok_ozeti(b) for b in kit["bloklar"] if b["id"] in ids]
    atif = set()
    for b in bloklar:
        for t in b["metin"].values():
            atif |= set(K.NOT_ISARETI.findall(t or ""))
    notlar = {g: n["metin"] for g, n in kit.get("dipnotlar", {}).items() if g in atif}
    sira = {g: i + 1 for i, g in enumerate(kit.get("dipnotlar", {}))}
    return {"no": no, "etiket": yapi[no]["etiket"], "bloklar": bloklar, "dipnotlar": notlar,
            "not_no": {g: sira[g] for g in notlar}, "toplam": len(yapi)}


class BlokDegisiklik(BaseModel):
    dil: str | None = None
    metin: str | None = None
    tur: str | None = None
    seviye: int | None = None
    silindi: bool | None = None


def _duzenle(kid, islem):
    """kitap.json'u kilit altında yükle-değiştir-kaydet; sonra EPUB'ları yeniden üretmeyi kuyruğa koy."""
    kilit = depo.kitap_kilidi(kid)
    if not kilit.acquire(timeout=3):
        raise HTTPException(409, "Kitap şu an arka planda işleniyor; biraz sonra tekrar dene")
    try:
        kit = _kitap(kid)
        sonuc = islem(kit)
        K.kaydet(kit, depo.kitap_yolu(kid))
    finally:
        kilit.release()
    depo.is_ekle("epub", kid, tur="epub")
    return sonuc


@app.patch("/api/kitaplar/{kid}/blok/{bid}")
def blok_duzelt(kid: str, bid: str, g: BlokDegisiklik):
    uyari = []

    def islem(kit):
        try:
            b = K.blok_bul(kit, bid)
        except KeyError:
            raise HTTPException(404, "Böyle bir paragraf yok")
        if g.metin is not None:
            dil = g.dil or "tr"
            yeni = " ".join(g.metin.split())
            if not yeni:
                raise HTTPException(400, "Metin boş olamaz; satırı kaldırmak için 'Sil'i kullan")
            eski = b["metin"].get(dil, "")
            if sorted(K.NOT_ISARETI.findall(eski)) != sorted(K.NOT_ISARETI.findall(yeni)):
                raise HTTPException(400, "Dipnot işaretleri ({{n…}}) değiştirilmemeli; metni işaretlere dokunmadan düzelt")
            if K.duzelt(kit, bid, dil, yeni) and dil == "tr" and b["metin"].get("osm") is not None \
                    and not b.get("elle", {}).get("osm"):
                try:  # Türkçe düzeldi: Osmanlıcası da yenilenir (elle düzeltilmiş Osmanlıca korunur)
                    osm_eski = b["metin"]["osm"]
                    b["metin"]["osm"] = osmanlica.blok_cevir(yeni)
                    b["gecmis"][-1]["osm_eski"] = osm_eski  # "Geri al" Osmanlıcayı da eski hâline döndürsün
                except Exception as e:
                    uyari.append(f"Osmanlıcası yenilenemedi ({type(e).__name__}); Türkçe kaydedildi")
        if g.tur is not None:
            try:
                K.tur_degistir(kit, bid, g.tur, g.seviye)
            except ValueError as e:
                raise HTTPException(400, str(e))
        if g.silindi is not None:
            K.sil(kit, bid, g.silindi)
        return _blok_ozeti(K.blok_bul(kit, bid))
    blok = _duzenle(kid, islem)
    return {"blok": blok, "uyari": uyari}


@app.post("/api/kitaplar/{kid}/blok/{bid}/geri")
def blok_geri_al(kid: str, bid: str):
    def islem(kit):
        try:
            if not K.geri_al(kit, bid):
                raise HTTPException(400, "Geri alınacak bir değişiklik yok")
        except KeyError:
            raise HTTPException(404, "Böyle bir paragraf yok")
        return _blok_ozeti(K.blok_bul(kit, bid))
    return {"blok": _duzenle(kid, islem)}


class Konum(BaseModel):
    bolum: int
    blok: str | None = None


@app.put("/api/kitaplar/{kid}/konum")
def konum_kaydet(kid: str, k: Konum):
    if not depo.durum_oku(kid):
        raise HTTPException(404, "Böyle bir kitap yok")
    depo.durum_yaz(kid, konum={"bolum": k.bolum, "blok": k.blok})
    return {"ok": True}


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)
