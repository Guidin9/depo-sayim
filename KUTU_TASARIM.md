# Kutu Barkodu ile Toplu Sayım — Tasarım

**Durum: KODLANDI — serisiz yarı** (2026-08-27). Saha cevapları §9, kapsam §10.
Seri takipli dal, `##KUTUKAPAT##` ve otomatik kilit **bilerek yazılmadı**:
I2 kilidi sahada denenmeden yazılması gerekip gerekmediği bilinmiyor (§9.2).

**Gerçek depoda HENÜZ DENENMEDİ.** 399 test geçiyor, arayüz derleniyor.

Kaynak: `depo_sayim_bugs_improvements.md` I3. Dosya kendi içinde "ayrı bir
tasarım/akış dokümanı gerektirebilir" diyor; bu o doküman.

---

## 1. Problem

Raftaki kutu bazlı stoklar: A1 rafında tek üründen 150 adet. Bugün her adet
tek tek okutuluyor. `##ADET-N##` (CLAUDE.md §4.5) bunun bir kısmını çözüyor
ama iki eksiği var:

1. Adet her sayımda yeniden giriliyor — kutunun içinde ne olduğu hiçbir yerde
   yazmıyor.
2. Seri takipli üründe hiç işe yaramıyor: Tiger'da her adet ayrı satır.

Depoda **100'den fazla kap var** (saha cevabı, §9.1). Bu, işin gerekçesidir:
100 kapta her sayımda malzeme aramak + adet girmek elle yapılan iştir.

## 2. Üç ayrı soru, üç ayrı etiket

Kutu barkodu `##RAF-A1##` DEĞİLDİR ve `DM-`/`DS-` de değildir (CLAUDE.md §12.1).
Dördüncü soruyu cevaplar:

| Etiket | Soru | Kapsam |
|---|---|---|
| `##RAF-A1##` | nerede duruyorum | konum |
| `DM-000123` | ne bu | malzeme tipi |
| `DS-000045` | hangisi bu | tekil cihaz |
| **`DK-000007`** | **bu kapta ne var** | **kap** |

Başlıktaki soru 2026-08-27'de değişti: "bu kapta ne, **kaç tane**" değil,
yalnızca "**ne**". Gerekçe §3'te.

## 3. Veri modeli

Yeni tablo — `SEMA`'ya yazılabilir. **Tuzak yalnızca mevcut tabloya *sütun*
eklemekte** (`app/db.py:128-134`); yeni tablo `CREATE TABLE IF NOT EXISTS` ile
eski veritabanlarında da oluşur.

```sql
CREATE TABLE IF NOT EXISTS kutu(
  kod TEXT PRIMARY KEY,      -- normalize: DK000007
  gosterim TEXT,             -- DK-000007
  malzeme TEXT,              -- beklenen.kod   <- KALICI olan bu
  adet REAL,                 -- SON BİLİNEN adet; gerçek değil, varsayılan
  izleme TEXT,               -- 'seri' | 'lot' | 'yok'  (malzemeden kopyalanır)
  raf TEXT,
  ts TEXT, ts_guncelle TEXT, -- ts_guncelle = adedin en son doğrulandığı an
  oturum INT);               -- ilk tanımlandığı oturum
```

**Kutu kalıcıdır, ama kalıcı olan şey malzeme bağıdır — adet değil.**

Bu, 2026-08-27 saha cevabının doğrudan sonucudur: kutu içeriği **ayda bir
civarında** değişiyor (§9.3). Sayım yılda bir yapılıyorsa, sayım anında
`kutu.adet` alanının doğru olma ihtimali pratikte sıfırdır. Kaydın kendisini
"kapta 150 var" diye okumak, uygulamanın kendi bayat verisini sayım sonucu
diye onaylaması olurdu — CLAUDE.md §6'daki "Sayım Miktarı sütunu" tuzağının
aynısı, bu kez bizim tarafımızda.

Ayda bir değişmeyen şey ise kabın **ne taşıdığıdır**: M.2 SSD kutusuna ertesi
ay switch konmaz. Kazanç buradadır — kutu okutulunca malzeme, izleme yöntemi
ve raf anında gelir, kullanıcı 150 kalemlik listede malzeme aramaz. Adet
yalnızca **girdi alanının varsayılanı** olarak kullanılır ve §6'daki tazelik
kuralına tabidir.

`data/etiket/` altına CSV yedeği yazılır (`DK-` etiketleri de basılmış fiziksel
etiketlerdir — CLAUDE.md §12.7 aynen geçerli).

## 4. Etiket sınıfını eklerken — bilinen tuzak (DÜZELTİLDİ)

**Bu bölüm kap akışından bağımsızdı.** `DK-` deseni tanımlandığı anda
aşağıdaki iki yer yanlış cevap vermeye başlıyordu; ikisi de aynı commit'te
düzeltildi ve `tests/test_kutu.py` regresyonu tutuyor.

Kimlik neredeyse bedava: `etiketler.ONEK` (`app/etiketler.py:30`) sözlüğünden
`DESEN`, `bicimle`, `sonraki_no` ve `bas()`'ın doğrulaması türüyor. **Ama iki
yerde ikili varsayım var ve ikisi de sessizce yanlış cevap verir:**

| Yer | Eski hâli | Şimdi |
|---|---|---|
| `etiketler.etiket_turu` | `DM` değilse **"seri"** dönüyordu | `ONEK` üzerinden ters arama |
| `reports` Etiketler sekmesi | `tur=="malzeme" ? "Malzeme" : "Seri"` | `ETIKET_TUR_ADI` — üç tür de kendi adıyla |

Birincisi kritikti: `etiket_turu("DK-000007")` `"seri"` dönüyordu, yani
`kuyruk_coz` ve `fazla_bagla` kap barkodunu "öğrenilmeyecek seri etiketi"
sanıyordu — doğru sonuç, yanlış sebep. `reports._yeni_seri` ise bir `DK-`
kodunu gerçek seri numarası adayı sayıyor ve Tiger'a kap numarasını cihazın
S/N'i diye yazdırıyordu. Kural artık tek yerde: `etiketler.ogrenilebilir()`
seri ve kap etiketini birlikte eler, üç çağıran da ona bağlı.

## 5. Motora bağlanışı

`coz()`'e yeni adım (1c'nin hemen ardına, `etiket` sorgusunun ikizi):

```
1d | etiket.kod=n AND tur='kutu'  ->  t="kutu"   (kutu tanımlıysa)
                                      t="kutu_bos" (etiket basılı, içerik yok)
```

`grup_coz` yeni bir dal alır. Yeni `okutma.tip` **gerekmez** — kutu sonuçta ya
`adet` dalına ya `slot`/`eslesti` dalına iner, sadece oraya *nasıl* girdiği
değişir:

```
kutu tanımlı, izleme='lot' | 'yok'          <- YAZILDI
    -> malzeme = kutu.malzeme
    -> adet kullanıcıdan alınır; kutu.adet yalnızca VARSAYILAN (§6)
    -> mevcut `adet` dalı (_adet_islemi / _adet_dagit) aynen çalışır
    -> sayımdan sonra kabın son bilinen adedi tazelenir

kutu tanımlı, izleme='seri'                 <- ERTELENDİ (§9.2, §10)
    -> oturum.sabit_kod = kutu.malzeme            (I2 kilidi)
    -> "kutu açık: 150'nin 0'ı" sayacı gösterilir
    -> kullanıcı seri numaralarını art arda okutur — I2'nin tam olarak
       çözdüğü akış
    -> ##KUTUKAPAT## ile kapanır; sayılan < beklenen ise UYARIR, örtmez

kutu tanımsız (kutu_bos)                    <- YAZILDI
    -> KUYRUĞA yazılır (tur='kutu'), arayüz paneli hemen açar
    -> malzeme seçilince izleme Tiger'dan gelir, kullanıcıya SORULMAZ
```

**Uygulamada üç sapma oldu, üçü de bilerek:**

1. **Tanımsız kap kuyruğa yazılıyor**, doğrudan bir tanımlama ekranına değil.
   Taslak "kuyruğa DEĞİL" diyordu; yanlıştı. Ekranda bırakılan soru,
   kullanıcı cevaplamadan rafa dönerse **sessizce kaybolurdu** — kap
   sayılmamış olur ve bunu kimse fark etmez. Kuyruk kaydı hem paneli besliyor
   hem de oturum kapanmadan cevaplanmasını garantiliyor. Uygulamanın başka
   hiçbir yerinde "cevapsız kalabilen soru" yok; kap da istisna olmamalı.
2. **Tanımlı kapta bile adet soruluyor** (`kutu_sor`), `##ADET-N##`
   girilmedikçe. Kayıttaki adedi sorusuz uygulamak §3'ün tam tersi olurdu.
3. **Kap kodu bir MALZEME KODU okutması gibi işleniyor.** Ayrı bir sayım dalı
   yazılmadı: kap malzemeyi getiriyor, sayımı mevcut dallar yapıyor
   (`slot` / `adet` / `onay`). Ayrı dal, `_adet_dagit` gibi kuralların iki
   yerde ayrı ayrı düzeltilmesi demekti.

Ayrıca **kap kodu `eslesme`'ye hiç yazılmıyor** (`etiketler.ogrenilebilir()`).
Bu §4'te öngörülmemişti ama aynı ailedendir: öğrenilseydi kap kodu Tiger'ın
malzeme kartına barkod olarak yazılır ve kap ertesi ay başka ürünle
dolduğunda kalıcı yanlış eşleşme bırakırdı.

> **Karar: "seri no mu gerekiyor" diye SORMUYORUZ.** Bug dosyası soruyu
> kullanıcıya yöneltiyor ama cevabı Tiger zaten biliyor
> (`beklenen.izleme`, CLAUDE.md §2.4). Sormak, yanlış cevaplanabilen bir soru
> eklemek olurdu.

Seri takipli kutu, kutusuz seri takipli malzemeden farksız çalışmaya devam
eder: `##KILIT##` elle basılır, seri numaraları okutulur. Kutu kaydı yine de
malzemeyi getirir — kaybolan tek şey otomatik kilit ve "150'nin 12'si"
sayacıdır.

Yeni komut `##KUTUKAPAT##` yalnızca seri dalıyla birlikte gelir; o dal
ertelendiği için **şimdilik eklenmez** (`norm.KOMUT` + `matching.okut` dalı +
`barkod.KOMUTLAR` üçlüsü bir arada eklenmeli; yarısı eklenirse komut kartına
basılıp sahada "tanınmayan barkod" olur).

## 6. Sahadaki akış ve tazelik kuralı

```
##RAF-A1##          rafa gir
DK-000007           kutuyu okut
                    -> tanımlıysa:  "M.2 SSD 256GB · lot · son sayımda 150"
                       adet alanı + BAŞKA MALZEME
                    -> tanımsızsa:  malzeme ara + adet gir
##SONRAKI##         grubu kapat
```

**Adet asla tek dokunuşla onaylanmaz.** İçerik ayda bir değiştiği için
"DOĞRULA" düğmesi refleksle basılan bir düğmeye dönerdi ve kutu kaydı sayımın
kendisini belirlerdi. Kural:

| `ts_guncelle` yaşı | Ekranda | Gerekçe |
|---|---|---|
| ≤ 30 gün | Adet alanı `kutu.adet` ile **dolu gelir**, düzeltilebilir | Kayıt taze; muhtemelen doğru |
| > 30 gün | Adet alanı **boş gelir**, son bilinen adet yalnızca gri ipucu | Bir aydan eski kayıt bilgi değil, tahmindir |

30 gün tek bir sabittir (`kutu.TAZELIK_GUN`) ve sahada ayarlanır. Yıllık
sayımda pratikte hep ikinci satır işler; birinci satır aynı kutunun kısa
aralıkla iki kez sayıldığı durum içindir (raf tekrarı, kısmi sayım).

Adet girildiğinde `kutu.adet` ve `ts_guncelle` güncellenir — bir sonraki sayım
için son bilinen değer budur.

## 7. Etiket basımı

`barkod._etiket()` (`app/barkod.py:151-171`) zaten `s["tur"]`e göre dallanıyor;
`kutu` için bir dal eklenir. Kutu etiketi **büyük basılır** (kap üstünde, uzaktan
okunacak) ve üzerinde insan okunur **malzeme** yazar:

```
DK-000007
M.2 SSD 256GB
```

**Adet etikete BASILMAZ.** İlk taslakta `150 AD` satırı vardı; ayda bir değişen
içerikle bu, ayda bir yeniden basım demektir ve depoda yazıcı yok (CLAUDE.md
§12). Basılmayan sayı yerine **yanlış basılmış sayı** çok daha kötüdür: kapta
`150 AD` yazar, içinde 130 vardır ve sayan kişi elindeki gerçeğe değil etikete
inanır.

Malzeme adı değişirse (kap başka ürüne ayrıldıysa) etiket yeniden basılır —
**kod aynı kalır**, yoksa depoda aynı kap için iki numara dolaşır
(CLAUDE.md §12.7'nin aynı gerekçesi).

## 8. Rapora etkisi

Yeni sekme **gerekmez.** Kutudan sayılan adet normal `okutma` satırıdır; Eksik /
Fazla / Eşleşen aynen çalışır. `okutma.not_` alanına `"kutu: DK-000007"` yazılır
— denetim izi.

Tek ek: **Etiketler** sekmesi `DK-` satırlarını "Kutu" olarak göstermeli (§4).

## 9. Saha cevapları (2026-08-27)

1. **Kaç kap var? → 100'den fazla.** İş gerekçeli; kalıcı kutu tablosu yazılır.
2. **I2 kilidi seri takipli kutuyu yeterince hızlandırdı mı? → Henüz sahada
   denenmedi.** §5'in seri dalı, `##KUTUKAPAT##` ve kutu sayacı **yazılmaz**;
   I2 depoda denendikten sonra buraya dönülür. Bu tek açık sorudur.
3. **İçerik ne sıklıkla değişiyor? → Ayda bir civarı.** Kalıcı tablo kalır ama
   `adet` alanının anlamı düştü: gerçek değil varsayılan (§3), etikete basılmaz
   (§7), tazelik kuralına tabidir (§6).

## 10. Kapsam — kodlandı / kodlanmadı

Kodlandı (kap akışının serisiz yarısı):

- `etiketler.ONEK`'e `"kutu": "DK"`, `etiket_turu` ters aramaya çevrildi,
  `reports` üç türü de kendi adıyla yazıyor (§4)
- `etiketler.ogrenilebilir()` — "bu barkod bir malzemeye bağlanabilir mi"
  kuralı tek yerde (seri ve kap etiketi elenir); `kuyruk_coz`, `fazla_bagla`
  ve `elle_say` üçü de oraya bağlandı
- `kutu` tablosu (§3) + `app/kutu.py` defteri + `data/etiket/kutu.csv` yedeği
  (`sifirla.bat` sonrası kap bağları geri gelir)
- `coz()` 1d adımı: `kutu` / `kutu_bos` / `kutu_yabanci` (§5)
- `grup_coz` kap dalları + `kutu_coz()` (kuyruktan çözme)
- `_adet_islemi()` — adet yazma gövdesi `grup_coz` ile ortaklaştırıldı
- Tazelik kuralı: `kutu.TAZELIK_GUN` = 30 (§6)
- `##GERIAL##` kap kaydını da geri alır (`geri` JSON'unda kabın önceki hâli)
- Aynı kap iki kez okutulunca ikinci kuyruk kaydı açılmaz
- `barkod._etiket()` kap dalı, adetsiz büyük etiket + yeniden basım (§7)
- `okutma.not_` = `"kutu: DK-000007"` (§8)
- Arayüz: Sayım ekranında kap panelleri (adet cevabı orada verilir), Kuyruk ve
  Telefon ekranlarında malzeme + adet paneli, Etiket ekranında kap basımı
- `tests/test_kutu.py` — 25 test

Kodlanmadı (I2 saha testine kadar):

- `grup_coz`'un `izleme='seri'` dalı, otomatik `sabit_kod` kurulumu
- `##KUTUKAPAT##` komutu ve "150'nin 12'si" sayacı

Seri takipli kap bu sürümde kutusuz akışla sayılır: kap malzemeyi getirir,
kilit elle basılır. Kap tek başına okutulduğunda **hiçbir satır yazılmaz**
(`kutu_seri`) — kap kodunu okutup `##SONRAKI##` demek "bir cihaz saydım"
anlamına gelmemeli. Arayüz o an "şu koda kilitle" düğmesini gösterir.

## 11. Sahada denenecekler

Aşağıdakiler kodda doğru, depoda doğrulanmadı:

1. Kap etiketi gerçek okuyucuyla okunuyor mu (büyük basım, laminatsız kap
   yüzeyi)?
2. "Kaç adet?" sorusu akışı yavaşlatıyor mu — kullanıcı `##ADET-N##` okutmayı
   mı yeğliyor, ekrandan yazmayı mı?
3. 30 günlük tazelik eşiği doğru mu? Sayım yılda birse pratikte hep bayat
   dalı işler; eşik yalnızca aynı kabın kısa aralıkla iki kez sayıldığı
   durumda fark yaratır.
4. Kap içeriği değişince kullanıcı etiketi yeniden basıyor mu, yoksa eski
   malzeme adı kabın üstünde mi kalıyor? (Kod aynı kalır, yanlış olan yalnızca
   insan okur satırdır.)
