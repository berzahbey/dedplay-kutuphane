"""Kuru deneme: bir kitabın kaynak dosyasını yeni kodla okur, fihristi eskisiyle karşılaştırır. HİÇBİR ŞEY YAZMAZ.
Çalıştırma: python tests/kuru_deneme_icindekiler.py <kitap kimliği>"""
import collections, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from kutuphane import kaynak

kid = sys.argv[1]
kit_eski = json.load(open(f"/data/kitaplar/{kid}/kitap.json", encoding="utf-8"))
yol = kit_eski["kunye"].get("kaynak", {}).get("yol")
print("Kaynak dosya:", yol)
if not yol or not os.path.exists(yol):
    sys.exit("HATA: kaynak dosya bulunamadı")


def fihrist(kit):
    return [("  " * (b.get("seviye", 1) - 1)) + b["metin"]["tr"] + "   [s. " + ",".join(s["no"] for s in b.get("sayfalar", [])) + "]"
            for b in kit["bloklar"] if b["tur"] == "baslik"]


print("\n=== ESKİ FİHRİST (şu anki kitap.json) ===")
print("\n".join(fihrist(kit_eski)))
bilgi_kayit = {}
_eski_pdf_oku = kaynak.pdf_oku


def pdf_oku(*a, **k):
    o, n, b = _eski_pdf_oku(*a, **k)
    bilgi_kayit.update(b)
    return o, n, b


kaynak.pdf_oku = pdf_oku
girdi_kayit = []
_eski_girdiler = kaynak.icindekiler_girdileri


def icindekiler_girdileri(*a, **k):
    g = _eski_girdiler(*a, **k)
    girdi_kayit[:] = g
    return g


kaynak.icindekiler_girdileri = icindekiler_girdileri
kit = kaynak.cevir(yol, lambda m: None)
print("\n=== BASILI İÇİNDEKİLERDEN OKUNAN GİRDİLER ===")
print("\n".join(("[bölüm] " if g.get("ara") else "        ") + g["baslik"] + "  -> s. " + str(g["no"]) for g in girdi_kayit)
      or "(içindekiler sayfası bulunamadı)")
print("\n=== YENİ FİHRİST (yeni kod, kaydedilmedi) ===")
print("Fihrist kaynağı:", bilgi_kayit.get("fihrist_kaynagi") or "yazı boyu tahmini (içindekiler kullanılamadı)")
print("\n".join(fihrist(kit)))
eski_p = collections.Counter(b["metin"]["tr"] for b in kit_eski["bloklar"] if b["tur"] == "p")
yeni_p = collections.Counter(b["metin"]["tr"] for b in kit["bloklar"] if b["tur"] == "p")
fark = list((yeni_p - eski_p).elements())
print(f"\n=== YENİDE OLUP ESKİDE OLMAYAN PARAGRAFLAR ({len(fark)}; ilk 40, kısaltılmış) ===")
print("\n".join("  | " + t[:110] for t in fark[:40]))
print("\nParagraf sayısı: eski", sum(b["tur"] == "p" for b in kit_eski["bloklar"]), "/ yeni", sum(b["tur"] == "p" for b in kit["bloklar"]))
