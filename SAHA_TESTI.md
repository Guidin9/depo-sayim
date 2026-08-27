# Sahada Yapılacaklar — tek liste

**Bu dosyanın tek işi şu soruya cevap vermek: "sırada ne var?"**

Durum (2026-08-27, denetim sonrası): 443 test geçiyor, arayüz derleniyor.
`depo_sayim_bugs_improvements.md` ve `DEMO_FEEDBACK.md` maddelerinin hepsi
kapalı.

**Bu dosya bir gün önce "kodda bilinen açık hata yok" diyordu ve yanlıştı.**
Bağımsız denetim, 413 test geçerken sekiz hata buldu (CLAUDE.md §7'deki tablo);
beşi sessiz yanlış sayım üretiyordu. Hepsi kapatıldı, hepsinin regresyon testi
var ve hepsi gerçek Tiger verisiyle uçtan uca doğrulandı. Yine de aşağıdaki
listeyi "kod hazır" diye değil, **"kod sahada sınanmadı"** diye okuyun.

Geriye kalan iş büyük ölçüde **kodda değil, depoda**: yazılanların hiçbiri
gerçek okuyucu, gerçek yazıcı, gerçek telefon ve gerçek raf ile denenmedi.

Bir madde sahada denendiğinde **bu dosyada işaretleyin ve sonucu yazın** —
"çalıştı" da bir bulgudur, bir daha denenmesin.

---

## 0. Önce: yarım saatlik ilk tur

Sırayla, tek oturumda. Amaç sistemi kırmak değil, akışın ayakta olduğunu
görmek.

- [ ] `git pull` → `kurulum.bat` → `baslat.bat` (depodaki laptopta, temiz kurulum)
- [ ] Tiger'dan güncel Seri/Lot Envanter Raporu al (CLAUDE.md §3.1 filtreleri),
      Kurulum ekranından yükle, ambar seç, oturum aç
- [ ] **Barkod ekranından** komut kartını ve bir sayfa raf etiketini bastır
      (bu ekran artık Excel yüklemeden de açılıyor — onu da bir kez deneyin)
- [ ] Bir rafta 10-15 ürün say, `##SONRAKI##` ile ilerle
- [ ] Sayımı bitir (**`##BITIR##` artık İKİ kez okutuluyor**), Excel raporunu
      aç: Eksik / Fazla / Eşleşen sayıları beklediğiniz gibi mi?

Denetimde kapatılan sekiz hatanın sahada da doğru davrandığını görün:

- [ ] **B1** — `##SONRAKI##`'yi bilerek unutun, iki cihazın S/N'ini arka arkaya
      okutun: "2 AYRI CİHAZ SAYILDI" sarı uyarısı çıkmalı ve sayaç 2 artmalı.
- [ ] **B2** — üstünde hem UPC hem seri numarası olan bir ürün okutun: Tiger
      Düzeltme'ye **seri numarası**, Barkod Tablosu'na **UPC** düşmeli.
      İki tanınmayan alfanümerik barkod varsa ekran hangisinin S/N olduğunu
      SORMALI.
- [ ] **B3** — aynı cihazın seri numarasını iki kez okutun: ikincisi "TEKRAR"
      demeli ve ikinci bir slot DOLMAMALI.
- [ ] **B4** — bir lot kalemini adet girmeden okutun: sayaç "KALAN ADET"i
      düşürmemeli, `##BITIR##` eksik lotu listelemeli.
- [ ] **B7** — `##ADET-5##` + çok lotlu malzeme + `##GERIAL##`: beş satırın
      **hepsi** geri alınmalı, sayaç sıfırlanmalı.
- [ ] **B8** — `##BITIR##`'i bir kez okutun (kapanmamalı), sonra Geçmiş
      ekranından "Yeniden aç" ile oturumu geri açın: sayım korunmalı.

Buraya kadar sorunsuzsa gerisi ayrıntı. Takılırsanız durun, notunu alın.

---

## 1. Basılan kâğıtlar (hiç okuyucuyla denenmedi)

- [ ] **Komut kartı** — laminatlı kart okuyucuyla okunuyor mu? `##SONRAKI##`,
      `##GERIAL##`, `##ADET-25##`, `##KILIT##`, `##KUTUKAPAT##` sırayla.
- [ ] **Raf etiketi** — yapışkanlı A4 sayfa (3×8, 70×37,125 mm) yazıcıdan
      kayarak mı çıkıyor? Alt satır kendi etiketinin dışına taşıyor mu?
      (Kenar boşluğu 0 olmak zorunda — CLAUDE.md §12.4.)
- [ ] **Türkçe raf adı** — `##RAF-ÜST-1##` bastırın: kart `UST-1` basmalı ve
      telefondan elle `ÜST-1` yazınca **aynı rafa** düşmeli, iki ayrı raf
      oluşmamalı.
- [ ] **DM- / DS- etiketleri** — bir sayfa basıp ürüne yapıştırın, okutun.
      Etiketi yapıştırmadan **önce** okutmak gerekiyor (CLAUDE.md §12.3).
- [ ] **DK- kap etiketi** — büyük basılıyor; laminatsız kap yüzeyinden,
      uzaktan ve açılı tutulan okuyucuyla okunuyor mu?
- [ ] Termal rulo düzeni (50×25 mm) kullanılacaksa o da denenmeli.

## 2. Telefon (CLAUDE.md §9 — sunucu tarafı doğrulandı, telefon hiç denenmedi)

- [ ] Sayfayı tamamen kapat, PC'deki QR'ı okut → `/telefon` açılıyor mu,
      gösterge 🟢 mi?
- [ ] Laptopta barkod okut → telefon dokunmadan güncelleniyor mu?
- [ ] Telefonu 30 sn kilitle, aç → ekran kendiliğinden tazeleniyor mu?
- [ ] Sunucuyu kapat → 🔴 çıkıyor mu; geri aç → 🟢'ye dönüp veriyi çekiyor mu?
- [ ] Tanınmayan grup okut → telefonda kart + 📷 çıkıyor mu, çekilen foto
      laptoptaki Kuyruk ekranında görünüyor mu?
- [ ] Telefondan aday seç → laptop ekranı anında düşüyor mu?
- [ ] Telefondaki alt çubuk (Sıradaki ürün / Geri al) ve Raf · İptal · Atla ·
      Fazla düğmeleri eldivenle basılabiliyor mu (48 px hedef)?

> Güncellenmiyorsa: telefonun adres çubuğuna `http://<laptop-ip>:8000/api/olaylar`
> yazın. Metin akıyorsa sorun arayüzde, akmıyorsa bağlantı/sunucu tarafında
> (sunucu `--host 0.0.0.0` ile mi açık, güvenlik duvarı 8000'i kapatıyor mu).

## 3. Sayımı hızlandıran kipler (kod hazır, hangisi işe yarıyor bilinmiyor)

- [ ] **`##KILIT##` (I2)** — 21 cihazlı bir malzemede kodu bir kez okutup
      yalnız seri numaralarıyla devam etmek gerçekten hızlandırıyor mu?
- [ ] **`##YEDEK##` (I4)** — yedek parça modunda okutulanlar rapordaki kendi
      sekmesinde doğru görünüyor mu?
- [ ] **`##ADET-N##`** — lot/dökme kalemde adet girmek kartla mı, telefondaki
      Adet paneliyle mi pratik?
- [ ] **Elle sayma (I5)** — barkodu olmayan ürünü listeden bulmak sahada ne
      kadar sürüyor?
- [ ] **Akıştan satır silme (I1)** — yanlış okutmayı birkaç ürün sonra fark
      edip silmek işe yarıyor mu?

## 4. Kap barkodu (KUTU_TASARIM.md — en yeni, en az denenmiş)

- [ ] Depoda gerçekten kaç kap var, kaçına etiket bastınız?
- [ ] **"Kaç adet?" sorusu** akışı yavaşlatıyor mu — `##ADET-N##` okutmak mı,
      ekrandan yazmak mı pratik?
- [ ] **30 günlük tazelik eşiği** (`kutu.TAZELIK_GUN`) doğru mu? Yıllık sayımda
      pratikte hep "bayat" dalı işler; eşik yalnızca aynı kap kısa aralıkla iki
      kez sayılırsa fark yaratır.
- [ ] İçerik değişince kullanıcı etiketi yeniden basıyor mu, yoksa eski malzeme
      adı kabın üstünde mi kalıyor? (Kod aynı kalır; yanlış olan yalnızca insan
      okur satır.)
- [ ] **Seri takipli kapta hangisi hızlı:** kabı okutup açmak mı, kodu bir kez
      okutup `##KILIT##` demek mi? İkisi aynı kilidi kuruyor; kap ayrıca sayaç
      veriyor ama bir de kapatma adımı istiyor.
- [ ] Kabı kapatmayı unutan kullanıcı ne yapıyor? Rozet ekranda duruyor ve
      sonraki kap açılınca öncekinin sayacı kapanıyor — sahada yetiyor mu,
      yoksa raf değişiminde de kapanmalı mı?

## 5. Rapor ve Tiger'a işleme (uçtan uca hiç yapılmadı)

- [ ] Sayım sonu **eşleştirme ekranı**: fazla çıkanların kaçı aslında eksik
      listesindeki kaydın kendisiydi?
- [ ] **Tiger Düzeltme** sekmesindeki `eski S/N → yeni S/N` satırları Tiger'a
      girilebildi mi?
- [ ] **Barkod Tablosu** sekmesi malzeme kartı > Birimler > Barkod alanına
      yazıldı mı? Yazıldıktan sonra o ürünler sorusuz eşleşiyor mu?
- [ ] **Ambar Sayımı ekranı**: Sayım Miktarı sütunu fiili stokla dolu geliyor —
      sıfırlamadan fiş oluşturmayın (CLAUDE.md §6).
- [ ] Rapordaki Eksik sayısı depodaki gerçekle örtüşüyor mu, yoksa sayım mı
      eksik kaldı?

## 6. Dayanıklılık

- [ ] Sayım ortasında sunucuyu kapatıp açın: oturum kaldığı yerden devam
      ediyor mu?
- [ ] `sifirla.bat` çalıştırın: `data/etiket` (etiket ve **kap** defteri)
      yerinde kalıyor mu, sayaç basılmış bir numarayı ikinci kez veriyor mu?
- [ ] 800+ satırlık ambarda eşleştirme listesi (Kuyruk ekranı arama) yavaş mı?

---

## Denenip sonucu yazılanlar

_(Boş. İlk saha turundan sonra buraya taşıyın: madde, tarih, sonuç, çıkan yeni
iş varsa nereye yazıldığı.)_
