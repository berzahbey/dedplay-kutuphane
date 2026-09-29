"""Yabancı asıllı kitapların (OpenITI Arapça vb.) Türkçeye çevirisi: Translate'in paragraf işleriyle.

Paragraflar sırasıyla gönderilir (hiza kaymaz), iş başına model (varsayılan gemma3:27b: denemede anlamı en doğru
çeviren) ve kelam terim sözlüğüyle çevrilir. Çeviri saatler sürer; izleyici (depo.baslat) yarım dakikada bir durumu
okur, bitince Türkçe metni kitaba yazar. Elle düzeltilmiş Türkçe paragraflara dokunulmaz.
"""
import json
import os
import time

import requests

from . import kitap as K

TRANSLATE_URL = os.environ.get("TRANSLATE_URL", "http://host.docker.internal:8060").rstrip("/")
MODEL = os.environ.get("CEVIRI_MODEL", "gemma3:27b")
SANIYE_HARF = float(os.environ.get("CEVIRI_SANIYE_HARF", "0.283"))  # bu sunucuda gemma3:27b ölçümü (el-İktisâd)
CEVRILEMEDI = "[Çevrilemedi] "

# Kelam terimleri (Arapça -> Türkçe). Bölüm yapı terimleri günümüz Türkçesiyle (Osmanlıca sürümde klasik karşılıklar).
TERIMLER = [
    ("خطبة الكتاب", "Kitabın Önsözü"), ("فاتحة الكتاب", "Kitabın Açılışı"),
    ("تمهيدات", "girişler"), ("التمهيد", "giriş"), ("تمهيد", "giriş"),
    ("أقطاب", "kısımlar"), ("القطب", "kısım"), ("أبواب", "bölümler"), ("الباب", "bölüm"),
    ("دعاوى", "davalar"), ("الدعوى", "dava"),
    ("زائدة على الذات", "zâta zâid"), ("قائمة بالذات", "zâtla kâim"),
    ("فروض الكفايات", "farz-ı kifâye"), ("فرض الكفاية", "farz-ı kifâye"), ("فروض الأعيان", "farz-ı ayn"),
    ("تكليف ما لا يطاق", "güç yetirilemeyecek şeyi teklif etmek"),
    ("الواجب", "vâcip"), ("الحسن", "hasen"), ("القبيح", "kabîh"), ("حادث", "hâdis"), ("قديم", "kadîm"),
    ("الحشوية", "Haşviyye"), ("المعتزلة", "Mu'tezile"),
]


def _yol(klasor):
    return os.path.join(klasor, "ceviri.json")


def cevrilecekler(kit, asil):
    """(harita, paragraflar): Türkçesi olmayan (ve elle düzeltilmemiş) bloklar ve dipnotlar, sırasıyla."""
    harita, paragraflar = [], []
    for b in kit["bloklar"]:
        if b.get("silindi") or b.get("elle", {}).get("tr") or (b["metin"].get("tr") or "").strip():
            continue
        t = " ".join(K.NOT_ISARETI.sub(" ", b["metin"].get(asil) or "").split())
        if t:
            harita.append(["blok", b["id"]])
            paragraflar.append({"kind": "h" if b["tur"] == "baslik" else "p", "text": t})
    for alan in ("baslik", "yazar"):  # eser adı ve yazar: Türkçe adlı dosyalar ve künye için
        ku = kit["kunye"].get(alan) or {}
        t = " ".join((ku.get(asil) or "").split())
        if t and not (ku.get("tr") or "").strip():
            harita.append(["kunye", alan])
            paragraflar.append({"kind": "h", "text": t})
    for g, n in kit.get("dipnotlar", {}).items():
        if (n["metin"].get("tr") or "").strip():
            continue
        t = " ".join((n["metin"].get(asil) or "").split())
        if t:
            harita.append(["not", g])
            paragraflar.append({"kind": "p", "text": t})
    return harita, paragraflar


def tahmini_sure(paragraflar):
    return int(sum(len(p["text"]) for p in paragraflar) * SANIYE_HARF)


def baslat(kit, klasor, sonra_studyo=False):
    """Çeviri işini Translate'e verir; durum bilgisini döndürür (durum.json'a 'ceviri' olarak yazılır)."""
    asil = kit["kunye"].get("asil_dil", "ar")
    if asil == "tr":
        raise ValueError("Kitap zaten Türkçe")
    harita, paragraflar = cevrilecekler(kit, asil)
    if not paragraflar:
        raise ValueError("Çevrilecek paragraf yok (hepsinin Türkçesi var)")
    baslik = kit["kunye"]["baslik"].get("tr") or kit["kunye"]["baslik"].get(asil) or "Kütüphane"
    r = requests.post(f"{TRANSLATE_URL}/api/jobs/segments", timeout=120, json={
        "title": baslik, "src_lang": asil, "model": MODEL, "terimler": [list(t) for t in TERIMLER], "segments": paragraflar})
    if r.status_code in (404, 405):
        raise RuntimeError("Translate bu özelliği henüz bilmiyor (Translate'i güncelleyin: /api/jobs/segments)")
    if r.status_code >= 400:
        raise RuntimeError(f"Translate kabul etmedi: {r.text[:200]}")
    with open(_yol(klasor), "w", encoding="utf-8") as f:
        json.dump({"is": r.json()["id"], "harita": harita}, f)
    return {"is": r.json()["id"], "durum": "calisiyor", "yapilan": 0, "toplam": len(paragraflar), "model": MODEL,
            "baslangic": int(time.time()), "tahmini_sn": tahmini_sure(paragraflar), "sonra_studyo": bool(sonra_studyo)}


def yokla(ceviri):
    """Translate'teki işin durumu: (güncellenmiş ceviri durumu, çeviriler ya da None)."""
    r = requests.get(f"{TRANSLATE_URL}/api/jobs/{ceviri['is']}/segments", timeout=60)
    if r.status_code == 404:
        return dict(ceviri, durum="hata", hata="Translate'teki çeviri işi bulunamadı (silinmiş olabilir)"), None
    r.raise_for_status()
    d = r.json()
    c = dict(ceviri, yapilan=d["done"], toplam=d["total"] or ceviri["toplam"])
    if d["done"] >= 3 and d.get("elapsed"):
        c["kalan_sn"] = int(d["elapsed"] / d["done"] * (c["toplam"] - d["done"]))
    if d["status"] == "error":
        return dict(c, durum="hata", hata=d.get("error") or "Çeviri durdu"), None
    if d["status"] == "done":
        return dict(c, durum="bitti", cevrilemeyen=d.get("failed") or 0), d["segments"]
    return c, None


def uygula(kit, klasor, ciktilar):
    """Çevirileri kitaba yazar. Döndürür: yazılan paragraf sayısı. Elle düzeltilmiş Türkçe korunur."""
    harita = json.load(open(_yol(klasor), encoding="utf-8"))["harita"]
    if len(harita) != len(ciktilar):
        raise ValueError(f"Çeviri sayısı tutmuyor ({len(ciktilar)} / {len(harita)})")
    asil = kit["kunye"].get("asil_dil", "ar")
    bloklar = {b["id"]: b for b in kit["bloklar"]}
    yazilan = 0
    for (tur, kimlik), s in zip(harita, sorted(ciktilar, key=lambda x: x["idx"])):
        out = (s.get("out") or "").strip()
        if not out:
            continue
        if tur == "blok":
            b = bloklar.get(kimlik)
            if not b or b.get("elle", {}).get("tr"):
                continue
            isaretler = "".join("{{" + g + "}}" for g in K.NOT_ISARETI.findall(b["metin"].get(asil) or ""))
            b["metin"]["tr"] = out + isaretler  # dipnot atıfları paragraf sonunda korunur
        elif tur == "kunye":
            ku = kit["kunye"].setdefault(kimlik, {})
            if ku.get("elle") or (ku.get("tr") or "").strip():
                continue
            ku["tr"] = out.strip(" .")
        else:
            n = kit.get("dipnotlar", {}).get(kimlik)
            if not n:
                continue
            n["metin"]["tr"] = out
        yazilan += 1
    kit["kunye"]["ceviri"] = {"model": MODEL, "tarih": int(time.time())}
    return yazilan
