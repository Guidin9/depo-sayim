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
tek tek okutmak anlamsız — lot okut, adet gir.

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
- Ayrıca açıklamasında `LIC`, `LİSANS`, `E-LTU`, `NAKLİYE`, `KARGO` geçenler
  (tür filtresi bunları yakalamaz — örn. `JW473AAE` Aruba lisansı 460 adet,
  `60007` nakliye 118 adet)

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
        yoksa                             -> FAZLA
    izleme='lot' veya 'yok' ise:
        -> adet +1 (veya kullanıcıdan adet iste)
    her durumda tanınmayan barkodlar öğrenilir

hiçbiri eşleşmedi:
    -> KUYRUĞA atılır, kullanıcı durdurulmaz
```

Öğrenme döngüsü budur: bir ürünün P/N'i ve UPC'si aynı grupta okutulduğunda,
tanınmayan UPC tanınan P/N'in malzemesine bağlanır ve kalıcı kaydedilir.

### 4.5 Komut barkodları

Code128 ile basılır, laminatlı kart olarak sahada taşınır.

| Kod | İşlev |
|---|---|
| `##SONRAKI##` | Grubu kapat ve çözümle |
| `##IPTAL##` | Mevcut grubu sil |
| `##GERIAL##` | Son okutmayı geri al |
| `##FAZLA##` | Grubu fazla olarak işaretle |
| `##ATLA##` | Grubu kuyruğa at |
| `##BITIR##` | Oturumu kapat |
| `##RAF-A1##` | Aktif rafı ayarla (sonraki okutmalar bu rafa yazılır) |

---

## 5. Rapor çıktısı

5 sekmeli Excel:

| Sekme | İçerik | Kullanım |
|---|---|---|
| Eksik | Okutulmamış beklenen kayıtlar | Tiger sayım eksikliği fişi |
| Fazla | Karşılığı bulunamayan okutmalar | Tiger sayım fazlası fişi |
| Eşleşen | Başarılı okutmalar (denetim izi) | Kontrol |
| Tiger Düzeltme | `eski (uydurma) S/N -> yeni (gerçek) S/N` | Seri no düzeltme fişi |
| Barkod Tablosu | `öğrenilen barkod -> malzeme kodu` | Tiger malzeme kartı Barkod alanına yazılır |

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

Uygulama çalışır durumda: `app/` altında FastAPI + SQLite arka uç, `web/`
altında React + Vite + Tailwind arayüz, 136 test geçiyor. Arayüzün tasarım
dili §10'da, dağıtım ve kurulum tuzakları §11'de.

`depo_sayim.py` ilk prototiptir (stdlib + openpyxl, tek dosya) ve **eşleştirme
mantığının referansı olarak durur** — `app/matching.py` ile davranışı aynı
olmalıdır.

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

### Nerede doğrulandı, nerede doğrulanmadı

| Ortam | Sonuç |
|---|---|
| pytest (134 test) | ÇALIŞIYOR |
| `npm run build` (tsc dahil) | ÇALIŞIYOR |
| `curl /telefon` → `Cache-Control: no-store` | ÇALIŞIYOR |
| `curl /api/telefon-qr.svg` → SVG | ÇALIŞIYOR |
| `curl -N /api/olaylar` | ÇALIŞIYOR |
| `sifirla.bat` (kum havuzunda) | ÇALIŞIYOR |
| **Telefon tarayıcısı** | **TEST EDİLMEDİ** — asıl senaryo |

### Telefonda sırayla denenecekler

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

## 10. Arayüz tasarım dili

**Durum: 2026-08-20'de yazıldı. Laptop tarayıcısında gerçek veriyle doğrulandı,
gerçek telefonda test edilmedi (bkz. §9).**

`Design.md` başka bir ürünün ("Measured") tanıtım sayfası promptudur — bizim
projeyle işlevsel ilgisi yoktur, yalnızca **görsel dili** alınmıştır. Damıtılmış
hâli: katmanlı koyu zemin, frosted cam kabuk, hap geometrisi, serif başlık /
sans gövde ayrımı, `cubic-bezier(0.77, 0, 0.18, 1)` ile kademeli giriş.

### 10.1 Değiştirilmeyen kurallar

Design.md'nin bazı kararları depo koşullarıyla çelişir (§ kötü aydınlatma,
uzaktan bakış, eldiven). Aşağıdakiler **bilerek** uyarlanmıştır:

| Design.md | Bizde neden farklı |
|---|---|
| `.liquid-glass` yüzeyi `rgba(255,255,255,0.01)` | Arkasında koyu ürün fotoğrafı olduğu için okunuyor. Bizde arkada ızgara var; o opaklıkta nav metni depoda okunmaz. Panel renginin %72'si kullanıldı. |
| Cam her yerde | Cam **yalnızca kabukta**: nav, panel başlığı, modal, telefon başlığı. Barkod girişi, sayaçlar, okutma şeridi ve liste satırları **opak** kalır. |
| Google Fonts `<link>` | CDN yok (`vite.config.ts`). Fontlar `web/src/fonts/` altında self-host. **latin-ext şart** — `ğ Ğ ş Ş İ` o blokta, `ı` (U+0131) latin bloğunda. |
| İmleç takipli spot ışık + video | Video yok, telefonda imleç yok. Yerine okutma sonucunun rengiyle kısa ambiyans ışıması (`Isima.tsx`) — sesli geri bildirimin görsel eşi. |

### 10.2 CSS sınıfları (`web/src/stil.css`)

| Sınıf | Nerede | Not |
|---|---|---|
| `.cam` | nav, panel kabuğu, modal, bölüm kartı | Gerçek `backdrop-filter`. **Önek sırası kritik**: `-webkit-backdrop-filter` önce, öneksiz sonra — ters yazılırsa Lightning CSS öneksizi eler ve bulanıklık hiç uygulanmaz. |
| `.cam-hafif` | düğmeler | Aynı yüzey ve gradyan kenarlık, `backdrop-filter` YOK. Sayım ekranında ~10 sade düğme var; her biri gerçek cam olsa 10 ayrı backdrop katmanı çıkardı. |
| `.cam-yogun` | telefonun yapışkan başlığı | %94 opak. %72'de altından kayan satırlar camın içinden okunup başlıkla yarışıyordu. |
| `.girdi` | okutma şeridi, tampon satırı | 0.18s / 10px — kısa tutuldu, sahada geri bildirim gecikmesi hataya dönüşüyor. |
| `.kademe` + `.kademe-1..8` | kuyruk kartları | Design.md'nin 100ms + n×60ms kademesi. 8'den sonrası sabit. |
| `.isima` | okutma sonucu | 900ms'de sönen radyal ışık, `mix-blend-mode: screen`. |

`prefers-reduced-motion` altında hepsi kapanır; `.isima` hiç çizilmez.

### 10.3 Emoji kullanma

Arayüzde **emoji yoktur**. Emoji her işletim sisteminde başka çizilir, kendi
rengini dayatır, yazı tipi ölçeğine uymaz ve depo aydınlatmasında uzaktan
bakınca renk lekesine döner. Bunun yerine `web/src/ikonlar.tsx` — 28 çizgi
ikon, 24'lük ızgara, 1.75 kalınlık, `currentColor`. Yeni bir ikon gerekiyorsa
oraya ekleyin; `📷` yazmayın.

`▣ ✓ ⚠ ⛔` gibi geometrik glifler de ikona çevrildi. Metin içindeki `→` okları
kaldı — onlar emoji değil, cümlenin parçası.

**Ama ikon+metin çifti korunur**: `Rozet` ve durum şeritleri hem ikon hem yazı
gösterir. Renk tek başına bilgi taşımaz (§ kötü aydınlatma).

### 10.4 Tipografi

- Başlıklar ve boş durumlar: `font-serif` (Instrument Serif). Boş durumlar italik.
- Gövde: Inter.
- **Sayaçlar serif DEĞİL** — Instrument Serif'te sabit genişlikli rakam
  garantisi yok, sayaçlar her okutmada zıplardı. Inter + `.rakam`
  (`tabular-nums`) kalır; "dev tipografi" karakteri boyutla verilir.

### 10.5 Şirket logosu

`app.ico` (kaynak) ve `web/public/logo.png` (256px, ico'dan çıkarıldı).
Sekmede favicon, telefonda ana ekran kısayolu, PC'de sol üstte isimle,
Sayım ekranı ve telefon başlığında yalnız işaret olarak kullanılır.

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

### 12.1 İki etiket sınıfı

Bunların ikisi de `##RAF-A1##` konum barkodu (§4.5) DEĞİLDİR. Üç ayrı soru var:
`##RAF-A1##` "nerede duruyorum", `DM-` "ne bu", `DS-` "hangisi bu".

| Sınıf | Ne söyler | Kaç FARKLI kod | Nereye |
|---|---|---|---|
| **Malzeme** `DM-000123` | Malzeme kodunun taranabilir hâli | Malzeme kodu sayısı | Raf gözüne / kutuya |
| **Seri** `DS-000045` | Sadece sıralı numara, basılırken hiçbir şeye ait değil | Etiketlenecek adet sayısı | Okutma anında hangi ürüne yapıştıysa ona |

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

Örnek veride Ambar 1: 160 tekil malzeme (6'sı barkod olamayan kod), 393 kirli
seri kaydı → seri etiketi tavanı 393. Gerçekte gereken bunun çok altındadır.

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
