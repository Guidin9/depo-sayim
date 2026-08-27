# Depo Sayım Uygulaması

Barkod okuyucuyla ambar sayımı yapar, Logo Tiger 3'ün Seri/Lot Envanter
Raporu'yla karşılaştırır ve Tiger'da fiş kesmek için 5 sekmeli fark raporu
üretir. Tek kişi, tek makine, internet gerekmez.

Alan bilgisi ve kurallar için `CLAUDE.md`'yi okuyun — bu dosya sadece kurulum ve
kullanım anlatır.

---

## Yeni bilgisayara kurmak

Önce **Python 3.10+** ve **Node.js LTS** kurun (Python kurulumunda
*"Add python.exe to PATH"* kutusunu işaretleyin). Sonra:

```powershell
git clone https://github.com/Guidin9/depo-sayim.git
cd depo-sayim
.\kurulum.bat
```

`kurulum.bat` sanal ortamı kurar, paketleri indirir, arayüzü derler ve
masaüstüne kısayol koyar. Bir kez, internet varken. Sonrası offline çalışır.

> **Kurulum uzun sürebilir — Ctrl+C ile kesmeyin.** Yavaş diskte veya antivirüs
> taramalı bir makinede `npm install` adımı 10+ dakika sürebilir ve arada uzun
> süre yeni satır yazmayabilir. Yarım kesilirse arayüz derlenmemiş kalır ve
> `baslat.bat` "Arayuz derlenmemis" hatası verir; çözüm `kurulum.bat`'ı yeniden
> çalıştırmaktır (bozuk `.venv`'i kendisi temizler).
>
> Referans: `python -m venv` normal bir makinede ~4 saniyedir. Dakikalar
> sürüyorsa klasör büyük ihtimalle **USB sürücüde**; `C:\` altına taşıyın.

> **Klasörü USB ile kopyalamayın.** `.venv` içinde onu yaratan bilgisayarın
> Python yolu, `node_modules` içinde o makineye derlenmiş ikili dosyalar durur;
> kopyalanınca `No Python at ...` hatası verir. `git clone` bunları hiç
> taşımaz. Yine de kopyalanmış bir klasörle karşılaşırsanız `kurulum.bat`
> bozuk `.venv`'i kendisi silip yeniden kurar.

Güncelleme: `git pull` sonra `kurulum.bat`.

## Çift tıkla çalıştırma (depodaki laptop için)

| Dosya | Ne yapar |
|---|---|
| `kurulum.bat` | Sanal ortamı kurar, Python paketlerini indirir, arayüzü derler, masaüstü kısayolunu oluşturur. **Bir kez**, internet varken. |
| `baslat.bat` | Sunucuyu başlatır ve hazır olunca tarayıcıyı açar. Her gün bu. |
| `kisayol.bat` | Masaüstüne ve Başlat menüsüne şirket ikonlu **Depo Sayım** kısayolu koyar. `kurulum.bat` bunu zaten çağırır; kısayol silinirse tek başına da çalıştırılabilir. |
| `sifirla.bat` | Deneme verilerini temizler: oturumlar, okutmalar, kuyruk, fotoğraflar, öğrenilmiş barkodlar, yüklenen Excel'ler. Silmez, `data\yedek-<tarih>` klasörüne taşır. Tiger'a dokunmaz. |

**Sayımı yapan kişi klasörü hiç açmaz:** kurulumdan sonra masaüstündeki
bukalemun ikonlu **Depo Sayım** kısayoluna çift tıklar. Aynı kısayol Başlat
menüsünde de durur — Windows tuşuna basıp "depo" yazmak yeter. Sağ tıklayıp
"Görev çubuğuna sabitle" denirse hep elinin altında olur.

`baslat.bat` uygulama zaten açıksa ikinci sunucu başlatmaz, sadece tarayıcı
sekmesini açar. Durdurmak için siyah pencerede `Ctrl+C` ya da pencereyi kapatın.

## Kurulum (komut satırından)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
cd web; npm install; npm run build; cd ..     # arayüzü app/static'e derler
```

İnternet yalnızca bu adımda gerekir. Sonrasında uygulama tamamen çevrimdışı
çalışır — arayüzde tek bir CDN çağrısı yoktur, yazı tipi sistem yığınıdır.

Arayüzde çalışırken canlı yeniden yükleme isterseniz iki terminal:
`uvicorn app.main:app` ve `cd web; npm run dev` (Vite `/api` isteklerini
8000'e yönlendirir).

## Çalıştırma

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app          # http://127.0.0.1:8000
```

Arayüz henüz derlenmemişse kök adres ne yapılacağını söyler; API `/docs`
altından kullanılabilir.

## Komut satırı (sunucusuz doğrulama)

```powershell
.\.venv\Scripts\python -m app.cli yukle deneme.XLSX     # rapor yükle + özet
.\.venv\Scripts\python -m app.cli ozet                  # son yüklemenin özeti
.\.venv\Scripts\python -m app.cli kurallar              # sayım dışı kuralları
.\.venv\Scripts\python -m app.cli oturumlar             # oturum geçmişi
.\.venv\Scripts\python -m app.cli rapor 1               # 5 sekmeli Excel
```

## Testler

```powershell
.\.venv\Scripts\python -m pytest -q
```

CLAUDE.md 8'deki yedi saha senaryosu `tests/test_senaryolar.py` içinde birebir
test olarak durur. `tests/test_genel_rapor.py` uygulamanın örnek dosyaya değil,
rapor biçimine bağlı olduğunu doğrular (farklı sütun sırası, farklı ambar,
başka sayfa, eş anlamlı başlıklar).

---

## Saha akışı

1. **Kurulum ekranı** — Tiger raporunu yükle (Excel veya JSON), sayım dışı
   kalem kurallarını gözden geçir, ambarı seç.
2. **Sayım** — bir ürünün üstündeki bütün barkodları okut (P/N, S/N, UPC —
   hangisi varsa), sonra `##SONRAKI##` okut. Uygulama o gruptaki barkodların
   aynı ürüne ait olduğunu anlar, tanımadıklarını tanıdıklarına bağlayıp
   kalıcı olarak öğrenir.
3. **Kuyruk** — hiçbiri tanınmayan gruplar sayımı durdurmaz, kuyruğa düşer.
   Kuyruğun gün sonunda çözülemez bir yığına dönüşmemesi için üç kademe var:

   - **Anında aday önerisi** (isteğe bağlı): grup kuyruğa düşerken ekranda 5
     olası malzeme çıkar — bu rafta aynı koddan sayılmış olanlar ve açık
     uydurma kaydı çok olanlar üstte. `Alt+1..5` ile seçilir. Rakam tuşları
     bilerek kullanılmadı: okuyucu barkodu tuş tuş yazıyor, `1` ile başlayan
     her barkod yanlışlıkla seçim yapardı.
   - **Raftan ayrılma kapısı** (zorunlu): `##RAF-XX##` ile başka rafa geçmek
     ya da sayımı bitirmek, o rafta çözülmemiş kayıt varsa engellenir. Ürün
     hâlâ önündeyken çözmek, gün sonunda barkod listesine bakıp hatırlamaya
     çalışmaktan çok daha kolay. Gerçekten çözülemiyorsa "Yine de geç"
     butonuyla bilinçli olarak aşılır.
   - **Not ve fotoğraf** (isteğe bağlı): her kuyruk kaydına kısa not
     yazılabilir ve fotoğraf eklenebilir. Laptop kamerası yoksa telefondan:
     telefon monitörünü açın (aşağıya bakın), kuyruk kartındaki 📷 Foto çek
     düğmesine basın — telefonun kendi kamera uygulaması açılır. Fotoğraf
     yüklenmeden önce 1280px'e küçültülür ve SQLite'ta saklanır.

   Kuyruk ekranı kayıtları **rafa göre gruplar**; hangi rafta okutulduğu ve
   saati her kayıtta yazar.
4. **Rapor** — Excel indir, Tiger'ın `Malzeme Yönetimi > Hareketler > Ambar
   Sayımı` ekranında fiş oluştururken kullan.

### Telefonu monitör yapmak

`baslat.bat` ile başlatın (yerel ağa da açılır), telefonu aynı Wi-Fi'a alın. Laptoptaki sayım
ekranında **📱 Telefon** düğmesine basın: ekranda bir QR kodu ve adres çıkar.
Telefonun kamerasıyla kodu okutun — `http://<laptop-ip>:8000/telefon` açılır.
(Laptopta birden çok ağ adresi varsa — Hyper-V / VirtualBox sanal anahtarları da
IP taşır — kutudaki listeden başka adres seçilebilir.)

Telefon monitörü **sayım yapmaz, sayımı gösterir**:

- Sayaçlar (okutulan / kalan / fazla / kuyruk), son okutma, laptopta o an
  okutulan grup ve son okutmalar listesi — dokunmadan güncellenir.
- **Kuyruğa bir ürün düştüğünde** kart kendiliğinden açılır, telefon titrer ve
  iki düğme çıkar: **📷 Foto çek** ve **Sonra çöz**. Normal akış: fotoğrafı çek,
  "Sonra çöz"e bas, ürünü rafa bırak, saymaya devam et. Kart "⏸ PC'de çözülecek"
  bölümüne iner, ekranı meşgul etmez. Kuyrukta bekleyen eski kayıtlara da aynı
  düğmeden fotoğraf eklenebilir.
- Karta telefondan **kısa not** yazılabilir (📝 Not ekle): "siyah kutu, üst raf,
  HP yazıyor". Klavye kendiliğinden açılmaz, düğmeye basınca çıkar. Not hem
  ertelenenler listesinde hem laptoptaki Kuyruk ekranında görünür.
- Ertelenen kayıt **raf değiştirmeyi engellemez** — fotoğrafını çekip bilerek
  ertelediğin için raf kapısı seni durdurmaz. Ama sayımı bitirme kapısı hepsini
  sayar: oturum kapanmadan kuyruk boşalmalı. Laptoptaki Kuyruk ekranında bu
  kayıtlar **⏸ telefondan ertelendi** rozetiyle görünür; raf bitince başına
  geçip fotoğrafa bakarak toplu çözersin.
- İstersen ürün eldeyken telefondan da çözebilirsin: kartı aç, aday listesinden
  seç ya da kod / açıklama ara. Karşılığı gerçekten yoksa "fazla yaz" (iki
  dokunuşla onaylanır).
- Bilerek **yok**: Excel yükleme, ambar seçimi, rapor, oturumu bitirme. Depoda
  telefona yanlış dokunup sayımı bozmak, kolaylıktan pahalıya gelir. Gerekirse
  ekranın altındaki "tam sürüme geç" bağlantısı normal arayüzü açar.

Üst köşedeki gösterge canlı bağlantının durumunu söyler: 🟢 canlı · 🟡
bağlanıyor · 🔴 kopuk. Bağlantı üç katmanlıdır — SSE ile anında haber, telefon
cebe girip çıkınca bir kez tazeleme, ve bağlantı yokken yedek yoklama. Yani
ekran hiçbir durumda donuk kalmaz.

### Klavye kısayolları (komut kartı elde değilse)

`F2` sıradaki ürün · `Esc` grubu iptal · `Ctrl+Z` son okutmayı geri al ·
`F3` fazla · `F4` atla · `F10` sayımı bitir

Sayım ekranındaki giriş alanı sürekli odakta kalır; yanlışlıkla başka yere
tıklansa bile odak geri döner, dönmezse ekranın üstünde kırmızı uyarı çıkar.
Okutmalar tek sıraya dizilerek gönderilir — okuyucu hızlı bassa bile
`##SONRAKI##` kendinden önceki barkodun önüne geçmez.

### Komut barkodları

| Kod | İşlev |
|---|---|
| `##SONRAKI##` | Grubu kapat ve çözümle |
| `##IPTAL##` | Mevcut grubu sil |
| `##GERIAL##` | Son okutmayı geri al |
| `##FAZLA##` | Grubu fazla olarak işaretle |
| `##ATLA##` | Grubu kuyruğa at |
| `##BITIR##` | Oturumu kapat |
| `##RAF-A1##` | Aktif rafı ayarla |

Yazdırılabilir kart: `POST /api/komut-karti` gövdesinde `{"raflar":["A1","B2"]}`
→ A4 HTML döner, tarayıcıdan Ctrl+P ile bas, kes, laminatla.

---

## Etiketi olmayan ürünler

Kablo, fan, dökme parça gibi kalemlerde ne üretici parça numarası ne de okunabilir
seri numarası var. **Etiket** ekranı bunlar için üç ayrı etiket basar:

| Etiket | Ne söyler | Kaç farklı kod | Nereye |
|---|---|---|---|
| **Malzeme** `DM-000123` | Malzeme kodunun taranabilir hâli | Malzeme kodu sayısı | Raf gözüne / kutuya |
| **Seri** `DS-000045` | Sadece sıralı numara | Etiketlenecek adet kadar | Okutulduğunda hangi ürüne yapıştıysa ona |
| **Kap** `DK-000007` | Kabın kimliği: bu kapta ne var | Kap sayısı | Kabın üstüne, kalıcı |

Bunlar `##RAF-A1##` konum barkodundan farklıdır: `##RAF-A1##` "neredeyim",
`DM-` "ne bu", `DS-` "hangisi bu", `DK-` "bu kapta ne var" der.

### Kap etiketi

Aynı üründen 150 adedin durduğu kutular için. Kap bir kez okutulur, "içinde ne
var" bir kez sorulur ve **kalıcı olarak** kaydedilir — gelecek sayımda kap
malzemesini kendisi söyler, listede aramanız gerekmez.

**Adet her sayımda yeniden sorulur** ve etikete basılmaz. Sebebi basit: kabın
içeriği ayda bir değişiyor, sayım ise yılda bir yapılıyor. Kapta "150" yazıp
içinde 130 olması hiç sayı yazmamaktan kötüdür — sayan kişi elindekine değil
etikete inanır. Uygulama son bilinen adedi gösterir, ama 30 günden eskiyse
alanı boş açar.

Seri takipli üründe kap sayım yapmaz: kap malzemeyi getirir, siz cihazların
seri numaralarını okutursunuz (kodu **kilitlerseniz** her cihazda malzemeyi
tekrar okutmanız gerekmez).

Malzeme etiketi kod başına **bir numaradır**, ama **kaç tane** basacağınızı siz
seçersiniz. 160 malzemenin hepsine etiket gerekmez; bir sayfa basıp devam edin,
sonraki basım kaldığı yerden sürer.

Hangi 24'ünün basılacağı rastgele değil: **kodu hiç barkod olamayan malzemeler
başa alınır.** Kodunda boşluk ya da Türkçe karakter olanın
(`210-ACXU-TİP2`, `SC9000 CONTROLLER CARD`) kutusunda taranabilir kod bulunamaz,
etiket orada kesin gereklidir. Ekrandaki "Barkodsuz" düğmesi tam o sayıyı
doldurur.

Ayrıca kaç **kopya** basacağınızı seçebilirsiniz — aynı malzeme üç rafta
duruyorsa aynı kodu üç kez bastırın. Kopya yeni numara üretmez.

Seri etiketi basılırken **hiçbir ürüne ait değildir** — hangi ürüne ait olduğu
okutulduğunda belli olur. Bu yüzden "A ürününden kaç tane basayım" diye
hesaplamanız gerekmez.

### Kaç tane basmalı

Ekran bir sayı gösterir ama bu **tavandır, hedef değil**. Depodaki ürünlerin
birçoğunun kutusunda üretici kodu ya da seri numarası zaten basılıdır — sisteme
girilmemiş olsa bile. Onlar okutulduğunda etiket hiç gerekmez.

Gerçek ihtiyaç ancak bir raf sayıldıktan sonra belli olur. Bu yüzden **az basıp
devam edin**: bir iki sayfayla başlayın, oran belli olunca gerisini bastırın.
Numaralar tükenmez, sonraki basım kaldığı yerden sürer.

Her iki etiket türünde de adedi elle yazabilir ya da hazır düğmeleri
kullanabilirsiniz: **1 sayfa (24)**, **4 sayfa (96)**, **Barkodsuz**, **Tümü**.

### Depodaki sıra

```
##RAF-A1##      rafa gir
DM-000123       malzeme etiketini okut
[üretici S/N]   kutuda/cihazda yazıyorsa okut ya da elle yaz + Enter
DS-000045       gerekiyorsa etiket al, ÖNCE OKUT sonra yapıştır
##SONRAKI##     grubu kapat
```

Kutusunda okunabilir kod varsa seri etiketi hiç kullanılmaz. Etiketi
yapıştırmadan önce okutun: bağlama okutmada olur.

Çıktı iki düzende: A4 lazer etiket sayfası (3 × 8, 70 × 37 mm — yarım kalmış
sayfayı israf etmemek için "kaçıncı hücreden başla" seçeneğiyle) veya termal rulo
(50 × 25 mm).

Sayım sonunda raporun **Tiger Düzeltme** sekmesi seri etiketlerini
(`BC-U6030SAYIM1 → DS-000045`), **Barkod Tablosu** sekmesi malzeme etiketlerini
Tiger'a girilecek biçimde listeler. Malzeme etiketi, boşluk ya da Türkçe karakter
yüzünden hiç barkod olamayan kodları (`210-ACXU-TİP2`) da taranabilir yapar.

> **`data/etiket` klasörünü silmeyin.** Basılmış etiket veritabanından uzun
> ömürlüdür; basım kayıtları orada tutulur ki `sifirla.bat` sonrası sayaç aynı
> numarayı ikinci kez vermesin.

---

## Yapı

```
app/
  main.py        FastAPI + statik servis
  db.py          SQLite şema (yukleme / beklenen / oturum / okutma / eslesme /
                 kuyruk / etiket / basim)
  norm.py        normalizasyon, UPC checksum, kirli kayıt tespiti, komut barkodları
  matching.py    eşleştirme motoru — prototipten birebir taşındı
  importer.py    Excel + JSON yükleyici, sayım dışı kural motoru
  reports.py     6 sekmeli Excel + arayüz önizlemesi (tek kaynak)
  etiketler.py   kendi bastığımız etiketlerin defteri ve numaralandırması
  barkod.py      komut kartı ve etiket sayfası üretimi
  cli.py         komut satırı
  routers/       API uç noktaları
web/             React arayüz kaynağı
tests/           pytest
data/            sayim.db, yüklenen dosyalar, raporlar, etiket/ basım kayıtları
                 (sürüm dışı — etiket/ klasörünü silmeyin)
```

`depo_sayim.py` ve `komut_karti.py` referans prototiptir, çalışan uygulamanın
parçası değildir — eşleştirme mantığının kaynağı olarak durur.

## Bilinmesi gerekenler

- **Tiger'a hiçbir şey yazılmaz.** Uygulama okur ve rapor üretir.
- **Tiger kayıtlarını silmeyin.** Uydurma seri numaraları Ambar Sayımı ekranından
  düzeltilir; silmek maliyet katmanlarını ve garanti geçmişini yok eder.
- **Sayım Miktarı sütunu:** Ambar Sayımı ekranı açıldığında Sayım Miktarı, Fiili
  Stok ile aynı gelir. Sıfırlanmadan fiş oluşturulursa yanlış stok resmen
  onaylanmış olur.
- Açık oturum SQLite'ta durur; uygulama kapanıp açılsa bile kaldığı yerden
  devam eder (yarım kalan grup dahil).
