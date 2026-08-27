# Depo Sayım Uygulaması — Proje Bağlamı

Bu dosya projenin alan bilgisini içerir. Kod yazmadan önce tamamını oku.
Buradaki kurallar sahada gerçek veriyle doğrulanmış bilgilerdir, varsayım değildir.

---

## 1. Problem

Bir bilgisayar donanımı toptancısının deposunda envanter sayımı elle yapılıyor. Şirket
**Logo Tiger 3 Enterprise v3.06.00.01** kullanıyor. Amaç: barkod okuyucuyla sayım
yapan, Tiger'ın envanter raporuyla karşılaştıran ve fark raporu üreten bir web
uygulaması.

Barkod okuyucu **USB HID** — klavye gibi davranır, barkodu yazıp Enter'a basar.
Sürücü veya SDK gerekmez, odaklanmış bir input alanı yeterlidir.

Sayımı **tek kişi**, depodaki laptopa bağlı USB okuyucuyla yapar.

---

## 2. Kritik alan bilgisi — bunları bilmeden doğru kod yazılamaz

### 2.1 Malzeme Kodu ≠ Seri Numarası

Tiger'daki "Malzeme Kodu" **ürün tipini** temsil eder, tekil cihazı değil.
`000DJ5` kodunun stoğu 21 adettir — yani 21 fiziksel cihaz tek kodun altındadır.

Kod sütunundaki değerler üç farklı türdedir ve karışıktır:

| Tür | Örnek | Etikette var mı |
|---|---|---|
| Üretici parça numarası (P/N) | `000DJ5`, `JZ336A`, `P00924-B21` | Genelde evet |
| Sipariş SKU'su | `210-ACXU-TİP2`, `580-ADHQ` | Hayır |
| Şirket içi serbest kod | `0,70MM TEL`, `DMR-R720 KASA FAN` | Hayır |

666 tekil koddan 57'si boşluk veya Türkçe karakter içerir — bunlar hiçbir zaman
barkod olamaz.

### 2.2 Okutulabilecek dört farklı şey

Sahada test edildi, gerçek çıktılar:

| Okunan | Ne olduğu | Not |
|---|---|---|
| `198701689928` | UPC-A (12 hane, checksum geçerli) | Ürün tipi, perakende kutu |
| `190017273624` | UPC-A | Ürün tipi |
| `ARK-1250L-S5A1` | Üretici P/N | Tiger'daki kod `ARK-1250LS5A1ATR/8641924` — **birebir değil** |
| `EDBP0000000000000` | Seri numarası | Tiger'da karşılığı yok (kirli kayıt) |

Dell Service Tag barkodu **önek eklemeden** birebir gelir: `AB12CD3` okutulur,
`AB12CD3` yazar. Test edildi.

### 2.3 Kirli seri numaraları — projenin en önemli kısmı

Seri numarası alanındaki kayıtların yarısı gerçek bir seri numarası değil.
Örnek veride 801 seri kaydından **394'ü** böyle. İki sebepten oluşuyor: stok
farkını kapatmak için yer tutucu kayıtlar açılmış, ve seri no alanı zamanla
proje/müşteri bilgisi için serbest not alanı gibi kullanılmış. Uygulamanın işi
bunları tanıyıp gerçek seri numarasıyla eşleştirmek.

Desenler:

```
0WGP72SAYIM1                 -> malzeme kodu + "SAYIM" + sayaç
470-ABDL STOK 2026 3         -> kod + boşluk + yıl + sayaç
303-092-102BSAYIMFAZLASI1    -> kod + "SAYIMFAZLASI"
XR11 DEN ÇIKAN ÜRÜN          -> serbest Türkçe metin
470-AEUIPROJEADIFAZ2663323654           -> kod + proje adı + gerçek S/N
920-007925MUSTERIADIARTTIRIM9           -> kod + müşteri adı + sayaç
ARK-1250TAKILAN1SNX9Y/0000Z  -> metin + "SN" + GERÇEK seri no (X9Y/0000Z)
```

Son iki örnek kritik: **içinde gerçek seri numarası gömülü olabilir.** Okutulan
S/N bir kirli kaydın alt dizesi olarak geçiyorsa eşleştirme adayıdır.

Malzeme bazında dağılım (152 seri takipli malzeme):
- 83 malzeme tamamen temiz
- 65 malzeme tamamen kirli
- 4 malzeme karışık

`Seri/Lot Açıklaması` alanı 801 kaydın sadece 5'inde dolu — doğru alan boş dururken
herkes seri no alanına yazmış.

### 2.4 Üç izleme modu

Tiger'da malzeme kartı > İzleme ve Sıralama > İzleme Yöntemi:

| Mod | Davranış | Ambar 1'de |
|---|---|---|
| `Seri No.` | Her adet ayrı satır, miktar hep 1 | 801 satır / 152 malzeme |
| `Lot Numarası` | Tek lot altında çok adet | 69 satır / 9 malzeme (271 adet) |
| `İzleme Yapılmayacak` | Sadece adet | Seri/Lot raporunda hiç gelmez |

Lot örneği: `0C5RNH` SFP, `0C5RNHLOT1221` lot numarası altında 77 adet. Bunları
tek tek okutmak anlamsız — lot okut, adet gir (`##ADET-N##` ya da telefondaki
Adet paneli, §4.5).

**Bir malzemenin birden çok lotu olabilir ve bu istisna değil kuraldır.** Örnek
veride `BRODCOM 57414` tek başına **57 ayrı lot satırı** taşıyor, her biri 1
adet. Bu yüzden okutma hep "o malzemenin ilk satırına" yazılamaz: lot numarası
okutulduysa O satıra, yalnızca malzeme kodu biliniyorsa kapasitesi kalan
satırlara sırayla dağıtılır (`matching._adet_dagit`). Hep ilk satıra yazmak o
lotu şişirip diğer 56 satırı eksik gösteriyordu.

Lot satırı **tek okutmayla kapanmaz**: ölçüt `sayılan < beklenen`
(`matching.kapasite_kaldi`), seri takiplideki "bir kez okutuldu" değil.

### 2.5 Barkod alanı boş

Malzeme kartı > Birimler > Barkod alanı **hiçbir kartta dolu değil.** Bu yüzden
Tiger'ın kendi Ambar Sayımı ekranındaki barkod kutusu her zaman "Barkot bulunamadı"
der. Uygulama sayımı tamamen üstlenmek zorunda.

Uygulamanın öğrendiği barkodlar sayım sonunda Tiger'a yazılacak — rapordaki
"Barkod Tablosu" sekmesi bu iş için.

---

## 3. Veri kaynakları

### 3.1 Seri/Lot Envanter Raporu (ana kaynak)

Tiger yolu: `Malzeme Yönetimi > Maliyet Raporları > Lot / Seri Envanter Raporu`
(TFRS versiyonunu **kullanma** — tutarlar farklı hesaplanır).

Filtreler: Malzeme İzleme Yöntemi `1,2,3` · Ambar No `0-14` · Ambar Maliyet Grubu
istenen ambar · Son Envanter Tarihi = sayım günü.

Excel çıktısı. **Başlık satırı 2. satırdadır**, 1. satır rapor başlığıdır.

Sütunlar:
```
Malzeme Türü · Malzeme Kodu · Malzeme Açıklaması · Ambar Maliyet Grubu ·
İzleme Yöntemi · Seri/Lot No. · Seri/Lot Açıklaması · Envanter Miktarı ·
Birim · Ortalama Değer · Envanter Tutarı
```

Tiger ayrıca **JSON** çıktısı da verebiliyor (rapor ekranının üst barında).
İleride Excel yerine JSON tercih edilebilir — daha temiz parse edilir.

**Aynı rapor ikinci kez yüklenirse satırlar İKİLENMEZ.** Kurulum ekranındaki
"İkinci rapor ekle" düğmesi ikinci dosyayı aynı yüklemeye ekler; oraya yanlışlıkla
aynı Seri/Lot dosyası seçilirse 870 satır sessizce 1740 oluyordu. Her fiziksel
cihaz yalnızca ilk kopyaya eşleştiği için ikinci kopya sonuna kadar "eksik"
kalıyor ve sayım asla tamamlanamıyordu — kullanıcı bütün depoyu sayıp raporda
870 hayalet eksik görüyordu (2026-08-27). Tekrar ölçütü `(kod, ambar, seri)`;
atlanan satır sayısı yükleme özetinde gösterilir.

### 3.2 Envanter Raporu (ikincil, adet bazlı)

Seri takipsiz kalemler bu raporda. Aynı sütunlar, `Seri/Lot No.` yok.

### 3.3 Ambar yapısı

`Ambar Maliyet Grubu` alanı **fiziksel depoları** temsil eder (doğrulandı).
Ambar 1 = merkez ofis deposu. Sayım ambar bazında ayrı ayrı raporlanır.

Ambar 1 (test verisi): 870 satır, 801 seri + 271 lot adedi.

### 3.4 Sayım dışı kalemler

Bunlar fiziksel nesne değildir, sayım kapsamından **çıkarılmalıdır**, yoksa hepsi
"eksik" olarak raporlanır:

- Malzeme Türü: `DESTEK-HP`, `YAZILIM`, `MİCROSOFT OPEN`, `HİZMET`, `FİKTİF`
- Ayrıca açıklamasında `LICENSE`, `LİSANS`, `E-LTU`, `NAKLİYE`, `KARGO` geçenler
  (tür filtresi bunları yakalamaz — örn. `JW473AAE` Aruba lisansı 460 adet,
  `60007` nakliye 118 adet)

**Desenler alt dize olarak aranır ve kelime sınırı YOKTUR.** `norm()` boşlukla
noktalamayı attığı için `"Dual Port 10GB Ethernet S-LIC-E Optical"` metni
`"...ETHERNETSLICOPTICAL"` oluyor. Bu yüzden kısa desen tehlikelidir: üç
harflik `LIC` bu ağ kartını lisans sanıp sayım dışı bırakıyordu — örnek veride
hariç edilen TEK satır oydu, üstelik gerçek yazılım lisansı
(`04RW5H` OEM MICROSOFT SQL SERVER) filtreye hiç takılmıyordu. Filtre tam
tersini yapıyordu. 2026-08-26'da `LICENSE`'a çevrildi; mevcut veritabanları
`db.lic_kuralini_duzelt()` göçüyle düzeltiliyor. **Yeni desen eklerken kısa ve
başka kelimelerin içinde geçebilecek olanlardan kaçının.**

**Sayım dışı kalem okutulursa sistem SESSİZ KALMAZ.** `grup_coz` `haric`
tipiyle döner, hiçbir şey yazmaz ve ekran hangi kuralın kalemi dışarıda
bıraktığını söyler. Eskiden `coz()` bu alana hiç bakmıyordu: ekran yeşil yanıp
"eşleşti" sesi veriyor, ama `sayaclar()` hariç satırları saymadığı için sayaç
dönmüyor, `eksik_kayitlar` da onları atladığı için raporda hiç görünmüyordu.
Kullanıcı elindeki ürünü okutup "tamam" sesini duyuyor, ürün mutabakattan
tamamen buharlaşıyordu. Çıkış yolu Kurulum ekranından kuralı kapatmaktır.

**Uyarı — bu tür değerleri kendi Tiger çıktınızda doğrulayın.** Örnek Ambar 1
raporunda `Malzeme Türü` sütunu `TM` (860) ve `TK` (10) kısa kodlarını
döndürüyor; yukarıdaki beş tür deseninin hiçbiri bu veride geçmiyor, yani
o kurallar hiç ateşlemiyor.

### 3.5 Uygulama sayılan ambarın dışına ÇIKMAZ

**Bu bir eksiklik değil, karardır** (2026-08-27). Yeniden tartışılmasın diye
yazılıyor.

Şirkette birden çok depo var ve kayıtlardaki depo bilgisi kirli: bir ürün
Tiger'da Kayseri'de 31 adet görünürken gerçekte Ankara'da 21 adet duruyor.
Uygulamanın bunu "çözmesi" için ambarlar arası arama yapması, "şu ambarda
kayıtlı ama burada bulundu" demesi ve bir transfer önerisi üretmesi gerekirdi.

**Yapmıyoruz.** Sayılan depoda eksikse eksik çıkar, fazlaysa fazla çıkar.
Bütün depolar tek tek sayıldığında kayıtlar kendiliğinden temizlenir: Kayseri
sayımı 31'i eksik gösterir, Ankara sayımı 21'i fazla gösterir, düzeltme Tiger
tarafında yapılır.

Gerekçe: ambarlar arası eşleştirme, uygulamanın **tahmin yürütmediği** tek
kuralını (CLAUDE.md §5, `DEMO_FEEDBACK.md` §4) bozardı. "Bu ürün aslında öteki
depodaki kayıt olabilir" tam olarak kaldırdığımız "bu olabilir" önerisidir,
üstelik ambar sınırını da aşarak.

Sonuç olarak `beklenen` sorgularının hepsi `ambar` filtresi taşır ve taşımaya
devam edecek — `matching.coz`, `ara`, `elle_say`, `reports.rapor_verisi`.

---

## 4. Eşleştirme motoru — çekirdek mantık

### 4.1 Normalizasyon

Her karşılaştırma normalize edilmiş dizeler üzerinden yapılır:

```python
TR = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigguussoocc")
def norm(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).translate(TR).upper())
```

Ayrıca **baştaki sıfırlar** önemlidir: Tiger'da `00008682122630086` durabilir ama
okuyucu `8682122630086` yazar. Karşılaştırmada `lstrip("0")` varyantı da denenmeli.

### 4.2 Tekil okutma çözümleme sırası

Sırayla dene, ilk tutan kazanır:

1. **Birebir seri eşleşmesi** — `norm(okutulan) == beklenen.seri_n` (aynı ambar)
2. **Birebir malzeme kodu** — `norm(okutulan) == norm(beklenen.kod)`
3. **Kod öneki** — biri diğerinin başında geçiyorsa, her iki taraf da ≥8 karakter
   (`ARK1250LS5A1` ⊂ `ARK1250LS5A1ATR8641924`)
4. **Öğrenilmiş eşleşme** — `eslesme` tablosunda kayıtlı mı
5. **İçerme** — okutulan (≥6 karakter) bir **kirli** kaydın içinde geçiyor mu,
   ve o kaydın malzeme kodundan farklı mı
6. **UPC** — 12/13 hane, checksum geçerli → geçerli barkod ama tanınmıyor
7. Hiçbiri → bilinmiyor

### 4.3 Kirli kayıt tespiti

```
boşluk içeriyor                                  -> kirli
SAYIM|SAYIN|STOK|CIKAN|DENEME|FAZLA|TEST|PROJE|DEPO|BAKIM geçiyor -> kirli
malzeme koduyla başlıyor (kod uzunluğu > 3)      -> kirli
25 karakterden uzun                              -> kirli
```

### 4.4 Grup mantığı (ayraç barkodu)

Sahada durmamak için tasarlandı. Kullanıcı bir ürünün tüm barkodlarını okutur,
sonra `##SONRAKI##` komut barkodunu okutur. O ana kadarki okutmalar **tek ürün**
sayılır ve birlikte çözümlenir.

```
grup = [okutma1, okutma2, ...]
her okutmayı ayrı çöz

eğer gruptan biri SERİ olarak eşleşti:
    -> o kayıt sayıldı olarak işaretlenir
    -> gruptaki TANINMAYAN barkodlar bu malzemeye bağlanıp öğrenilir

değilse eğer gruptan biri KOD/ÖĞRENİLMİŞ olarak eşleşti:
    malzeme izleme='seri' ise:
        o malzemede açık KİRLİ slot varsa -> slot doldurulur (Tiger düzeltmesi)
        yoksa                             -> ONAY KUYRUĞU (fazla_onay)
    izleme='lot' veya 'yok' ise:
        -> adet +1 (veya kullanıcıdan adet iste)
    her durumda tanınmayan barkodlar öğrenilir

hiçbiri eşleşmedi:
    -> KUYRUĞA atılır, kullanıcı durdurulmaz
```

Öğrenme döngüsü budur: bir ürünün P/N'i ve UPC'si aynı grupta okutulduğunda,
tanınmayan UPC tanınan P/N'in malzemesine bağlanır ve kalıcı kaydedilir.

**Grupta İKİ FARKLI beklenen seri kaydı eşleşirse bu bir çelişkidir.** Tek
cihazın üstünde Tiger'daki iki ayrı seri kaydına eşleşen iki barkod olamaz;
bu ancak `##SONRAKI##` unutulduğunda olur — sahadaki en olası hata.

Eskiden ilk eşleşme alınıp **gerisi sessizce atılıyordu**: üç cihaz okutuluyor,
sayaç 1 artıyor, ekran yeşil yanıyor, ses normal. Kalan iki cihaz raporda
"eksik" çıkıyor ve gerçekten depoda olmayan bir üründen ayırt edilemiyordu
(2026-08-27, çalışan uygulamada üretildi).

Artık **hepsi sayılır** — her cihaz kendi grup numarasıyla ayrı satır olur —
ve ekran sarı uyarı verir. Tanınmayan barkodlar bu dalda **öğrenilmez**:
hangi cihaza ait oldukları belirsiz ve yanlış malzemeye bağlanan bir barkod
gelecek yılın sayımına taşınır (§12.6 ile aynı gerekçe).

Ölçüt "iki seri eşleşmesi" değil **iki FARKLI `beklenen.id`**: aynı kaydın iki
barkodu (büyük/küçük harf, baştaki sıfır varyantı) tek cihazdır.

**Tiger'a önerilecek seri numarası UPC OLAMAZ.** Perakende barkodu o malzemenin
her adedinde aynıdır; seri numarası tek cihaza aittir. `slot` dalı eskiden
düpedüz `max(bilinmeyen, key=len)` diyordu ve UPC çoğu zaman gerçek S/N'den
uzun: `0WGP72 + 198701689928 + W3S2000G7745` grubunda Tiger'a
`0WGP72SAYIM1 -> 198701689928` yazılıyordu — o malzemenin 21 cihazına aynı
"tekil" numara. Aynı eleme `reports._yeni_seri` içinde zaten vardı, `slot`
dalı tek başına onu kullanmıyordu.

Karar `matching._sn_karar`'da, tek yerde:

```
UPC'ler elenir
0 aday  -> öneri yok (`sn_yok`), sayım yine işlenir
1 aday  -> sorusuz kullanılır          <- sahadaki en sık akış
2+ aday -> geçici olarak en uzunu yazılır ve KULLANICIYA SORULUR
```

Soru sayımı **durdurmaz**: kayıt zaten yazılmıştır, belirsiz olan yalnızca
Tiger'a hangi değerin önerileceği. Adaylar `okutma.sn_adaylar`'da bekler,
`##BITIR##` cevaplanmayanları uyarı olarak listeler ve Tiger Düzeltme sekmesi
dipnotta "bu satırlarda değer uygulama tarafından seçildi" der.

**Aynı seri numarası bu oturumda ikinci kez okutulamaz.** Kirli slot doldurulan
gerçek S/N `eslesme`'ye de öğreniliyor (kutudaki bütün barkodlar kaydedilsin
diye — bilinçli karar, kullanıcı isteği). Ama o öğrenme, aynı cihazın S/N'i
kazara ikinci kez okutulduğunda 4. adımdan `ogrenilmis` olarak geçip
malzemenin **bir sonraki** kirli slotunu dolduruyordu: tek cihaz iki kez
sayılıyor, hiçbir uyarı çıkmıyordu. Temiz kayıtlarda bu korumayı 1. adım zaten
veriyordu (`tekrar`); kirli kayıtlarda karşılığı yoktu — yani deponun tam da
yarısında. `coz()` 3b adımı bu oturumun `okutma.yeni_seri` değerlerine bakıp
`tekrar` döner ve hangi slota yazıldığını söyler.

**Fazla, onaydan geçmeden oluşmaz.** Kirli slot bulunamayan dal eskiden sessizce
"fazla" yazıyordu; demo sayımında bunun yanlış olduğu görüldü
(`DEMO_FEEDBACK.md` §5). O dala düşmek "stokta yok" demek değil, **"Tiger'daki
seri numaralarıyla eşleşmedi"** demektir — malzemenin sayılmamış *temiz*
satırları dururken de oraya düşülür. Artık kayıt `kuyruk` tablosuna
`tur='fazla_onay'` ile yazılır ve kullanıcı üç cevaptan birini verir: doğru
kaydı seç · gerçekten fazla · sonra çöz. Fazla kaydı yalnızca bu onaydan ve
`##FAZLA##` komutundan doğar.

**Bir grubun BÜTÜN barkodları `okutma.ham`'da saklanır**, `" + "` ile
birleşik. Grup zaten tek üründür; okutulan her barkod o cihazın denetim izidir.

2026-08-27'ye kadar `eslesti` dalı yalnızca eşleşen seri numarasını, `slot`
dalı yalnızca tek bir adayı yazıyordu. Sonuç: ürünün üstündeki fabrika barkodu
okutuluyor, kayıt eşleşiyor, ama **barkod kayıttan düşüyordu** — gerçek sayım
denemesinde görüldü (`depo_sayim_bugs_improvements.md` B1). `kuyruk_coz` ve
`kuyruk_fazla` zaten hepsini yazıyordu; üç dal aynı sözleşmede değildi.

Tiger'a önerilecek seri numarası **ayrı sütundadır** (`okutma.yeni_seri`) ve
her yazmada **açıkça doldurulur**; öneri yoksa boş dize yazılır. İkisi tek
alanda durursa — ya da sütun boş bırakılırsa — `ham`'a malzeme kodu da girdiği
için rapor kodu seri no sanıp Tiger'a yazdırır: `kirli_mi(kod, kod)` KİRLİ
döner, yani uygulama tam da temizlemeye çalıştığı deseni üretir. Bu 2026-08-27
denetiminde gerçek veriyle üretildi
(`900-5G144-2200-000 TD SYNNEX 8000USD 2 -> 900-5G144-2200-000`).

Son savunma raporda: **önerilen değerin kendisi kirliyse Tiger'a çıkmaz**,
elenir ve dipnotta sayılır.

**Bir grup bir fazla kaydı üretir — barkod sayısı kadar değil.** Grubun tanımı
zaten budur: kullanıcı bir ürünün üstündeki bütün barkodları (P/N, S/N, UPC,
lot, kendi etiketimiz) okutup `##SONRAKI##` der. Fazla yazılırken barkodlar
`ham` içinde `" + "` ile birleşir (denetim izi), Tiger'a yazılacak tek seri
numarasını `_fazla_seri` seçer, `miktar` 1 kalır.

2026-08-23'e kadar bu kural yalnızca `fazla_onay` dalında uygulanıyordu;
`kuyruk_fazla`'nın normal dalı ve `##FAZLA##` komutu **barkod başına bir satır**
yazıyordu. Sonuç: tek üründen okutulan iki barkod raporda iki ayrı fazla
oluyor, kullanıcıya adı iki kez soruluyor ve eşleştirme ekranı aynı ürünü iki
kez eşleştirmesini bekliyordu. `db.bolunmus_fazlalari_birlestir()` göçü bu
hatayla oluşmuş kayıtları açılışta tek satıra indirir.

Bu, `depo_sayim.py` prototipinden **bilinçli** bir sapmadır (§7).

### 4.5 Komut barkodları

Code128 ile basılır, laminatlı kart olarak sahada taşınır.

| Kod | İşlev |
|---|---|
| `##SONRAKI##` | Grubu kapat ve çözümle |
| `##IPTAL##` | Mevcut grubu sil |
| `##GERIAL##` | Son GRUBU geri al (öğrenilen barkodu unutur, etiketi çözer) |
| `##FAZLA##` | Grubu fazla olarak işaretle |
| `##ATLA##` | Grubu kuyruğa at |
| `##BITIR##` | Oturumu kapat — **iki kez okut** (aşağıya bakın) |
| `##RAF-A1##` | Aktif rafı ayarla (sonraki okutmalar bu rafa yazılır) |
| `##RAF-UST-1##` | Raf adı ASCII'ye katlanır — aşağıya bakın |
| `##ADET-25##` | Sıradaki grubun miktarı — lot / dökme kalemde (§2.4) |
| `##ADET-0##` | Girilen adedi sıfırla |
| `##KILIT##` | Malzeme kodunu kilitle — aşağıya bakın |
| `##KILITAC##` | Kilidi kaldır |
| `##KUTUKAPAT##` | Açık seri takipli kabı kapat (`KUTU_TASARIM.md`) |
| `##YEDEK##` | Yedek parça modunu aç / kapat |

**`##KILIT##` sahadaki en büyük tekrarı kaldırır.** 21 cihazlı bir malzemede
malzeme kodu 21 kez okutuluyordu. Kod bir kez okutulur, `##KILIT##` denir,
ardından yalnızca seri numaraları gelir; grupta kod yoksa kilit devreye girer.

Üç kural:

* Kilit **parametresiz basılır.** Malzeme kodlarının 57'si boşluk ya da Türkçe
  karakter taşıyor (§2.1) ve Code128'e girmiyor — o yüzden kilitlenecek kod
  TAMPONDAN okunur. Arayüz açık kod gönderdiğinde (`##KILIT-<kod>##`) o
  kullanılır; bu biçim yalnızca telefon/PC düğmesinden doğar, karta basılmaz.
* **Elle okutulan kod her zaman kilidi yener.** Yoksa kullanıcı kilidi
  açmadan başka bir ürünü sayamazdı.
* Kilit **grup kapanınca tükenmez** (`##ADET-N##`'den farkı budur) ve
  kilitlenecek kod bulunamazsa **sessiz kalmaz**: `kilit_yok` döner. Sessizce
  kilitlenmemek şart — kullanıcı kilitlendiğini sanıp onlarca seri numarası
  okutur ve hepsi kuyruğa düşerdi.

**Kap AÇMAK için komut yoktur** — kabın kendi `DK-` etiketi o işi yapar
(`KUTU_TASARIM.md`). Seri takipli bir kap okutulunca malzeme kendiliğinden
kilitlenir ve sayaç başlar; ardından yalnızca seri numaraları okutulur.
`##KUTUKAPAT##` kilidi bırakır ve "kapta 150 yazıyordu, 12 okuttun" der —
**uyarır, engellemez**: kaptaki sayı son sayımdan kalma bir ipucudur, gerçek
değil. İki kap aynı anda açık olamaz; yeni kap öncekini kapatır.

**`##YEDEK##` açıkken hiçbir şey ARANMAZ.** Yedek parçalar Tiger'da kayıtlı
değil; aranmaları yalnızca yanlış eşleşme üretiyordu (yedek parçanın üstündeki
üretici kodu başka bir malzemenin önekine takılıp o malzemenin slotunu
dolduruyordu). Mod açıkken grup doğrudan `tip='yedek'` yazılır: öğrenme yok,
kuyruk yok, sayaçlara girmez, kendi rapor sekmesinde durur. `##ADET-N##`
burada geçerlidir — aynı parçadan 20 tane olabilir.

Kilit ve yedek parça modu **ekranda görünmek zorundadır.** İkisi de açık
unutulursa bütün raf yanlış malzemeye ya da yedek parçaya yazılır ve bu ancak
rapor açılınca fark edilir; bu yüzden hem Sayım hem telefon başlığında kalıcı
rozetleri var.

Adet **birikir**: `##ADET-25##` iki kez okutulursa 50 olur. Kartta sabit
değerler basılı (1/5/10/25/50/100), ara değere ancak böyle ulaşılır. Telefondaki
Adet paneli aynı işi yapar ve her sayıyı girer — ikisi de `POST /oturum/{id}/adet`
ile aynı koddan geçer. Adet grup kapanınca (ya da `##IPTAL##` ile) tükenir,
sonraki ürüne sızmaz. **Boş tamponda `##SONRAKI##`'ye basmak adedi yakmaz.**

Seri takipli kalemde adet uygulanmaz — her cihaz Tiger'da ayrı bir satır.
Girilmişse sessizce yutulmaz, sonuçta `adet_yersiz` olarak bildirilir.

**Ürün TANINMAZSA adet kaybolmaz, kuyruk kaydına taşınır** (`kuyruk.adet`).
Sebebi: kuyruğa düşen kaydın malzemesi bilinmiyor, dolayısıyla seri takipli mi
lot mu bilinmiyor — adedin anlamlı olup olmadığına ancak kayıt çözülünce karar
verilebilir. Kayıt fazla olarak kapatılırsa miktar odur; bir malzemeye
bağlanırsa lot/izlemesizde miktar olur, seri takiplide `adet_yersiz` ile
bildirilir. Adet, kayıt çözülmeden önce kuyruk ekranından düzeltilebilir —
kutuda 150 sanılıp 130 çıkabilir.

2026-08-27'ye kadar bu yol yoktu ve **girilen adet sessizce buharlaşıyordu**:
150 girilip tanınmayan bir ürün fazla işaretlendiğinde raporda 1 yazıyordu.
Dahası `##FAZLA##` ve `##ATLA##` adedi tüketmiyordu bile — 150 ayakta kalıp
**sonraki ürüne sızıyordu.**

**Raf adı `norm.raf_adi()` ile temizlenir** ve normalizasyon TEK yerdedir:
`ÜST-1` → `UST-1`, `ön çıkış` → `ON CIKIS`. Türkçe harfler katlanır, sonra
yalnızca `A-Z 0-9 boşluk . _ -` bırakılır.

İki sebep, ikisi de zorunlu:

1. **Code128 ASCII dışını taşımaz.** `ÜST-1` basılamaz; python-barcode
   `IllegalCharacterError` atıyor ve komut kartı ucu 500 veriyordu. Türkçe bir
   depoda `ÜST`, `ÖN`, `ÇIKIŞ` yazmak en doğal şey.
2. **Asıl tuzak bu:** basılan değerle sonradan ELLE yazılan değer aynı olmak
   zorunda. Kart `UST-1` basıp telefondaki kutuya `ÜST-1` yazılırsa uygulama
   bunları **iki ayrı raf** sayardı ve sayımın raf bilgisi bölünürdü.

Temizlikten sonra hiçbir şey kalmazsa (`##RAF-ÇÇ##` değil ama `##RAF-<>##`
gibi) bu bir raf komutu SAYILMAZ; `POST /oturum/{id}/raf` ucu da 400 döner.
Sessizce boş rafa geçmek raf bilgisini yok ederdi.

---

## 5. Rapor çıktısı

7 sekmeli Excel:

| Sekme | İçerik | Kullanım |
|---|---|---|
| Eksik | Okutulmamış beklenen kayıtlar | Tiger sayım eksikliği fişi |
| Fazla | Karşılığı bulunamayan okutmalar (+ **Ürün Adı**) | Tiger sayım fazlası fişi |
| Eşleşen | Başarılı okutmalar + **okutulan barkodlar** (denetim izi) | Kontrol |
| Yedek Parça | Yedek parça modunda okutulanlar (§4.5) | Tiger'a fiş olarak GİRİLMEZ; ayrı karar |
| Tiger Düzeltme | `eski (uydurma) S/N -> yeni (gerçek) S/N` | Seri no düzeltme fişi |
| Barkod Tablosu | `öğrenilen barkod -> malzeme kodu` | Tiger malzeme kartı Barkod alanına yazılır |
| Etiketler | Kendi bastığımız etiketlerin defteri (§12) | Fiziksel etiketi bulmak |

**Ekran sayacı ADET bazındadır, satır değil.** Lot satırı tek satırda çok adet
taşır (§2.4): 77 adetlik bir lotu bir kez okutmak onu bitirmez. Sayaç eskiden
`COUNT(DISTINCT beklenen_id)` kullanıyordu ve o satırı "okutulmuş" sayıyordu —
870 satırın hepsi birer kez okutulduğunda ekran **"OKUTULAN 870 / KALAN 0"**
diyor, rapor ise **202 adet eksik** gösteriyordu. Kullanıcı depodan "bitti"
diye çıkıyor, farkı ancak Excel'i açınca görüyordu (2026-08-27, gerçek veriyle
üretildi). Ölçüt artık `kapasite_kaldi()` ve `ara(sadece_acik=True)` ile aynı;
`sayac.satir` beklenen satır sayısını ayrıca taşır.

`##BITIR##` eksik adetli lot satırlarını ve seri numarası seçilmemiş kayıtları
**yumuşak uyarı** olarak listeler — engellemez, çünkü sayımın kendisi doğru.
Aynı kapı `##BITIR##`'in çift okutma onayıdır: ilk okutma ne olduğunu söyler,
60 saniye içindeki ikincisi kapatır. Komut kartı sahada taşınıyor ve kazara
okutulan tek bir barkod günlerce süren bir sayımı kapatabiliyordu.

**Kapanan oturum geri açılabilir** (`POST /oturum/{id}/yeniden-ac`, Geçmiş
ekranındaki "Yeniden aç"). Yeni oturum açmak çözüm değildir: `beklenen` ile
eşleşme oturum bazlıdır, o ana kadar sayılan her şey "eksik" olurdu. Başka
açık oturum varken ya da o ambar için daha yeni bir oturum açılmışsa reddedilir.

**Rapordan önce eşleştirme adımı var.** Fazla çıkan ürün çoğu zaman eksik
görünen kaydın ta kendisidir, sadece seri numarası tutmamıştır. Eşleştirme
ekranı ikisini yan yana koyar, kararı kullanıcı verir; sistem tahmin yürütmez.
Bağlanan kayıt Eşleşen'e ve — kirli bir slota bağlandıysa — Tiger Düzeltme'ye
düşer.

**Fazla kaydı adsız oluşmaz.** Malzeme kodu bilinmeyen bir ürün fazla
işaretlenirken sistem **ne olduğunu yazdırır** — sunucu adsız kaydı reddeder
(`ad_gerekli`), oturum da adsız fazla varken kapanmaz (`ad_engel`). Sebebi
sahada görüldü: kodu olmayan kaydın açıklaması `beklenen` tablosundan
üretilemiyor, raporda geriye yalnızca seri numarası ve raf kalıyor ve gün
sonunda o satırın hangi ürün olduğu bulunamıyor. **Sisteme ilk kez giren ürün —
kendi bastığımız `DS-` etiketiyle girenler dahil — tam olarak bu yoldan
geçiyor.** Malzeme kodu biliniyorsa (onay kaydı) ad isteğe bağlıdır; açıklama
zaten Tiger'dan geliyor.

**Fazla kaydı KİMLİKSİZ kapanmaz — fotoğrafsız kapanır.** Fazla, sayım
bittikten sonra kimsenin doğrulayamayacağı tek çıktıdır: ürün rafa geri konur,
geriye yalnızca bir satır kalır. O satırı denetlenebilir yapan şey kimliktir:
**`kod` ya da `ad`.** İkisinden biri varsa fotoğraf istenmez.

2026-08-23'e kadar kural "her fazla kaydı fotoğraf ister" şeklindeydi ve
yanlıştı: kullanıcı ürünün ne olduğunu yazdığı hâlde fotoğraf sorulup oturum
kapatılamıyordu. Fotoğraf hâlâ en iyi denetim izidir ve arayüz onu önerir, ama
**engellemez**. Kuyrukta çekilen fotoğraf onay sırasında fazla kaydına taşınır
— aynı fotoğraf iki kez istenmez.

**Elle eşleştirme listesi eksiksiz ve yalnızca AÇIK kayıtları taşır.** İki
kural, ikisi de sahada bozulmuştu (bildirim 2026-08-23):

- *Eksiksiz*: `ara()` sınırsız döner (`limit=0` varsayılan). Eskiden varsayılan
  25'ti, arayüzler 40/50 istiyordu ve **sayfalama yoktu** — 870 satırlık bir
  kümenin ilk sayfası dışına çıkmanın yolu yoktu, kullanıcı listede olmayan
  ürünü tahmin etmeye çalışıyordu. Veri tek seferde gelir, süzme ve kademeli
  çizim istemcide yapılır (`web/src/liste.ts`).
- *Yalnızca açık*: bu oturumda sayılmış/eşleşmiş kayıt listede **görünmez.**
  Filtre değil kural — yoksa iki ayrı fiziksel ürün tek kayda bağlanır.
  Ölçüt `matching.kapasite_kaldi()`: seri takiplide "hiç okutulmamış",
  lot/izlemesizde "sayılan < beklenen" (77 adetlik lotun bir kez okutulmuş
  olması bittiği anlamına gelmez). Sunucu da aynı kuralı uygular —
  `kuyruk_coz()` ve `fazla_bagla()` dolu kayda bağlamayı reddeder.

---

## 6. Yapılmaması gerekenler

**Tiger kayıtlarını silme önerisi verme.** Kullanıcı "hepsini silip sıfırdan
girelim" diye düşünüyor. Bu maliyet katmanlarını, muhasebe izini ve garanti
geçmişini yok eder. Doğru yol Tiger'ın **Ambar Sayımı** ekranı
(`Malzeme Yönetimi > Hareketler > Ambar Sayımı`) ve oradaki **Fiş Oluştur**
butonudur. Uygulama sadece rapor üretir, Tiger'a yazmaz.

**Sayım Miktarı sütunu uyarısı:** Ambar Sayımı ekranı açıldığında Sayım Miktarı,
Fiili Stok ile aynı gelir. Sıfırlanmadan fiş oluşturulursa yanlış stok resmen
onaylanmış olur.

**Faz 4 (şimdilik kapsam dışı):** Tiger REST API ile fiş yazma. Şu an sadece
Excel çıktısı üretiyoruz.

---

## 7. Mevcut durum

**Sahada yapılacaklar `SAHA_TESTI.md`'dedir** — "ne yapmamız lazım?" sorusunun
cevabı o dosyadır.

**"Kodda bilinen açık hata yok" cümlesine güvenmeyin.** 2026-08-27'de yapılan
bağımsız denetim, 413 testin hepsi geçerken **sekiz hata** buldu; beşi sessiz
yanlış sayım üretiyordu (ekranda doğru sonuç, hata ancak Excel'de ya da hiç).
Hepsi kapatıldı ve regresyon testleri yazıldı:

| # | Neydi | Nerede |
|---|---|---|
| B1 | `##SONRAKI##` unutulunca fazla cihazlar sessizce kayboluyordu | §4.4 |
| B2 | UPC, Tiger'a seri numarası diye öneriliyordu | §4.4 |
| B3 | Aynı S/N ikinci kez okutulunca ikinci slotu doldurup çift sayıyordu | §4.4 |
| B4 | Sayaç lot adedini saymıyor, "KALAN 0" derken 202 adet eksik çıkıyordu | §5 |
| B5 | Aynı Tiger raporu ikinci kez yüklenince 870 satır 1740 oluyordu | §3.1 |
| B6 | Kuyruk kaydı çift dokunuşla iki kez çözülüyordu | — |
| B7 | `##GERIAL##` çok satırlı adet grubunu yarım geri alıyordu | §4.5 |
| B8 | Kapanan oturum geri açılamıyordu, `##BITIR##` onay sormuyordu | §5 |

Ders testlerin kendisindeydi: `test_5_kirli_slot_doldurma` ve
`test_kilitliyken_yalniz_seri_okutmak_slot_doldurur` "tanınmayan üretici
barkodu" için sabit olarak GEÇERLİ BİR UPC kullanıyordu ve B2'yi doğru davranış
diye kilitlemişti — `conftest.haric_kur`'daki `LIC` dersinin aynısı. Test
verisi seçerken "bu sabit gerçekte ne demek?" diye sorun.

Uygulama çalışır durumda: `app/` altında FastAPI + SQLite arka uç, `web/`
altında React + Vite + Tailwind arayüz. **447 arka uç testi** (`pytest`) ve
**32 arayüz testi** (`cd web && npm test`) geçiyor.

Arayüz testleri derlemeden yalıtıldı: `tsconfig.json` test dosyalarını dışlar
ve yapılandırma ayrı dosyadadır, çünkü test tarafındaki bir tip hatası sahaya
giden `npm run build` çıktısını kırmamalı. Ayrıntı `MIMARI.md` §7. **Arayüz yeniden
tasarlanıyor** — eski tasarım dili bırakıldı; uyulması gereken kısıtlar ve logo
kuralı §10'da, dağıtım ve kurulum tuzakları §11'de.

**Kod haritası bu dosyada değil, `MIMARI.md`'dedir**: modül listesi, veritabanı
şeması ve göç mekanizması, API uç tablosu, motorun dallanması, arayüz yapısı,
test paketi. Bu dosya alan bilgisidir (Tiger, kirli seri, etiket mantığı),
`MIMARI.md` koddur. **Mimari değişiklikte `MIMARI.md` aynı commit'te
güncellenir** — yeni bir API ucu, tablo, sütun ya da ekran oraya da işlenir.
Sayım dışı kalem gibi *alan* kuralları burada kalır.

`depo_sayim.py` ilk prototiptir (stdlib + openpyxl, tek dosya) ve **eşleştirme
mantığının referansı olarak durur** — `app/matching.py` ile davranışı aynı
olmalıdır. Bilinçli sapmalar burada listelenir, sessizce ayrılmaz:

| Sapma | Neden |
|---|---|
| Kirli slot bulunamayınca fazla değil **onay kuyruğu** (§4.4) | Prototip sessizce fazla yazıyordu; demo sayımında yanlış olduğu görüldü (`DEMO_FEEDBACK.md` §5) |
| **Sabit malzeme kodu kilidi** (`##KILIT##`, §4.5) | Prototipte yok. 21 cihazlı malzemede kod 21 kez okutuluyordu |
| **Yedek parça modu** (`##YEDEK##`, §4.5) | Prototipte yok. Yedek parçalar Tiger'da kayıtlı değil; aranmaları yanlış eşleşme üretiyordu |
| **`okutma.ham` grubun tamamını taşır**, tek değeri değil (§4.4) | Prototipte eşleşen satır yalnızca seri numarasını yazıyordu; okutulan fabrika barkodu kayıttan düşüyordu |
| **Çelişkili grup hepsini sayar** (`tip="coklu"`, §4.4) | Prototip ilk seri eşleşmesini alıp gerisini sessizce atıyordu; `##SONRAKI##` unutulunca cihazlar kayboluyordu |
| **UPC seri numarası adayı değildir** (`_sn_karar`, §4.4) | Prototip en uzun tanınmayan barkodu seçiyordu; perakende barkodu çoğu zaman gerçek S/N'den uzun |
| **Aynı S/N bu oturumda ikinci kez sayılmaz** (`coz()` 3b, §4.4) | Prototipte öğrenilmiş S/N ikinci okutmada bir sonraki kirli slotu dolduruyordu |
| **Sayaç adet bazlı**, satır değil (§5) | Prototipte lot satırı tek okutmayla "bitmiş" sayılıyordu |
| **`##BITIR##` iki okutma ister** (§5) | Prototipte tek okutma kapatıyordu ve kapanan oturum geri açılamıyordu |

`komut_karti.py` Code128 komut barkodu kartı üretir (python-barcode gerektirir).

Etiketi olmayan kalemler için kendi etiketimizi basıyoruz — §12.

Test verisi: `deneme.XLSX` — Tiger'dan alınmış bir Seri/Lot Envanter Raporu
(örnekte Ambar 1, 870 satır). **Depoda yok**, gerçek stok ve tutar içerdiği için
`.gitignore`'da. Test paketi bu dosya olmadan kendini atlar; çalıştırmak için
kendi Tiger çıktınızı proje kökene `deneme.XLSX` adıyla koyun.

---

## 8. Doğrulanmış test senaryoları

Aşağıdaki barkodlar temsilidir; gerçek değerler kendi Tiger çıktınızdadır.
Yeni kod bu senaryoların hepsini geçmelidir:

| Girdi | Beklenen sonuç |
|---|---|
| `210-ACXU-TİP2` + `AB12CD3` + SONRAKI | eşleşti, sunucu |
| `EF45GH6` + SONRAKI | eşleşti, monitör (küçük harf toleransı) |
| `ARK-1250L-S5A1` + `KSA0000000` + SONRAKI | eşleşti, önek eşleşmesi |
| `198701689928` + `EDBP0000000000000` + SONRAKI | kuyruk (ikisi de tanınmıyor) |
| `0WGP72` + yeni S/N + SONRAKI | slot dolduruldu, `0WGP72SAYIM1` düzeltilecek |
| `AB12CD3` ikinci kez | tekrar uyarısı |
| Kuyruk çözüldükten sonra aynı UPC | tanınır (öğrenme kalıcı) |

---

## 9. Telefon monitörü ve canlı güncelleme

**Durum: 2026-08-20'de yazıldı, sunucu tarafı ve derleme doğrulandı; gerçek
telefonda henüz test edilmedi.**

### Ne yapıldı

Telefon artık laptopla aynı arayüzü açmıyor. Ayrı adres: `/telefon`.

- `app/main.py`
  - `index.html` artık `Cache-Control: no-store` ile servis ediliyor. Eski
    belirtinin (telefonun SSE öncesi sayfayı tutması) en olası sebebi buydu.
  - `_birincil_ip()` / `_ag_adresleri()` — laptopta Hyper-V / VirtualBox sanal
    anahtarları da IP taşıyor ve isim çözümlemesinde önce geliyor; telefon
    bunlara ulaşamaz. Yönlendirme tablosuna sorup gerçek Wi-Fi adresini başa
    alıyoruz.
  - `GET /api/telefon-qr.svg` — segno ile QR. segno yoksa 501, arayüz adresi
    yazıyla gösteriyor.
- `web/src/olaylar.ts` — üç katman: (1) SSE, (2) `visibilitychange`'de bir kez
  tazeleme, (3) yedek yoklama (bağlantı yokken 3 sn, varken 15 sn emniyet
  çekimi). Bağlantı hâli `canli | baglaniyor | kopuk` olarak ekrana veriliyor.
- `web/src/ekranlar/Telefon.tsx` — monitör ekranı. Sıralama: sayaçlar → son
  okutma → **kuyruk (yalnızca iş varken)** → laptoptaki grup → son okutmalar →
  ⏸ PC'de çözülecek (en altta, arşiv). Kuyruk paneli boşken hiç çizilmiyor;
  ekranın üstü canlı bilgiye kalsın, iş çıkınca panel oraya giriyor ve kart
  kendini `scrollIntoView` ile gösteriyor. Kuyruğa yeni kayıt düşünce kart açılır,
  telefon titrer, **📷 Foto çek** ve **Sonra çöz** düğmeleri çıkar. Sahadaki
  asıl akış budur: fotoğrafla, ertele, saymaya devam et; çözümü raf bitince
  laptop başında toplu yap. İstenirse ürün eldeyken telefondan da çözülebilir
  (aday / arama / fazla). Karta telefondan kısa not da yazılır — klavye
  kendiliğinden açılmaz, 📝 düğmesiyle çıkar.
- `kuyruk.beklet` sütunu (`app/db.py` EK_SUTUNLAR) — "sonra çözerim" işareti.
  `matching.bekleyen_kuyruk(..., bekletilen_haric=True)` sayesinde **raf kapısı**
  bu kayıtları saymaz (kullanıcı kararını fotoğrafla birlikte zaten verdi),
  **bitir kapısı** ise sayar — oturum kapanmadan kuyruk boşalmalı. Laptoptaki
  Kuyruk ekranında ⏸ rozetiyle işaretli.
  `PATCH /api/kuyruk/{id}` kısmi güncelleme yapar: `not_` ve `beklet` birbirini
  silmez.
- `web/src/TelefonKutu.tsx` — PC'deki 📱 Telefon düğmesinin açtığı QR kutusu.
- `web/src/foto.ts` — `kucult()` Kuyruk ekranından buraya taşındı, iki ekran
  ortak kullanıyor.

Telefonda bilerek yok: Excel yükleme, ambar seçimi, rapor, oturumu bitirme.

**2026-08-22 eki — telefon artık kumanda.** Demo sayımında komut barkodu kartına
uzanmanın sayımı yavaşlattığı görüldü (`DEMO_FEEDBACK.md` §1-2). Telefona sabit
alt çubuk geldi: **Sıradaki ürün** (`##SONRAKI##`) ve **Geri al** (`##GERIAL##`);
sayaçların altına Raf · İptal · Atla · Fazla. Mimari değişmedi — okuyucu
laptopta, komutlar zaten `POST /okut` gövdesinden geçiyor. `##BITIR##` telefonda
hâlâ yok.

### Nerede doğrulandı, nerede doğrulanmadı

| Ortam | Sonuç |
|---|---|
| pytest (193 test) | ÇALIŞIYOR |
| `npm run build` (tsc dahil) | ÇALIŞIYOR |
| `curl /telefon` → `Cache-Control: no-store` | ÇALIŞIYOR |
| `curl /api/telefon-qr.svg` → SVG | ÇALIŞIYOR |
| `curl -N /api/olaylar` | ÇALIŞIYOR |
| `sifirla.bat` (kum havuzunda) | ÇALIŞIYOR |
| **Telefon tarayıcısı** | **TEST EDİLMEDİ** — asıl senaryo |

### Telefonda sırayla denenecekler

*(Bu liste ve sahada denenecek her şey `SAHA_TESTI.md`'de toplandı.)*

1. Sayfayı tamamen kapat, PC'deki QR'ı okut → `/telefon` açılıyor mu, gösterge
   🟢 mi?
2. Laptopta barkod okut → telefon dokunmadan güncelleniyor mu?
3. Telefonu 30 sn kilitle, aç → ekran kendiliğinden tazeleniyor mu?
4. Sunucuyu kapat → 🔴 çıkıyor mu; geri aç → 🟢'ye dönüp veriyi çekiyor mu?
5. Tanınmayan grup okut → telefonda kart + 📷 çıkıyor mu, çekilen foto laptoptaki
   Kuyruk ekranında görünüyor mu?
6. Telefondan aday seç → laptop ekranı anında düşüyor mu?

Hâlâ güncellenmiyorsa: telefonun adres çubuğuna doğrudan
`http://<laptop-ip>:8000/api/olaylar` yaz. Metin akıyorsa sorun arayüzde,
akmıyorsa bağlantı/sunucu tarafında (sunucu `--host 0.0.0.0` ile mi açık,
Windows güvenlik duvarı 8000'i kapatıyor mu).

Bu adımlar geçilmeden README'deki telefon bölümü doğrulanmış sayılmaz.
---

## 10. Arayüz — logo ve tasarımdan bağımsız kısıtlar

**Eski tasarım dili 2026-08-23'te bırakıldı.** Frosted cam kabuk, katmanlı koyu
zemin, hap geometrisi ve `Design.md`'den damıtılan her şey gitti; `Design.md`
depodan silindi.

**Yeni yön: Flat Design + Minimalism & Swiss, açık tema.** Zevkten değil
veriden türetildi — `ui-ux-pro-max` skill'inin `products.csv` dosyasındaki
**"Inventory & Stock Management"** satırı bu ürün tipi için birebir şunu
söylüyor: birincil stil *Flat + Swiss*, ikincil *Accessible & Ethical*,
pano stili *Real-Time Monitoring + Data-Dense*, palet odağı *"functional
neutral + status traffic-light + scanner accent"*.

Pratikte: gölge yok, gradyan yok, cam yok, hap yok. Yarıçap her yerde 2px.
Yüzeyler kenarlıkla ayrılır, yükseklikle değil. Palet §10.2'de.

Aşağıdakiler zevk kararı değil, **depo ve dil koşullarının dayattığı
kısıtlardır.** Hangi görsel yön seçilirse seçilsin geçerlidirler; ihlal
edildiklerinde ortaya çıkan şey çirkin arayüz değil, **bozuk metin, yanlış
okunan seri numarası ve sahada kaybolan zamandır.**

### 10.1 Kısıtlar

| Kısıt | Neden |
|---|---|
| Font **latin-ext subset'i şart** | `ğ Ğ ş Ş İ` latin-ext blokta, `ı` (U+0131) latin blokta. Yalnız latin subset'iyle gelen bir font Türkçe metni bozar — ve bu ancak sahada fark edilir. |
| **CDN yok** | Depo laptopu çevrimdışı çalışabilmeli. Fontlar `web/src/fonts/` altında self-host (`vite.config.ts`). Google Fonts `<link>` kullanılmaz. |
| Sayaçlarda **`tabular-nums`** | Orantılı rakamda sayaç her okutmada zıplar. `.rakam` sınıfı bunun için var. |
| Barkod ve seri numarası **mono** | `0/O` ve `1/l` ayrımı, alt alta hizalanan haneler. Kötü depo ışığında iki seri numarasını karşılaştırmayı mümkün kılan tek şey. |
| **Emoji yok** | Her işletim sisteminde başka çizilir, kendi rengini dayatır, yazı tipi ölçeğine uymaz, uzaktan bakınca renk lekesine döner. Yerine `web/src/ikonlar.tsx` — inline SVG çizgi ikonlar. |
| **Renk tek başına bilgi taşımaz** | Depo aydınlatması kötü. Durum gösteren her yerde ikon + metin birlikte bulunur. |
| **Dokunma hedefi en az 48 px** | Telefon sahada eldivenle kullanılıyor. `stil.css`'teki kural `button, select, input, [role=button]` kapsar — `input` 2026-08-23'te eklendi, o güne kadar `py-2` ile yazılmış girdiler eşiğin altındaydı. |
| **`prefers-reduced-motion` desteklenir** | Hareket ve ışıma efektleri o modda kapanır. |

### 10.2 Palet ve jetonlar

Tek kaynak: `web/src/stil.css` içindeki Tailwind v4 `@theme` bloğu.
`tailwind.config` yok.

**Jeton adları korunur.** 12 dosyada ~518 kullanım yeri bunlara bağlı; yeniden
adlandırma hepsine dokunur. Koyu temadan açığa geçerken yalnızca değerler
değişti.

| Jeton | Değer | Rol | Kontrast |
|---|---|---|---|
| `zemin` | `#f1f5f9` | sayfa zemini **ve girdi kuyusu** | — |
| `panel` | `#ffffff` | kart yüzeyi | — |
| `panel2` | `#f8fafc` | kartın içindeki satır / zebra | — |
| `cizgi` | `#cbd5e1` | ayraç, tablo kuralı | 1.42 |
| `cizgi-kuvvetli` | `#64748b` | **girdi ve form kontrolü çerçevesi** | 4.55 |
| `yazi` | `#0f172a` | ana metin | 17.06 |
| `solgun` | `#475569` | ikincil metin | 7.24 |
| `solgun-hafif` | `#64748b` | pasif düğme, yer tutucu | 4.76 |
| `vurgu` | `#1d4ed8` | birincil eylem, odak halkası | 6.41 |
| `ok` | `#047857` | başarılı | 5.24 |
| `uyari` | `#b45309` | uyarı | 4.80 |
| `hata` | `#b91c1c` | hata | 6.18 |
| `bilgi` | `#0e7490` | bilgi | 4.89 |

Ayrıca beş tint jetonu: `ok-tint #ecfdf5` · `uyari-tint #fffbeb` ·
`hata-tint #fef2f2` · `bilgi-tint #ecfeff` · `vurgu-tint #eff6ff`.

**Bilinmesi gereken dört karar:**

1. **`zemin` hem sayfa zemini hem girdi dolgusu.** 18 `bg-zemin` kullanımının
   18'i de `<input>`. Beyaz kartın içinde 1.10:1 kalıyor — kutunun sınırını
   gösteren tek şey kenarlık, o yüzden girdilerde `cizgi` değil
   **`cizgi-kuvvetli`** kullanılır (metin dışı 3:1 eşiğini geçen tek değer).
2. **Opaklık çarpanı kullanılmaz** (`bg-ok/15`, `border-hata/40`). Açık zeminde
   `/15` ve üstü kontrastı 4.5:1'in altına düşürüyor; amber hiçbir opaklıkta
   geçmiyor (%10'da bile 4.39). Durum dolgusu için tint jetonu, kenarlık için
   düz renk kullanılır — `border-hata/40` beyaz üzerinde 2.08, yani görünmez.
3. **`bilgi` camgöbeği**, mavi değil. Koyu temada `vurgu` (canlı indigo) ile
   `bilgi` (gök mavisi) kolay ayrılıyordu; açık temada ikisi de koyu maviye
   düşüyor ve "öğrenilmiş" / "malzeme kodu" rozetleri aynı listede yan yana
   geliyor.
4. **`-webkit-font-smoothing: antialiased` kullanılmaz**, `body` ağırlığı
   **450**. Antialiasing açık zemin üzerine koyu metinde glifleri inceltiyor
   (koyu temada tam tersi işe yarıyordu); kaldırılmazsa arayüz "soluk" görünür
   ve sebebi palette aranır.

Yazı ölçeği jetonla verilir — `text-mikro` (12px, rozet/etiket) ·
`text-kucuk` (14px, tablo/kod) · `text-govde` (16px, gövde/düğme/girdi).
**11px yasak.** Yarıçap için stok Tailwind ölçeği (`--radius-sm..3xl`) 2px'e
ezildi; `rounded-full` yalnızca `Nokta`'nın bağlantı noktasında kalır.

### 10.3 Şirket logosu

`app.ico` (kaynak) ve `web/public/logo.png` (256 px, ico'dan çıkarıldı).
Sekmede favicon, telefonda ana ekran kısayolu, PC'de sol üstte isimle, Sayım
ekranı ve telefon başlığında yalnız işaret olarak kullanılır.

**Logo yeni tasarımda da korunur ve bu dört yerde de kullanılmaya devam eder.**
Şirket kimliğidir, tasarım tercihi değil — yeniden renklendirilmez, yeniden
çizilmez, yerine tipografik bir marka konmaz.

---

## 11. Dağıtım ve kurulum tuzakları

**Dağıtım git ile yapılır**, USB ile klasör kopyalayarak değil:

```
git clone https://github.com/Guidin9/depo-sayim.git
cd depo-sayim
.\kurulum.bat
```

### 11.1 Klasör kopyalamak neden bozuluyor

Python sanal ortamı, onu yaratan Python'un **mutlak yolunu** `pyvenv.cfg`
içinde taşır:

```
home = C:\Users\<kullanici>\AppData\Local\Programs\Python\Python311
```

Klasör başka bilgisayara kopyalanınca `.venv\Scripts\python.exe` yerinde
durur ama çalışmaz — `No Python at '...'` der. Aynı şekilde
`web/node_modules` platforma özel derlenmiş ikili dosyalar (esbuild, rollup,
lightningcss) içerir ve `tsconfig.tsbuildinfo` mutlak yol tutar.

Hepsi `.gitignore`'da, yani `git clone` bunları hiç taşımaz. Buna rağmen
`kurulum.bat` ve `baslat.bat` artık `.venv`'in **varlığına değil çalışıp
çalışmadığına** bakar (`python -c "import sys"`); bozuksa silip yeniden kurar.

### 11.2 Kurulum uzun sürebilir, sessiz değildir

`pip -q` ve `npm --silent` bayrakları **bilerek kaldırıldı**: çıktıyı
bastırdıkları için yavaş diskte veya antivirüs taramalı makinede kurulum
donmuş gibi görünüyor ve Ctrl+C ile kesiliyordu. Yarım kesilen kurulumda
arayüz derlenmemiş oluyor ve `baslat.bat` "Arayuz derlenmemis" hatası veriyor.

`npm install` **devDependency'leri de kurar** ve kurmak zorunda: derleme
`vite`, `tailwindcss` ve `typescript`'e muhtaç, yani `--omit=dev` bir seçenek
değil. Test araçları (vitest + jsdom + testing-library) da orada duruyor ve
`node_modules`'ü 79,6 MB'tan 113,1 MB'a çıkarıyor. Depo laptopunda kurulum
yavaşsa sebebi budur — bir kez inen bir maliyet, ama beklenmedik değil.

Referans: `python -m venv` temiz bir makinede ~4 saniye. Dakikalar sürüyorsa
klasör USB sürücüde ya da antivirüs her dosyayı tarıyordur.

### 11.3 Batch dosyalarında çıplak ad kullanmayın

`call kisayol.bat` bazı sistemlerde çözümlenmez
(`NoDefaultCurrentDirectoryInExePath=1` ayarlıysa, kurumsal politikalarda ve
UNC yollarında). Her zaman `call "%~dp0kisayol.bat"` yazın.

`.gitattributes` `.bat` dosyalarını CRLF'te tutar — LF satır sonuyla cmd.exe
etiket/goto çözümlemesini bozabilir.

---

## 12. Kendi bastığımız etiketler

**Durum: 2026-08-21'de yazıldı. Gerçek Tiger verisiyle (Ambar 1) doğrulandı;
basılan sayfa gerçek barkod okuyucuyla HENÜZ test edilmedi.**

Depodaki kalemlerin bir kısmında ne üretici parça numarası ne de okunabilir bir
seri numarası var: kablo, fan, dökme parça, `0,70MM TEL` gibi şirket içi kodlu
kalemler. Depoda yazıcı yok, etiketler ofiste toplu basılıp elde götürülüyor.

### 12.1 Üç etiket sınıfı

Bunların hiçbiri `##RAF-A1##` konum barkodu (§4.5) DEĞİLDİR. Dört ayrı soru var:
`##RAF-A1##` "nerede duruyorum", `DM-` "ne bu", `DS-` "hangisi bu",
`DK-` "bu kapta ne var".

| Sınıf | Ne söyler | Kaç FARKLI kod | Nereye |
|---|---|---|---|
| **Malzeme** `DM-000123` | Malzeme kodunun taranabilir hâli | Malzeme kodu sayısı | Raf gözüne / kutuya |
| **Seri** `DS-000045` | Sadece sıralı numara, basılırken hiçbir şeye ait değil | Etiketlenecek adet sayısı | Okutma anında hangi ürüne yapıştıysa ona |
| **Kap** `DK-000007` | Kabın kimliği; içeriği ilk okutmada sorulur ve KALICI kaydedilir | Kap sayısı (depoda 100'den fazla) | Kabın üstüne, kalıcı |

**Kap etiketinin tasarımı ve gerekçeleri `KUTU_TASARIM.md`'dedir.** İki kural
burada da bilinmeli, çünkü ikisi de saha verisinden çıktı:

* Kapta **kalıcı olan malzeme bağıdır, adet değil.** İçerik ayda bir değişiyor,
  sayım yılda bir yapılıyor: kayıttaki adet sayım anında neredeyse her zaman
  bayattır ve sorusuz uygulanmaz (`kutu.TAZELIK_GUN` = 30 gün).
* Kap etiketine **adet basılmaz.** Depoda yazıcı yok; kapta "150" yazıp içinde
  130 olması, hiç sayı yazmamaktan kötüdür — sayan kişi elindekine değil
  etikete inanır.

Malzeme etiketi **kod başına bir numaradır**, ama kaç tanesinin basılacağı
kullanıcının seçimidir (`bas(..., adet=24)`). 160 malzemenin hepsine etiket
gerekmez: çoğunun kutusunda üretici kodu zaten basılıdır. `adet` verilmezse
kalan hepsi basılır; `kapsam="eksik"` (varsayılan) sayesinde her parti kaldığı
yerden sürer.

Sıralama rastgele değil: **kodu hiç barkod olamayanlar başa alınır.** Kodunda
boşluk ya da Türkçe karakter olan malzemenin (`210-ACXU-TİP2`,
`SC9000 CONTROLLER CARD`) kutusunda taranabilir bir kod bulunma ihtimali
yoktur — etiket orada kesin gerekli. `etiketler.kod_barkodlanabilir()` bunu
ayırır; örnek veride Ambar 1'in 160 kodundan 6'sı böyle.

**Boş malzeme havuzu** (`kapsam="bos"`): Tiger'da hiç malzeme kodu OLMAYAN
kalemler için — 5 m kablo gibi. Kod uyduramayız, o yüzden etiket bağlantısız
basılır. Ürüne yapıştırılıp okutulunca grup kuyruğa düşer; bir kez çözüldüğünde
`eslesme`'ye yazılır ve o koddan sonraki her üründe sorusuz tanınır. Bu yüzden
`kuyruk_coz()` yalnızca SERİ etiketini öğrenmekten kaçınır, malzeme etiketini
bilerek öğrenir.

`kopya` ayrı bir eksendir: aynı malzeme üç rafta duruyorsa aynı kod üç kez
basılır (`kopya=3`). Kopya yeni numara tüketmez — yoksa aynı malzeme için depoda
iki farklı kod dolaşırdı; yeniden basım da hep aynı kodu verir.

Seri etiketi basıldığında anonimdir; bağlanma **okutma anında** olur. Bu yüzden
"hangi üründen kaç etiket basayım" sorusu hiç sorulmaz ve fazla basmak israf
değildir.

### 12.2 Sayı vermiyoruz, tavan veriyoruz

`etiketler.ihtiyac()` **üst sınır** döner, hedef değil. Kesin bir sayı vermek
yanıltıcı olurdu: depodaki ürünlerin birçoğunun kutusunda üretici parça numarası
ya da seri numarası zaten basılı — Tiger'a girilmemiş olsa bile. Onlar
okutulduğunda hiç etiket gerekmez. Gerçek ihtiyaç ancak bir raf sayıldıktan
sonra ortaya çıkar.

Bu yüzden ekran karar vermez, öneri yapar; adedi kullanıcı seçer. Doğru kullanım
az basıp devam etmektir: numaralar tükenmez, sonraki basım kaldığı yerden sürer.

Örnek veride Ambar 1: 161 tekil malzeme (6'sı barkod olamayan kod), 394 kirli
seri kaydı → seri etiketi tavanı 394. Gerçekte gereken bunun çok altındadır.

(Bu sayılar bir dönem 160 / 393 yazıyordu: fazla geniş `LIC` kuralı bir ağ
kartını sayım dışı bırakıyordu. Kural `LICENSE`'a çevrilince o satır geri
geldi — §3.4.)

Arayüzde her iki tür için de adet elle girilir; hızlı düğmeler bir sayfa (24),
dört sayfa (96), barkodsuz kod sayısı ve tavan değerini doldurur.

### 12.3 Sahadaki akış

```
##RAF-A1##          rafa gir
DM-000123           malzeme etiketini okut          -> malzeme belli
[üretici S/N]       kutuda/cihazda yazıyorsa okut ya da elle yaz + Enter
DS-000045           gerekiyorsa havuzdan etiket al, ÖNCE OKUT sonra yapıştır
##SONRAKI##         grubu kapat
```

Kutusunda okunabilir bir kod varsa seri etiketi hiç kullanılmaz. Etiketi
yapıştırmadan **önce** okutun: bağlama okutmada olur, yapıştırmada değil.

### 12.4 Kod biçimi

- **Sabit 6 hane.** Değişken uzunlukta bir etiket kodu diğerinin öneki olabilirdi
  ve `coz()` 3. adımı ≥8 karakterde önek eşleşmesi yapıyor
  (`norm("DM-000123") = "DM000123"` tam 8 karakter).
- **Kontrol hanesi yok.** Code128'in kendi kontrol hanesi var; Tiger'a giriş
  Excel'den kopyalanıyor.
- Ön ek `norm.KIRLI_KELIME` desenlerinden hiçbirini içermemeli (`DEPO`, `STOK`,
  `SAYIM`… — `DM`/`DS` temiz), yoksa etiket ertesi yıl kirli sayılırdı.
- `barkod.ETIKET_SVG` modül genişliği 0.45 mm: 9 karakterlik Code128 ≈ 135 modül
  → ~60 mm, yani 70 mm'lik hücrenin neredeyse tamamı. İnce çubuk sayfaya daha çok
  etiket sığdırmaz (hücre sayısı sabit), sadece okumayı zorlaştırır.

### 12.5 Mevcut motora nasıl oturuyor

Yeni rapor mantığı gerekmedi; iki sınıf da var olan Tiger'a-geri-yazma yollarına
düşüyor:

- **Malzeme etiketi** basımda `eslesme`'ye yazılır → `coz()` 4. adımı tanır →
  **Barkod Tablosu** sekmesinde çıkar → Tiger malzeme kartı > Birimler > Barkod
  alanına girilir. Bu, boşluk ya da Türkçe karakter yüzünden hiç barkod olamayan
  57 kodu da (`210-ACXU-TİP2`, `0,70MM TEL`) taranabilir yapar.
- **Seri etiketi** kirli slotu doldurur → **Tiger Düzeltme** sekmesinde
  `BC-U6030SAYIM1 → DS-000045` olarak çıkar.

**Kendi kendini iyileştirir:** `kirli_mi("DS-000045", kod)` **temiz** döner.
Düzeltme Tiger'a işlendikten sonraki sayımda etiket normal bir seri numarası
olarak yüklenir ve `coz()` 1. adımda birebir eşleşir — etiket defterine hiç
ihtiyaç kalmaz.

### 12.6 Motorda değiştirilen üç davranış

Etiketler eklenmeseydi de birer tuzaktı; hepsinin regresyon testi var.

1. `coz()` 1c adımı — bağlanmış seri etiketi burada yakalanmazsa ikinci
   okutulduğunda `bilinmiyor`a düşer ve aynı malzemenin **bir sonraki** kirli
   slotunu doldurur → çift sayım. Gerçek S/N'lerde bu sorun yok çünkü onlar
   Tiger'da yazılı; bizim etiketimiz henüz yalnızca raporda duruyor.
2. `grup_coz()` boş etiketi `bilinmeyen` listesinden çıkarır — yoksa `eslesme`'ye
   yazılır ve tekil cihaza özgü numara malzeme seviyesine yükselir; üstelik
   Barkod Tablosu onu Tiger'ın malzeme kartına yazılacak barkod diye listelerdi.
   `kuyruk_coz()` de aynı ayrımı yapar.
3. `reports._yeni_seri` etiketleri son sıraya atar. `"DM-000123 + DS-000045"`
   grubunda iki parça aynı uzunlukta olduğu için `max()` ilkini — yani **malzeme**
   etiketini — seri numarası diye yazardı.

**Üretici S/N her zaman kazanır** (`yeni_sn` sırası): garanti/RMA izi uydurma
numarayla değiştirilmez. Havuz etiketi yalnızca başka kimlik yokken kullanılır.

**Hiçbir kimlik yoksa malzeme kodu seri numarası diye YAZILMAZ.** Yalnızca
malzeme kodu okutulunca (ne üretici S/N ne DS- etiketi) slot doldurulur ve
sayım işlenir, ama Tiger Düzeltme satırı üretilmez — kullanıcı uyarılır.
Eskiden oraya malzeme kodunun kendisi yazılıyordu: `kirli_mi(kod, kod)` KİRLİ
döner, yani uygulama Tiger'a tam da temizlemeye çalıştığı deseni yazdırıyordu,
üstelik aynı malzemenin birden çok slotu bu yoldan dolarsa aynı numaradan
birden çok tane.

**`##GERIAL##` son SATIRI değil son GRUBU alır.** Bir grup bir üründür (§4.4)
ve adet dalı tek grubu birden çok satıra yazabilir (`matching._adet_dagit`):
`##ADET-5##` çok lotlu bir malzemede 5 ayrı satır açıyor. Satır bazlı geri alma
bunun 4'ünü sayılmış bırakıyordu — kullanıcı geri aldığını sanıyor, 4 adet
sayımda kalıyordu; üstelik `geri` (öğrenme / etiket) yalnızca ilk satırda
durduğu için yan etkiler de temizlenmiyordu. `okutma_sil` bunu zaten grup
bazlı yapıyordu, iki yol aynı sözleşmede değildi (2026-08-27).

**`##GERIAL##` yan etkileri de geri alır.** Okutmanın `eslesme`'ye yazdığı
öğrenme silinir, bağladığı etiket havuza döner (numara tüketilmez, defter
kaydı durur). Yoksa yanlış ürüne okutulup geri alınan bir barkod kalıcı olarak
o malzemeye bağlı kalıyor ve Barkod Tablosu sekmesinden Tiger'ın malzeme
kartına yazılmak üzere listeleniyordu — sessiz, kalıcı, gelecek yıla taşınan
bir bozulma.

Lot / izlemesiz malzemede boş seri etiketi okutulursa bağlama yapılmaz — Tiger'da
adet başına seri saklanmıyor. Sayım yine işlenir, kullanıcı uyarılır.

### 12.7 Sıfırlama uyarısı

Basılmış fiziksel etiket veritabanından uzun ömürlüdür. Sayaç sıfırlanıp aynı
numarayı ikinci kez verirse depoda iki ayrı ürün aynı kodu taşır.

Bu yüzden her basım partisi `data/etiket/basim-<id>.csv` olarak da yazılır.
`sifirla.bat` yalnızca `data\*.db`, `data\yuklenen` ve `data\rapor` taşıdığı için
`data/etiket` hayatta kalır ve `db.baglan()` açılışta defteri geri yükler.
**`data/etiket` klasörünü elle silmeyin.**

Yükleme özeti `etiket_cakisma` alanında, Tiger'da etiket desenine uyup defterde
karşılığı olmayan kayıtları bildirir — defter kaybının sessiz kalmaması için.
