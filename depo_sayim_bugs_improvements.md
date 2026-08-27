# Depo Sayım Uygulaması - Bug & Improvement Listesi

*Gerçek depo sayımı denenirken toplanan geri bildirimler*

**Durum (2026-08-27): B1 · I1 · I2 · I4 · I5 çözüldü, 357 test geçiyor.
Hiçbiri gerçek sahada denenmedi.** I3'ün serisiz yarısı kodlandı —
`KUTU_TASARIM.md`. Veri temizliği maddesi karara bağlandı (aşağıda).

---

## 🐛 BUGLAR

### B1. Barkod okutup seri no etiketi eşleştirmede barkod kaydedilmiyor — ✅ ÇÖZÜLDÜ
Ürünün üzerinde fabrika barkodu var, önce o okutuluyor, sonra üzerine bizim seri no etiketimiz yapıştırılıyor. Bu ürün mevcut bir kayıtla eşleştirildiğinde sistem sadece seri numarasını güncelliyor, **barkodu kaydetmiyor/güncellemiyor**.

- **Etki:** Kayıtta ürün eşleşiyor ama barkod alanı boş/eksik kalıyor.
- **Fix yönü:** Eşleştirme (match) akışında barkod da diğer alanlarla birlikte update edilmeli; şu an sadece seri no yazan kod satırı düzeltilecek.
- **Yapıldı:** `grup_coz`'un `eslesti` ve `slot` dalları `okutma.ham` alanına
  grubun **bütün** barkodlarını yazıyor (`kuyruk_coz` zaten böyle yapıyordu —
  üç dal aynı sözleşmede değildi). Tiger'a önerilecek seri numarası ayrı
  sütuna alındı (`okutma.yeni_seri`): tek alanda kalsaydı rapor malzeme kodunu
  seri no sanıp Tiger'a yazdırabilirdi (ACIL_PLAN §3'ün kapattığı hata).
  Eşleşen sekmesine "Okutulan Barkodlar" sütunu eklendi.
  Testler: `tests/test_b1_barkod.py`.

---

## ✨ IMPROVEMENT'LAR

### I1. Okutulan listesinden silme — ✅ ÇÖZÜLDÜ
Bir ürün yanlış okutulup "sonraki" denildikten sonra hata bazen geç fark ediliyor. Okutulanlar listesinde her satıra **sil butonu** eklenmeli, böylece geri dönüp yanlış kaydı listeden çıkarabilelim.

- **Yapıldı:** Sayım ve telefon ekranlarındaki "Son okutmalar" listesinde her
  satırda sil düğmesi. `DELETE /api/okutma/{id}`, varsayılan kapsam **grup**
  (bir grup bir üründür). Yan etkiler `##GERIAL##` ile aynı yoldan geri
  alınıyor: öğrenilen barkod unutulur, etiket havuza döner, kuyruk kaydı
  yeniden açılır. Testler: `tests/test_silme.py`.

### I2. Malzeme kodunu tek okutup ardı ardına seri no okutma modu — ✅ ÇÖZÜLDÜ
Şu an her seri no için malzeme kodu barkodu da tekrar tekrar okutuluyor. Bunun yerine:
- Bir "**Bu malzeme koduna okut**" butonu/modu olsun.
- Malzeme kodu bir kere okutulsun, sonrasında art arda sadece seri no'lar okutulsun ("tak tak" seri girişi), malzeme kodu otomatik olarak o okuduğumuz koda atansın.

- **Yapıldı:** `oturum.sabit_kod` kilidi. Kod okutulur, `##KILIT##` denir
  (ya da PC/telefon düğmesi), sonrasında yalnız seri numaraları okutulur.
  Kilit grup kapanınca tükenmez; elle okutulan kod her zaman kilidi yener;
  kilitlenecek kod bulunamazsa sessiz kalmaz. Testler: `tests/test_sabit_kod.py`.

### I3. Kutu barkodu ile toplu sayım (Büyük Feature) — ✅ SERİSİZ YARISI KODLANDI
Raftaki kutu bazlı stoklar için (örn. A1 rafında bir üründen 150 adet) her ürünü tek tek okutmak yerine:
- Kutuya özel bir **kutu barkodu** oluşturulsun (sistem tarafından üretilebilir/etiketlenebilir).
- Kutu barkodu okutulduğunda sistem sorsun:
  - İçinde hangi üründen kaç adet var?
  - Bu ürün **seri numarası gerektiren** bir ürün mü, yoksa **serisiz** mi?
  - Bu ürün **bizim kayıtlarımızda var mı, yok mu**?
- Seri no gerektiren ürünlerde nasıl bir akış izleneceği (150 adedin seri no'larını tek tek mi okutacağız yoksa sadece adet mi gireceğiz) netleştirilmeli — **ayrıca tasarlanması gereken bir akış.**

> Not: Bu madde diğerlerine göre daha büyük bir iş; ayrı bir tasarım/akış dokümanı gerektirebilir.

**Tasarım `KUTU_TASARIM.md`'de, serisiz yarısı kodlandı** (2026-08-27).
Üç saha sorusunun ikisi cevaplandı: depoda **100'den fazla kap** var ve içerik
**ayda bir** değişiyor. Bu ikincisi tasarımın yarısını değiştirdi: kapta kalıcı
olan **malzeme bağıdır, adet değil** — adet etikete basılmaz, 30 günden eskiyse
ekrana dolu gelmez ve hiçbir zaman sorusuz sayıma yazılmaz.

- **Yapıldı:** `DK-` etiket sınıfı, `kutu` tablosu (+ `data/etiket/kutu.csv`
  yedeği), `coz()` 1d adımı, `grup_coz` kap dalları, `kutu_coz()`, tazelik
  kuralı, kap etiketi basımı (adetsiz), Sayım · Kuyruk · Telefon · Etiket
  ekranlarında paneller, `tests/test_kutu.py`.
- **Kap kodu bir malzeme kodu okutması gibi işleniyor:** ayrı sayım dalı yok,
  sayımı mevcut dallar yapıyor. Kap kodu `eslesme`'ye hiç yazılmıyor — kap bir
  malzeme değil, malzemenin durduğu yer.
- **Bekleyen:** seri takipli dal (kap okutunca otomatik kilit + sayaç) ve
  `##KUTUKAPAT##`. Açık soru: **I2 kilidi seri takipli kabı zaten yeterince
  hızlandırdı mı?** Cevap sahadan gelecek. O zamana kadar seri takipli kap
  kutusuz akışla sayılıyor: kap malzemeyi getirir, kilit elle basılır.

Yukarıdaki üç soru maddesinden ikisi tasarımda **sorulmuyor**: "seri no
gerektiren ürün mü" cevabı Tiger'da (`beklenen.izleme`), "kayıtlarımızda var
mı" ise mevcut `coz()` zincirinin işi.

### I4. Yedek parça modu (ayrı buton) — ✅ ÇÖZÜLDÜ
Yedek parçalar genelde ana veritabanında kayıtlı değil. Bunun için:
- Ayrı bir "**Yedek Parça**" butonu eklensin.
- Barkod (genelde bizim yapıştırdığımız seri no etiketi) okutulduğunda bu buton basılıysa sistem veritabanında **arama yapmadan** doğrudan "yedek parça" olarak kaydetsin.

- **Yapıldı:** `##YEDEK##` / PC · telefon düğmesi. Mod açıkken `coz()` hiç
  çağrılmıyor: öğrenme yok, kuyruk yok, sayaçlara girmiyor. Rapora **ayrı
  "Yedek Parça" sekmesi** eklendi (7. sekme). Testler: `tests/test_yedek.py`.

### I5. Barkodsuz ürünler için manuel giriş — ✅ ÇÖZÜLDÜ
Bazı ürünlerde barkod yok, sadece üzerinde seri no (veya benzeri bir tanımlayıcı) yazılı. Bunun için:
- Telefondan **elle seri no / tanımlayıcı girişi** yapılabilsin.
- Girilen değerle **ürün arama** yapılabilsin.
- Ürün bulunduğunda "**sayıldı**" olarak işaretlensin.

- **Yapıldı:** Telefonda "Elle gir" paneli. Yazılan değer okuyucudan gelmiş
  gibi `POST /okut`'tan geçiyor (eşleştirme ve öğrenme birebir aynı). Tutmazsa
  aynı panelden ürün aranıp listeden seçiliyor — `POST /oturum/{id}/say`.
  Dolu kayda ikinci ürün bağlanamaz. Testler: `tests/test_elle_giris.py`.

---

## ⚠️ VERİ TEMİZLİĞİ SORUNU (Ayrı Konu — Kritik)

Şirkette **birden fazla depo** var ve mevcut kayıtlarda depo bilgisi hatalı girilmiş durumda. Örnekler:
- Bir ürün kayıtta **Kayseri depo - 31 adet** görünüyor ama gerçekte **Ankara depo - 21 adet** olarak duruyor (yanlış depo + yanlış adet).
- Bazı ürünlerde depoda gerçekte **11 adet** varken kayıtta **15 adet** görünüyor (fazla girilmiş).

Bu, uygulama bug'ı değil, **var olan veritabanı kayıtlarının kirli/hatalı olması** sorunu. Sayım uygulamasının asıl amacı da bunu tespit edip düzeltmek olduğu için ayrı ele alınmalı:

### ✅ KARAR (2026-08-27): uygulama ambar dışına çıkmayacak

Sayılan depoda eksikse eksik çıkar, fazlaysa fazla çıkar. Bütün depolar tek tek
sayıldığında kayıtlar kendiliğinden temizlenir — Kayseri sayımı 31'i eksik,
Ankara sayımı 21'i fazla gösterir, düzeltme Tiger tarafında yapılır.

Ambarlar arası arama, "Depo Farkı" sekmesi ve reconciliation **yapılmayacak**;
gerekçesi `CLAUDE.md` §3.5'te. Aşağıdaki dört seçenek kayıt için duruyor.

**Değerlendirilen çözüm yönleri:**
1. **Fiziksel sayım = tek doğru kaynak (source of truth):** Sayım uygulamasında okutulan gerçek adet ve gerçek depo, sistemdeki kayıtla karşılaştırılıp fark raporu (deposu değişen / adedi değişen / fazla-eksik) otomatik üretilsin.
2. **Depo bazlı sayım + reconciliation raporu:** Her depo ayrı ayrı sayılıp, sayım bitince "sistemde X depoda görünen ama fiziksel olarak Y depoda bulunan" ürünler ayrı bir listede çıksın (transfer/düzeltme önerisi olarak).
3. Sayım sonunda üretilecek Excel/rapor çıktısına 3 ayrı sekme/blok eklenebilir:
   - Doğru olanlar (sistemle uyuşan)
   - Depo hatası olanlar (yanlış depoda kayıtlı)
   - Adet hatası olanlar (fazla/eksik girilmiş)
4. Bu farkları toplu şekilde ERP'ye geri yazmak için ayrı bir onay/aktarım adımı (manuel onay sonrası toplu update) düşünülmeli — otomatik direkt yazmak riskli olabilir.

---

## Özet Öncelik Sırası (öneri)
1. **B1** – barkod kaydedilmeme bug'ı (veri kaybına yol açıyor, öncelikli)
2. **I1** – silme butonu (hızlı, düşük efor)
3. **I2** – malzeme koduna toplu okutma modu (verimlilik)
4. **I5** – barkodsuz ürün manuel giriş
5. **I4** – yedek parça modu
6. **Veri temizliği / reconciliation raporu** – tasarım gerektirir
7. **I3** – kutu barkodu sistemi – en büyük kapsamlı iş, ayrı planlama gerekir
