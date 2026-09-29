"""Türkçe -> Osmanlıca: Osmanlıca çevirici uygulamasına (HTTP) gönderir.

Metin parçaları '¶' ayracıyla gönderilir (Stüdyo'daki yöntem): çevirici bir satırı silse ya da birleştirse bile
her parçanın karşısında kendi Osmanlıcası durur. Dipnot işaretleri ({{n0001}}) çeviriciye gönderilmez;
işaretlerin arasındaki metin parçaları çevrilip işaretler geri takılır. Elle düzeltilmiş Osmanlıca korunur.
"""
import os
import time

import requests

from . import kitap as K

URL = os.environ.get("OSMANLICA_URL", "http://host.docker.internal:8089").rstrip("/")
AYRAC = "\u00b6"
PARTI_HARF = 12000  # bir istekte en çok bu kadar harf


def _istek(metin, sure=1800):
    r = requests.post(f"{URL}/api/upload-text", data={"text": metin, "use_ollama": "false", "turkce": "true"},
                      timeout=60)
    r.raise_for_status()
    jid = r.json()["job_id"]
    son, bekle = time.time() + sure, 0.5
    while time.time() < son:
        s = requests.get(f"{URL}/api/status/{jid}", timeout=60).json()
        if s.get("error"):
            raise RuntimeError(f"Osmanlıca çevirici hatası: {s['error']}")
        if s.get("ready"):
            d = requests.get(f"{URL}/api/download/{jid}", timeout=120)
            d.raise_for_status()
            d.encoding = "utf-8"
            return d.text
        time.sleep(bekle)
        bekle = min(bekle * 1.5, 5)
    raise TimeoutError("Osmanlıca çeviri zaman aşımına uğradı")


def _parti(metinler):
    """Parçaları tek istekte çevirir; parça sayısı tutmazsa ikiye bölerek yeniden dener."""
    if not metinler:
        return []
    cikti = _istek(("\n" + AYRAC + "\n").join(metinler))
    parcalar = [p.strip() for p in cikti.split(AYRAC)]
    if len(parcalar) == len(metinler):
        return parcalar
    if len(metinler) == 1:
        return [cikti.replace(AYRAC, "").strip()]
    orta = len(metinler) // 2
    return _parti(metinler[:orta]) + _parti(metinler[orta:])


def liste_cevir(metinler, ilerleme=None):
    out, parti, uz, bitti = [], [], 0, 0
    for m in metinler + [None]:
        if m is None or (parti and uz + len(m) > PARTI_HARF):
            out += _parti(parti)
            bitti += len(parti)
            if ilerleme and metinler:
                ilerleme(f"Osmanlıcaya çevriliyor: %{bitti * 100 // len(metinler)}")
            parti, uz = [], 0
        if m is not None:
            parti.append(m)
            uz += len(m)
    return out


def _parcala(metin):
    """'metin {{n0001}} metin' -> (şablon, çevrilecek parçalar). Şablonda parçalar \\0, \\1 ... ile durur."""
    sablon, parcalar = [], []
    for i, p in enumerate(K.NOT_ISARETI.split(metin)):
        if i % 2:
            sablon.append(("not", p))
        elif p.strip():
            bas, son = p[:len(p) - len(p.lstrip())], p[len(p.rstrip()):]
            sablon.append(("metin", (bas, len(parcalar), son)))
            parcalar.append(p.strip())
        elif p:
            sablon.append(("bosluk", p))
    return sablon, parcalar


def _birlestir(sablon, cevrilmis):
    out = []
    for tur, v in sablon:
        if tur == "not":
            out.append("{{" + v + "}}")
        elif tur == "bosluk":
            out.append(v)
        else:
            bas, k, son = v
            out.append(bas + cevrilmis[k] + son)
    return "".join(out)


def blok_cevir(metin):
    """Tek bir paragraf (okuma ekranında düzeltilen Türkçe): dipnot işaretleri korunarak Osmanlıcaya."""
    sablon, parcalar = _parcala(metin)
    return _birlestir(sablon, _parti(parcalar)) if parcalar else metin


def kunye_cevir(kit):
    """Sadece kitap adı ve yazar (künye düzeltilince bütün kitabı yeniden çevirmeye gerek yok)."""
    alanlar = [a for a in ("baslik", "yazar") if kit["kunye"].get(a, {}).get("tr")]
    cevrilmis = liste_cevir([kit["kunye"][a]["tr"] for a in alanlar])
    for a, v in zip(alanlar, cevrilmis):
        kit["kunye"][a]["osm"] = v
    return kit


def kitabi_cevir(kit, ilerleme=None, zorla=False):
    """Bütün bloklara, dipnotlara ve künyeye Osmanlıca ekler. zorla=False: elle düzeltilmiş Osmanlıca korunur."""
    isler = []  # (yerleştirme fonksiyonu, şablon, parça başlangıcı, parça sayısı)
    tum = []

    def ekle(metin, yerlestir):
        sablon, parcalar = _parcala(metin)
        isler.append((yerlestir, sablon, len(tum), len(parcalar)))
        tum.extend(parcalar)

    for b in kit["bloklar"]:
        if not zorla and b.get("elle", {}).get("osm"):
            continue
        tr = b["metin"].get("tr")
        if tr:
            ekle(tr, lambda v, b=b: b["metin"].__setitem__("osm", v))
    for g, n in kit.get("dipnotlar", {}).items():
        if n["metin"].get("tr") and (zorla or not n.get("elle", {}).get("osm")):
            ekle(n["metin"]["tr"], lambda v, n=n: n["metin"].__setitem__("osm", v))
    for alan in ("baslik", "yazar"):
        tr = kit["kunye"].get(alan, {}).get("tr")
        if tr:
            ekle(tr, lambda v, a=alan: kit["kunye"][a].__setitem__("osm", v))
    cevrilmis = liste_cevir(tum, ilerleme)
    for yerlestir, sablon, bas, adet in isler:
        yerlestir(_birlestir(sablon, cevrilmis[bas:bas + adet]))
    kit["kunye"]["osmanlica"] = {"tarih": int(time.time()), "parca": len(tum)}
    return kit
