"""Hazır kitapların dışarıya verilmesi.

1) Çıktı klasörü (CIKTI_DIR, varsayılan /cikti = /media/ZimaOS-HD/Media/Kitaplar): EPUB'lar dile göre klasörlerde
   Türkçe/, Osmanlıca/, Türkçe-Osmanlıca/, Arapça/, Arapça-Türkçe/  ->  "Eser adı - Yazar.epub"
2) Stüdyo'ya gönderme: bölümler Türkçe + (düzeltilmiş) Osmanlıca hazır parçalar olarak gider; Stüdyo seslendirir ve
   öteki biçimleri (PDF, Word, HTML, TXT) kendi çıktı klasörüne, kendi düzeniyle kaydeder.
"""
import os
import re
import shutil
import time

import requests

from . import epub as EPUB
from . import kitap as K

CIKTI = os.environ.get("CIKTI_DIR", "/cikti")
STUDYO_URL = os.environ.get("STUDYO_URL", "http://host.docker.internal:8070").rstrip("/")
KLASOR_ADI = {("tr",): "Türkçe", ("osm",): "Osmanlıca", ("tr", "osm"): "Türkçe-Osmanlıca", ("ar",): "Arapça",
              ("ar", "tr"): "Arapça-Türkçe", ("en",): "İngilizce", ("en", "tr"): "İngilizce-Türkçe",
              ("fr",): "Fransızca", ("fr", "tr"): "Fransızca-Türkçe"}
_YASAK = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def dosya_adi(kit):
    ku = kit["kunye"]
    asil = ku.get("asil_dil", "tr")
    baslik = ku["baslik"].get("tr") or ku["baslik"].get(asil) or "Kitap"
    yazar = ku.get("yazar", {}).get("tr") or ku.get("yazar", {}).get(asil) or ""
    ad = f"{baslik} - {yazar}" if yazar and yazar != baslik else baslik
    return re.sub(r"\s+", " ", _YASAK.sub(" ", ad)).strip(" .")[:120] or "Kitap"


def ciktiya_yaz(kit, epublar, epub_klasoru, onceki=None):
    """EPUB'ları dil klasörlerine kopyalar. Döndürür: yazılan yollar (CIKTI'ye göre). Klasör bağlı değilse None.
    onceki: bir önceki yazımın yolları (kitap adı değiştiyse eski dosyalar kaldırılır)."""
    if not os.path.isdir(CIKTI):
        return None
    ad = dosya_adi(kit)
    yeni = []
    for e in epublar:
        klasor = KLASOR_ADI.get(tuple(e["diller"]), "-".join(e["diller"]))
        hedef_klasor = os.path.join(CIKTI, klasor)
        os.makedirs(hedef_klasor, exist_ok=True)
        hedef = os.path.join(hedef_klasor, ad + ".epub")
        shutil.copyfile(os.path.join(epub_klasoru, e["dosya"]), hedef + ".tmp")
        os.replace(hedef + ".tmp", hedef)
        yeni.append(os.path.relpath(hedef, CIKTI))
    for eski in onceki or []:  # ad değişmişse eski kopya kalmasın (başka kitabın dosyasına dokunulmaz: sadece bizim yazdığımız)
        if eski not in yeni:
            try:
                os.remove(os.path.join(CIKTI, eski))
            except OSError:
                pass
    return yeni


# ---------------- Stüdyo ----------------
def _temiz(t):
    return re.sub(r"\s+", " ", K.NOT_ISARETI.sub("", t or "")).strip()


def studyo_parcalari(kit):
    """Kitap -> Stüdyo parçaları: her bölüm bir Parca_ (seslendirmede bir ses parçası), dipnotlar sonda Dipnot_.
    Türkçe ve Osmanlıca satırlar birebir eşleşir (iki dilli çıktılar hizalı olsun). Dipnot işaretleri ve sayfa
    numaraları gitmez; bölüm, başlığıyla başlar ('Bölüm 001 (5-20)' etiketi seslendirmede okunmasın)."""
    gor = K.gorunur(kit)
    ana_dil = "tr" if "tr" in K.diller(gor) else gor["kunye"].get("asil_dil", "tr")
    yapi = EPUB._Uretici(gor, [ana_dil]).yapi()
    bloklar = {b["id"]: b for b in gor["bloklar"]}
    parcalar = []
    for i, bolum in enumerate(yapi, 1):
        tr, osm = [], []
        for bid in bolum["bloklar"]:
            b = bloklar[bid]
            t = _temiz(b["metin"].get(ana_dil))
            if not t:
                continue
            tr.append(t)
            osm.append(_temiz(b["metin"].get("osm")) or t)  # Osmanlıcası yoksa satır boş kalmasın (hiza bozulmasın)
        if tr:
            parcalar.append({"name": f"Parca_{i:03d}", "tr": "\n".join(tr), "osm": "\n".join(osm)})
    # dipnotlar: EPUB'daki numaralarla (görünüş sırası)
    sira = []
    for b in gor["bloklar"]:
        for g in K.NOT_ISARETI.findall(b["metin"].get(ana_dil) or ""):
            if g not in sira:
                sira.append(g)
    if sira:
        rakam = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
        tr = ["DİPNOTLAR"] + [f"{n}. {_temiz(gor['dipnotlar'][g]['metin'].get(ana_dil))}" for n, g in enumerate(sira, 1)]
        osm = ["حاشیه‌لر"] + [f"{str(n).translate(rakam)}. {_temiz(gor['dipnotlar'][g]['metin'].get('osm')) or _temiz(gor['dipnotlar'][g]['metin'].get(ana_dil))}"
                             for n, g in enumerate(sira, 1)]
        parcalar.append({"name": "Dipnot_001", "tr": "\n".join(tr), "osm": "\n".join(osm)})
    return parcalar


def studyoya_gonder(kit):
    ku = kit["kunye"]
    baslik = ku["baslik"].get("tr") or ku["baslik"].get(ku.get("asil_dil", "tr")) or "Kitap"
    govde = {"title": re.sub(r"\s+", " ", _YASAK.sub(" ", baslik)).strip(" ."),
             "osm_title": ku["baslik"].get("osm", ""), "parts": studyo_parcalari(kit)}
    r = requests.post(f"{STUDYO_URL}/api/jobs/from-kutuphane", json=govde, timeout=120)
    if r.status_code in (404, 405):
        raise RuntimeError("Stüdyo bu özelliği henüz bilmiyor (Stüdyo'yu güncelleyin: from-kutuphane)")
    if r.status_code >= 400:
        try:
            mesaj = r.json().get("detail")
        except ValueError:
            mesaj = r.text[:200]
        raise RuntimeError(f"Stüdyo kabul etmedi: {mesaj}")
    return {"is": r.json()["id"], "tarih": int(time.time()), "parca": len(govde["parts"])}
