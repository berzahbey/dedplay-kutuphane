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
from . import ceviri, cikti, epubcheck, kaynak, katalog, openiti, osmanlica
from . import kitap as K

VERI = os.environ.get("DATA_DIR", "/data")
KITAPLAR = os.path.join(VERI, "kitaplar")
KIMLIK = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
DIL_AD = {"ar": "arapca", "en": "ingilizce", "fr": "fransizca", "fa": "farsca"}
_kuyruk = queue.Queue()  # hafif şerit (0.5.17): EPUB/DOCX/TXT, katmanlı ya da önbellekteki PDF, Osmanlıca, EPUB işleri
_kuyruk_agir = queue.Queue()  # ağır şerit: OCR gerektiren PDF'ler, birer birer (Surya bütün işlemciyi kullanır)
_is_kilitleri = {}  # aynı kitabın iki işi aynı anda çalışmasın
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
                                                            "cikti", "cikti_uyari", "studyo", "ceviri",
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
        kapak = None  # kitabın kendi kapak görseli (PDF'in ilk sayfası / EPUB'un kapağı) varsa o
        if kit["kunye"].get("kapak") and os.path.exists(os.path.join(klasor(kid), kit["kunye"]["kapak"])):
            kapak = open(os.path.join(klasor(kid), kit["kunye"]["kapak"]), "rb").read()
        EPUB.uret(kit, diller, os.path.join(gecici, dosya), kapak_png=kapak)
        durum_yaz(kid, asama=f"Denetleniyor: {ekad}")
        dn = epubcheck.denetle(os.path.join(gecici, dosya))
        sonuc.append({"dosya": dosya, "diller": diller, "boyut": os.path.getsize(os.path.join(gecici, dosya)),
                      "denetim": dn})
    shutil.rmtree(ek, ignore_errors=True)  # hepsi başarıyla üretildikten sonra eskiler kalkar
    os.replace(gecici, ek)
    try:  # dil klasörlerine (Türkçe/, Osmanlıca/, Türkçe-Osmanlıca/ ...)
        yazilan = cikti.ciktiya_yaz(kit, sonuc, ek, durum_oku(kid).get("cikti"))
        durum_yaz(kid, cikti=yazilan, cikti_uyari=None if yazilan is not None else "Çıktı klasörü bağlı değil")
    except Exception as e:
        durum_yaz(kid, cikti_uyari=f"Çıktı klasörüne yazılamadı: {type(e).__name__}: {str(e)[:120]}")
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
    kit = kaynak.cevir(yol, lambda m: durum_asama(kid, m), {"yol": yol}, kapak_yolu=os.path.join(klasor(kid), "kapak"))
    eski = kitap_yolu(kid)
    if os.path.exists(eski):  # yeniden işleme: önceki hâl yedeklenir, Türkçe künye düzeltmeleri korunur
        onceki = K.yukle(eski)
        shutil.copy2(eski, eski + ".yedek")
        for alan in ("baslik", "yazar"):
            if onceki["kunye"].get(alan, {}).get("elle"):
                kit["kunye"][alan] = onceki["kunye"][alan]
    K.kaydet(kit, eski)  # Osmanlıca sonra, ayrı iş (önce kitabın kendi dilindeki EPUB'u hazır olur)


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


def _is_kilidi(kid):
    with _kilit:
        return _is_kilitleri.setdefault(kid, threading.Lock())


def isci(agir=False):
    """0.5.17: iki şerit. Hafif şerit, OCR gerektiren dosya işini ağır şeride devreder. Aynı kitabın iki işi aynı anda
    çalışmaz: kitabın işi ağır şeritte sürerken gelen hafif iş ağır şeridin arkasına geçer."""
    kuyruk = _kuyruk_agir if agir else _kuyruk
    while True:
        tur, kid, arg = kuyruk.get()
        try:
            if not agir and tur == "dosya":
                durum_asama(kid, "Dosya inceleniyor")
                if kaynak.ocr_gerekir(arg):
                    durum_yaz(kid, asama="OCR sırasında")
                    _kuyruk_agir.put((tur, kid, arg))
                    continue
            kilit = _is_kilidi(kid)
            if not agir and not kilit.acquire(blocking=False):
                # bu kitabın işi ağır şeritte sürüyor (hafif şerit tek iş parçacığı): iş ağır şeridin arkasına geçer,
                # hafif şerit beklemez ve dönüp durmaz
                _kuyruk_agir.put((tur, kid, arg))
                continue
            if agir:
                kilit.acquire()  # hafif şeritteki kısa iş bitene kadar bekler
            try:
                _isle(tur, kid, arg)
            finally:
                kilit.release()
        finally:
            kuyruk.task_done()


def _isle(tur, kid, arg):
    if True:
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
            # 1. aşama bitti: kitap kendi dilinde Kütüphane'de. 2. aşama: Türkçe değilse çeviri, Türkçeyse Osmanlıca
            if tur == "openiti":
                _otomatik_ceviri(kid)
            elif tur == "dosya":
                kit = K.yukle(kitap_yolu(kid))
                if kit["kunye"].get("asil_dil") == "tr":
                    is_ekle("osmanlica", kid, tur="epub")
            _studyo_bekleyen(kid)
        except Exception as e:
            traceback.print_exc()
            durum_yaz(kid, asama="hata", hata=f"{type(e).__name__}: {e}")


OTOMATIK_CEVIRI = False  # 0.5.8: çeviri kaldırıldı (Translate yok)


def _otomatik_ceviri(kid):
    """Türkçe olmayan kitap temizlenip EPUB'u hazır olunca Türkçe çevirisi kendiliğinden başlar."""
    if not OTOMATIK_CEVIRI:
        return
    c = durum_oku(kid).get("ceviri") or {}
    if c.get("durum") in ("calisiyor", "bitti", "durduruldu"):
        return  # sürüyor, bitmiş ya da kullanıcı durdurmuş
    kit = K.yukle(kitap_yolu(kid))
    asil = kit["kunye"].get("asil_dil", "tr")
    if asil == "tr" or not ceviri.cevrilecekler(kit, asil)[1]:
        return
    try:
        durum_yaz(kid, ceviri=ceviri.baslat(kit, klasor(kid)))
    except Exception as e:
        durum_yaz(kid, uyari=f"Türkçe çeviri başlatılamadı ({str(e)[:120]}); kitap sayfasından başlatabilirsin")


def _studyo_bekleyen(kid):
    """'Türkçeye çevir ve Stüdyo'ya gönder': çeviri bitip EPUB'lar üretilince Türkçesi Stüdyo'ya gider."""
    c = durum_oku(kid).get("ceviri") or {}
    if not (c.get("sonra_studyo") and c.get("durum") == "bitti" and not c.get("gonderildi")):
        return
    try:
        sonuc = cikti.studyoya_gonder(K.yukle(kitap_yolu(kid)))
        durum_yaz(kid, studyo=sonuc, ceviri=dict(c, gonderildi=True))
    except Exception as e:
        durum_yaz(kid, uyari=f"Stüdyo'ya gönderilemedi: {str(e)[:150]} (kitap sayfasından yeniden gönderebilirsin)",
                  ceviri=dict(c, gonderildi=True))


def ceviri_izleyici():
    """Süren çevirileri yarım dakikada bir yoklar; biten çeviriyi kitaba yazar, Osmanlıca ve EPUB'ları kuyruğa koyar."""
    while True:
        for k in liste():
            kid = k["kimlik"]
            c = durum_oku(kid).get("ceviri") or {}
            if c.get("durum") != "calisiyor":
                continue
            try:
                yeni, ciktilar = ceviri.yokla(c)
            except Exception as e:  # geçici bağlantı sorunu: sonra tekrar
                durum_yaz(kid, ceviri=dict(c, not_=f"Translate'e ulaşılamadı, tekrar denenecek ({type(e).__name__})"))
                continue
            yeni.pop("not_", None)
            if ciktilar is None:
                durum_yaz(kid, ceviri=yeni)
                continue
            try:
                with kitap_kilidi(kid):
                    kit = K.yukle(kitap_yolu(kid))
                    yeni["yazilan"] = ceviri.uygula(kit, klasor(kid), ciktilar)
                    K.kaydet(kit, kitap_yolu(kid))
                durum_yaz(kid, ceviri=yeni)
                is_ekle("osmanlica", kid, tur="epub")  # Türkçeden Osmanlıca, sonra EPUB'lar (ve gerekirse Stüdyo)
            except Exception as e:
                traceback.print_exc()
                durum_yaz(kid, ceviri=dict(yeni, durum="hata", hata=f"Çeviri kitaba yazılamadı: {e}"))
        time.sleep(30)


def is_ekle(is_turu, kid, arg=None, **durum):
    with _kilit:
        if is_turu == "epub" and kid in _bekleyen_epub:
            return  # zaten kuyrukta: tek sefer üretilir
        if is_turu == "epub":
            _bekleyen_epub.add(kid)
    # 0.5.17: yazı işi söyler (Türkçe EPUB hazırken "sırada" yanıltıcıydı); işin türü yeniden başlatma için saklanır
    yazi = {"osmanlica": "Osmanlıca sırada", "epub": "EPUB sırada", "kunye": "EPUB sırada"}.get(is_turu, "sırada")
    durum_yaz(kid, asama=yazi, hata=None, is_turu=is_turu, is_arg=arg, **durum)
    _kuyruk.put((is_turu, kid, arg))


def baslat():
    threading.Thread(target=isci, daemon=True, name="kutuphane-hafif").start()
    threading.Thread(target=isci, args=(True,), daemon=True, name="kutuphane-agir").start()
    # 0.5.8: çeviri kaldırıldı; çeviri izleyicisi başlatılmaz
    # yeniden başlatmada yarım kalan işler kuyruğa geri alınır
    for k in liste():
        if k.get("asama") not in (None, "hazır", "hata"):
            d = durum_oku(k["kimlik"])
            if d.get("is_turu"):  # 0.5.17: yarım kalan işin kendisi (Osmanlıca işi "epub" diye geri alınıyordu)
                is_ekle(d["is_turu"], k["kimlik"], d.get("is_arg"))
            else:
                is_ekle(d.get("tur", "epub"), k["kimlik"], d.get("kaynak_kimlik"))


def sil(kid):
    shutil.rmtree(klasor(kid))
