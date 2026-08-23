# Demo Geri Bildirimi — Depo Sayım Uygulaması

> Sahada yapılan ilk demo sayımı sırasında alınan notlar. Öncelik sırası kabaca yukarıdan aşağıya.

---

## 1. Mimari Karar: Tüm süreç telefon üzerinden yürüsün

**Karar:** Sistemin gerekli tüm akışının (proses) telefon üzerinden yapılmasına karar verildi.

**Gerekçe:** Demo sayımında barkodu okutan kişi ile telefon dışı bir adım (bilgisayar, kağıt vb.) araya girdiğinde süreç ciddi şekilde uzuyor. Sayım hızını düşüren ana etken bu.

**Etki:** Telefon arayüzü artık ikincil bir görüntüleme ekranı değil, birincil çalışma arayüzü olarak tasarlanmalı.

---

## 2. Feature: Telefon tarafına temel sayım kontrolleri

Telefon ekranına eklenecek:

- **Sıradaki ürüne geçme butonu** — mevcut ürünün sayımını bitirip listedeki bir sonrakine geçiş.
- **Son okutulan barkodu iptal etme / geri alma (undo)** — yanlış okutulan barkodu tek dokunuşla geri alabilmek.

---

## 3. Feature: Elle "fazla" işaretlenen ürünlerde isim sorulsun

Elle fazla olarak işaretlediğimiz ürünlerde sistem **ürün ismini sorsun**, ve girilen bu isim kayıtlara eklenirken de **korunsun / görünür kalsın**.

**Neden:** Seri numarasını sıfırdan okuttuğum bazı depo ürünleri sistemde hiç kayıtlı değil. Bu yüzden bunları fazla olarak işaretlemek zorunda kaldım — ama isimsiz kayıt sonradan hiçbir işe yaramıyor.

---

## 4. Feature: Tanınmayan ürünü telefondan bulma araçları

Şu anda tanınmayan bir ürünü telefondan bulmanın **tek yolu isim ile aratmak**. Bu yeterli değil, ek arama/filtreleme,listeleme, listeden seçme vb. özellikleri gerekiyor.

**İlgili istek:** Otomatik gelen **"bu olabilir" önerisi kaldırılsın** — pratikte hiçbir işe yaramıyor, doğru sonuç vermiyor.

---

## 5. BUG: Bazı ürünler okutulunca otomatik "fazla" işaretleniyor

**Sorun:** Bazı ürünler okutulduğunda sistem bunları hiç sormadan otomatik olarak "fazla" işaretliyor.

**Sorular:**
- Bu kararı neye göre veriyor? Hangi mantık tetikleniyor?
- Neden önce bana "bu kayıtlarda var mı?" diye sormuyor?

**Beklenen davranış:**
- Otomatik fazla işaretleme **yapılmasın**.
- Eğer gerçekten otomatik fazla işaretlenmesi gereken bir durum varsa, **önce kullanıcıya sorsun**: "Stokta karşılığı var mı? Gerçekten fazla mı?"

---

## 6. Feature: Sayım sonu eşleştirme akışı

Sayım bittiğinde, rapor üretilmeden önce bir **eşleştirme adımı** olsun:

1. Sistem, **fazla çıkan stok** ile **listede eksik kalan ürünleri** yan yana kullanıcıya sunsun.
2. "Bu, bu olabilir mi?" mantığıyla **eşleştirmeyi biz manuel yapalım**.
3. Fazla ürünler "fazla" olarak işaretlenmeden önce sistem **fotoğraf çekmeyi istesin**.

**Amaç:** Eksik ve fazla ürünleri görsel olarak karşılaştırıp eşleştirmeyi kolaylaştırmak.

---

## Özet Tablo

| # | Tip | Başlık | Öncelik |
|---|-----|--------|---------|
| 1 | Mimari | Tüm süreç telefon üzerinden | Yüksek |
| 2 | Feature | Sonraki ürün + son barkodu geri alma | Yüksek |
| 3 | Feature | Elle fazla işaretlemede isim sorma | Orta |
| 4 | Feature | Tanınmayan ürün arama araçları / "bu olabilir" kaldır | Orta |
| 5 | **Bug** | Otomatik fazla işaretleme, onay sormadan | Yüksek |
| 6 | Feature | Sayım sonu eksik-fazla eşleştirme + foto | Orta |
