"""0.5.13 gerileme testi: Surya'ya özel kurallar (İki Madnun'un önbellekteki gerçek Surya satırlarından). OCR çalıştırmaz."""
import os, sys, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kutuphane import kaynak as S

kalan = []


def dene(ad, kosul):
    print(("GECTI " if kosul else "KALDI ") + ad)
    if not kosul:
        kalan.append(ad)


def satirlar(liste):
    return [r["text"] for r in S._surya_satirlari([types.SimpleNamespace(text=t, bbox=b) for t, b in liste], 72 / 200, None)]


# 1) dipnot içindeki sayı yeni dipnot değildir
n = S._notlari_bol(["(1) Kur'an'da geçen yedi kat gök gibi. O'nun devrinde, yani zamanımızdan 850 sene evvel Batı "
                    "dünyâsında bir bilgin yoktur. (2) Bu ilâhi kelâmdan evvelâ. (3) Dünyânın, yörüngesine meyilli."])
dene("Dipnottaki '850 sene' yeni dipnot sayılmaz", [k for k, _ in n] == [1, 2, 3] and "850 sene evvel" in n[0][1])
n = S._notlari_bol(["1. Birinci not metni. 2. İkinci not metni."])
dene("Sıradaki çıplak numara yine yeni dipnot", [k for k, _ in n] == [1, 2])
# 2) uydurma süzgeci yalnız uydurma bölgesinde
t = satirlar([("1. KITAP", (379, 583, 560, 619)), ("BÜYÜK MADNÛN", (293, 686, 636, 726)),
              ("( كتاب المضنون الكبير )", (267, 757, 645, 803)), ("医肾炎", (208, 1239, 265, 1263)), ("花", (674, 1316, 714, 1367)),
              ("<b>不可</b>", (546, 1391, 658, 1444)), ("province.", (647, 1432, 736, 1460))])
dene("Çince uydurmanın üstündeki '1. KITAP' kalır, uydurma gider", t == ["1. KITAP", "BÜYÜK MADNÛN", "( كتاب المضنون الكبير )"])
dene("Boş sayfadaki tek uydurma satır atılır (Carl)", satirlar([("Carl", (400, 700, 480, 730))]) == [])
dene("Boş sayfada büyük harfli kısa başlık kalır", satirlar([("NOTLAR", (400, 700, 560, 730))]) == ["NOTLAR"])
dene("Tek başına sayfa numarası atılmaz", satirlar([("16", (113, 1329, 144, 1355))]) == ["16"])
dene("Kısa ama geçerli satır atılmaz", satirlar([("Allah'a hamd olsun.", (100, 300, 600, 330))]) == ["Allah'a hamd olsun."])
# 3) aynı satırda ayrı gelen Arapça ve Türkçe soldan sağa birleşir
t = satirlar([("şekilde görülmesine izin gelmiştir. Çünki (salâtü Selâm ona", (98, 938, 884, 967)),
              ("( رأيت ربّي في أحسن صورة )", (456, 988, 880, 1034)), ("olsun) : Allah'ın Resûlü", (98, 994, 413, 1022)),
              ("«Rabbimi en güzel sûrette gördüm» demiştir.", (98, 1047, 883, 1076))])
dene("Ayrı gelen Arapça ibare Türkçenin sağına (aynı satır)", t[1] == "olsun) : Allah'ın Resûlü ( رأيت ربّي في أحسن صورة )" and len(t) == 3)
t = satirlar([("Türkçe sol sütun satırı burada", (100, 300, 700, 330)), ("سطر عربي في العمود الأيمن", (1000, 300, 1600, 340))])
dene("İki sütunlu sayfada sütunlar birleşmez", len(t) == 2)
# 4) satır içi tekrar
dene("Surya'nın satır içi tekrarı atılır",
     S._tekrari_at("senelerinde İstanbul'da basılan ( فالسدفة اولى senelerinde İstanbul'da basılan (") ==
     "senelerinde İstanbul'da basılan ( فالسدفة اولى")
dene("Tekrarsız satır değişmez", S._tekrari_at("bir iki üç dört bir iki") == "bir iki üç dört bir iki")
# 5) büyük harfli başlığın ikinci satırı; liste maddesi
r = {"text": "RÜYÂDA GÖRÜLMESİ", "h": 10, "top": 100, "bot": 110, "x0": 60, "x1": 200, "n": 2, "kalin": False, "ocr": True}
dene("Büyük harfli kısa OCR satırı başlık", S._baslik_mi(r, 10, 340, 0.0))
dene("Büyük harfli ama noktalı satır başlık değil", not S._baslik_mi(dict(r, text="BU BİR CÜMLEDİR."), 10, 340, 0.0))
rows = [{"text": t, "h": 10, "top": 100 + 13 * k, "bot": 110 + 13 * k, "x0": 47, "x1": 300, "n": 3, "kalin": False,
         "ocr": True} for k, t in enumerate(["3 - Su üzerinde bulunan kuru çamur küresi : (kabuk)", "4 — Su küresi : (denizler)"])]
dene("'4 — ' liste maddesi ayrı paragraf", len(S._sayfa_paragraflari(rows, 340, 10, 0.0)) == 2)
# 6) sayfa sınırında bölünmüş kelime
dene("Sayfa sınırında 'ken-' + 'di' birleşir", "ken\ue00216\ue003di" in S._duzelt(["Âdemi ken- \ue00216\ue003di sûretinde"])[0])

print("SONUC: HEPSI GECTI" if not kalan else f"SONUC: {len(kalan)} TEST KALDI")
sys.exit(1 if kalan else 0)
