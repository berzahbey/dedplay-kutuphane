"""Dedplay Kütüphane'nin ortak kitap biçimi (kitap.json).

Bütün çıktılar (Türkçe, Osmanlıca, iki dilli, asıllı EPUB) bu tek dosyadan üretilir.

{
  "surum": 1,
  "kunye": {"baslik": {"ar": "...", "tr": "...", "osm": "..."}, "yazar": {...},
            "asil_dil": "ar", "vefat_hicri": 505,
            "kaynak": {"tur": "openiti", "kimlik": "...", "adres": "...", "baski": "...", "lisans": "..."},
            "sayfa_kaynagi": "Beyrut 1993 baskısı"},
  "bloklar": [
     {"id": "b00001", "tur": "baslik", "seviye": 1, "metin": {"ar": "..."}},
     {"id": "b00002", "tur": "p", "metin": {"ar": "...", "tr": "...", "osm": "..."},
      "sayfalar": [{"no": "27", "konum": {"ar": 512}}],   # sayfa bu paragrafın içinde başlıyor
      "notlar": ["n0003"],                                 # paragraftaki dipnot atıfları (sırayla)
      "elle": {"tr": true},                                # elle düzeltildi: yeniden çeviri üzerine yazmaz
      "gecmis": [{"dil": "tr", "eski": "...", "zaman": 1760000000}]}
  ],
  "dipnotlar": {"n0003": {"metin": {"tr": "..."}}}
}

Dipnot atıfı metinde {{n0003}} işaretiyle durur; EPUB üretici bunu tıklanabilir nota çevirir.
Sayfa işaretinin "konum"u o dildeki karakter konumudur; bir dilde konum yoksa işaret paragraf başına konur.
"""
import json
import os
import re
import tempfile
import time

SURUM = 1
NOT_ISARETI = re.compile(r"\{\{(n\d{4,})\}\}")


def yeni(kunye):
    return {"surum": SURUM, "kunye": kunye, "bloklar": [], "dipnotlar": {}}


def blok_ekle(kitap, tur, metin, **kw):
    b = {"id": "b%05d" % (len(kitap["bloklar"]) + 1), "tur": tur, "metin": metin}
    b.update({k: v for k, v in kw.items() if v})
    kitap["bloklar"].append(b)
    return b


def diller(kitap):
    """Kitapta metni bulunan diller (blokların çoğunda dolu olanlar)."""
    say = {}
    ps = [b for b in kitap["bloklar"] if b["tur"] == "p"]
    for b in ps:
        for d, t in b["metin"].items():
            if t and t.strip():
                say[d] = say.get(d, 0) + 1
    return [d for d, n in say.items() if n >= 0.9 * max(1, len(ps))]


def duzelt(kitap, blok_id, dil, yeni_metin):
    """Okuma ekranından gelen düzeltme: eski hâl geçmişe yazılır, 'elle' işaretlenir."""
    for b in kitap["bloklar"]:
        if b["id"] == blok_id:
            eski = b["metin"].get(dil, "")
            if eski == yeni_metin:
                return False
            b.setdefault("gecmis", []).append({"dil": dil, "eski": eski, "zaman": int(time.time())})
            b["metin"][dil] = yeni_metin
            b.setdefault("elle", {})[dil] = True
            return True
    raise KeyError(blok_id)


def kaydet(kitap, yol):
    """Önce geçici dosyaya yazılır, sonra yerine konur: yarıda kesilirse eski dosya bozulmaz."""
    klasor = os.path.dirname(os.path.abspath(yol))
    os.makedirs(klasor, exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=klasor, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(kitap, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol)


def yukle(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def denetle(kitap):
    """Yapısal hatalar listesi (boşsa kitap sağlam)."""
    hatalar = []
    idler = set()
    notlar_atif = []
    for b in kitap["bloklar"]:
        if b["id"] in idler:
            hatalar.append("tekrar eden blok kimliği: " + b["id"])
        idler.add(b["id"])
        if b["tur"] not in ("baslik", "p"):
            hatalar.append(f"{b['id']}: bilinmeyen tür {b['tur']}")
        if b["tur"] == "baslik" and not (1 <= b.get("seviye", 0) <= 6):
            hatalar.append(f"{b['id']}: başlık seviyesi hatalı")
        for d, t in b["metin"].items():
            notlar_atif += NOT_ISARETI.findall(t or "")
    for n in set(notlar_atif):
        if n not in kitap["dipnotlar"]:
            hatalar.append("atfı olan ama metni olmayan dipnot: " + n)
    for n in kitap["dipnotlar"]:
        if n not in notlar_atif:
            hatalar.append("metinde atfı olmayan dipnot: " + n)
    onceki = None
    for b in kitap["bloklar"]:
        for s in b.get("sayfalar", []):
            try:
                no = int(s["no"])
            except ValueError:
                continue  # roma rakamı vb.
            if onceki is not None and no <= onceki:
                hatalar.append(f"{b['id']}: sayfa sırası bozuk ({onceki} → {no})")
            onceki = no
    return hatalar
