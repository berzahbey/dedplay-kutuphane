"""Kitapların diskteki düzeni ve arka plan işleri.

/data/kitaplar/<kimlik>/kitap.json   tek kaynak
/data/kitaplar/<kimlik>/durum.json   iş durumu, EPUB listesi, denetim sonuçları
/data/kitaplar/<kimlik>/kaynak.txt   indirilen asıl metin (yeniden okumak için)
/data/kitaplar/<kimlik>/epub/*.epub
"""
import json
import os
import queue
import re
import shutil
import threading
import time
import traceback
import unicodedata

import requests

from . import epub as EPUB
from . import epubcheck, kaynak, katalog, openiti, osmanlica
from . import kitap as K

VERI = os.environ.get("DATA_DIR", "/data")
KITAPLAR = os.path.join(VERI, "kitaplar")
KIMLIK = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
DIL_AD = {"ar": "arapca", "en": "ingilizce", "fr": "fransizca", "fa": "farsca"}
_kuyruk = queue.Queue()
_kilit = threading.Lock()
_kitap_kilitleri = {}
_bekleyen_epub = set()  # kuyrukta bekleyen EPUB işleri: art arda düzeltmelerde tek iş


def kitap_kilidi(kid):
    """kitap.json'u yazan her iş (arka plan ya da okuma ekranı) bu kilidi tutar: düzeltmeler kaybolmaz."""
    with _kilit:
        return _kitap_kilitleri.setdefault(kid, threading.Lock())


def klasor(kid):
    if not KIMLIK.match(kid or ""):
        raise ValueError("geçersiz kitap kimliği")
    return os.path.join(KITAPLAR, kid)


def durum_oku(kid):
    yol = os.path.join(klasor(kid), "durum.json")
    try:
        return json.load(open(yol, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def durum_yaz(kid, **kw):
    with _kilit:
        d = durum_oku(kid)
        d.update(kw)
        d["guncellendi"] = int(time.time())
        yol = os.path.join(klasor(kid), "durum.json")
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with open(yol + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(yol + ".tmp", yol)
        return d


def liste():
    if not os.path.isdir(KITAPLAR):
        return []
    out = []
    for kid in sorted(os.listdir(KITAPLAR)):
        if not KIMLIK.match(kid) or not os.path.isdir(os.path.join(KITAPLAR, kid)):
            continue
        d = durum_oku(kid)
        out.append({"kimlik": kid, **{k: d.get(k) for k in ("baslik", "baslik_asil", "yazar", "asama", "hata", "uyari", "guncellendi",
                                                            "eklendi", "epublar")}})
    return sorted(out, key=lambda x: -(x.get("eklendi") or 0))


def kitap_yolu(kid):
    return os.path.join(klasor(kid), "kitap.json")


def surumler(kit):
    """Kitaptaki dillere göre üretilecek EPUB sürümleri (dosya eki, diller)."""
    d = K.diller(kit)
    asil = kit["kunye"].get("asil_dil", "ar")
    out = []
    if "tr" in d:
        out.append(("turkce", ["tr"]))
    if "osm" in d:
        out.append(("osmanlica", ["osm"]))
    if "tr" in d and "osm" in d:
        out.append(("turkce-osmanlica", ["tr", "osm"]))
    if asil not in ("tr", "osm"):  # yabancı asıl (Arapça, İngilizce…): asıllı sürümler
        ad = DIL_AD.get(asil, asil)
        if asil in d and "tr" in d:
            out.append((f"{ad}-turkce", [asil, "tr"]))
        if asil in d:
            out.append((ad, [asil]))
    return out


def _dosya_adi(kid, kit):
    """Sade harfli dosya adı (şapka/Türkçe harf yok): her cihazda ve ağ paylaşımında sorunsuz."""
    b = kit["kunye"]["baslik"].get("tr") or (kid.split(".")[1] if "." in kid else kid)
    b = b.translate(str.maketrans("İıŞşĞğÇçÖöÜü", "IiSsGgCcOoUu"))
    b = "".join(c for c in unicodedata.normalize("NFKD", b) if not unicodedata.combining(c))
    b = re.sub(r"[^A-Za-z0-9\s-]", "", b).strip()
    return re.sub(r"\s+", "_", b)[:60] or "kitap"


def epub_uret(kid):
    """kitap.json'dan bütün sürümleri üretir ve denetler. Eski EPUB'lar silinir, yenileri yazılır."""
    kit = K.yukle(kitap_yolu(kid))
    sorunlar = K.denetle(kit)
    if sorunlar:
        raise ValueError("kitap.json yapısal hata: " + "; ".join(sorunlar[:5]))
    ek = os.path.join(klasor(kid), "epub")
    gecici = ek + ".yeni"
    shutil.rmtree(gecici, ignore_errors=True)
    os.makedirs(gecici)
    ad = _dosya_adi(kid, kit)
    sonuc = []
    for ekad, diller in surumler(kit):
        dosya = f"{ad}_{ekad}.epub"
        durum_yaz(kid, asama=f"EPUB üretiliyor: {ekad}")
        EPUB.uret(kit, diller, os.path.join(gecici, dosya))
        durum_yaz(kid, asama=f"Denetleniyor: {ekad}")
        dn = epubcheck.denetle(os.path.join(gecici, dosya))
        sonuc.append({"dosya": dosya, "diller": diller, "boyut": os.path.getsize(os.path.join(gecici, dosya)),
                      "denetim": dn})
    shutil.rmtree(ek, ignore_errors=True)  # hepsi başarıyla üretildikten sonra eskiler kalkar
    os.replace(gecici, ek)
    ku = kit["kunye"]
    durum_yaz(kid, epublar=sonuc, asama="hazır", hata=None,
              baslik=ku["baslik"].get("tr") or ku["baslik"].get(ku.get("asil_dil", "ar")),
              baslik_asil=ku["baslik"].get(ku.get("asil_dil", "ar")),
              yazar=ku["yazar"].get("tr") or ku["yazar"].get(ku.get("asil_dil", "ar")) or ku["yazar"].get("lat"))
    return sonuc


def _openiti_ekle(kid, version_uri):
    satir = katalog.bul(VERI, version_uri)
    if not satir:
        raise ValueError("katalogda bulunamadı: " + version_uri)
    yol = os.path.join(klasor(kid), "kaynak.txt")
    if not os.path.exists(yol):
        durum_yaz(kid, asama="Metin indiriliyor")
        r = requests.get(satir["url"], timeout=300)
        r.raise_for_status()
        r.encoding = "utf-8"
        with open(yol + ".tmp", "w", encoding="utf-8") as f:
            f.write(r.text)
        os.replace(yol + ".tmp", yol)
    durum_yaz(kid, asama="Bölümler ve sayfalar ayrılıyor")
    kit = openiti.cevir(open(yol, encoding="utf-8").read(), satir)
    eski = kitap_yolu(kid)
    if os.path.exists(eski):  # yeniden ekleme: elle yapılan düzeltmeler ve Türkçe künye korunur
        onceki = K.yukle(eski)
        kit["kunye"]["baslik"].update({k: v for k, v in onceki["kunye"]["baslik"].items() if k != "ar"})
        kit["kunye"]["yazar"].update({k: v for k, v in onceki["kunye"]["yazar"].items() if k not in ("ar", "lat")})
    K.kaydet(kit, eski)


def _dosya_ekle(kid, yol):
    """Elindeki kitap (PDF/EPUB/DOCX/TXT) -> kitap.json (Türkçe) -> Osmanlıca -> EPUB'lar."""
    if not os.path.exists(yol):
        raise FileNotFoundError("Kaynak dosya bulunamadı: " + yol)
    kit = kaynak.cevir(yol, lambda m: durum_asama(kid, m), {"yol": yol})
    eski = kitap_yolu(kid)
    if os.path.exists(eski):  # yeniden işleme: önceki hâl yedeklenir, Türkçe künye düzeltmeleri korunur
        onceki = K.yukle(eski)
        shutil.copy2(eski, eski + ".yedek")
        for alan in ("baslik", "yazar"):
            if onceki["kunye"].get(alan, {}).get("elle"):
                kit["kunye"][alan] = onceki["kunye"][alan]
    K.kaydet(kit, eski)
    _osmanlica(kid)


def _osmanlica(kid, zorla=False):
    kit = K.yukle(kitap_yolu(kid))
    durum_asama(kid, "Osmanlıcaya çevriliyor")
    try:
        osmanlica.kitabi_cevir(kit, lambda m: durum_asama(kid, m), zorla=zorla)
        K.kaydet(kit, kitap_yolu(kid))
        durum_yaz(kid, uyari=None)
    except Exception as e:  # çevirici kapalıysa Türkçe EPUB yine üretilir
        durum_yaz(kid, uyari=f"Osmanlıca çevrilemedi ({type(e).__name__}: {str(e)[:120]}); sadece Türkçe üretildi")


def durum_asama(kid, mesaj):
    durum_yaz(kid, asama=mesaj)


def isci():
    while True:
        tur, kid, arg = _kuyruk.get()
        with _kilit:
            _bekleyen_epub.discard(kid)
        try:
            if tur in ("openiti", "dosya", "osmanlica", "kunye"):
                with kitap_kilidi(kid):  # bu sırada okuma ekranından düzeltme yapılamaz
                    if tur == "openiti":
                        _openiti_ekle(kid, arg)
                    elif tur == "dosya":
                        _dosya_ekle(kid, arg)
                    elif tur == "osmanlica":
                        _osmanlica(kid, zorla=bool(arg))
                    elif tur == "kunye":
                        kit = K.yukle(kitap_yolu(kid))
                        try:
                            osmanlica.kunye_cevir(kit)
                            K.kaydet(kit, kitap_yolu(kid))
                        except Exception as e:
                            durum_yaz(kid, uyari=f"Künyenin Osmanlıcası çevrilemedi: {type(e).__name__}")
            epub_uret(kid)
        except Exception as e:
            traceback.print_exc()
            durum_yaz(kid, asama="hata", hata=f"{type(e).__name__}: {e}")
        finally:
            _kuyruk.task_done()


def is_ekle(is_turu, kid, arg=None, **durum):
    with _kilit:
        if is_turu == "epub" and kid in _bekleyen_epub:
            return  # zaten kuyrukta: tek sefer üretilir
        if is_turu == "epub":
            _bekleyen_epub.add(kid)
    durum_yaz(kid, asama="sırada", hata=None, **durum)
    _kuyruk.put((is_turu, kid, arg))


def baslat():
    threading.Thread(target=isci, daemon=True, name="kutuphane-isci").start()
    # yeniden başlatmada yarım kalan işler kuyruğa geri alınır
    for k in liste():
        if k.get("asama") not in (None, "hazır", "hata"):
            d = durum_oku(k["kimlik"])
            is_ekle(d.get("tur", "epub"), k["kimlik"], d.get("kaynak_kimlik"))


def sil(kid):
    shutil.rmtree(klasor(kid))
