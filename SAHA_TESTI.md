# Sahada Yapılacaklar — tek liste

> ## GERÇEK SAYIM BAŞLADI VE YARIM DURUYOR (2026-08-28)
>
> Ambar 1'de **oturum #2 açık**. 28.08 saat 10:18–16:45 arası A1/A2/A3 rafları
> sayıldı: 255 okutma, 171/1075 adet, 84 fazla kaydı, 8 açık kuyruk kaydı.
> Mesai bitiminde ara verildi, **2026-09-04 civarı kaldığı yerden devam
> edilecek.** Oturum `aktif_raf='A3'` ile duruyor; tampon boş, kilit ve yedek
> parça modu kapalı — temiz bir noktada durduruldu.
>
> **`data/sayim.db` artık canlı veridir.** `sifirla.bat` ÇALIŞTIRILMAZ, yeni
> oturum AÇILMAZ, rapor yeniden YÜKLENMEZ — eşleşme oturum bazlıdır, yeni
> oturum o ana kadar sayılan her şeyi "eksik"e çevirir.
>
> **Yedek alındı — 2026-09-02.** İki kopya, ikisi de `sayim.db` ile birebir
> aynı (SHA256 `18a0ec04…37409`):
>
> | Nerede | Ne var |
> |---|---|
> | `data/yedek-20260902-092138-sayim-yarim/` | `sayim.db` · `etiket/` · `yuklenen/` |
> | `%USERPROFILE%\Desktop\depo-sayim-yedek-20260902\` (depo dışı) | aynısı |
>
> Motor (`app/matching.py`) üzerinde çalışmadan önce yedeği tazeleyin.

> ### ÜÇÜNCÜ DENETİM — 2026-09-04, 11 hata daha (`DENETIM_20260904.md`)
>
> 478 test geçerken yapıldı. Üçü sessiz yanlış sayım üretiyordu, **ikisi canlı
> veride ZATEN gerçekleşmişti.** Hepsi kapatıldı (507 arka uç + 32 arayüz testi).
>
> Sayıma devam etmeden önce iki şey:
>
> 1. **`data/sayim.db` içinde elle düzeltilecek yedi kayıt var** —
>    `DENETIM_20260904.md` > "Açık kalanlar". Kod düzeltmeleri geriye dönük
>    çalışmıyor; bu satırlar 28.08'de yazıldı.
> 2. **Yeni komut kartı bastırın.** `##GERIAL##` kartının adı ve açıklaması
>    düzeltildi (yanlış davranış anlatıyordu) ve `##YEDEK##` artık
>    `##SONRAKI##` ile aynı renkte değil.

**Bu dosyanın tek işi şu soruya cevap vermek: "sırada ne var?"**

Durum (2026-08-27, denetim sonrası): 447 arka uç + 32 arayüz testi geçiyor,
arayüz derleniyor.
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

## Sahadan bildirilen hatalar (2026-08-28 sayımı, hepsi kod üzerinde doğrulandı)

Kullanıcının depoda karşılaştığı ve **veritabanının kopyası üzerinde birebir
üretilen** beş hata.

**S1, S2, S4, S5 kapatıldı (2026-09-02)** ve `tests/test_saha_20260828.py` ile
regresyona bağlandı — 462 arka uç + 32 arayüz testi geçiyor.
`test_silme.py`'deki bir test S5'in ESKİ davranışını doğru sanıp kilitliyordu;
sözleşme değişince güncellendi (2026-08-27 dersinin aynısı, CLAUDE.md §7).

**S3 bilinçli olarak AÇIK bırakıldı** — düzeltmek CLAUDE.md §4.4'ün "sistem
tahmin yürütmez" kuralına dokunuyor, karar kullanıcınındır.

| # | Durum | Belirti | Kök sebep | Nerede |
|---|---|---|---|---|
| S1 | KAPANDI | Fazla işaretlenen üründe `##KILIT##` **bir önceki ürüne** kilit açıyor | Tamponda tanınmayan barkod varken kilit `okutma` tablosundaki son koda düşüyor; `kilit_yok` demesi gerekirdi | `matching.okut`, `komut=="kilit"` son çare dalı |
| S2 | KAPANDI | Tiger'da olmayan ürüne etiket yapıştırıp fazla işaretleyince, ertesi okutmada **etiketten ürünü tanımıyor** | `kuyruk_fazla` hiçbir şey öğrenmiyor ve etiket bağlamıyor — `kuyruk_coz`'daki öğrenme bloğunun karşılığı yok. `##FAZLA##` komutunda da yok | `matching.kuyruk_fazla`, `matching.okut` |
| S3 | **AÇIK** | Malzeme kodu olan ama seri numarası okunmayan üründe **her adet için ayrı ayrı Tiger'dan seçtiriyor** | Malzemenin Tiger kayıtları TEMİZ olduğunda `slot` dalı (`kirli=1` filtresi) hiç ateşlemiyor, her cihaz `fazla_onay` kuyruğuna düşüyor. Örnek: `SR335`, 13 temiz kayıt, 6 cevapsız onay | `matching.grup_coz`, `izleme=='seri'` dalı |
| S4 | KAPANDI | Yapıştırılan DS- etiketi okutulup fazla işaretlense bile **kayıt listeye düşmüyor**; etiket sökülüp yenisi yapıştırılınca oluyor | Etiket daha önce bağlanmışsa `coz()` 1c `tekrar` döner, `grup_coz` grubu hiçbir şey yazmadan bırakır | `matching.coz` 1c, `matching.grup_coz` |
| S5 | KAPANDI | Akış listesindeki **Sil** tuşu silmiyor, kayıt "Tiger'da kaydı yok" kuyruğuna geri düşüyor | `_yan_etkileri_geri_al` kuyruk kaydını yeniden açıyor (`cozuldu=0`). Geri alma için doğru, "bu satırı tamamen kaldır" için yanlış — iki ayrı niyet tek yola bağlanmış | `matching.okutma_sil` |

### Ne yapıldı

| # | Düzeltme |
|---|---|
| S1 | Kilidin son çare dalı YALNIZCA tampon boşken çalışıyor ("az önce saydığıma kilitle"). Tamponda tanınmayan barkod varsa `kilit_yok` döner, **hangi barkodun tanınmadığını yazar** ve tamponu korur |
| S2 | Yeni `fazla_ogren()` yardımcısı: fazla yazan üç dal da artık öğreniyor. Kod biliniyorsa `eslesme`'ye, bilinmiyorsa yeni **`fazla_ad`** tablosuna (barkod → serbest ad). `coz()`'a **4b** adımı eklendi; ikinci okutmada ürün tanınır, kuyruğa düşmez, adı sorulmaz. DS- etiketi bu yolda da deftere işlenir |
| S4 | `grup_coz` hiçbir satır yazmadan dönüyorsa (`tekrar`, `haric`) **tamponu ve `##ADET-N##` değerini geri koyar** — ##FAZLA## / ##ATLA## hâlâ çalışır |
| S5 | `okutma_sil` artık kuyruk kaydını yeniden AÇMIYOR (`kuyruga_geri=False` varsayılan). `##GERIAL##` açmaya devam ediyor — iki ayrı niyet ayrıldı. Onay metni ve sonuç şeridi ne olduğunu söylüyor |
| Miktar | `PATCH /okutma/{id}` artık `miktar` alıyor (yalnızca `fazla` / `yedek`; eşleşende 400). Akış listesinde her fazla satırında adet düğmesi var |

**DK-000002'nin 34 adedi hâlâ düzeltilmedi** — uygulamayı açıp o satırın adet
düğmesinden 35 yazmanız gerekiyor (okutma #92).

Ayrıca sayımın kendi verisinde bulunanlar:

- **DK-000002'de 34 adet kayıp.** Fazla kaydının adı "… **35 tane**", `miktar`
  alanı **1**. Adet, ad kutusuna yazılmış. `PATCH /api/okutma/{id}` yalnızca
  `ad` ve `not_` alıyor — **kaydedilmiş bir miktarı düzeltmenin yolu yok.**
- **`kutu` tablosu boş.** İki DK etiketi de fazla olarak kapatıldığı için
  kap→malzeme bağı hiç kurulmadı; seneye ikisi de yine "kap tanımsız" diyecek.
- **Etiket defteri eksik:** fiziksel olarak 109 DS- etiketi yapıştırılmış,
  `etiket` tablosunda 30'u bağlı görünüyor. Aradaki 79'un hepsi S2'nin
  sonucu — fazla yolundan geçenler.
- **Rapora sızacak iki kayıt:** adı "*Yanlış Okuma İgnorla" olan iki fazla
  satırı (okutma #22, #23) Fazla sekmesine düşecek.
- **Aynı ürün iki adla:** `SL-75 A` (19) ve `SL-75A` (2) raporda iki satır olur.
- **Seri etiketi tükenmek üzere:** 288 basıldı, DS-000287'ye kadar gelindi.
  Devam etmeden önce yeni parti basılmalı.

---

## Bağımsız kod denetimi (2026-09-02) — 5 hata

Dokümanlara güvenmeden, sıfırdan yapılan kod taraması. **476 test geçerken
bulundu**; üçü sessiz yanlış sayım üretiyordu. Hepsi kapatıldı ve
`tests/test_denetim_20260902.py` ile regresyona bağlandı.

| # | Neydi | Neden gözden kaçtı |
|---|---|---|
| **D1** | `izleme='seri'` + `miktar=2` olan satırda tek okutma satırı kapatıyor, ikinci cihaz "tekrar" deyip **hiçbir yere düşmüyordu** — ne sayaçta, ne eksikte, ne fazlada | CLAUDE.md §2.4 "seri satırında miktar hep 1" diyordu. **Gerçek Tiger verisinde yanlış:** miktarı 2 ve 4 olan **32 seri satırı** var (ambar 0/13/14) |
| **D2** | `fazla_bagla` `okutma.geri` alanını **eziyordu**: kuyruk bağı, öğrenilmiş ad ve bağlanmış etiket düşüyor, kayıt silinince hiçbiri geri alınamıyordu | Yan etki sözleşmesi tek yerde toplanmamıştı; `geri` üç ayrı adımda büyüyor ama biri onu yeniden yazıyordu |
| **D3** | Boş havuzdan basılan `DM-` etiketi çözülünce yalnızca `eslesme`'ye yazılıyor, **deftere yazılmıyordu**. `bas(kapsam="eksik")` tam o alana baktığı için aynı malzemeye **ikinci bir numara basıyordu** | İki kayıt yeri (`eslesme` motor için, `etiket` defter için) ve yalnızca biri dolduruluyordu. Gerçek veride doğrulandı: `DM-000002 → SR335` eşleşmede yazılı, defterde boş; yeniden basımda SR335'e `DM-000174` veriliyordu |
| **D4** | 150 adetlik bir fazla kaydı tek cihazlık bir satıra bağlanabiliyordu; **149 adet buharlaşıyordu.** Eşleştirme ekranı miktarı göstermiyordu bile | Kapasite kontrolü "satır dolu mu" diye bakıyordu, "kaç adet sığıyor" diye değil |
| **D5** | `:memory:` veritabanı **gerçek etiket defterini okuyup üstüne yazıyordu** | `klasor()` dosya yolu olmayan bağlantıda `data/etiket`e düşüyordu — docstring'inde yazan amacın tam tersi |

**D5 bu denetim sırasında gerçekleşti:** bir denetim betiği `basim-1.csv`
(240 seri etiketi) ve `basim-2.csv` (24 malzeme etiketi) dosyalarını iki
satırlık deneme verisiyle ezdi. **Yedekten geri alındı**, dördü de SHA256
olarak birebir doğrulandı; `sayim.db` hiç etkilenmedi. Yedek almasaydık
basılmış 264 fiziksel etiketin defteri gidiyordu.

### Ne yapıldı

- **Tek ölçüt:** `beklenen_adet(b)` — seri ve lot artık aynı kuralı kullanıyor
  (`sayılan < beklenen`). `kapasite_kaldi`, `sayaclar`, `ara(sadece_acik)`,
  `eksik_lotlar` ve `reports.eksik_kayitlar` beşi de oradan geçiyor. Seri
  takiplide beklenen en az 1 — Tiger'dan 0 miktarla gelen satır sayılamaz
  hâle gelmesin.
- **`_geri_ekle()`**: `okutma.geri` artık EKLENİYOR, ezilmiyor.
- **`etiketler.malzeme_etiketi_isle()`** + `db.malzeme_etiket_defterini_onar()`
  göçü: yeni bağlamalar deftere işleniyor, mevcut veri açılışta onarılıyor
  (canlı veride `DM-000002 → SR335` doğrulandı).
- **`fazla_bagla` miktar kapısı**: sığmayan kayıt `miktar_sigmiyor` ile
  reddediliyor; eşleştirme ekranı 1'den büyük adedi rozetle gösteriyor.
- **`klasor()` bellek veritabanında `None`** döner; `csv_yaz`/`csv_geri_yukle`
  (hem etiket hem kap) sessizce atlar.

### D1 hangi ambarları etkiliyor

Ambar 1'de (şu an sayılan) **hiç yok** — 805 seri satırının hepsi 1 adet.
Etkilenen 32 satır ambar 0 (10), 13 (2), 14 (4) ve diğerlerinde. Yani
**yarım kalan sayım bu hatadan etkilenmedi**, ama sıradaki ambarlar
etkilenecekti.

---

## Sahada bakılacak — 2026-09-04 düzeltmeleri

Hepsinin regresyon testi var ama hiçbiri gerçek okuyucuyla denenmedi.

- [ ] **K2** — bir ürüne DS- etiketi yapıştırıp fazla yazın, sonra AYNI etiketi
      bir daha okutun: "TEKRAR" demeli, ikinci fazla kaydı OLUŞMAMALI. Tampon
      durmalı (gerçekten ikinci bir ürünse F3 ile fazla yazabilmelisiniz).
- [ ] **K3** — Tiger'da olmayan bir ürünü adlandırın, sonra başka bir malzemeye
      `##KILIT##` deyip o barkodu yeniden okutun: kilitli malzemeye YAZILMAMALI,
      öğrenilmiş adıyla fazla çıkmalı.
- [ ] **Y3** — yarım kalmış bir lot varken Rapor ekranından "Sayımı bitir":
      artık "Yine de bitirilsin mi?" sormalı (eskiden kırmızı kutuda kalıyordu).
- [ ] **Y4** — boş tamponda `##ADET-150##` sonra `##ATLA##`: "OKUTULMUŞ BARKOD
      YOK" demeli ve 150 ayakta kalmalı.
- [ ] **O3** — telefondan Adet paneline 40 girip "Ürünü listeden bul" ile bir
      lot kalemini seçin: 40 adet yazmalı, panel sıfırlanmalı.
- [ ] **O5** — aynı tanınmayan ürünü iki kez okutun: ikincisinde "AYNISI ZATEN
      VAR" uyarısı çıkmalı ama kayıt yine yazılmalı.
- [ ] **Dx1/Dx2** — yeni komut kartını bastırın: `GERİ AL` yazmalı ve
      `YEDEK PARÇA MODU` kartı `SIRADAKİ ÜRÜN`den farklı renkte olmalı.
- [ ] **O2** — kapalı bir oturumda akıştan satır silmeyi deneyin: 409 vermeli
      ve "Geçmiş ekranından Yeniden aç" demeli.

---

## Denenip sonucu yazılanlar

**2026-08-28 — ilk gerçek sayım günü, Ambar 1, A1/A2/A3 rafları.** Akış ayakta:
komut barkodları, raf geçişleri, grup mantığı, kuyruk ve fotoğraf çalıştı; 255
okutma sorunsuz kaydedildi ve program kapatılıp açıldığında oturum kaldığı
yerden geldi (§6'nın ilk maddesi ✔). Çıkan beş hata yukarıdaki tabloda.

Sayımın kendi rakamları da bir bulgu: A1 rafında 76 fazla / 16 eşleşme çıktı —
o raf büyük ölçüde **Tiger'a hiç girilmemiş ürünlerden** oluşuyor. A2 (79/3) ve
A3 (73/5) beklenen görünümde. Yani kendi bastığımız etiket akışı (§1) sahada
düşünülenden çok daha merkezi bir yol; S2 ve S4 tam da orayı vuruyor.
