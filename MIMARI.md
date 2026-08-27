# Mimari Referansı — Depo Sayım Uygulaması

Bu dosya **kod haritasıdır**: modüller, veritabanı şeması, API uçları, motorun
dallanması, arayüz yapısı. Amacı her oturumda kodu yeniden keşfetmek zorunda
kalmamaktır.

`CLAUDE.md` ile karışmasın: orası **alan bilgisidir** (Tiger, kirli seri
numaraları, etiket mantığı, sahada doğrulanmış kurallar). Burası **koddur.**

> **Kural:** Mimari değişiklikte bu dosya aynı commit'te güncellenir. Yeni bir
> API ucu, tablo, sütun veya ekran eklendiğinde buradaki tablolara da işlenir.

Son güncelleme: 2026-08-27 · 409 test geçiyor.

---

## 1. Modül haritası

```
app/
  main.py        FastAPI uygulaması, SSE ucu, ağ/QR uçları, SPA servisi
  db.py          SQLite şeması, bağlantı, göç (EK_SUTUNLAR), hariç kuralları
  norm.py        norm() / sifirsiz() / upc_mi() / kirli_mi() / komut_coz()
  matching.py    EŞLEŞTİRME MOTORU — coz(), grup_coz(), okut(), kuyruk_coz()
  importer.py    Tiger Excel/JSON raporunu beklenen tablosuna yükler
  reports.py     6 sekmeli rapor verisi + Excel yazıcı
  etiketler.py   Kendi bastığımız DM-/DS-/DK- etiketlerinin defteri
  kutu.py        Kap defteri: hangi kapta ne var + tazelik kuralı (DK-)
  barkod.py      Code128 komut kartı ve etiket sayfası (HTML, base64 SVG)
  olaylar.py     SSE yayını (tek global sürüm sayacı)
  oturumlar.py   Oturum yaşam döngüsü (ac / acik / getir / bitir / gecmis)
  cli.py         Komut satırı arayüzü
  routers/       ortak.py · yukleme.py · oturum.py · kuyruk.py · rapor.py · etiket.py · kutu.py
  static/        web/ derlemesinin çıktısı (git'te yok)

web/src/
  App.tsx        Yönlendirme, açık oturum durumu, SSE aboneliği
  api.ts         Tüm API çağrıları ve TypeScript tipleri
  olaylar.ts     SSE + görünürlük tazelemesi + yedek yoklama
  bilesenler.tsx Dugme · Marka · Baslik · EkranBasligi · Panel · Rozet · SayacKutu ·
                 Nokta · Uyari · Durum · Girdi · Alan · Ortu · Sekmeler · Tablo ·
                 Foto · FotoBuyut · Bos · Kod   (DURUM_STILI tek renk tablosu)
  ikonlar.tsx    Inline SVG çizgi ikonlar (emoji YASAK — CLAUDE.md §10.1)
  foto.ts        kucult() — 1280 px / JPEG 0.72
  liste.ts       suz() + kademeli() + grupla() — eşleştirme listesi: veri
                 eksiksiz gelir, süzme/gruplama/kademeli çizim istemcide
  GrupluListe.tsx  Malzemeye (kod+açıklama) göre gruplanmış açılır seçim listesi
                 + sayaç kutusu; Kuyruk · Eşleme · Telefon ortak kullanır
  ses.ts         bip() ve ses tercihi
  Isima.tsx · TelefonKutu.tsx · stil.css   (Zemin.tsx 2026-08-23'te silindi)
  ekranlar/      Kurulum · Sayim · Kuyruk · Esleme · Rapor · Gecmis · Ayarlar · Etiket · Telefon
```

İş mantığı router'larda **yoktur**, `matching.py` ve `reports.py`'dedir.

---

## 2. Veritabanı şeması

SQLite, `data/sayim.db` (`SAYIM_DB` ortam değişkeniyle değiştirilebilir).
Şema `db.py` `SEMA` sabitinde; `baglan()` her açılışta `executescript` ile
idempotent kurar, sonra `goc()` ve `kurallari_tohumla()` çalışır.

| Tablo | Sütunlar |
|---|---|
| `yukleme` | id · ts · dosya_adi · kaynak · satir · not_ |
| `beklenen` | id · yukleme · kod · **kod_n** · aciklama · tur · ambar · izleme · seri · **seri_n** · **seri_n0** · seri_aciklama · miktar · birim · kirli · kirli_sebep · haric · haric_sebep · kaynak |
| `haric_kural` | id · tip · desen · aktif · varsayilan · UNIQUE(tip,desen) |
| `oturum` | id · yukleme · ambar · basla · bitir · aktif_raf · durum · **bekleyen_adet** · **sabit_kod** · **yedek_parca** · **acik_kutu** · **acik_kutu_ilk** |
| `okutma` | id · oturum · ts · **ham** · kod · seri · miktar · beklenen_id · **tip** · raf · grup · not_ · ad · **geri** · **yeni_seri** |
| `eslesme` | **barkod (PK)** · kod · seri · ts |
| `tampon` | id · oturum · ts · ham |
| `kuyruk` | id · oturum · ts · barkodlar (JSON) · raf · cozuldu · not_ · beklet · **tur** · kod · ad · **adet** |
| `kuyruk_foto` | id · kuyruk · **okutma** · ts · tur · boyut · **veri BLOB** |
| `basim` | id · ts · tur · adet · ilk · son · duzen · not_ |
| `etiket` | **kod (PK)** · gosterim · **tur** (`malzeme`\|`seri`\|`kutu`) · basim · ts · malzeme · beklenen_id · oturum · ts_bagla · raf |
| `kutu` | **kod (PK)** · gosterim · **malzeme** · adet · izleme · raf · ts · **ts_guncelle** · oturum |

### Bilinmesi gerekenler

* **`fazla` diye tablo yoktur.** Fazla, `okutma.tip` değeridir.
  `okutma.tip` **dört** değer alır: `eslesti`, `kod`, `fazla`, **`yedek`**.
  (`bilinmiyor` üç ayrı sorguda filtreleniyordu ama prototip dahil hiçbir
  sürüm onu yazmamıştı — 2026-08-26'da kaldırıldı.)
  `yedek` 2026-08-27'de eklendi (yedek parça modu). Mevcut sorguların hepsi
  **olumlu** filtre kullandığı için (`tip='fazla'`, `tip IN ('eslesti','kod')`)
  kendiliğinden dışarıda kalıyor — `sayaclar`, `esleme_verisi`,
  `adsiz_fazlalar`, `fotosuz_fazlalar`, `fazla_bagla`, `reports` Fazla/Eşleşen
  ve `db.bolunmus_fazlalari_birlestir`. **Yeni bir `tip` eklerken bu listeyi
  tek tek gözden geçirin**; olumsuz filtre (`tip<>'...'`) yazan ilk sorgu bu
  güvenceyi bozar. Kilidi `tests/test_yedek.py`.
* **`okutma.ham` grubun BÜTÜN barkodlarını taşır**, `" + "` ile birleşik.
  Bir grup bir üründür (CLAUDE.md §4.4). 2026-08-27'ye kadar `eslesti` ve
  `slot` dalları buraya tek değer yazıyordu ve okutulan fabrika barkodu
  kayıttan düşüyordu (saha bildirimi B1). `kuyruk_coz` / `kuyruk_fazla` zaten
  doğru yazıyordu — üç dal artık aynı sözleşmede.
* **`okutma.yeni_seri` HER YAZMADA açıkça doldurulur — NULL bırakılamaz.**
  NULL yalnızca "bu sütun eklenmeden önce yazılmış" demektir ve rapor orada
  eski kurala (`_yeni_seri(ham)`) düşer. `ham` artık malzeme kodunu da
  taşıdığı için o kural en uzun aday olarak MALZEME KODUNU seçebiliyor:
  gerçek veriyle üretildi (2026-08-27) —
  `900-5G144-2200-000 TD SYNNEX 8000USD 2 -> 900-5G144-2200-000`.
  Öneri yoksa **boş dize** yazılır. `okutma`'ya yazan sekiz yolun sekizi de
  sütunu doldurur; **yeni bir yazma yolu eklerken bunu da doldurun.**
  Değer seçimi: `eslesti` kaydı eşleştiren değeri önerir (kaydın mevcut
  serisiyle aynıysa boş), `kuyruk_coz` / `fazla_bagla` `_fazla_seri` ile
  malzeme kodunu eleyip `_yeni_seri` sırasını uygular, `adet` / `yedek` /
  `fazla` boş yazar.
* **Son savunma `reports`'ta:** önerilen değerin kendisi `kirli_mi` desenine
  uyuyorsa satır rapora GİRMEZ ve dipnotta sayılır. Bu ağ tam da yukarıdaki
  hatayı yakalamak için var; motor düzeltildi ama ağ duruyor.
* **`okutma.yeni_seri` Tiger'a önerilecek seri numarasıdır** ve `ham`'dan
  AYRIDIR. İkisi tek alanda durunca `ham`'a malzeme kodunu eklemek Tiger
  Düzeltme sekmesini bozuyordu: `_yeni_seri` en uzun adayı seçtiği için kodu
  seri no sanıp Tiger'a yazdırabilirdi (ACIL_PLAN §3'te kapatılan hata).
  Boşsa Tiger Düzeltme satırı **üretilmez** (`sn_yok` sözleşmesi). NULL ise
  sütun eklenmeden önce yazılmış eski satırdır; rapor orada `_yeni_seri(ham)`
  eski kuralına düşer.
* **`oturum.sabit_kod` kalıcıdır, `bekleyen_adet` değildir.** Kilit (I2) grup
  kapanınca tükenmez — açıkça kapatılır ya da oturumla biter. Kural budur:
  amaç aynı malzemeden art arda cihaz saymak.
* **`kuyruk.tur` iki değer alır:** `bilinmiyor` (ne seri ne kod tanındı — "bu
  hangi malzeme?") ve `fazla_onay` (malzeme tanındı, karşılığı bulunamadı —
  "gerçekten fazla mı?"). Fazla kaydı yalnızca `kuyruk_fazla()` ve `##FAZLA##`
  komutundan doğar; motor kendiliğinden fazla yazmaz.
* **Girilen adet grupla birlikte gider, ama KAYBOLMAZ.** Ürün tanınmazsa
  `bekleyen_adet` sıfırlanırken değeri `kuyruk.adet`'e taşınır; kayıt
  çözülünce oradan alınır. Sahada 150 girilip tanınmayan ürün fazla
  işaretlendiğinde rapora 1 yazılıyordu (bildirim 2026-08-27): dört yer birden
  adedi düşürüyordu — `grup_coz` kuyruk dalı (sütun yoktu), `kuyruk_fazla`
  (`miktar` sabit 1), `##FAZLA##` ve `##ATLA##` (hem sabit 1 hem adedi
  tüketmiyorlardı, yani 150 **sonraki ürüne sızıyordu**).
  `kuyruk_coz` adedi malzemenin izlemesine göre karara bağlar: lot /
  izlemesizde miktar olur, seri takiplide `adet_yersiz` ile bildirilir.
  Kilidi `tests/test_kuyruk_adet.py` (10 test, hepsi eski kodda düşüyor).
* **`oturum.bekleyen_adet` kalıcı bir ayar değildir.** Sıradaki grubun miktarını
  taşır (`##ADET-N##` / telefon Adet paneli) ve grup kapanınca — ya da
  `##IPTAL##` ile — sıfırlanır. Oturum ayarı gibi davranırsa 25 adet sonraki
  ürüne sızar.
* **`okutma.geri`, `##GERIAL##`'in sözleşmesidir.** Bir okutmanın KENDİ SATIRI
  DIŞINDA ne yarattığını JSON olarak tutar:
  `{"ogrenilen": ["198701689928"], "etiket": "DS-000045"}` (kap sayımında
  ayrıca `{"kutu": {"kod": ..., "onceki": {...}}}` — kabın okutmadan önceki
  hâli; yoksa reddedilen adet kayıtta taze görünmeye devam ederdi). Geri alma bunu
  okuyup `eslesme` kaydını siler ve etiket bağlamasını çözer
  (`etiketler.coz_bagla`, numara TÜKETİLMEZ — defter kaydı durur), kuyruk
  kaydını yeniden açar (`cozuldu=0`) ve silinen okutmaya bağlı fotoğrafın
  `okutma` alanını NULL'lar (kuyruk bağlantısı durur).
  **`eslesme` ya da `etiket` yazan yeni bir yol eklerseniz `geri`'yi de
  doldurun**, yoksa geri alma yarım kalır ve öğrenilen yanlış barkod Barkod
  Tablosu üzerinden Tiger'a taşınır.
  `kuyruk_coz` ve `kuyruk_fazla` da `geri`'ye kendi kuyruk id'lerini yazar,
  bu yüzden onlardan doğan okutmalar geri alınınca kayıt kuyruğa döner.
* **`sayim` diye tablo yoktur.** Sayaçlar `okutma` + `beklenen` üzerinden
  anlık hesaplanır (`matching.sayaclar()`).
* `beklenen.kod_n` / `seri_n` / `seri_n0` yükleme anında yazılır; motor
  Python'da tam tablo taramıyor, indeksli SQL kullanıyor. **`ORDER BY id` şart** —
  prototip satırları ekleme sırasında tarayıp ilk tutanı dönüyordu.
* `etiket.tur` gerçek değerleri **`malzeme`** ve **`seri`**'dir
  (`db.py`'deki `'raf' | 'birim'` yorumu eskidir).
* Fotoğraf veritabanında BLOB olarak durur, dosya sisteminde değil.
  `kuyruk_foto` hem kuyruk kaydına (`kuyruk`) hem fazla okutmasına (`okutma`)
  bağlanabilir; ikisi de nullable. Tablo adı korundu — `ADD COLUMN` göçüyle
  yeniden adlandırma yapılamıyor.
* İndeksler: `beklenen` × 5, `okutma` × 3, `kuyruk` × 1, `kuyruk_foto` × 2,
  `etiket` × 1.

### Göç (yeni sütun eklemek)

`db.py:goc()` her bağlantı açılışında çalışır: `PRAGMA table_info` ile bakar,
sütun yoksa `ALTER TABLE ... ADD COLUMN` eder.

**Yeni sütun iki yere birden yazılır:**
1. `SEMA` içindeki `CREATE TABLE` gövdesine — yeni veritabanları için
2. `EK_SUTUNLAR` listesine `(tablo, sutun, tur)` — mevcut veritabanları için

Yalnızca `ADD COLUMN` desteklenir, yani sütun **nullable ya da DEFAULT'lu**
olmalı. Sütun silme, yeniden adlandırma, tip değiştirme desteklenmez.

**TUZAK — yeni sütuna indeks:** `CREATE INDEX`'i `SEMA`'ya YAZMAYIN, `EK_INDEKS`
listesine yazın. `baglan()` önce `SEMA`'yı, sonra `goc()`'u çalıştırır; mevcut
bir veritabanında `CREATE TABLE IF NOT EXISTS` boşa geçer (tablo eski hâliyle
durur) ve hemen ardındaki indeks henüz olmayan sütunu isteyip
`no such column` ile **tüm `executescript`'i düşürür** — `goc()` hiç çalışamaz,
uygulama açılmaz. `EK_INDEKS` göçten sonra uygulanır. Bu gerçekten yaşandı
(`ix_foto_ok`, 2026-08-22); regresyonu `tests/test_goc.py`'de.

### Veri onarımı (şema değil, içerik)

`goc()` yalnızca **sütun** ekler. Hatalı kodun ürettiği **veriyi** düzeltmek
ayrı bir iştir; `baglan()` bunun için `bolunmus_fazlalari_birlestir()` çağırır.

İki onarım var.

`lic_kuralini_duzelt()` — fazla geniş `LIC` hariç kuralını `LICENSE` ile
değiştirir ve hariç bayraklarını tüm yüklemelerde yeniden hesaplar.
`kurallari_tohumla()` yalnızca tablo boşken çalıştığı için varsayılan listesini
düzeltmek mevcut veritabanlarına ulaşmıyor. Yalnızca `varsayilan=1` kurala
dokunur: kullanıcı deseni elle yazdıysa karar onundur.

`bolunmus_fazlalari_birlestir()` — 2026-08-23'e kadar bir gruptaki her barkod için ayrı bir
fazla satırı yazılıyordu (bkz. `CLAUDE.md` §4.4). Onarım aynı `(oturum, grup)`
içindeki `tip='fazla'` satırlarını tek satıra indirir — `ham` birleşir, `seri`
yeniden seçilir, fotoğraflar taşınır, fazlası silinir.

**Yeni onarım yazarken:** idempotent olmalı (her açılışta çalışıyor), yalnızca
kendi ürettiği hatayı hedeflemeli, ve **silme içeriyorsa testi şart** —
`tests/test_goc.py` bu onarımı üç açıdan kilitliyor (birleşme, idempotanlık,
doğru kayda dokunmama).

Göç yolunun kendi test dosyası var: **`tests/test_goc.py`** eski şemayla
kurulmuş bir dosyadan başlar. Diğer tüm testler sıfırdan veritabanı kurduğu
için göç yolunu hiç denemezler — yeni sütun eklerken oraya da bakın.

---

## 3. API uçları

Hepsi `/api` önekli. Bağlantı `routers/ortak.py:DB` bağımlılığıyla gelir
(istek başına bir bağlantı, çıkışta commit).

### Yükleme (`routers/yukleme.py`)

| Uç | Gövde / parametre | İş |
|---|---|---|
| `POST /yukleme` | multipart `dosya` | Tiger raporunu yükle |
| `GET /yukleme` | — | Yükleme listesi |
| `GET /yukleme/{id}/ozet` | — | Satır sayıları, istatistik |
| `GET /yukleme/{id}/kurallar` | — | Sayım dışı kurallar |
| `PUT /yukleme/{id}/kurallar` | kural listesi | Kuralları güncelle + yeniden uygula |
| `GET /yukleme/{id}/ambarlar` | — | Ambar listesi |

### Oturum ve sayım (`routers/oturum.py`)

| Uç | Gövde / parametre | İş |
|---|---|---|
| `POST /oturum` | `{yukleme, ambar}` | Aç (başka açık oturum varsa 409) |
| `GET /oturum/acik` | — | `durum()` ya da `null` |
| `GET /oturumlar` | — | Geçmiş |
| `GET /oturum/{id}/durum` | `?akis=40` | Sayaç + tampon + son akış |
| **`POST /oturum/{id}/okut`** | `{ham, zorla}` | **Tek giriş noktası** |
| `POST /oturum/{id}/gerial` | `{kapsam}` — `okutma` \| `grup` | Geri al |
| `PATCH /okutma/{id}` | `{ad?, not_?}` | Fazla kaydına ürün adı / not (kısmi) |
| **`DELETE /okutma/{id}`** | `{kapsam?}` — `grup` (varsayılan) \| `satir` | Akıştan sil (I1). Yan etkiler `_yan_etkileri_geri_al` ile geri alınır |
| `POST /oturum/{id}/sabit-kod` | `{kod}` — null kilidi açar | Malzeme kilidi (I2). İçeride `##KILIT-<kod>##` / `##KILITAC##` üretip `okut()`'a verir |
| `POST /oturum/{id}/yedek-parca` | `{acik}` | Yedek parça modu (I4), aynı desen |
| `POST /oturum/{id}/kutu-kapat` | — | Açık seri takipli kabı kapat (`##KUTUKAPAT##` ikizi) |
| `POST /oturum/{id}/say` | `{beklenen_id, ham?}` | Barkodsuz ürünü listeden seçerek say (I5) |
| `GET /oturum/{id}/esleme` | — | Sayım sonu: `{fazla, eksik}` |
| `POST /okutma/{id}/bagla` | `{beklenen_id}` | Fazlayı eksik kayda bağla |
| `POST /okutma/{id}/coz-ayir` | — | Eşleştirmeyi geri al |
| `POST /oturum/{id}/bitir` | `?zorla=` | Çözülmemiş kuyruk, **adsız fazla** veya fotoğrafsız fazla varsa 409 |
| `POST /oturum/{id}/raf` | `{raf, zorla}` | Adı `norm.raf_adi()` ile temizler, `##RAF-X##` üretip `okut()`'a verir. Temizlikten sonra boş kalırsa **400** |
| `POST /oturum/{id}/adet` | `{adet}` | İçeride `##ADET-N##` üretip `okut()`'a verir. 0 sıfırlar, öteki değerler EKLENİR. Telefondaki Adet paneli buraya gider |
| `GET /oturum/{id}/raflar` | — | Bu oturumda kullanılmış raflar |
| `GET /oturum/{id}/ara` | `?q=&limit=&offset=&sadece_acik=&kirli=&izleme=` | Malzeme arama / listeleme → `{satirlar, toplam}` |

> **Grup kapatma / komut barkodları için ayrı uç YOKTUR.** `##SONRAKI##`,
> `##IPTAL##`, `##GERIAL##`, `##FAZLA##`, `##ATLA##`, `##BITIR##`, `##RAF-X##`,
> `##ADET-N##`, `##KILIT##` / `##KILIT-<kod>##` / `##KILITAC##`,
> `##YEDEK##` / `##YEDEKKAPAT##`, `##KUTUKAPAT##`
> hepsi `POST /oturum/{id}/okut` gövdesindeki `ham` alanından geçer ve
> Raf adı `norm.raf_adi()`den geçer (`ÜST-1` -> `UST-1`): Code128 ASCII dışını
> taşımıyor ve **basılan değerle elle yazılan değer aynı olmalı**, yoksa iki
> ayrı raf oluşur. Barkod üretimi (`barkod.kart_html`, `barkod.raf_satirlari`)
> da aynı işlevi kullanır — normalizasyon tek kaynaktan.
>
> `matching.okut()` içinde `norm.komut_coz()` ile ayrıştırılır. Yeni bir komut
> eklemek = `norm.py` `KOMUT` sözlüğüne bir satır + `matching.okut()`'ta bir dal.

### Kuyruk ve fotoğraf (`routers/kuyruk.py`)

| Uç | Gövde / parametre | İş |
|---|---|---|
| `GET /oturum/{id}/kuyruk` | `?hepsi=false` | Kayıtlar; her satırda `fotolar` id listesi |
| `POST /kuyruk/{id}/coz` | `{beklenen_id}` | Malzemeye bağla, barkodları öğren |
| `POST /kuyruk/{id}/kutu` | `{malzeme?, adet?}` | **Kap kaydını çöz**: içeriği kalıcı yaz + (serisizse) say. Adet eksikse 400 `kap_adet_gerekli` |
| `PATCH /kuyruk/{id}` | `{not_?, beklet?, ad?, adet?}` | Kısmi güncelleme (biri diğerini silmez). `adet` kayıt çözülmeden düzeltilebilir |
| `DELETE /kuyruk/{id}` | `{ad?}` | **Fazla olarak kapatır** (`matching.kuyruk_fazla`). Kod bilinmiyorsa `ad` zorunlu → 400 `ad_gerekli` |
| `POST /kuyruk/{id}/foto` | multipart `dosya` | Maks 6 MB · jpeg/png/webp |
| `POST /okutma/{id}/foto` | multipart `dosya` | Fazla kaydının fotoğrafı (aynı sınırlar) |
| `GET /foto/{id}` | — | BLOB, `Cache-Control: max-age=86400` |
| `DELETE /foto/{id}` | — | Sil |

### Rapor ve etiket

| Uç | İş |
|---|---|
| `GET /oturum/{id}/rapor/onizleme` | `reports.rapor_verisi()` — arayüz sekme önizlemesi |
| `GET /oturum/{id}/rapor.xlsx` | Excel indir |
| `POST /komut-karti` | Code128 komut kartı (HTML, laminat) |
| `POST /raf-etiketi` | Raf konum barkodları — yapışkanlı 24'lük A4 sayfa (HTML). Defter kalemi değil, `barkod.raf_satirlari()` → `etiket_html()` |
| `GET /etiket/ihtiyac` | Etiket ihtiyacı **üst sınırı** (hedef değil) |
| `POST /etiket/basim` | Parti bas, HTML sayfa + defter + CSV |
| `GET /etiket` · `GET /etiket/basimlar` | Defter ve partiler |
| `GET /kutu` · `GET /kutu/{kod}` | Kap defteri / tek kap. Liste BASILMIŞ kaplardan türer (`etiket LEFT JOIN kutu`) — `kutu` satırı ilk tanımlamada doğduğu için yalnızca ona bakmak yeni basılmış kapları görünmez yapardı. Tek kap ucu tazelik kararını da verir (`gorunum`) |
| `POST /kutu/{kod}` | `{malzeme, adet?, yukleme, ambar}` — içeriği yaz. İzleme **malzemeden kopyalanır**, sorulmaz. Malzeme bu ambarda yoksa 400 |
| `DELETE /kutu/{kod}` | Kap boşaldı: içerik bağı silinir, **numara kalır** |

### Altyapı (`main.py`)

| Uç | İş |
|---|---|
| `GET /api/olaylar` | SSE kanalı |
| `GET /api/ag` | Bu makinenin ağ adresleri (telefon için) |
| `GET /api/telefon-qr.svg` | QR (segno yoksa 501 — arayüz adresi yazıyla gösterir) |
| `GET /api/saglik` | Sağlık ve sayılar |
| `GET /{yol}` | SPA fallback; `index.html` **`Cache-Control: no-store`**. Yol `realpath` ile `app/static` altında kalmaya zorlanır — bkz. aşağıdaki uyarı |

---

## 4. Eşleştirme motoru

### `coz(c, ham, yukleme, ambar, oturum)` — tekil okutma

İlk tutan kazanır, hepsi `ORDER BY id LIMIT 1`.

| # | Koşul | Dönen `t` |
|---|---|---|
| 0 | `norm(ham)` boş | `bos` |
| 1 | `beklenen.seri_n = n` | `seri` / `tekrar` |
| 1b | 1 boş **ve** `n` tamamen rakam, `seri_n0 = sifirsiz(n)` | `seri` / `tekrar` |
| 1c | `etiket.kod=n AND tur='seri'` | bağlıysa `seri`/`tekrar`, boşsa **`etiket_bos`** |
| 1d | `n` DK- deseni (kap etiketi) | tanımlı `kutu` · tanımsız **`kutu_bos`** · malzemesi bu ambarda yok **`kutu_yabanci`** |
| 2 | `beklenen.kod_n = n` | `kod` |
| 3 | `len(n)>=8`, iki yönlü önek eşleşmesi (her iki taraf en az 8) | `kod` |
| 4 | `eslesme.barkod = n` (öğrenilmiş) | `ogrenilmis` |
| 5 | `len(n)>=6`, kirli seri kaydının **içine gömülü** ve bu oturumda sayılmamış | `seri` |
| 6/7 | hiçbiri | `upc` ya da `bilinmiyor` |

`tekrar` = o `beklenen` satırının **kapasitesi bitmiş** (`kapasite_kaldi()`):
seri takiplide "bu oturumda zaten okutulmuş", lot/izlemesizde
"sayılan >= beklenen". Tek satır çok adet taşıdığı için lot satırı bir
okutmayla kapanmaz — 77 adetlik lot 77 okutma kabul eder. Ölçüt tek yerde
durur; `ara(sadece_acik=True)` ve `kuyruk_coz()` de aynı işlevi kullanır.

**`coz()` asla "fazla" döndürmez** — fazla kararı yalnızca `grup_coz()`'da alınır.

### `grup_coz(c, ot, raf)` — `##SONRAKI##`

Tampondaki barkodların hepsi **tek ürün** kabul edilir.

```
YEDEK PARÇA MODU açık                    -> tip="yedek"    (coz() HİÇ çağrılmaz)
tekrar var, seri yok                     -> tip="tekrar"   (hiçbir şey yazılmaz)
kaynak SAYIM DIŞI kalem                  -> tip="haric"    (hiçbir şey yazılmaz)
KAP okutuldu (bkz. aşağıdaki kap dalı)   -> tip="kutu_*"   (kap kodu = malzeme kodu)
seri de kod da tanınmadı                 -> tip="kuyruk"   (kullanıcıya sorulur)
izleme='seri' satırı eşleşti             -> tip="eslesti"  (+ bilinmeyenler öğrenilir)
kod tanındı (ya da lot satırı eşleşti):
  izleme='seri', açık KİRLİ slot var     -> tip="slot"     (Tiger düzeltmesi *)
  izleme='seri', slot yok                -> tip="onay"     (*)
  izleme='lot' | 'yok'                   -> tip="adet"     (adet +1)
```

**Yedek parça modu her şeyden önce gelir** (I4): tampon boşaltılır, tek satır
`tip='yedek'` yazılır, `coz()` hiç çağrılmaz. Öğrenme ve kuyruk yoktur — yedek
parçalar Tiger'da kayıtlı değil ve aranmaları yalnızca yanlış eşleşme
üretiyordu.

**Kap kodu, malzeme kodu okutmakla AYNI ŞEYDİR** (`KUTU_TASARIM.md`). Kap
malzemeyi, izleme yöntemini ve son bilinen adedi getirir; sayımın kendisi
mevcut dallardan geçer (slot / adet / onay). Ayrı bir sayım yolu yazılmadı —
olsaydı `_adet_dagit` gibi kurallar iki yerde ayrı ayrı düzeltilirdi. Tek fark
kabın TEK BAŞINA ne anlama geldiğidir:

```
kap tanımsız / malzemesi bu ambarda yok  -> tip="kutu_tanimsiz" | "kutu_yabanci"
                                            (kuyruk tur='kutu', hiçbir şey sayılmaz)
kap tanımlı, izleme='seri', yalnız kap   -> tip="kutu_acildi" (SATIR YAZILMAZ)
                                            malzeme kilitlenir, sayaç başlar
kap tanımlı, izleme='seri', S/N de var   -> normal seri dalı + kap AÇILIR
kap tanımlı, lot/yok, ##ADET-N## var     -> tip="adet"  + kap kaydı tazelenir
kap tanımlı, lot/yok, adet YOK           -> tip="kutu_sor" (kuyruk tur='kutu')
```

**Seri takipli kapta kap AÇILIR** (`_kutu_ac`): `oturum.sabit_kod` kabın
malzemesine kurulur (elle `##KILIT##` gerekmez) ve `acik_kutu_ilk` o anki en
büyük okutma id'sine yazılır — sayaç ("150'nin 12'si") o işaretten sonraki
okutmaları sayar. Zaman damgası değil id: aynı saniyede iki okutma olabilir,
aynı id olamaz. İki kap aynı anda açık olamaz; yeni kap öncekini kapatır.
`##KUTUKAPAT##` (`_kutu_kapat`) kilidi bırakır, kabın son bilinen adedini
sayılana göre tazeler (sayılan 0 ise DOKUNMAZ — yanlışlıkla açılıp kapatılan
kap ipucunu kaybetmesin) ve eksik kaldıysa **uyarır, engellemez**.

Kap üç yoldan daha kapanır ve üçü de sessiz kalmaz: **başka bir kap açılınca**
(özet yanıtta döner), **`##KILITAC##` ile** (kilit kabın kilidiydi; yalnız
kilidi açmak sayacı dondururdu) ve **oturum biterken** — sonuncusu
`oturumlar.bitir()` içinde, iki `##BITIR##` yolunun (komut barkodu ve `/bitir`
ucu) birleştiği tek yerde.

**Kap kaydındaki adet sorusuz uygulanmaz.** Saha cevabı: içerik ayda bir
değişiyor, sayım yılda bir yapılıyor — yani kayıttaki adet sayım anında
neredeyse her zaman bayattır. Sorusuz uygulamak, uygulamanın kendi bayat
verisini sayım sonucu diye onaylaması olurdu (CLAUDE.md §6'daki "Sayım
Miktarı" tuzağının bizim tarafımızdaki hâli). `kutu.TAZELIK_GUN` (30) içindeki
kayıt arayüze **öneri** olarak gelir (`oneri_adet`), eskisi **boş** gelir.

**Kap kodu `eslesme`'ye HİÇ girmez** (`etiketler.ogrenilebilir()` eler): kap bir
malzeme değil, malzemenin durduğu yerdir. Öğrenilseydi 4. adım onu kalıcı bir
malzeme barkodu sayar, Barkod Tablosu sekmesi Tiger'ın malzeme kartına
yazdırır ve kap ertesi ay başka bir ürünle dolduğunda yanlış eşleşme kalıcı
olurdu. `reports._yeni_seri` de kap kodunu seri numarası adayı saymaz.

**Aynı kap iki kez okutulursa ikinci kuyruk kaydı AÇILMAZ**
(`_acik_kutu_kuyrugu`): kullanıcı "kaç adet?" sorusunu görüp `##ADET-130##`
okutur ve kabı yeniden okutur — ilk kayıt açık kalsaydı, cevabı çoktan verilmiş
bir soru oturumun kapanmasını engellerdi. Sayım gerçekleşince o kaba ait açık
soru kapanır (`_kutu_kuyrugu_kapat`).

**Sabit kod kilidi `kod_h`'nin yedeğidir** (I2): grupta malzeme kodu YOKSA ve
`oturum.sabit_kod` doluysa kilit devreye girer. Elle okutulan kod her zaman
kilidi yener — yoksa kullanıcı kilidi açmadan başka bir ürünü sayamazdı.

**Seri dalına yalnızca `izleme='seri'` satırları girer.** Lot numarası birebir
eşleşse bile (1. adım) adet dalına düşer: seri dalı `miktar=1` yazıp satırı
kapatır, lot satırı ise tek satırda çok adet taşır. Bu ayrım olmadan 77 adetlik
lot bir okutmada "sayıldı" olup ikinci okutmada `tekrar` diyordu.

Adet dalında **hangi satır(lar)a yazıldığı** önemlidir (`_adet_dagit()`): lot
numarası okutulduysa miktarın tamamı o satıra, yalnızca malzeme kodu biliniyorsa
**kapasitesi kalan satırlara sırayla dağıtılır**. Bir malzemenin birden çok lotu
olabilir (örnek veride bir malzeme tek başına 57 lot satırı taşıyor); hep ilk
satıra yazmak o lotu şişirip ötekileri eksik bırakıyordu.

Miktar `oturum.bekleyen_adet`'ten gelir (`##ADET-N##` / telefon Adet paneli),
verilmemişse 1. Grup kapanınca tüketilir. Seri takipli kalemde uygulanmaz ama
sessizce yutulmaz — yanıtta `adet_yersiz` döner.

> **UYARI — statik servis kök dışına çıkmamalı.** `os.path.join(STATIK, yol)` +
> `isfile` yeterli DEĞİLDİ: `..` normalize edilmiyordu. Tarayıcı düz `../`
> yolunu düzeltiyor ama yüzde-kodlanmışını düzeltmiyor, sunucu da hiç
> düzeltmiyordu — `GET /..%2f..%2fdata%2fsayim.db` canlı sayım veritabanını,
> `/..%2f..%2fdeneme.XLSX` stok ve tutarları döndürüyordu. Sunucu
> `--host 0.0.0.0` ile açık ve kimlik doğrulaması yok (`baslat.bat`), yani depo
> Wi-Fi'sındaki herkes indirebiliyordu. Artık `realpath` ile hem `..` hem
> sembolik bağlantı çözülüp kökün altında kalıp kalmadığına bakılıyor.
> Regresyonu `tests/test_servis.py`'de.

(*) Slot dolduruluyorsa `okutma.ham` alanına Tiger'a önerilecek YENİ seri
numarası yazılır. Aday yoksa (ne üretici S/N ne DS- etiketi okutuldu) alan
**boş bırakılır** ve `sn_yok=True` döner: sayım işlenir, Tiger Düzeltme satırı
üretilmez, kullanıcı uyarılır. Eskiden oraya MALZEME KODU yazılıyordu ve
Tiger'a "bu cihazın seri numarası 04RW5H olsun" deniyordu —
`kirli_mi(kod, kod)` kirli döndüğü için düzeltme kendi kendini bozuyordu.

(*) `kuyruk` tablosuna `tur='fazla_onay'` ile yazılır. **Motor kendiliğinden
fazla yazmaz** — eski davranış sessizce fazla yazıyordu ve sahada yanlış çıktı
(`DEMO_FEEDBACK.md` §5). Bu dala düşmek "stokta yok" demek değil, "Tiger'daki
seri numaralarıyla eşleşmedi" demektir.

Bilinmeyen barkodlar tanınan malzemeye bağlanıp `eslesme`'ye yazılır —
**öğrenme döngüsü budur.** Boş seri etiketi bilerek öğrenilmez (tekil cihaza
özgü numara malzeme seviyesine yükselmemeli).

### `okut(c, ot, ham, zorla)` — tek giriş noktası

Komut barkodu mu diye bakar; değilse `tampon`'a yazıp anlık çözümlemeyi döner.
İki kapı, `zorla=True` ile bilinçli aşılır:
* **raf kapısı** — o rafta çözülmemiş kuyruk varsa raf değiştirilemez
  (`beklet=1` işaretliler sayılmaz)
* **bitir kapısı** — çözülmemiş kuyruk varsa oturum kapatılamaz
  (`beklet` dahil hepsi sayılır)

### Diğer

* `kuyruk_coz(c, kuyruk_id, beklenen_id)` — grubu malzemeye bağlar, barkodları
  kalıcı öğretir, `tip='eslesti'` yazar.
* `kutu_coz(c, kuyruk_id, malzeme=None, adet=None)` — kap kaydının cevabı.
  İki şeyi birden yapar ve ikisi ayrı ömürlüdür: kabın içeriği `kutu`
  tablosuna **kalıcı** yazılır, sayım bu **oturuma** işlenir. Seri takipli
  malzemede sayım yapılmaz (`sayildi=False`) — her adet Tiger'da ayrı satır;
  kap tanımlanır, cihazlar tek tek okutulur. Sayım `_adet_islemi()` ile
  `grup_coz` ile aynı koddan geçer.
* `_adet_islemi(...)` — lot/izlemesiz miktarı doğru satır(lar)a yazan ORTAK
  gövde (`grup_coz` adet dalı + `kutu_coz`). `_adet_dagit` kuralı tek yerde
  dursun diye ayrıldı.
* `kuyruk_fazla(c, kuyruk_id, ad=None)` — kaydı fazla olarak kapatır. Malzeme
  kodu bilinmiyorsa `ad` **zorunlu**; yoksa `{"hata": "ad_gerekli"}` döner ve
  kayıt oluşmaz. `fazla_onay`
  kaydında **tek** okutma satırı yazılır (grup tek üründür, barkod başına satır
  yazılsaydı raporda iki fazla görünürdü) ve malzeme kodu korunur;
  `bilinmiyor` kaydında barkod başına bir satır yazılır.
* `ara(c, yukleme, ambar, q, limit, offset, oturum, sadece_acik, kirli, izleme, raf)`
  — kod / açıklama / seri araması ve listeleme. `q` boşken de çalışır.
  `{satirlar, toplam}` döner; her satırda `sayildi` ve `ayni_raf` bayrağı.
  `haric=1` kalemler hiç görünmez (fiziksel nesne değiller, bağlanacak hedef
  de değiller). Sıralama: aynı rafta sayılmış → sayılmamış → kirli → id.
  **"Bu olabilir" aday önerisi (`adaylar`, `_adayli`, `/adaylar` ucu) tamamen
  kaldırıldı** — sahada doğru sonuç vermiyordu (`DEMO_FEEDBACK.md` §4).
  **Gruplama istemcide** (`web/src/GrupluListe.tsx` + `liste.grupla`): aynı
  kodun 21 seri satırı listede tek malzeme satırına iner, yanında kaç açık
  kayıt kaldığını gösteren sayaç durur, satıra basınca seriler açılır. Sunucu
  yine düz satır döner; `sadece_acik` sayesinde sayılan/eşleşen kayıt hiç
  gelmez, kayıt çözülünce liste tazelenir ve sayaç düşer.
* `okutma_sil(c, ot, okutma_id, kapsam="grup")` — akıştan silme (I1).
  `gerial`den farkı: o yalnızca SONUNCUYU alır. Varsayılan kapsam **grup**,
  çünkü `adet` dalı bir grubu birden çok satıra yazabilir ve `geri` yalnızca
  ilkinde durur. Yan etkiler `_yan_etkileri_geri_al` ile geri alınır — ayrı
  temizleme kodu YOKTUR.
* `elle_say(c, ot, beklenen_id, ham=None)` — barkodsuz ürün (I5).
  `kuyruk_coz` ile aynı iki kural: dolu kayda bağlanmaz (`kapasite_kaldi`),
  yazılan değer öğrenilir ama DS- seri etiketi öğrenilmez.
* `fazla_bagla(c, okutma_id, beklenen_id)` — sayım sonu eşleştirmesi: fazla
  satırını `eslesti` yapar, barkodları öğretir. Zaten sayılmış kayda bağlamayı
  reddeder (çift sayım olurdu). `fazla_coz_ayir()` geri alır.
* `esleme_verisi(c, ot)` — solda fazlalar, sağda eksikler. Eksik listesi
  `reports.eksik_kayitlar()`'tan gelir; **ekran ile rapor aynı satırları
  göstermeli.**
* `adsiz_fazlalar(c, oturum)` — bitirme kapısı. Malzeme kodu **olmayan** ve
  adı yazılmamış fazla kayıtları. Kodu olanda rapor açıklamayı `beklenen`
  tablosundan çekebiliyor; olmayanda geriye seri numarası ve raf kalıyor.
* `fotosuz_fazlalar(c, oturum)` — bitirme kapısı. Fazla, sayım bittikten sonra
  kimsenin doğrulayamayacağı tek çıktıdır: ürün rafa geri konur, geriye yalnızca
  bir satır kalır.
* `sayaclar(c, ot)` — okutulan / kalan / fazla / kuyruk / toplam.
* `durum(c, ot, akis)` — sayım ekranının tek çağrıda ihtiyacı olan her şey.
  Akış satırları `id` ve `grup` taşır (satır bazlı silme için şart);
  `sabit_kod` / `sabit_aciklama` / `yedek_parca` da buradan gelir — ikisi de
  ekranda **görünmek zorunda**, açık unutulursa bütün raf yanlış malzemeye ya
  da yedek parçaya yazılır.

---

## 5. Canlı güncelleme (SSE)

* Yayın: `olaylar.bildir(istemci)` global sürüm sayacını artırır.
* **Tetikleyici `main.py`'deki `degisikligi_yayinla` middleware'i** — her
  başarılı `POST/PUT/PATCH/DELETE` sonrası otomatik çağırır. Yani **yeni bir
  yazma ucu eklemek canlı güncellemeyi kendiliğinden çalıştırır**, uca kod
  eklemeye gerek yoktur.
* Kanal: `GET /api/olaylar`, `text/event-stream`, `X-Accel-Buffering: no`.
* **Tek olay tipi: `guncel`**, gövdesi `{"surum": n, "istemci": "..."}` — kasten
  içeriksiz: "bir şey değişti", istemci veriyi kendi çeker. Ayrıca `: bagli` ve
  10 sn'de bir `: kalp` yorum satırı.
* İstemci (`web/src/olaylar.ts`) üç katman: EventSource, `visibilitychange`
  tazelemesi, yedek yoklama (kopukken 3 sn, canlıyken 15 sn). Kendi
  `X-Istemci` kimliğinden gelen olayı yok sayar.
* Yeni olay **tipi** eklemek pahalıdır: tasarım tek sürüm numarasına dayanıyor,
  tip başına ayrı sayaç ve `gorulen` takibi gerekir. Neredeyse her zaman doğru
  cevap "olay ekleme, istemci veriyi çeksin".

---

## 6. Arayüz

### Yönlendirme

**React Router yok.** İki mekanizma:

1. `App.tsx`: `window.location.pathname === "/telefon"` ise `TELEFON_MODU`.
   Sunucu tarafında SPA fallback karşılar (`main.py` `TELEFON_YOLU`).
2. Diğer her şey tek `useState<Ekran>` + koşullu render. **URL değişmez, geri
   tuşu çalışmaz.**

`uzaktan` bayrağı ayrı bir kavramdır: PC arayüzü telefonda açılınca barkod
alanının odaklanmasını engeller. `/telefon` rotasıyla ilgisi yoktur.

### Ekranlar (9)

| Ekran | Dosya | İş | Nerede |
|---|---|---|---|
| Kurulum | `ekranlar/Kurulum.tsx` | Excel yükle, kurallar, ambar seç, oturum aç | PC |
| Sayım | `ekranlar/Sayim.tsx` | Barkod girişi, tampon, akış | PC |
| Kuyruk | `ekranlar/Kuyruk.tsx` | Tanınmayanları rafa göre çöz; **kap kaydında malzeme + adet paneli** | PC |
| Rapor | `ekranlar/Rapor.tsx` | 7 sekme önizleme, xlsx, oturumu bitir. **`SEKME` listesi `reports.SEKME`'nin kopyasıdır** — sekme eklerken ikisi de güncellenir | PC |
| Geçmiş | `ekranlar/Gecmis.tsx` | Eski oturumlar, rapor indirme | PC |
| Ayarlar | `ekranlar/Ayarlar.tsx` | Aktif raf, kurallar, ses, cihaz modu | PC |
| Barkod | `ekranlar/Etiket.tsx` | **Basılan her şey**: DM / DS / DK etiketleri, raf konum barkodları, komut kartı, etiket defteri, **kap defteri** (hangi kapta ne var + tazelik + Boşalt). **Açık oturum İSTEMEZ** — yalnızca "ambardaki malzemelerin etiketi" yükleme ister, ekran bunu söyler | PC |
| Eşleştirme | `ekranlar/Esleme.tsx` | Sayım sonu: fazla ↔ eksik elle eşleştirme, fazla fotoğrafı | PC |
| Telefon | `ekranlar/Telefon.tsx` | Monitör + uzaktan kumanda + kuyruk çözme | `/telefon` |

Üst menüdeki **Barkod** düğmesi her zaman görünür (2026-08-27): sayıma
çıkmadan komut kartı ve raf barkodu basmak gerekiyor, çoğu zaman Tiger raporu
daha alınmamış oluyor. Raf ve komut barkodları Geçmiş ekranından buraya
taşındı — ikisi de basılan kâğıt, oturumla ilgileri yok.

**Telefon modunda iç yönlendirme yoktur** — `App.tsx` tek bileşen render eder,
nav yoktur. Telefona sekme gerekirse önce orada bir `useState` açılmalıdır.

### Telefon kumandası

Okuyucu laptopta kalır; telefon komutları `api.okut` ile gönderir (komutlar
zaten `POST /okut` gövdesinden geçtiği için yeni uç gerekmedi).

| Yer | Eylem |
|---|---|
| Sabit alt çubuk | **Sıradaki ürün** (`##SONRAKI##`) · **Geri al** (`##GERIAL##`) |
| Sayaçların altındaki satır | Raf (`##RAF-X##`) · Adet · İptal · Atla · Fazla |

`raf_engel` yanıtı telefonda da onay sorup `zorla:true` ile tekrar gönderir.
`##BITIR##` telefonda **bilerek yoktur.** Alt çubuk `fixed` olduğu için kabuk
`pb-28` taşır ve `env(safe-area-inset-bottom)` kullanır.

### Sayım ekranında eylemler

Üç yol: (1) komut barkodu, (2) klavye kısayolu — `F2` sonraki, `F3` fazla,
`F4` atla, `Esc` iptal, `F10` bitir, `Ctrl+Z` geri al; aday seçimi `Alt+1..5`,
(3) ekran düğmesi — yalnızca **uzaktan modda** iki tane. Okutmalar tek promise
zincirine dizilir ki `##SONRAKI##` okunan barkodun önüne geçmesin.

### Yeni ekran eklemek

1. `web/src/ekranlar/Yeni.tsx`
2. `App.tsx` içinde dört nokta: `type Ekran` birliği, import, nav düğmesi,
   render bloğu (gerekirse `Sayim.tsx`'in `git` prop tipine de)
3. API ucu gerekiyorsa `api.ts`'e bir satır

### Tasarım kuralları

**Flat Design + Minimalism & Swiss, açık tema** (2026-08-23). Gölge yok,
gradyan yok, cam yok, hap yok; yarıçap her yerde 2px, yüzeyler kenarlıkla
ayrılır. Palet ve jeton tablosu `CLAUDE.md` §10.2'de.

Tek stil kaynağı `web/src/stil.css`'teki Tailwind v4 `@theme` bloğu —
`tailwind.config` yok. `.cam` / `.cam-hafif` / `.cam-yogun` sınıfları kaldırıldı;
yüzey için `border border-cizgi bg-panel` yazılır. `Zemin.tsx` (ızgara + parallax
+ parıltı) silindi.

Görsel yönden bağımsız olarak geçerli kalan kısıtlar `CLAUDE.md` §10.1'de.
Kısaca: **emoji yasak** (`ikonlar.tsx` kullan), sayaçlarda `.rakam`
(`tabular-nums`) şart, barkod/seri mono yazı tipinde, dokunma hedefi en az
48 px, renk tek başına bilgi taşımaz, CDN yok (fontlar `web/src/fonts/` altında
self-host) ve font **latin-ext subset'i içermeli** — yoksa `ğ Ğ ş Ş İ` bozulur.

---

## 7. Test paketi

`.\.venv\Scripts\python -m pytest -q` ile **409 test**. `pytest.ini` yok,
`sys.path` `tests/conftest.py` içinde elle ayarlanıyor.

| Dosya | Kapsam |
|---|---|
| `test_api.py` | FastAPI uçtan uca (TestClient) |
| `test_etiket.py` | DM-/DS- etiketleri: basım, defter, bağlama, CSV geri yükleme |
| `test_kutu.py` | DK- kap etiketi: tanımsız kap kuyruğu, tazelik kuralı, seri takipli kapta sayım YAPILMAMASI, geri alma, CSV defteri, uçlar |
| `test_genel_rapor.py` | Yükleyici `deneme.XLSX`'e bağımlı değil (sentetik Excel) |
| `test_goc.py` | **Eski şemalı veritabanının göçü** — `deneme.XLSX` gerektirmez |
| `test_haric.py` | Sayım dışı kalem kuralları |
| `test_importer.py` | `deneme.XLSX` Ambar 1 üzerinde doğrulanmış rakamlar |
| `test_kuyruk_akisi.py` | Raf/bitir kapıları, arama/filtreleme, not, fotoğraf |
| `test_norm.py` | `norm` / `upc_mi` / `kirli_mi` regresyonu |
| `test_olaylar.py` | SSE akışı |
| `test_rapor.py` | Rapor sekmeleri |
| `test_senaryolar.py` | `CLAUDE.md` §8'deki saha senaryoları |
| `test_b1_barkod.py` | **B1**: grup barkodları `ham`'da hayatta kalıyor, malzeme kodu Tiger'a seri no diye yazılmıyor |
| `test_silme.py` | **I1**: akıştan silme, yan etkilerin geri alınması, grup kapsamı |
| `test_sabit_kod.py` | **I2**: malzeme kilidi — kilitliyken slot dolar, kilitsizken kuyruğa düşer |
| `test_yedek.py` | **I4**: `tip='yedek'` hiçbir mevcut sorguya sızmıyor, kendi sekmesinde çıkıyor |
| `test_elle_giris.py` | **I5**: listeden seçerek sayma, öğrenme, çift bağlama koruması |
| `test_kuyruk_adet.py` | Tanınmayan üründe girilen adedin kaybolmaması ve sonraki ürüne sızmaması |

Denetimden çıkanlar (2026-08-27, kendi değişikliklerimin gözden geçirmesi):
`eslesti` dalı `yeni_seri`'yi NULL bırakıp malzeme kodunu Tiger'a önerdiriyordu
(gerçek veriyle üretildi); `kuyruk_coz` ve `fazla_bagla` aynı sınıftan
**önceden var olan** bir hataya sahipti (malzeme kodunu elemiyorlardı);
yedek satırları akış listesinde yeşil (= "eşleşti") görünüyordu; `elle_say`
DS- etiketini bağlamıyordu; yedek parça modunda `##FAZLA##` / `##ATLA##` modu
sessizce deliyordu. Hepsi düzeltildi ve testle kilitlendi.

**Fixture'lar (`conftest.py`):** `sablon` (session, XLSX bir kez yüklenir) ·
`c` (şablonun kopyası, her test izole) · `ot` (Ambar 1'de açık oturum) ·
`yaz` (barkod dizisini sırayla okutur) · `oturum_taze` (aktif_raf değişince
oturum satırını tazeler).

`conftest.py` **`deneme.XLSX` yoksa paketin tamamını atlar** — dosya gerçek
stok ve tutar içerdiği için `.gitignore`'da.

**Frontend testi yoktur.** `web/package.json` script'leri yalnızca `dev`,
`build` (`tsc -b && vite build`), `preview`.

---

## 8. Değiştirilmemesi gereken davranışlar

* `norm.py`'nin tamamı ve `coz()` adım sırası sahada gerçek veriyle doğrulandı
  (`CLAUDE.md` §4.1–4.3). `matching.py` docstring'i "prototipten birebir
  taşındı, değiştirmeyin" der.
* `depo_sayim.py` ilk prototiptir ve **eşleştirme mantığının referansıdır**;
  `app/matching.py` ile davranışı aynı olmalıdır. Bilinçli sapmalar bu dosyaya
  yazılır — sessizce ayrılmasın.
* Etiket kodu **sabit 6 hane** olmalıdır: değişken uzunlukta bir kod diğerinin
  öneki olabilir ve `coz()` 3. adımı en az 8 karakterde önek eşleşmesi yapar.
* `.bat` dosyalarında çıplak ad kullanılmaz: `call "%~dp0kisayol.bat"`.
* `data/etiket` klasörü silinmez — basılmış fiziksel etiket veritabanından uzun
  ömürlüdür (`CLAUDE.md` §12.7).

---

## 9. Bilinen sapmalar / açık işler

* `depo_sayim_bugs_improvements.md` — **gerçek** sayım denemesinden çıkan
  1 bug + 5 feature. **Altısı da çözüldü** (2026-08-27), I3 dahil —
  `KUTU_TASARIM.md`. Seri takipli dal da yazıldı: kap okutunca otomatik kilit,
  "150'nin 12'si" sayacı ve `##KUTUKAPAT##`. **Hiçbiri gerçek sahada
  denenmedi**; kap akışının bekleyen sorusu artık "yazılsın mı" değil, "sahada
  hangisi hızlı" — I2 kilidi tek başına yetiyor mu, yoksa kap açılışı
  gerçekten zaman kazandırıyor mu.
* **Çok depo bir eksiklik değil, karar** (2026-08-27): uygulama sayılan
  ambarın dışına çıkmaz. Ayrıntı `CLAUDE.md` §3.5.

* `DEMO_FEEDBACK.md` — demo sayımından çıkan 1 bug + 5 feature.
  **Altısı da çözüldü** (2026-08-22): telefon kumandası, sıradaki/geri al, elle
  fazlada ürün adı, aday önerisinin kaldırılıp yerine arama/filtre gelmesi,
  sessiz otomatik fazlanın onay kuyruğuna çevrilmesi, sayım sonu eşleştirme
  ekranı + fotoğraf kapısı. **Hiçbiri gerçek sahada denenmedi.**
* `CLAUDE.md` §9'daki telefon doğrulama listesi hâlâ açık: sunucu tarafı ve
  derleme doğrulandı, **gerçek telefonda test edilmedi.**
* `CLAUDE.md` §12 etiketleri gerçek Tiger verisiyle doğrulandı ama **basılan
  sayfa gerçek barkod okuyucuyla test edilmedi.**
* `db.py`'deki `etiket.tur` yorumu düzeltildi: `malzeme` · `seri` · `kutu`.
* `okutma.tip='bilinmiyor'` raporlarda filtrelenir ama hiçbir yerde yazılmaz.
