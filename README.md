# Dedplay Kütüphane

Klasik eserleri (OpenITI ve diğer açık kaynaklar) bulup profesyonel EPUB'a dönüştüren uygulama.
Dedplay ailesinin parçası: metin çıkarma Stüdyo'dan, çeviri Translate'ten, Osmanlıca Osmanlıca
çeviriciden gelir; Kütüphane bunları arka planda çağırır.

- Tek kaynak: her kitap `/data/kitaplar/<kimlik>/kitap.json` dosyasıdır; bütün EPUB sürümleri
  (Türkçe, Osmanlıca, iki dilli, asıllı) bundan üretilir.
- EPUB 3: çok seviyeli fihrist, basılı baskının sayfa numaraları (page-list), dipnot pencereleri,
  sağdan sola Osmanlıca/Arapça (Amiri gömülü). Her EPUB W3C epubcheck ile denetlenir.
- Port: 8075. Veri: `/DATA/AppData/dedplay-studyo/kutuphane`.

Sürümler:
- 0.1: OpenITI'de Türkçe yazımla arama, ekleme, Arapça EPUB, künye düzenleme.
- 0.2: Elindeki kitaplar (PDF, EPUB, DOCX, TXT; sunucu arşivinden ya da bilgisayardan). Bozuk metin katmanı
  tanınıp OCR ile baştan okunur; basılı sayfa numaraları, fihrist (başlık seviyeleri) ve dipnot bağlantıları
  korunur; Stüdyo'nun düzeltmeleri (Zemberek harf onarımı vb.) uygulanır; Osmanlıca çeviriciyle Türkçe,
  Osmanlıca ve iki dilli EPUB üretilir.

Testler (sunucuda, kod klasöründe):
    docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kutuphane:latest python tests/test_temel.py
    docker run --rm -v "$PWD":/k -w /k -e PYTHONPATH=/app berzahbey/dedplay-kutuphane:latest python tests/test_kaynak.py

Sırada: okuma ve düzeltme ekranı, fihrist düzenleme, Arapça eserlerin çevirisi (gemma3:27b).

OpenITI metinleri CC BY-NC-SA 4.0 lisanslıdır; üretilen EPUB'lar kişisel, ticari olmayan kullanım içindir.
