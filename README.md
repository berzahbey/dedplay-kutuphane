# Dedplay Kütüphane

Klasik eserleri (OpenITI ve diğer açık kaynaklar) bulup profesyonel EPUB'a dönüştüren uygulama.
Dedplay ailesinin parçası: metin çıkarma Stüdyo'dan, çeviri Translate'ten, Osmanlıca Osmanlıca
çeviriciden gelir; Kütüphane bunları arka planda çağırır.

- Tek kaynak: her kitap `/data/kitaplar/<kimlik>/kitap.json` dosyasıdır; bütün EPUB sürümleri
  (Türkçe, Osmanlıca, iki dilli, asıllı) bundan üretilir.
- EPUB 3: çok seviyeli fihrist, basılı baskının sayfa numaraları (page-list), dipnot pencereleri,
  sağdan sola Osmanlıca/Arapça (Amiri gömülü). Her EPUB W3C epubcheck ile denetlenir.
- Port: 8075. Veri: `/DATA/AppData/dedplay-studyo/kutuphane`.

Kurulum (ZimaOS):
- `docker-compose.zimaos.yml`: Uygulama Mağazası → Özel Kurulum (Custom Install) → İçe aktar → dosyanın içeriğini
  yapıştır. Önce dosyanın başındaki iki klasörü (kitap klasörü, EPUB çıktı klasörü) kontrol et. Dedplay Stüdyo
  stack'i kurulu olmalı (Translate, Osmanlıca, Stüdyo, Ollama). Dosyadaki işlemci ayarı servisi ZimaOS'un 1 çekirdek
  sınırını kendiliğinden kaldırır.
- `docker-compose.yml`: komut satırından kurulum (`docker compose -p dedplay-kutuphane up -d`).

Sürümler:
- 0.1: OpenITI'de Türkçe yazımla arama, ekleme, Arapça EPUB, künye düzenleme.
- 0.2: Elindeki kitaplar (PDF, EPUB, DOCX, TXT; sunucu arşivinden ya da bilgisayardan). Bozuk metin katmanı
  tanınıp OCR ile baştan okunur; basılı sayfa numaraları, fihrist (başlık seviyeleri) ve dipnot bağlantıları
  korunur; Stüdyo'nun düzeltmeleri (Zemberek harf onarımı vb.) uygulanır; Osmanlıca çeviriciyle Türkçe,
  Osmanlıca ve iki dilli EPUB üretilir.

- 0.2.1-0.2.2: fihrist "Bölüm 001 (5-20) Başlık", OCR çöpü başlık denetimi, sayfa numarası denetimi, sade künye.
- 0.3: Okuma ve düzeltme ekranı (/oku/<kitap>): Türkçe, Osmanlıca ya da ikisi; fihrist çekmecesi; kaldığın yer
  sunucuda (başka cihazdan devam). Düzelt kipinde paragraf düzeltme (Türkçe düzelince Osmanlıcası yenilenir, elle
  düzeltilmiş Osmanlıca korunur), paragraf/başlık dönüşümü, silme; her değişiklik "Geri al" ile döner.
  EPUB'lar düzeltmelerden sonra arka planda yeniden üretilir.

- 0.4: Hazır EPUB'lar Kitaplar klasörüne dile göre (Türkçe/, Osmanlıca/, Türkçe-Osmanlıca/, Arapça/) yazılır.
  "Stüdyo'ya gönder": bölümler Türkçe + düzeltilmiş Osmanlıca hazır parçalar olarak Stüdyo'ya gider (Stüdyo'da
  /api/jobs/from-kutuphane); Stüdyo seslendirir ve PDF, Word, HTML, TXT biçimlerini kendi çıktı klasörüne kaydeder.

- 0.5: İş akışı: ekle -> temizle, fihrist, kendi dilinde EPUB -> (Türkçe değilse) Türkçe çeviri (Translate paragraf
  işi, gemma3:27b + kelam sözlüğü, kendiliğinden başlar) -> Osmanlıca ve Türkçe-Osmanlıca -> okuyup düzelt ->
  "Stüdyo'ya gönder" (sadece Türkçe; Stüdyo seslendirir, Osmanlıcaya kendisi çevirir). OpenITI'nin düzeltilmemiş
  OCR metinlerinde resim bağlantıları, varak işaretleri ve naşir dipnot numaraları temizlenir.

- 0.5.1: EPUB'un kendi fihristi ve PDF yer imleri kullanılır (başlıklar, seviyeler, ön sayfalar); bölünmüş kelime
  onarımı ("oldu ğundan" -> "olduğundan", Stüdyo'nun düzeltme kodundan); kesme işareti boşlukları.

- 0.5.3: Basılı içindekilerden fihrist (PDF, yer imi yoksa): girdiler, girintiden seviye, başlık gösterdiği sayfada
  aranır; taranmış içindekiler sayfası nokta dizilerine dayanıklı okunur; iki sayfalık içindekiler.
- 0.5.2: Orijinale sadakat: kitap adı dosya adından (Türkçe harfliyse), kitabın kendi kapak görseli, basılı
  içindekiler sayfası kitabın sonuna, "Page N" yer imleri yok sayılır. OCR katmanında ayrı yazı tipli ı/ğ/ş parçaları
  kaynağında birleşir; normal boyda yazılmış dipnot numaraları sayfanın dipnotuna bağlanır; kenar numaraları
  ("(17)", aslın sayfa numarası) metinden ayıklanır.

Testler (sunucuda, kod klasöründe):
    docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kutuphane:latest python tests/test_temel.py
    docker run --rm -v "$PWD":/k -w /k -e PYTHONPATH=/app berzahbey/dedplay-kutuphane:latest python tests/test_kaynak.py
    docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kutuphane:latest python tests/test_okuma.py
    docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kutuphane:latest python tests/test_studyo.py
    docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kutuphane:latest python tests/test_ceviri.py

Sırada: taranmış Türkçe kitaplardaki Arapça satırların Arapça OCR'ı, Arapça eserlerin çevirisi (gemma3:27b).

OpenITI metinleri CC BY-NC-SA 4.0 lisanslıdır; üretilen EPUB'lar kişisel, ticari olmayan kullanım içindir.
