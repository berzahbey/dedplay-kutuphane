# Dedplay Kütüphane

Klasik eserleri (OpenITI ve diğer açık kaynaklar) bulup profesyonel EPUB'a dönüştüren uygulama.
Dedplay ailesinin parçası: metin çıkarma Stüdyo'dan, çeviri Translate'ten, Osmanlıca Osmanlıca
çeviriciden gelir; Kütüphane bunları arka planda çağırır.

- Tek kaynak: her kitap `/data/kitaplar/<kimlik>/kitap.json` dosyasıdır; bütün EPUB sürümleri
  (Türkçe, Osmanlıca, iki dilli, asıllı) bundan üretilir.
- EPUB 3: çok seviyeli fihrist, basılı baskının sayfa numaraları (page-list), dipnot pencereleri,
  sağdan sola Osmanlıca/Arapça (Amiri gömülü). Her EPUB W3C epubcheck ile denetlenir.
- Port: 8075. Veri: `/DATA/AppData/dedplay-studyo/kutuphane`.

Sürüm 0.1: OpenITI'de Türkçe yazımla arama, ekleme, Arapça EPUB, künye düzenleme.
Sırada: çeviri (Translate), Osmanlıca, okuma ve düzeltme ekranı, sunucu/yerel/internet kaynakları.

OpenITI metinleri CC BY-NC-SA 4.0 lisanslıdır; üretilen EPUB'lar kişisel, ticari olmayan kullanım içindir.
