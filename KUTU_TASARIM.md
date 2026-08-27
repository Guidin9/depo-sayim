# Kutu Barkodu ile Toplu Sayım — Tasarım

**Durum: TASARIM. Kod yazılmadı.** (2026-08-27)

Kaynak: `depo_sayim_bugs_improvements.md` I3. Dosya kendi içinde "ayrı bir
tasarım/akış dokümanı gerektirebilir" diyor; bu o doküman.

Kodlanmadan önce sahada okunmalı. Diğer maddeler (B1, I1, I2, I4, I5) depoda
denendikten sonra buraya dönülecek — çünkü aşağıdaki akışın yarısı I2'nin
sabit kod kilidiyle zaten çalışıyor olacak ve **gerçek soru "kutu akışı
gerekiyor mu" değil, "kilit yetmiyor mu"**.

---

## 1. Problem

Raftaki kutu bazlı stoklar: A1 rafında tek üründen 150 adet. Bugün her adet
tek tek okutuluyor. `##ADET-N##` (CLAUDE.md §4.5) bunun bir kısmını çözüyor
ama iki eksiği var:

1. Adet her sayımda yeniden giriliyor — kutunun içinde ne olduğu hiçbir yerde
   yazmıyor.
2. Seri takipli üründe hiç işe yaramıyor: Tiger'da her adet ayrı satır.

## 2. Üç ayrı soru, üç ayrı etiket

Kutu barkodu `##RAF-A1##` DEĞİLDİR ve `DM-`/`DS-` de değildir (CLAUDE.md §12.1).
Dördüncü soruyu cevaplar:

| Etiket | Soru | Kapsam |
|---|---|---|
| `##RAF-A1##` | nerede duruyorum | konum |
| `DM-000123` | ne bu | malzeme tipi |
| `DS-000045` | hangisi bu | tekil cihaz |
| **`DK-000007`** | **bu kapta ne, kaç tane** | **kap** |

## 3. Veri modeli

Yeni tablo — `SEMA`'ya yazılabilir. **Tuzak yalnızca mevcut tabloya *sütun*
eklemekte** (`app/db.py:128-134`); yeni tablo `CREATE TABLE IF NOT EXISTS` ile
eski veritabanlarında da oluşur.

```sql
CREATE TABLE IF NOT EXISTS kutu(
  kod TEXT PRIMARY KEY,      -- normalize: DK000007
  gosterim TEXT,             -- DK-000007
  malzeme TEXT,              -- beklenen.kod
  adet REAL,                 -- kapta kaç tane
  izleme TEXT,               -- 'seri' | 'lot' | 'yok'  (malzemeden kopyalanır)
  raf TEXT,
  ts TEXT, ts_guncelle TEXT,
  oturum INT);               -- ilk tanımlandığı oturum
```

**Kutu KALICIDIR, sayıma özel değildir.** Gerekçe: kutunun içeriği fiziksel bir
gerçek, sayım oturumu değil. Gelecek yıl aynı kutu tek okutmayla sayılır — asıl
kazanç bu. Bedeli: içerik değişince kutu güncellenmeli, yoksa uygulama yanlış
adet sayar. Bu yüzden §6'daki doğrulama adımı zorunlu.

`data/etiket/` altına CSV yedeği yazılır (`DK-` etiketleri de basılmış fiziksel
etiketlerdir — CLAUDE.md §12.7 aynen geçerli).

## 4. Etiket sınıfını eklerken — bilinen tuzak

Kimlik neredeyse bedava: `etiketler.ONEK` (`app/etiketler.py:30`) sözlüğünden
`DESEN`, `bicimle`, `sonraki_no` ve `bas()`'ın doğrulaması türüyor. **Ama iki
yerde ikili varsayım var ve ikisi de sessizce yanlış cevap verir:**

| Yer | Bugünkü hâli | Olması gereken |
|---|---|---|
| `etiketler.etiket_turu` `:59-68` | `DM` değilse **"seri"** döner | `ONEK` üzerinden ters arama |
| `reports.py:188` | `tur=="malzeme" ? "Malzeme" : "Seri"` | üç değeri de karşılayan tablo |

Birincisi kritik: `etiket_turu("DK-000007")` bugün `"seri"` döner, yani
`kuyruk_coz` ve `fazla_bagla` kutu barkodunu **öğrenmemesi gereken bir seri
etiketi sanar**. `reports._yeni_seri` (`:56-78`) de bir `DK-` kodunu seri
numarası adayı sayar — Tiger'a kutu numarası seri no diye yazılırdı.

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
kutu tanımlı, izleme='lot' | 'yok'
    -> bekleyen_adet = kutu.adet, malzeme = kutu.malzeme
    -> mevcut `adet` dalı (_adet_dagit) aynen çalışır

kutu tanımlı, izleme='seri'
    -> oturum.sabit_kod = kutu.malzeme            (I2 kilidi)
    -> "kutu açık: 150'nin 0'ı" sayacı gösterilir
    -> kullanıcı seri numaralarını art arda okutur — I2'nin tam olarak
       çözdüğü akış
    -> ##KUTUKAPAT## ile kapanır; sayılan < beklenen ise UYARIR, örtmez

kutu tanımsız (kutu_bos)
    -> kuyruğa DEĞİL, tanımlama ekranına: hangi malzeme, kaç adet
    -> malzeme seçilince izleme Tiger'dan gelir, kullanıcıya SORULMAZ
```

> **Karar: "seri no mu gerekiyor" diye SORMUYORUZ.** Bug dosyası soruyu
> kullanıcıya yöneltiyor ama cevabı Tiger zaten biliyor
> (`beklenen.izleme`, CLAUDE.md §2.4). Sormak, yanlış cevaplanabilen bir soru
> eklemek olurdu.

Yeni komutlar: `##KUTUKAPAT##` (`norm.KOMUT` + `matching.okut` dalı +
`barkod.KOMUTLAR`).

## 6. Sahadaki akış

```
##RAF-A1##          rafa gir
DK-000007           kutuyu okut
                    -> tanımlıysa:  "M.2 SSD 256GB · 150 adet · serisiz"
                       DOĞRULA / DÜZELT / İÇERİK DEĞİŞTİ
                    -> tanımsızsa:  malzeme ara + adet gir
##SONRAKI##         serisizde biter; serilide kilit açılır ve S/N'ler okutulur
```

**Doğrulama adımı atlanamaz.** Kalıcı kutunun tek riski bu: kapta 150 yazıyor
ama 130 kalmış. Uygulama kutuya körü körüne güvenirse sayım kendi hatasını
onaylar — §7'deki "Sayım Miktarı" tuzağının (CLAUDE.md §6) aynısı. Onay tek
dokunuş, ama zorunlu.

## 7. Etiket basımı

`barkod._etiket()` (`app/barkod.py:151-171`) zaten `s["tur"]`e göre dallanıyor;
`kutu` için bir dal eklenir. Kutu etiketi **büyük basılır** (kap üstünde, uzaktan
okunacak) ve üzerinde insan okunur içerik yazar:

```
DK-000007
M.2 SSD 256GB
150 AD
```

İçerik değişince etiket yeniden basılır — **kod aynı kalır**, yoksa depoda aynı
kap için iki numara dolaşır (CLAUDE.md §12.7'nin aynı gerekçesi).

## 8. Rapora etkisi

Yeni sekme **gerekmez.** Kutudan sayılan adet normal `okutma` satırıdır; Eksik /
Fazla / Eşleşen aynen çalışır. `okutma.not_` alanına `"kutu: DK-000007"` yazılır
— denetim izi.

Tek ek: **Etiketler** sekmesi `DK-` satırlarını "Kutu" olarak göstermeli (§4).

## 9. Kodlamadan önce cevaplanacak

1. Depoda gerçekten kaç kutu var? 10 kutu için bu iş fazla; 200 kutu için şart.
2. I2 kilidi seri takipli kutuyu **zaten** yeterince hızlandırdı mı? Cevap
   evetse §5'in seri dalı hiç yazılmayabilir.
3. Kutu içeriği ne sıklıkla değişiyor? Haftada bir değişiyorsa kalıcı kutu
   yanlış karar — o zaman kutu sayıma özel olmalı.

Bu üç sorunun cevabı **sahadan** gelir, koddan değil.
