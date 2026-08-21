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

CREATE TABLE IF NOT EXISTS oturum(
  id INTEGER PRIMARY KEY, yukleme INT, ambar TEXT, basla TEXT, bitir TEXT,
  aktif_raf TEXT, durum TEXT DEFAULT 'acik');

CREATE TABLE IF NOT EXISTS okutma(
  id INTEGER PRIMARY KEY, oturum INT, ts TEXT, ham TEXT, kod TEXT, seri TEXT,
  miktar REAL DEFAULT 1, beklenen_id INT, tip TEXT, raf TEXT, grup INT,
  not_ TEXT);
CREATE INDEX IF NOT EXISTS ix_ok_bek  ON okutma(oturum, beklenen_id);
CREATE INDEX IF NOT EXISTS ix_ok_kod  ON okutma(oturum, kod);
CREATE INDEX IF NOT EXISTS ix_ok_grup ON okutma(oturum, grup);

CREATE TABLE IF NOT EXISTS eslesme(
  barkod TEXT PRIMARY KEY, kod TEXT, seri TEXT, ts TEXT);

CREATE TABLE IF NOT EXISTS tampon(
  id INTEGER PRIMARY KEY, oturum INT, ts TEXT, ham TEXT);

CREATE TABLE IF NOT EXISTS kuyruk(
  id INTEGER PRIMARY KEY, oturum INT, ts TEXT, barkodlar TEXT, raf TEXT,
  cozuldu INT DEFAULT 0, not_ TEXT, beklet INT DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_kuy ON kuyruk(oturum, cozuldu);

-- Kuyruk kaydına eklenen fotoğraflar. Depodaki laptopta kamera olmayabildiği
-- için telefondan da yüklenebilir (telefon monitörü, bkz. README).
CREATE TABLE IF NOT EXISTS kuyruk_foto(
  id INTEGER PRIMARY KEY, kuyruk INT, ts TEXT, tur TEXT, boyut INT, veri BLOB);
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
    ("okutma", "grup", "INT"),
    ("okutma", "raf", "TEXT"),
    ("oturum", "aktif_raf", "TEXT"),
]

# CLAUDE.md 3.4 — sayım dışı kalemler. Kullanıcı Kurulum ekranında açıp kapatır.
HARIC_VARSAYILAN = [
    ("tur", "DESTEK-HP"), ("tur", "YAZILIM"), ("tur", "MİCROSOFT OPEN"),
    ("tur", "HİZMET"), ("tur", "FİKTİF"),
    ("aciklama", "LIC"), ("aciklama", "LİSANS"), ("aciklama", "E-LTU"),
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
