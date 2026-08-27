"""SQLite şema ve bağlantı.

Prototipin (depo_sayim.py:53-83) şeması üzerine kuruldu. İki yapısal fark:
  * Yüklemeler sürümlenir (yukleme tablosu) — geçmiş oturumların raporu
    yeni bir Tiger raporu yüklendikten sonra da yeniden üretilebilir.
  * kod_n / seri_n0 alanları yükleme anında yazılır; eşleştirme motoru artık
    Python'da tam tablo taramıyor, indeksli SQL kullanıyor.
"""
import os
import sqlite3

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERI = os.path.join(KOK, "data")
DB_YOLU = os.environ.get("SAYIM_DB") or os.path.join(VERI, "sayim.db")

SEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS yukleme(
  id INTEGER PRIMARY KEY, ts TEXT, dosya_adi TEXT, kaynak TEXT,
  satir INT DEFAULT 0, not_ TEXT);

CREATE TABLE IF NOT EXISTS beklenen(
  id INTEGER PRIMARY KEY, yukleme INT, kod TEXT, kod_n TEXT, aciklama TEXT,
  tur TEXT, ambar TEXT, izleme TEXT, seri TEXT, seri_n TEXT, seri_n0 TEXT,
  seri_aciklama TEXT, miktar REAL, birim TEXT, kirli INT DEFAULT 0,
  kirli_sebep TEXT, haric INT DEFAULT 0, haric_sebep TEXT, kaynak TEXT);
CREATE INDEX IF NOT EXISTS ix_bek_seri  ON beklenen(yukleme, ambar, seri_n);
CREATE INDEX IF NOT EXISTS ix_bek_seri0 ON beklenen(yukleme, ambar, seri_n0);
CREATE INDEX IF NOT EXISTS ix_bek_kod   ON beklenen(yukleme, ambar, kod_n);
CREATE INDEX IF NOT EXISTS ix_bek_izl   ON beklenen(yukleme, ambar, izleme, kirli);
CREATE INDEX IF NOT EXISTS ix_bek_kodex ON beklenen(yukleme, ambar, kod);

CREATE TABLE IF NOT EXISTS haric_kural(
  id INTEGER PRIMARY KEY, tip TEXT, desen TEXT, aktif INT DEFAULT 1,
  varsayilan INT DEFAULT 0, UNIQUE(tip, desen));

-- sabit_kod: "bu malzeme koduna okut" kilidi (I2). Malzeme kodu bir kez
--   okutulur, ardından art arda yalnızca seri numaraları okutulur. Sahada
--   her cihaz için kodu yeniden okutmak sayımın en çok zaman yiyen adımıydı.
--   `bekleyen_adet`in aksine grup kapanınca TÜKENMEZ — açıkça kapatılır.
-- yedek_parca: yedek parça modu (I4). Açıkken okutulan grup veritabanında
--   ARANMAZ, doğrudan `tip='yedek'` yazılır; yedek parçalar Tiger'da kayıtlı
--   değil ve aranması yalnızca yanlış eşleşme üretiyordu.
CREATE TABLE IF NOT EXISTS oturum(
  id INTEGER PRIMARY KEY, yukleme INT, ambar TEXT, basla TEXT, bitir TEXT,
  aktif_raf TEXT, durum TEXT DEFAULT 'acik', bekleyen_adet INT DEFAULT 0,
  sabit_kod TEXT, yedek_parca INT DEFAULT 0);

-- ad: kullanıcının elle yazdığı ürün adı. Tiger'da kaydı olmayan bir ürün
-- fazla işaretlendiğinde `kod` boş kalır ve raporda açıklama üretilemez;
-- isimsiz fazla kaydı sonradan hiçbir işe yaramıyor (DEMO_FEEDBACK.md 3).
-- ham: grubun BÜTÜN barkodları, " + " ile birleşik (denetim izi). Bir grup
--   bir üründür (CLAUDE.md 4.4) — üstündeki P/N, S/N, UPC, lot ve kendi
--   etiketimiz aynı satırda durur. Eskiden `eslesti`/`slot` dalları buraya tek
--   bir değer yazıyordu ve okutulan fabrika barkodu kayıttan düşüyordu.
-- yeni_seri: Tiger'a önerilecek YENİ seri numarası — `ham`'dan ayrı tutulur.
--   İkisi tek alanda olunca `ham`'a malzeme kodunu eklemek Tiger Düzeltme
--   sekmesini bozuyordu (kod seri no sanılıp yazılıyordu, ACIL_PLAN 3).
--   Boşsa Tiger Düzeltme satırı ÜRETİLMEZ (`sn_yok` sözleşmesi).
-- geri: bu okutmanın KENDİ SATIRI DIŞINDA ne yarattığı (JSON).
--   {"ogrenilen": ["198701689928"], "etiket": "DS-000045"}
-- ##GERIAL## bunu okuyup `eslesme` kaydını siler ve etiket bağlamasını çözer.
-- Olmadan geri alma yarım kalıyordu: okutma siliniyor ama öğrenilen barkod
-- kalıcı olarak yanlış malzemeye bağlı kalıyor ve Barkod Tablosu sekmesinden
-- Tiger'ın malzeme kartına yazılmak üzere listeleniyordu.
CREATE TABLE IF NOT EXISTS okutma(
  id INTEGER PRIMARY KEY, oturum INT, ts TEXT, ham TEXT, kod TEXT, seri TEXT,
  miktar REAL DEFAULT 1, beklenen_id INT, tip TEXT, raf TEXT, grup INT,
  not_ TEXT, ad TEXT, geri TEXT, yeni_seri TEXT);
CREATE INDEX IF NOT EXISTS ix_ok_bek  ON okutma(oturum, beklenen_id);
CREATE INDEX IF NOT EXISTS ix_ok_kod  ON okutma(oturum, kod);
CREATE INDEX IF NOT EXISTS ix_ok_grup ON okutma(oturum, grup);

CREATE TABLE IF NOT EXISTS eslesme(
  barkod TEXT PRIMARY KEY, kod TEXT, seri TEXT, ts TEXT);

CREATE TABLE IF NOT EXISTS tampon(
  id INTEGER PRIMARY KEY, oturum INT, ts TEXT, ham TEXT);

-- Karar bekleyen kayıtlar. İki tür var (tur sütunu):
--   'bilinmiyor'  ne seri ne kod tanındı — "bu hangi malzeme?"
--   'fazla_onay'  malzeme tanındı ama karşılığı bulunamadı — "gerçekten fazla mı?"
-- Fazla, bu onaydan geçmeden oluşmaz (CLAUDE.md 4.4).
-- adet: grup kapanırken girilmiş olan ##ADET-N##. Kuyruğa düşen ürünün
--   MALZEMESİ bilinmiyor, dolayısıyla seri takipli mi lot mu bilinmiyor —
--   adedin anlamlı olup olmadığına ancak kayıt çözülünce karar verilebilir.
--   Burada saklanmazsa kullanıcının "150 tane var" bilgisi buharlaşır:
--   `bekleyen_adet` grup kapanırken sıfırlanıyor ve kuyruk satırı onu hiçbir
--   yere yazmıyordu (saha bildirimi 2026-08-27).
CREATE TABLE IF NOT EXISTS kuyruk(
  id INTEGER PRIMARY KEY, oturum INT, ts TEXT, barkodlar TEXT, raf TEXT,
  cozuldu INT DEFAULT 0, not_ TEXT, beklet INT DEFAULT 0,
  tur TEXT DEFAULT 'bilinmiyor', kod TEXT, ad TEXT, adet REAL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_kuy ON kuyruk(oturum, cozuldu);

-- Kuyruk kaydına ve/veya fazla okutmasına eklenen fotoğraflar. Depodaki
-- laptopta kamera olmayabildiği için telefondan da yüklenebilir.
-- okutma: fazla kaydının fotoğrafı. Fazla, sayım bittikten sonra kimsenin
-- doğrulayamayacağı tek çıktıdır (ürün rafa geri konur, geriye bir satır
-- kalır); fotoğraf onu denetlenebilir yapar. Tablo adı korundu — ADD COLUMN
-- göçüyle yeniden adlandırma yapılamıyor.
CREATE TABLE IF NOT EXISTS kuyruk_foto(
  id INTEGER PRIMARY KEY, kuyruk INT, ts TEXT, tur TEXT, boyut INT, veri BLOB,
  okutma INT);
CREATE INDEX IF NOT EXISTS ix_foto ON kuyruk_foto(kuyruk);

-- Kendi bastığımız etiketler (CLAUDE.md 12). Basım partisi ve tekil etiket
-- ayrı tutulur: parti "hangi numaralar kâğıda çıktı"yı, etiket "o numara
-- sonunda neye yapıştı"yı bilir.
CREATE TABLE IF NOT EXISTS basim(
  id INTEGER PRIMARY KEY, ts TEXT, tur TEXT, adet INT,
  ilk TEXT, son TEXT, duzen TEXT, not_ TEXT);

CREATE TABLE IF NOT EXISTS etiket(
  kod TEXT PRIMARY KEY,      -- normalize edilmiş: DM000123 / DS000045
  gosterim TEXT,             -- insan okur hâli: DM-000123
  tur TEXT,                  -- 'raf' | 'birim'
  basim INT, ts TEXT,
  malzeme TEXT,              -- raf: basımda dolu · birim: bağlanınca dolar
  beklenen_id INT,           -- birim: doldurduğu kirli slot
  oturum INT, ts_bagla TEXT, raf TEXT);
CREATE INDEX IF NOT EXISTS ix_etiket_tur ON etiket(tur, malzeme);
"""

# Eski veritabanlarına sonradan eklenen sütunlar.
EK_SUTUNLAR = [
    ("kuyruk", "not_", "TEXT"),
    # Telefondan "sonra çözerim" işareti: fotoğrafı çekildi, ürün bırakıldı,
    # çözümü PC başında toplu yapılacak. Raftan ayrılmayı engellemez.
    ("kuyruk", "beklet", "INT DEFAULT 0"),
    # Fazla artık onaydan geçiyor: 'bilinmiyor' | 'fazla_onay'. Onay kaydı
    # tanınan malzeme kodunu da taşır, kullanıcı neyi onayladığını görsün.
    ("kuyruk", "tur", "TEXT DEFAULT 'bilinmiyor'"),
    ("kuyruk", "kod", "TEXT"),
    ("kuyruk", "ad", "TEXT"),
    # Kuyruğa düşerken girilmiş adet. 0 = girilmedi (1 değil — "girilmedi" ile
    # "1 tane" ayrı şeyler, ikincisi kullanıcının kararı).
    ("kuyruk", "adet", "REAL DEFAULT 0"),
    ("okutma", "grup", "INT"),
    ("okutma", "raf", "TEXT"),
    ("okutma", "ad", "TEXT"),
    # ##GERIAL##'in geri alacağı yan etkiler (öğrenilen barkod, bağlanan etiket).
    ("okutma", "geri", "TEXT"),
    # Tiger'a önerilecek yeni seri numarası. `ham` artık grubun bütün
    # barkodlarını taşıdığı için karar ayrı sütunda durur.
    ("okutma", "yeni_seri", "TEXT"),
    ("kuyruk_foto", "okutma", "INT"),
    ("oturum", "aktif_raf", "TEXT"),
    # Sıradaki grubun adedi (##ADET-25## / telefondaki tuş takımı). Lot ve
    # izlemesiz kalemde 77 adedi 77 kez okutmamak için — CLAUDE.md 2.4.
    # Grup kapanınca sıfırlanır, oturumda kalıcı değildir.
    ("oturum", "bekleyen_adet", "INT DEFAULT 0"),
    # Sabit malzeme kodu kilidi (I2) ve yedek parça modu (I4). İkisi de
    # `bekleyen_adet` gibi oturuma yazılıyor: okuyucu laptopta, düğme telefonda.
    ("oturum", "sabit_kod", "TEXT"),
    ("oturum", "yedek_parca", "INT DEFAULT 0"),
]

# EK_SUTUNLAR'daki bir sütuna dayanan indeksler. SEMA'ya YAZILAMAZLAR.
#
# Sebep: baglan() önce SEMA'yı, sonra goc()'u çalıştırır. Mevcut bir
# veritabanında CREATE TABLE IF NOT EXISTS boşa geçer — tablo eski hâliyle
# durur — ve hemen ardındaki CREATE INDEX henüz var olmayan sütunu isteyip
# "no such column" ile TÜM executescript'i düşürür; goc() hiç çalışamaz ve
# uygulama açılmaz. Yeni sütuna indeks gerekiyorsa buraya yazın.
EK_INDEKS = [
    "CREATE INDEX IF NOT EXISTS ix_foto_ok ON kuyruk_foto(okutma)",
]

# CLAUDE.md 3.4 — sayım dışı kalemler. Kullanıcı Kurulum ekranında açıp kapatır.
HARIC_VARSAYILAN = [
    ("tur", "DESTEK-HP"), ("tur", "YAZILIM"), ("tur", "MİCROSOFT OPEN"),
    ("tur", "HİZMET"), ("tur", "FİKTİF"),
    # "LIC" DEĞİL: desenler norm() üzerinden alt dize olarak aranıyor ve
    # normalize edilmiş metinde kelime sınırı kalmıyor. Gerçek veride
    # "Dual Port 10GB Ethernet S-LIC-E Optical" (bir ağ kartı) lisans sanılıp
    # sayım dışı bırakılıyordu — tüm Ambar 1'de hariç edilen TEK satır oydu.
    ("aciklama", "LICENSE"), ("aciklama", "LİSANS"), ("aciklama", "E-LTU"),
    ("aciklama", "NAKLİYE"), ("aciklama", "KARGO"),
]


def baglan(yol=None):
    """Şeması kurulu, satırları sözlük gibi davranan bağlantı döner."""
    yol = yol or DB_YOLU
    if yol != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(yol)), exist_ok=True)
    # check_same_thread=False: FastAPI eş zamanlı uç noktaları thread havuzunda
    # çalıştırıyor ve bağlantıyı kuran thread ile kullanan thread farklı olabiliyor.
    # Her istek kendi bağlantısını açtığı için paylaşım yok (tek kullanıcı, tek makine).
    c = sqlite3.connect(yol, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(SEMA)
    goc(c)
    bolunmus_fazlalari_birlestir(c)
    lic_kuralini_duzelt(c)
    kurallari_tohumla(c)
    etiketleri_geri_yukle(c)
    c.commit()
    return c


def goc(c):
    """Eski veritabanlarında eksik sütunları tamamlar (veri kaybı olmadan)."""
    for tablo, sutun, tur in EK_SUTUNLAR:
        var = {r["name"] for r in c.execute("PRAGMA table_info(%s)" % tablo)}
        if sutun not in var:
            c.execute("ALTER TABLE %s ADD COLUMN %s %s" % (tablo, sutun, tur))
    # Sütunlar tamamlandıktan SONRA — bkz. EK_INDEKS.
    for sql in EK_INDEKS:
        c.execute(sql)


def bolunmus_fazlalari_birlestir(c):
    """Hatayla barkod başına bölünmüş fazla kayıtlarını tek satıra indirir.

    2026-08-23'e kadar `matching.kuyruk_fazla` ve `##FAZLA##` komutu, bir
    gruptaki HER BARKOD için ayrı bir fazla satırı yazıyordu. Oysa grup tek
    üründür (CLAUDE.md 4.4): kullanıcı bir ürünün üstündeki bütün barkodları
    okutup ##SONRAKI## der. Sonuç: tek ürün raporda N fazla olarak görünüyor,
    adı N kez soruluyor ve eşleştirme ekranı aynı ürünü N kez eşleştirmesini
    bekliyordu.

    Kod düzeldi ama oluşmuş veri duruyor. Bu göç onu toplar:

    - Aynı (oturum, grup) içindeki `tip='fazla'` satırları tek satırda birleşir.
    - `ham` " + " ile birleştirilir — denetim izi korunur, hiçbir barkod
      kaybolmaz.
    - `seri` yeniden seçilir (`matching._fazla_seri` kuralı: UPC değil gerçek
      S/N, kendi etiketimiz son çare).
    - `ad`, `kod`, `not_` ve `raf` dolu olan ilk satırdan alınır.
    - Fotoğraflar hayatta kalan satıra taşınır.
    - Fazla satırlar silinir.

    Yalnızca `tip='fazla'` satırlarına dokunur: `eslesti` kayıtları da grup
    numarası paylaşır ama onlar zaten satır başına bir beklenen kayda bağlı.

    Idempotent: birleşecek grup kalmayınca hiçbir şey yapmaz.
    """
    from .matching import _fazla_seri
    gruplar = c.execute(
        """SELECT oturum, grup FROM okutma WHERE tip='fazla' AND grup IS NOT NULL
           GROUP BY oturum, grup HAVING COUNT(*) > 1""").fetchall()
    for g in gruplar:
        satirlar = c.execute(
            "SELECT * FROM okutma WHERE tip='fazla' AND oturum=? AND grup=? ORDER BY id",
            (g["oturum"], g["grup"])).fetchall()
        kalan, gidenler = satirlar[0], satirlar[1:]

        hamlar, gorulen = [], set()
        for r in satirlar:                       # tekrarlı barkodu iki kez yazma
            for h in str(r["ham"] or "").split(" + "):
                h = h.strip()
                if h and h not in gorulen:
                    gorulen.add(h)
                    hamlar.append(h)
        ilk = lambda alan: next((r[alan] for r in satirlar if r[alan]), None)
        kod = ilk("kod")
        c.execute("UPDATE okutma SET ham=?, kod=?, seri=?, ad=?, raf=?, miktar=1 "
                  "WHERE id=?",
                  (" + ".join(hamlar), kod, _fazla_seri(hamlar, kod), ilk("ad"),
                   ilk("raf"), kalan["id"]))
        for r in gidenler:
            c.execute("UPDATE kuyruk_foto SET okutma=? WHERE okutma=?",
                      (kalan["id"], r["id"]))
            c.execute("DELETE FROM okutma WHERE id=?", (r["id"],))


def lic_kuralini_duzelt(c):
    """Fazla geniş "LIC" hariç kuralını "LICENSE" ile değiştirir.

    `kurallari_tohumla()` yalnızca tablo BOŞKEN çalışır, o yüzden varsayılan
    listesini düzeltmek mevcut veritabanlarına ulaşmıyor. Bu onarım ulaştırır.

    Neden gerekti: kural desenleri `norm()` çıktısında alt dize olarak aranıyor
    ve normalize edilmiş metinde kelime sınırı yok
    ("...ETHERNETSLICOPTICAL"). Üç harflik "LIC" gerçek bir ağ kartını
    (`303-195-100C-001`, EMC Dual Port 10GB Ethernet S-LIC-E) lisans sanıp
    sayım dışı bırakıyordu — üstelik gerçek yazılım lisansları (OEM MICROSOFT
    SQL SERVER) filtreye hiç takılmıyordu. Filtre tam tersini yapıyordu.

    Yalnızca VARSAYILAN kurala dokunur: kullanıcı deseni elle değiştirdiyse
    (`varsayilan=0`) kararı onundur. Değişiklik olursa hariç bayrakları tüm
    yüklemelerde yeniden hesaplanır, yoksa düzeltme bir sonraki yüklemeye
    kadar görünmezdi. Idempotent: LIC kuralı kalmayınca hiçbir şey yapmaz.
    """
    var = c.execute("SELECT id FROM haric_kural WHERE tip='aciklama' AND desen='LIC' "
                    "AND varsayilan=1").fetchone()
    if not var:
        return
    if c.execute("SELECT 1 FROM haric_kural WHERE tip='aciklama' AND desen='LICENSE'"
                 ).fetchone():
        c.execute("DELETE FROM haric_kural WHERE id=?", (var["id"],))
    else:
        c.execute("UPDATE haric_kural SET desen='LICENSE' WHERE id=?", (var["id"],))
    from . import importer
    for r in c.execute("SELECT id FROM yukleme").fetchall():
        importer.haric_uygula(c, r["id"])


def etiketleri_geri_yukle(c):
    """sifirla.bat sonrası etiket defterini data/etiket CSV'lerinden tamamlar.

    Basılmış fiziksel etiket veritabanından uzun ömürlü; sayaç sıfırlanıp aynı
    numarayı ikinci kez verirse depoda iki ayrı ürün aynı kodu taşır.
    """
    from . import etiketler
    try:
        etiketler.csv_geri_yukle(c)
    except OSError:
        pass


def kurallari_tohumla(c):
    if c.execute("SELECT COUNT(*) n FROM haric_kural").fetchone()["n"]:
        return
    c.executemany("INSERT OR IGNORE INTO haric_kural(tip,desen,aktif,varsayilan) "
                  "VALUES(?,?,1,1)", HARIC_VARSAYILAN)
