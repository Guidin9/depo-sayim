# Claude Code Görev Promptu

Aşağıdaki metni Claude Code'a ver. Önce Plan Mode'da çalıştır, planı onayla,
sonra uygulat.

---

## Prompt

```
Bu klasörde bir depo sayım uygulaması geliştireceğiz. Başlamadan önce CLAUDE.md
dosyasının tamamını oku — projenin alan bilgisi orada, sahada gerçek veriyle
doğrulanmış kurallar içeriyor. depo_sayim.py çalışan bir prototip; eşleştirme
motorunun mantığı doğru ve test edilmiş, ama arayüzü ilkel. deneme.XLSX gerçek
test verisi (870 satır).

Görev: prototipi düzgün bir web uygulamasına dönüştür.

## Mimari

Backend: FastAPI + SQLite. Frontend: React + Vite + Tailwind, build alınıp
FastAPI tarafından statik servis edilecek. Tek komutla ayağa kalkmalı:
`uvicorn app.main:app`. Depodaki laptopta çalışacak, internet bağlantısı
olmayabilir — hiçbir CDN bağımlılığı olmasın, her şey bundle'a girsin.

Klasör yapısı:
  app/          FastAPI backend
    main.py     uygulama + statik servis
    db.py       SQLite şema ve bağlantı
    matching.py eşleştirme motoru (prototipten taşı, TESTLERİ VAR)
    importer.py Tiger Excel/JSON yükleyici
    reports.py  5 sekmeli Excel çıktısı
    routers/    API uç noktaları
  web/          React kaynak
  tests/        pytest
  data/         sayim.db ve yüklenen dosyalar (gitignore)

## Eşleştirme motoru — dikkat

matching.py prototipteki mantığı BİREBİR korumalı. Çözümleme sırası, kirli kayıt
tespiti, grup mantığı ve kod öneki eşleşmesi sahada doğrulandı, değiştirme.
İyileştirebileceğin tek yer performans: prototip her okutmada tüm beklenen
listeyi Python'da tarıyor, bunu SQL indeksleriyle çöz.

CLAUDE.md bölüm 8'deki 7 test senaryosunu pytest olarak yaz. Hepsi geçmeli.

## Ekranlar

1. Kurulum — Tiger raporunu yükle, ambar seç, sayım dışı kalem filtresini
   (CLAUDE.md 3.4) göster ve kullanıcıya onaylat. Yükleme özeti: kaç satır,
   kaç seri/lot/adet, kaç kirli kayıt.

2. Sayım — asıl ekran. Tam ekran, tek bir input alanı sürekli odaklı.
   - Üstte: ambar, aktif raf, canlı sayaçlar (okutulan / kalan / fazla / kuyruk)
   - Ortada: mevcut grup — o an tampondaki barkodlar, her birinin ne olarak
     tanındığı (S/N, P/N, UPC, tanınmadı) rozetle
   - Altta: son okutmalar akışı, renk kodlu
   - Ses geri bildirimi: her okutma tık, grup eşleşti uzun bip, uyarı çift
     alçak bip, kuyruk üç bip. Web Audio API, ekrana bakmadan kullanılabilmeli.
   - Klavye kısayolları da olsun (komut kartı yanında değilse)

3. Kuyruk — çözülmeyi bekleyen gruplar. Her grup için malzeme arama (kod ve
   açıklamada, kirli kayıtlı malzemeler üstte), seçince eşleşme öğrenilir.

4. Rapor — sekme önizlemeleri ve Excel indirme.

5. Oturum geçmişi — geçmiş sayımlar, tekrar rapor indirme.

## UI tasarımı

Depo ortamı için tasarla, ofis için değil:
- Büyük dokunma hedefleri, yüksek kontrast, uzaktan okunabilir tipografi
- Sayım ekranındaki input her zaman odaklı kalmalı — kullanıcı yanlışlıkla
  tıklasa bile odak geri dönmeli
- Renk tek başına bilgi taşımasın, ikon ve metinle destekle
- Koyu tema varsayılan (depo aydınlatması genelde kötü)
- Generic bootstrap/shadcn görünümü olmasın; sade ama karakterli olsun
- Türkçe arayüz, Türkçe karakterler doğru render edilmeli

## Ek özellikler

- Raf takibi: ##RAF-XX## okutulunca aktif raf değişir, sonraki okutmalar o rafa
  yazılır. Rapora raf sütunu eklenir.
- Oturum devam ettirme: uygulama kapanıp açılsa bile açık oturum kaldığı yerden
  devam etsin.
- Geri alma: son okutmayı ve son grubu geri alabilme.
- Komut barkodu kartı üretimi uygulama içinden yapılabilsin (komut_karti.py'yi
  bir uç noktaya taşı, raf listesi kullanıcıdan alınsın).
- Yükleyici hem Excel hem JSON kabul etsin (Tiger her ikisini de veriyor).

## Yapma

- Tiger'a yazma girişimi yok. Uygulama sadece okur ve rapor üretir.
- Kullanıcı doğrulaması, çok kullanıcı, bulut yok. Tek kişi, tek makine.
- localStorage'a kritik veri koyma; her şey SQLite'ta olsun.
- Eşleştirme motorunun mantığını "iyileştirme" adına değiştirme.

## Sıra

1. Backend iskeleti + şema + matching.py taşıma + testler (önce testler geçsin)
2. Importer + rapor üretimi, CLI ile doğrula
3. API uç noktaları
4. Frontend
5. README ve kurulum talimatı

Her adımdan sonra dur ve göster. Plan Mode'da başla.
```

---

## Claude Code'a verilecek dosyalar

Proje klasörüne şunları koy:

```
CLAUDE.md          bu bağlam dosyası
PROMPT.md          bu dosya
depo_sayim.py      referans prototip
komut_karti.py     barkod kartı üreticisi
deneme.XLSX        Tiger raporu - depoda yok, .gitignore'da (gercek stok verisi)
```

## Sonrası

İlk çalışan sürümü aldıktan sonra sahada bir rafta dene. Tıkanan yerleri not al,
Claude Code'a `/clear` sonra tek tek düzelt. Prototipte test edilmemiş tek şey
gerçek okuyucu ritmi — `##SONRAKI##` okutma alışkanlığının elde nasıl oturduğu
ancak sahada anlaşılır.
