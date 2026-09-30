"""Tanı: PDF'in ilk sayfalarının satırlarını, basılı sayfa numarasını ve içindekiler tanıma sonucunu yazdırır. HİÇBİR ŞEY YAZMAZ."""
import sys
from kutuphane import kaynak as K
import fitz
asil, ilk, son = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
d = fitz.open(asil)
print("Yer imleri (ilk 15):", d.get_toc(simple=True)[:15])
kisa = fitz.open(); kisa.insert_pdf(d, from_page=0, to_page=min(son + 3, len(d)) - 1)
yol = "/tmp/tani_kisa.pdf"; kisa.save(yol)  # sadece ilk sayfalar (konteynerin kendi geçici klasörü)
S, bilgi = K.pdf_sayfalari(yol)
print("Sayfa sayısı:", len(S), "| OCR'lı sayfa:", bilgi.get("ocr"), "| bozuk katman:", bilgi.get("bozuk_katman"),
      "| yer imi:", len(bilgi.get("yer_imleri") or []))
nolar, satirlar = [], []
for rows, w, h, _ in S:
    no, kalan = K._sayfa_no_ve_kenar(rows, h)
    nolar.append(no); satirlar.append(kalan)
nolar = K._eksik_numaralari_doldur(nolar)
for i in range(ilk - 1, min(son, len(S))):
    print(f"\n##### PDF sayfa {i + 1} | basılı no: {nolar[i]} | OCR: {S[i][3]} | içindekiler sanıldı: {K._icindekiler_sayfasi(satirlar[i])}")
    for r in satirlar[i][:45]:
        print(f"  x={r['x0']:5.0f} h={r['h']:4.1f} | {r['text'][:90]}")
