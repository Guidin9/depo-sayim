# Acil Durum Planı — Depoya Gitmeden Önce

**Oluşturuldu:** 2026-08-26
**Kaynak:** dış göz kod incelemesi (`app/`, `web/`, gerçek `deneme.XLSX` verisiyle davranış sınaması)
**Durum:** tespit tamamlandı · **A grubu BİTTİ (A1-A6)** · sırada **B1**

Bu dosya bir çalışma listesidir. Her madde tek başına doğrulanmış bir hatadır;
hiçbiri tahmin değildir, hepsinin altında çalıştırılmış çıktı vardır.
Düzeltme bittikçe kutucuk işaretlenir ve "Doğrulandı" satırı doldurulur.

---

## 0. Tespit aşaması — TAMAMLANDI

- [x] Kod haritası çıkarıldı (`app/` 11 modül, `web/src/` 20 dosya, ~11.300 satır)
- [x] Test paketi çalıştırıldı — **203/203 geçiyor** (hataların hiçbirini test paketi yakalamıyor)
- [x] Eşleştirme motoru gerçek veriye karşı sınandı — `coz()` 1-5. adımları temiz:
      - önek çakışması (adım 3): **0 çift**
      - malzeme koduyla başlayan gerçek S/N: **0 satır**
      - aynı ambarda tekrarlanan `seri_n`: **0**
      - `seri_n` = başka bir malzemenin `kod_n`'i olan satır: **0**

      > Sonuç: çekirdek mantığa dokunulmayacak. Sorunlar kenarlarda.
- [x] Ambar 1 veri profili doğrulandı: 870 satır · seri 801 (394 kirli) · lot 69 satır / 271 adet
- [x] 8 hata + 4 küçük bulgu üretilebilir şekilde tekrarlandı

---

## 1. Lot kalemleri sayılamıyor — 271 adet (Ambar 1'in ~%25'i)

- [x] **Düzeltildi** (2026-08-26) — `app/matching.py`, `web/src/ekranlar/Sayim.tsx`, `web/src/api.ts`
- [x] Regresyon testi yazıldı — `tests/test_lot.py`, **19 test**
- [x] **Doğrulandı** (2026-08-26): ilk 8 testin **5'i düzeltmeden önceki kodda
      düşüyor** (`git stash` ile ayrıca sınandı), sonrasında hepsi geçiyor.
      Tüm paket **222/222**. `npm run build` (tsc dahil) temiz.
- [x] **Adet girişi eklendi** (2026-08-26) — komut barkodu VE telefon paneli

**Yer:** `app/matching.py:183` (`if tekrar and not seri_h`) ve `grup_coz` seri dalı (miktar sabit 1)

**Belirti**

```
0C5RNH / 0C5RNHLOT1221 / beklenen 77 adet
  1. okutma + SONRAKI  -> eslesti, miktar 1, satır "sayıldı" oldu
  2. okutma + SONRAKI  -> {'tip': 'tekrar'}          <- reddedildi, hiç işlenmedi
  rapor                -> "adet farkı — sayılan 1 / beklenen 77"
```

**Kök sebep**

Lot numarası `beklenen.seri` sütununda duruyor, bu yüzden `coz()` 1. adımda
birebir eşleşiyor ve `grup_coz` **seri dalına** giriyor. O dal `miktar=1` yazar
ve satırı kapatır. `_sayildi()` artık True olduğu için ikinci okutma `tekrar`.

`kapasite_kaldi()` lot için doğru kuralı biliyor (`sayılan < beklenen`) ama
`coz()` / `grup_coz` o kuralı hiç sormuyor — iki yerde iki ayrı gerçek var.

**Ek tutarsızlık:** aynı ürünün **malzeme kodunu** okutmak çalışıyor
(`adet` dalı, her SONRAKI'de +1: `1/77`, `2/77`, `3/77`). Yani lot barkodunu
okutan kullanıcı cezalandırılıyor.

**Eksik özellik:** CLAUDE.md §2.4 "lot okut, **adet gir**" diyor. "Adet gir"
tarafı ne API'de ne arayüzde var (`grep -rn "miktar" web/src/ekranlar/Sayim.tsx`
→ tek eşleşme, o da bir `case` etiketi).

### Yapılan (2026-08-26)

**1. `coz()` — `tekrar` kararı artık kapasiteye bakıyor** (`app/matching.py`, 1. ve 1c adımları)

`"t": "tekrar" if _sayildi(...)` → `"t": "seri" if kapasite_kaldi(...) else "tekrar"`.
Kural artık **tek yerde** (`kapasite_kaldi`); seri takipli satırda sonuç
aynı (`not _sayildi()`), lot satırında `sayılan < beklenen` oluyor.

**2. `grup_coz` — lot satırı seri dalına girmiyor**

Yeni `seri_kaydi` değişkeni: seri dalına (`miktar=1`, satırı kapat) yalnızca
`izleme='seri'` satırları giriyor. Lot numarası okutulmuş grup adet dalına
düşüyor — böylece §12.6'daki "lot malzemesinde boş etiket bağlanmaz" kuralı da
kendiliğinden korunuyor.

**3. Yeni `_adet_dagit()` — doğru lot satır(lar)ına yazılıyor**

Adet dalı `ORDER BY id LIMIT 1` ile hep ilk satıra yazıyordu. Örnek veride
`BRODCOM 57414` tek başına **57 ayrı lot satırı** taşıyor (her biri 1 adet);
malzeme kodu 5 kez okutulunca 5 adet birinci lota yığılıyor, o satır adet
fazlası veriyor, diğer 56 satır eksik çıkıyordu.

Artık: lot numarası okutulduysa **o satır**, yalnızca malzeme kodu biliniyorsa
**kapasitesi kalan satırlara sırayla dağıtım**. Açık satır kalmazsa artan miktar
son paya eklenir (sayım işlenir, adet fazlası olarak raporlanır — sessizce
kaybolmaz).

**4. Sayaç satır bazına indi**

`toplam` malzeme geneli yerine `beklenen_id` bazında hesaplanıyor; çok lotlu
malzemede "sayılan 12 / beklenen 1" gibi anlamsız oran çıkıyordu. Yanıta `seri`
(lot no) ve `izleme` eklendi, arayüz `Lot 0C5RNHLOT1221 · ...` diye gösteriyor.

### Doğrulama çıktısı

```
1 adetlik lot          -> 1. okutma adet, 2. okutma tekrar
BRODCOM 57414 x5       -> 5 FARKLI lot satırına dağıldı, adet fazlası yok
77'lik lot x77         -> 77/77, 78. okutma tekrar, Eksik'te YOK
seri takipli (regres.) -> 1. okutma eslesti, 2. okutma tekrar (değişmedi)
```

### Adet girişi (2026-08-26) — İKİSİ DE

Karar: komut barkodu **ve** telefon paneli. İkisi de tek koddan geçiyor
(`matching.okut` → `##ADET-N##`), böylece iki giriş yolu iki ayrı davranışa
ayrılamaz.

| Parça | Yer |
|---|---|
| `##ADET-N##` / `##ADET-0##` çözümlemesi | `app/norm.py` (`ADET_ONEK`, `ADET_TAVAN=9999`) |
| `oturum.bekleyen_adet` sütunu + göç | `app/db.py` (`SEMA` + `EK_SUTUNLAR`) |
| Komut işleme, tüketme, dağıtma | `app/matching.py` (`okut`, `grup_coz`, `_adet_dagit`) |
| Telefon ucu | `POST /api/oturum/{id}/adet` (`app/routers/oturum.py`) |
| Komut kartına adet barkodları | `app/barkod.py` (1/5/10/25/50/100 + SIFIRLA) |
| PC: bekleyen adet rozeti + sonuç şeridi | `web/src/ekranlar/Sayim.tsx` |
| Telefon: Adet paneli + başlık rozeti | `web/src/ekranlar/Telefon.tsx`, yeni `Ik.Katman` |

**Davranış kuralları** (hepsinin testi var):

- Adet **birikir** — `##ADET-25##` iki kez = 50. Kartta sabit değerler basılı,
  ara değere ancak böyle ulaşılır. `##ADET-0##` sıfırlar.
- Grup kapanınca (ya da `##IPTAL##` ile) **tükenir** — sonraki ürüne sızmaz.
- **Boş tamponda `##SONRAKI##` adedi YAKMAZ.** Yanlışlıkla F2'ye basmak girilen
  25 adedi silmemeli.
- Lot numarası okutulduysa miktarın tamamı **o satıra** yazılır (fazlalık adet
  fazlası olarak raporlanır, örtülmez). Yalnızca malzeme kodu biliniyorsa
  miktar **açık satırlara dağıtılır**.
- Seri takipli kalemde adet uygulanmaz ama **sessizce yutulmaz**: yanıtta
  `adet_yersiz` döner, arayüz "25 adet uygulanmadı, bu kalem seri takipli" der.
- `##ADET-ABC##` / `##ADET-99999##` komut sayılmaz, tampona düşer — sessizce
  0 adet saymaktansa kullanıcının gördüğü bir "bilinmiyor" daha iyi.

### Belgeler

- [x] `CLAUDE.md` §2.4 — çok lotlu malzeme kuralı ve `kapasite_kaldi` ölçütü
- [x] `CLAUDE.md` §4.5 — komut tablosuna `##ADET-N##` / `##ADET-0##`
- [x] `MIMARI.md` — şema (`oturum.bekleyen_adet`), API tablosu, motor dallanması

---

## 2. `##BITIR##` kendi kuyruk kapısını deliyor · öncelik **A2**

- [x] **Düzeltildi** (2026-08-26) — `app/matching.py`, `app/routers/oturum.py`
- [x] Regresyon testi yazıldı — `test_bitir_kapanmamis_grubu_da_gorur`,
      `test_bitir_kapanmamis_eslesen_grubu_kaybetmez`,
      `test_bitir_ucu_kapanmamis_grubu_da_gorur`
- [x] **Doğrulandı** (2026-08-26): üç test de eski kodda düşüyor
      (`git stash` ile sınandı). Tüm paket **231/231**.

**Yer:** `app/matching.py:361-377` **ve** `app/routers/oturum.py` `bitir()` — aynı hata iki yerde

**Belirti**

```
tanınmayan barkod okut, SONRAKI DEME, ##BITIR##
  -> {'tip': 'bitti'}
  -> oturum durumu: bitti
  -> çözülmemiş kuyruk: 1        <- kapı boşuna durdu
```

**Kök sebep**

Sıra yanlış: kuyruk kontrolü → adsız kontrolü → fotoğrafsız kontrolü →
**`grup_coz(c, ot)`** → oturumu kapat. `grup_coz` tampondaki tanınmayan grubu
yeni bir kuyruk kaydına yazıyor, hemen ardından oturum kapanıyor.

Kullanıcı "bitti" sesini duyup depodan çıkıyor; elindeki ürün kayıt dışı kalıyor.
Kapının varlık sebebi tam olarak buydu.

### Yapılan (2026-08-26)

`grup_coz(c, ot)` çağrısı üç kapı kontrolünden **önce** alındı — iki dosyada da.
Kural tek cümle: **tampon önce kapanır, kapılar sonra bakar.**

**Uçta ayrıca `c.commit()` gerekti.** `HTTPException`, DB bağımlılığının
`yield`'ine fırlatılıyor ve oradaki `c.commit()` hiç çalışmıyor; grup_coz'un
yazdığı kuyruk kaydı geri alınır, kullanıcıya **var olmayan bir kayıt**
bildirilirdi. Testi var.

### Doğrulama çıktısı

```
tanınmayan barkod (SONRAKI YOK) + ##BITIR##
  -> bitir_engel · oturum AÇIK · kuyrukta 1 kayıt
tanınan barkod (SONRAKI YOK) + ##BITIR##
  -> bitti · okutma yazıldı, kaybolmadı
POST /api/oturum/{id}/bitir  -> 409 + kuyruk kaydı KALICI
```

---

## 3. Tiger Düzeltme sekmesi malzeme kodunu seri numarası diye yazıyor · öncelik **A6**

- [x] **Düzeltildi** (2026-08-26) — seçenek **B**, aşağıda gerekçesi
- [x] Regresyon testi yazıldı — `tests/test_geri_alma.py`, 5 test
- [x] **Doğrulandı** (2026-08-26): 4'ü eski kodda düşüyor. Kimlik VARKEN normal
      yolun bozulmadığı ayrı test.

**Yer:** `app/matching.py:236` — `yeni_sn or kod`

**Belirti**

```
kirli slotu olan bir malzemenin SADECE kodunu okut + SONRAKI
  -> {'tip': 'slot', 'yeni': ''}        <- ekranda sorun yok görünüyor
  -> Tiger Düzeltme sekmesi:
     04RW5H | OEM MICROSOFT SQL SERVER 2022 | KB5021522OEM...OEM1 -> 04RW5H
```

**Kök sebep**

Kullanıcı yalnızca malzeme kodunu (ya da `DM-` etiketini) okutursa `bilinmeyen`
ve `bos_etiket` listeleri boş kalır, `yeni_sn = ""` olur ve `okutma.ham` alanına
**malzeme kodu** yazılır. Rapor o alanı "Tiger'a yazılacak gerçek seri no" diye
kullanıyor.

**Neden ciddi**

- `kirli_mi("04RW5H", "04RW5H")` → **kirli** (`kod+sayac` deseni). Uygulamanın
  tek işi kirli kaydı temizlemekken Tiger'a yeni bir kirli kayıt yazdırıyor.
- Aynı malzemenin birden çok slotu bu yoldan doldurulursa Tiger'a **aynı seri
  numarasından birden çok tane** yazılır.
- Arayüz uyarmıyor: ekranda `yeni: ''` görünüyor, kötü değer yalnızca Excel'de.

### Yapılan (2026-08-26) — seçenek **B**, önerimi değiştirdim

Plan **A**'yı öneriyordu (slot doldurma yapılmasın, onay kuyruğuna düşsün).
Uygularken A'nın yanlış olduğu görüldü: **saymak ile Tiger'ın seri numarasını
düzeltmek iki ayrı iş.** Birincisi asıl iş, ikincisi yan ürün.

Kutusunda okunabilir hiçbir kod olmayan bir kalem (kablo, fan, dökme parça —
`DM-` etiketinin var olma sebebi) düzenli olarak bu dala düşüyor. A ile her
biri onay kuyruğuna girerdi; kullanıcı kuyruğu boşaltmadan oturumu
kapatamıyor, yani **sayılmış ve doğru sayılmış** bir ürün yüzünden sayım
bitmiyordu. Kuyruk gürültüsü, A5'te düzelttiğimiz "kuyruk kapısı" ile
birleşince sahada tıkanma üretirdi.

B'nin "sessiz kalıyor" itirazı da geçerli değildi — sessizliği kaldırdık:

- `okutma.ham` alanına malzeme kodu yerine **boş** yazılıyor; `reports`'taki
  `o.ham<>''` filtresi o satırı zaten eliyor, yani **Tiger Düzeltme satırı
  üretilmiyor**.
- Yanıtta **`sn_yok=True`** dönüyor, ses `uyari`, şerit SARI (yeşil değil).
- Ekran ne yapılacağını yazıyor: "Tiger'daki uydurma kayıt düzelmeyecek.
  Düzelmesi için üretici S/N'yi okut ya da bir DS- etiketi yapıştırıp okut,
  sonra Ctrl+Z ile bu okutmayı geri al." — Ctrl+Z artık gerçekten geri alıyor
  (A5).
- Sayım normal işleniyor: sayaç dönüyor, kalem eksik görünmüyor.

Ayrıca genel bir kural testi eklendi: **Tiger Düzeltme'nin "YENİ seri no"
sütunu hiçbir satırda malzeme kodunun kendisi olamaz.** Olursa `kirli_mi` onu
bir sonraki sayımda yine kirli sayar ve düzeltme kendi kendini bozar.

**Test edilecek senaryo**

```
sadece malzeme kodu + SONRAKI -> slot DOLMAMALI, onay kuyruğuna düşmeli
Tiger Düzeltme sekmesinde "YENİ seri no" sütununda hiçbir satır
  malzeme kodunun kendisi olmamalı
```

---

## 4. Boş tamponda `##FAZLA##` (F3) oturumu kilitliyor · öncelik **A4**

- [x] **Düzeltildi** (2026-08-26) — `app/matching.py`, `##ATLA##` ile aynı guard
- [x] Regresyon testi yazıldı — `tests/test_geri_alma.py`
- [x] **Doğrulandı** (2026-08-26): eski kodda düşüyor. Dolu tamponda
      `##FAZLA##` bozulmadı (ayrı test).

**Yer:** `app/matching.py:329-345`

**Belirti**

```
hiçbir şey okutmadan ##FAZLA##
  -> okutma satırı: {ham: '', kod: None, seri: '', tip: 'fazla'}
  -> adsiz_fazlalar: 1 kayıt
  -> ##BITIR## -> 'ad_engel'    <- oturum kapanmıyor
```

**Kök sebep**

`##ATLA##` boş tamponu kontrol ediyor (`if hs:`), `##FAZLA##` etmiyor. Barkodu
olmayan hayalet bir fazla kaydı oluşuyor; ne olduğu sorulamıyor çünkü sorulacak
bir şey yok, ama bitirme kapısı onu adsız sayıp oturumu kilitliyor.

Kurtuluş yolu var (`##GERIAL##` son okutmayı siler) ama sahada kimse bilmez.
Yanlışlıkla F3'e basmak yetiyor.

**Yapılacak**

`if not hs: return {"tip": "bos", "ses": "uyari"}` — `##ATLA##` ile aynı guard.

---

## 5. Dizin geçişi — tüm proje klasörü Wi-Fi'dan indirilebiliyor

- [ ] **Düzeltildi**
- [ ] Regresyon testi yazıldı
- [ ] Doğrulandı: _(tarih / nasıl)_

**Yer:** `app/main.py:159-166` (SPA yakalayıcısı) · sunucu `--host 0.0.0.0` (`baslat.bat:84`) · kimlik doğrulama yok

**Belirti**

```
GET /..%2f..%2fdata%2fsayim.db     -> 200  380.928 bayt  b'SQLite format 3'
GET /..%2f..%2fdeneme.XLSX          -> 200   83.387 bayt  (stok + tutar)
GET /..%2fmain.py                   -> 200
GET /..%2f..%2f.venv%2fpyvenv.cfg   -> 200
```

**Kök sebep**

`os.path.join(STATIK, tam_yol)` + `isfile` → dosyayı ver. `..` normalize
edilmiyor. Tarayıcı düz `../` yolunu düzeltiyor, **yüzde-kodlanmışını
düzeltmiyor**; sunucu hiç düzeltmiyor.

Depo Wi-Fi'sındaki herkes canlı sayım veritabanını ve Tiger çıktısını
(miktarlar, seri numaraları, ortalama değer, envanter tutarı) indirebiliyor.
`.gitignore` bu dosyaları depodan tutuyor ama sunucu açıkça servis ediyor.

**Yapılacak**

```python
kok = os.path.realpath(STATIK)
aday = os.path.realpath(os.path.join(kok, tam_yol))
if tam_yol and (aday == kok or aday.startswith(kok + os.sep)) and os.path.isfile(aday):
    return FileResponse(aday)
```

**Test edilecek senaryo**

```
/..%2f..%2fCLAUDE.md      -> index.html dönmeli (404 değil, SPA davranışı korunsun)
/assets/<gerçek dosya>    -> hâlâ çalışmalı
/telefon                  -> hâlâ index.html
```

> Sayım doğruluğunu etkilemiyor, o yüzden 1-4'ten sonra. Ama aynı gün.

---

## 6. `##GERIAL##` öğrendiğini geri almıyor · öncelik **A5**

- [x] **Düzeltildi** (2026-08-26) — yeni `okutma.geri` sütunu + `etiketler.coz_bagla()`
- [x] Regresyon testi yazıldı — `tests/test_geri_alma.py`, 7 test
- [x] **Doğrulandı** (2026-08-26): hepsi eski kodda düşüyor.

**Yer:** `app/matching.py:402` `gerial()`

**Belirti**

```
temiz S/N + tanınmayan UPC + SONRAKI  -> eslesti, eslesme kaydı VAR
##GERIAL##                            -> okutma silindi
eslesme kaydı                         -> HÂLÂ VAR
```

**Kök sebep**

Geri alma yalnızca `okutma` satırını siliyor. Aynı işlemde yazılan
`eslesme` kaydı ve `etiket` bağlaması duruyor.

**Neden sinsi**

Yanlış ürüne okutulan bir UPC, Ctrl+Z ile geri alınsa bile kalıcı olarak o
malzemeye bağlanıyor — ve **Barkod Tablosu sekmesine düşüp Tiger'ın malzeme
kartına yazılmak üzere listeleniyor.** Sahada fark edilmesi imkânsız; hata
gelecek yılın sayımına taşınıyor.

### Yapılan (2026-08-26) — not ayrıştırma YOK, açık sütun

Plandaki iki seçenek de bırakıldı. `not_` ayrıştırmak kırılgandı **ve
eksikti**: öğrenme her dalda oluyor ama `"öğrenildi: ..."` notu yalnızca seri
dalında yazılıyordu — slot ve adet dallarındaki öğrenmeler nota hiç
girmiyordu, yani ayrıştırma sessizce yarım kalırdı.

Yerine yeni bir sütun: **`okutma.geri`** — bu okutmanın KENDİ SATIRI DIŞINDA
ne yarattığı, JSON olarak.

```json
{"ogrenilen": ["198701689928"], "etiket": "DS-000045"}
```

`##GERIAL##` bunu okuyup `eslesme` kaydını siler ve `etiketler.coz_bagla()` ile
etiket bağlamasını çözer. Etiket **numarası tüketilmez**: `basim` kaydı ve CSV
defteri yerinde kalır, yalnızca "neye yapıştı" bilgisi silinir — fiziksel
etiket hâlâ elde.

Beş yerde dolduruluyor: `grup_coz`'un seri / slot / adet dalları, `kuyruk_coz`,
`fazla_bagla`. Adet dalında miktar birden çok satıra dağılabildiği için `geri`
yalnızca İLK satıra yazılıyor.

**Sözleşme `MIMARI.md`'ye işlendi:** `eslesme` ya da `etiket` yazan yeni bir
yol eklenirse `geri` de doldurulmalı.

*Bilinen sınır:* `kuyruk_coz` ile çözülmüş bir kaydı geri almak
`kuyruk.cozuldu` bayrağını geri döndürmüyor. C grubuna yazıldı.

---

## 7. Hariç kuralları gerçek veride ters çalışıyor

- [x] **7a — `LIC` yanlış pozitifi düzeltildi** (2026-08-26) · öncelik **A3**
- [ ] **7b — tür kuralları gerçek veriye göre gözden geçirildi** · öncelik **C**
      (Tiger'da `TM`/`TK` karşılığına bakmak gerekiyor — araştırma işi)
- [x] **7c — hariç kalem okutulunca uyarıyor** (2026-08-26) · öncelik **A3**
- [x] Regresyon testi yazıldı — `tests/test_haric.py` baştan yazıldı, 11 test
- [x] **Doğrulandı** (2026-08-26): 9 test eski kodda düşüyor.
      `tests/conftest.py:haric_kur()` eklendi.

> **Testler hatayı kodlamıştı.** `test_haric.py`, `test_api.py`,
> `test_rapor.py` ve `test_kuyruk_akisi.py`'deki 8 test, `LIC` kuralının o EMC
> ağ kartını hariç tutmasına dayanıyordu — yani yanlış davranışı doğru diye
> kilitliyorlardı. Hariç mekanizması artık veriye gerçekten uyan bir kuralla
> (`tur:TK`, 10 satır) sınanıyor; varsayılanların **hiçbir satır
> yakalamaması** ayrı bir test.

**Yer:** `app/db.py` `HARIC_VARSAYILAN` · `app/importer.py` `_kural_tutar` · `app/matching.py` `coz()`

### 7a) `LIC` yanlış pozitifi

Tüm veride hariç edilen **tek satır** var, o da yanlış:

```
303-195-100C-001 | EMC 303-195-100C-01 Dual Port 10GB Ethernet SLIC Optical | 1 adet
                                                              ^^^^ S-LIC-E
```

Gerçek bir ağ kartı lisans sanılıp sayım dışı bırakılıyor.

Buna karşılık `04RW5H | OEM MICROSOFT SQL SERVER 2022 STANDART` (gerçek bir
yazılım lisansı) **sayıma dahil**. Filtre tam tersini yapıyor.

**Yapıldı:** desen `LICENSE`'a çevrildi. Kelime sınırı kontrolü **mümkün
değil** — desenler `norm()` çıktısında aranıyor ve orada boşluk/noktalama hiç
yok ("...ETHERNETSLICOPTICAL"). Tek çare deseni yeterince uzun tutmak.

`kurallari_tohumla()` yalnızca tablo boşken çalıştığı için mevcut
veritabanlarına **göç** gerekti: `db.lic_kuralini_duzelt()` kuralı değiştirip
hariç bayraklarını tüm yüklemelerde yeniden hesaplıyor. Idempotent; yalnızca
`varsayilan=1` kurala dokunuyor (kullanıcı deseni elle yazdıysa karar onundur).

### 7b) Tür kuralları ölü

Ambar 1'de `Malzeme Türü` sütununun tüm değerleri **`TM` (860) ve `TK` (10)** —
Tiger'ın kısa kodları. `DESTEK-HP`, `YAZILIM`, `MİCROSOFT OPEN`, `HİZMET`,
`FİKTİF` desenlerinin hiçbiri bu veride geçmiyor. Beş kural da hiç ateşlemiyor.

→ Tiger'da bu kodların karşılığı ne, kontrol edilecek. Muhtemelen CLAUDE.md §3.4
farklı bir rapordan/dönemden yazılmış. Doğru filtre alanı `Malzeme Türü` değil
`Malzeme Açıklaması` olabilir.

### 7c) Hariç satır okutulunca yalan söylüyor

`coz()` `beklenen.haric` alanına hiç bakmıyor:

```
hariç edilen kalemin serisini okut + SONRAKI
  -> {'tip': 'eslesti', 'ses': 'ok'}     <- yeşil, başarı sesi
  -> sayaçlar: okutulan 0, kalan 869     <- hiçbir şey olmadı
  -> raporda: Eksik'te YOK (haric atlanıyor), Eşleşen'de duruyor
```

Kullanıcı elindeki fiziksel ürünü okutuyor, "tamam" sesini duyuyor, ürün
mutabakattan tamamen buharlaşıyor.

**Yapıldı:** `coz()` her dönüşünde `haric` / `haric_sebep` taşıyor; `grup_coz`
kaynak hariçse `tip="haric"` dönüp **hiçbir şey yazmıyor**. Ekran hangi kuralın
kalemi dışarıda bıraktığını söylüyor ve çıkış yolunu gösteriyor (Kurulum
ekranından kuralı kapat). Kural kapatılınca kalem normal sayılıyor — testi var.

---

## 8. Türkçe karakterli raf adı 500 veriyor

- [ ] **Düzeltildi**
- [ ] Regresyon testi yazıldı
- [ ] Doğrulandı: _(tarih / nasıl)_

**Yer:** `app/barkod.py:46` `kart_html` · `app/routers/rapor.py` `komut_karti` ve `raf_etiketi`

**Belirti**

```python
barkod.kart_html(["ÜST-1"])
-> IllegalCharacterError: The following characters are not valid for Code 128: Ü
```

Router yalnızca `ImportError` yakalıyor → 500, boş sayfa, stack trace.

Türkçe bir depoda `ÜST`, `ÖN`, `ÇIKIŞ` raf adı yazmak en doğal şey.

**Yapılacak**

- `raf_satirlari` / `kart_html` raf adını `norm.TR` ile katlasın (`ÜST-1` → `UST-1`)
  **ve kullanıcıya ne bastığını göstersin** — okutulan değerle bastığı değer
  aynı olmalı, yoksa `komut_coz` tanımaz.
- Router `ValueError` / `IllegalCharacterError` yakalayıp 400 + anlaşılır mesaj dönsün.
- `_kart()` raf adını HTML-kaçışsız basıyor; `_etiket()` kaçışıyor. Tutarsız,
  `html.escape` eklensin.

---

## Küçükler — depodan sonra

- [ ] **`Escape` küresel `##IPTAL##`** (`web/src/ekranlar/Sayim.tsx:24`) —
      `window` seviyesinde dinleniyor. Ürün adı yazarken Escape'e basmak
      (evrensel "bu kutuyu kapat" refleksi) o anki grubu sessizce siliyor.
      → Girdi odaktayken kısayollar susmalı.
- [ ] **Barkod Tablosu tüm `eslesme` tablosunu döküyor** (`app/reports.py`) —
      oturum/yükleme filtresi yok. Önceki sayımlardan öğrenilen her şey ve
      basılmış her `DM-` etiketi her raporda tekrar çıkıyor; liste sonsuza
      kadar büyüyor.
- [ ] **`ara()` LIKE kaçışı yok** (`app/matching.py`) — kullanıcı `%` veya `_`
      yazarsa joker karakter olarak davranıyor.
- [ ] **`tip='bilinmiyor'` ölü kod** — `sayaclar()`, `reports.py` ve
      `oturumlar.gecmis()` bu tipi sayıyor ama `okutma`'ya hiçbir yerde
      yazılmıyor.

---

## Belge güncellemeleri

- [ ] `CLAUDE.md` §3.4 — hariç kuralları gerçek rapor biçimiyle uyuşmuyor
      (bulgu 7b). Doğrusu öğrenilince güncellenecek.
- [x] `CLAUDE.md` §2.4 — "lot okut, adet gir" uygulandı ve yazıldı (bulgu 1).
- [ ] `MIMARI.md` — 3. maddedeki motor değişikliği aynı commit'te işlenecek.
      (1. madde işlendi.)

---

## Sıra — "bu olmadan depoya gidilmez" ölçütüne göre

Madde numaraları tespit sırasıdır, öncelik değil. Gerçek ölçüt tek soru:
**bu hata sayımı bozar / kaybeder / bitirtmez mi?**

### A · DEPOYA GİTMEDEN ŞART

Hepsi sayımın kendisini vuruyor. Sonradan düzeltilemezler: karar ürün eldeyken
veriliyor, ya da hata sessiz olduğu için gün sonunda fark edilmiyor.

| Öncelik | Madde | Ne yapıyor |
|---|---|---|
| ~~A1~~ | ~~§1 Lot sayımı~~ | **BİTTİ** (2026-08-26) — 271 adet yanlış sayılıyordu |
| ~~A2~~ | ~~§2 `##BITIR##` kapısı~~ | **BİTTİ** (2026-08-26) |
| ~~A3~~ | ~~§7a+7c Hariç kalemi~~ | **BİTTİ** (2026-08-26) |
| ~~A4~~ | ~~§4 Boş `##FAZLA##`~~ | **BİTTİ** (2026-08-26) |
| ~~A5~~ | ~~§6 `##GERIAL##`~~ | **BİTTİ** (2026-08-26) |
| ~~A6~~ | ~~§3 Tiger'a malzeme kodu~~ | **BİTTİ** (2026-08-26) — seçenek B |

**A5 ve A6 neden "sonra" değil:** ikisi de sayım ANINDA veri üretiyor.
A5'in bozduğu `eslesme` kaydı geri alınamaz (hangi okutmadan geldiği kayıtlı
değil). A6'da slot doldurma kararı ürün eldeyken verilebilir; gün sonunda
"bu hangi cihazdı" sorusunun cevabı yok.

### B · Depoya gitmeden, ama sayımı etkilemiyor

| Öncelik | Madde | Neden yine de önce |
|---|---|---|
| **B1** | §8 Türkçe raf adı → 500 | Komut kartı depoya gitmeden basılıyor. `ÜST-1` yazan boş sayfa ve stack trace görüyor |
| **B2** | §5 Dizin geçişi | Sayım doğruluğunu etkilemiyor ama veritabanı ve Tiger çıktısı Wi-Fi'dan indirilebiliyor |

### C · Depodan sonra

| Madde | Neden bekleyebilir |
|---|---|
| §7b Tür kuralları ölü | Tiger'da `TM`/`TK` kodlarının karşılığına bakmak gerekiyor — araştırma işi. Bu kurallar zaten hiç ateşlemiyor, yani **yanlış bir şey yapmıyorlar**, sadece işe yaramıyorlar |
| Küçükler (Escape, Barkod Tablosu, LIKE kaçışı, ölü kod) | Hiçbiri sayım verisini bozmuyor |
| `##GERIAL##` `kuyruk.cozuldu` bayrağını geri döndürmüyor | A5'in bilinen sınırı. Kuyruktan çözülmüş bir kaydı geri almak okutmayı ve öğrenmeyi siliyor ama kuyruk kaydı "çözüldü" kalıyor |

**A grubu BİTTİ** (2026-08-26) — 245 test geçiyor. Sayımı bozan, kaybeden ya
da bitirtmeyen bilinen bir hata kalmadı. B grubu aynı gün kapatılmalı.
