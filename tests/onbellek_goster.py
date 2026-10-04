"""OCR önbelleğindeki bir sayfanın ham Surya satırlarını ve işlenmiş satırlarını gösterir (Surya çalıştırmaz).
Kullanım: python tests/onbellek_goster.py <pdf yolu> <ilk PDF sayfası> [son PDF sayfası]   (sayfalar 1'den başlar)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kutuphane import kaynak as S
import types

yol, ilk = sys.argv[1], int(sys.argv[2])
son = int(sys.argv[3]) if len(sys.argv) > 3 else ilk
klasor = S._ocr_onbellek_klasoru(yol)
print("önbellek klasörü:", klasor)
import fitz
from PIL import Image
doc = fitz.open(yol)
for p in range(ilk, son + 1):
    print(f"\n========== PDF sayfa {p} ==========")
    ham = S._onbellek_oku(klasor, p - 1, S._surya_anahtari())
    if ham is None:
        print("  önbellekte yok (bu sayfa henüz 0.5.12 ile OCR'lanmamış)")
        continue
    print("  -- Surya ham satırları --")
    for t, b in ham:
        print(f"  [x {int(b[0]):4d}-{int(b[2]):4d}  y {int(b[1]):4d}-{int(b[3]):4d}] {t}")
    satirlar = [types.SimpleNamespace(text=t, bbox=b) for t, b in ham]
    img = None
    if any(S._AR.search(s.text) and S._LATIN.search(s.text) for s in satirlar):
        pix = doc[p - 1].get_pixmap(dpi=S._SURYA_DPI)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    print("  -- işlenmiş satırlar --")
    for r in S._surya_satirlari(satirlar, 72 / S._SURYA_DPI, img):
        print(f"  y{r['top']:6.1f} h{r['h']:4.1f} x{r['x0']:5.1f} | {r['text']}")
