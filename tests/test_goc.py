"""Eski veritabanının yeni sürüme göçü.

Buradaki testlerin hepsi ESKİ şemayla kurulmuş bir dosyadan başlar. Diğer tüm
testler sıfırdan veritabanı kurar ve `CREATE TABLE` her sütunu yazdığı için
göç yolunu hiç denemezler — bu dosya o boşluğu kapatır.

Gerçek bir arıza yüzünden yazıldı: `ix_foto_ok` indeksi SEMA'ya konmuştu ve
mevcut veritabanında "no such column: okutma" ile açılışı tamamen düşürüyordu
(CREATE TABLE IF NOT EXISTS boşa geçiyor, indeks henüz olmayan sütunu istiyor).
"""
import sqlite3

from app import db as dbm

# 2026-08-21 sürümünün ilgili tabloları — yeni sütunlar yok.
ESKI_SEMA = """
CREATE TABLE oturum(
  id INTEGER PRIMARY KEY, yukleme INT, ambar TEXT, basla TEXT, bitir TEXT,
  aktif_raf TEXT, durum TEXT DEFAULT 'acik');
CREATE TABLE okutma(
  id INTEGER PRIMARY KEY, oturum INT, ts TEXT, ham TEXT, kod TEXT, seri TEXT,
  miktar REAL DEFAULT 1, beklenen_id INT, tip TEXT, raf TEXT, grup INT,
  not_ TEXT);
CREATE TABLE kuyruk(
  id INTEGER PRIMARY KEY, oturum INT, ts TEXT, barkodlar TEXT, raf TEXT,
  cozuldu INT DEFAULT 0, not_ TEXT, beklet INT DEFAULT 0);
CREATE TABLE kuyruk_foto(
  id INTEGER PRIMARY KEY, kuyruk INT, ts TEXT, tur TEXT, boyut INT, veri BLOB);
CREATE INDEX ix_foto ON kuyruk_foto(kuyruk);
"""


def _eski_db(tmp_path):
    """İçinde veri olan, eski şemalı bir veritabanı dosyası üretir."""
    yol = str(tmp_path / "eski.db")
    c = sqlite3.connect(yol)
    c.executescript(ESKI_SEMA)
    c.execute("INSERT INTO oturum(id,yukleme,ambar,basla,durum) "
              "VALUES(1,1,'1','2026-08-21T09:00:00','acik')")
    c.execute("INSERT INTO okutma(id,oturum,ts,ham,tip) "
              "VALUES(1,1,'2026-08-21T09:01:00','ESKI-BARKOD','fazla')")
    c.execute("INSERT INTO kuyruk(id,oturum,ts,barkodlar,cozuldu) "
              "VALUES(1,1,'2026-08-21T09:02:00','[\"X\"]',0)")
    c.execute("INSERT INTO kuyruk_foto(id,kuyruk,ts,tur,boyut,veri) "
              "VALUES(1,1,'2026-08-21T09:03:00','image/jpeg',3,?)", (b"jpg",))
    c.commit()
    c.close()
    return yol


def test_eski_veritabani_acilir(tmp_path):
    """Asıl arıza: açılış hiç tamamlanmıyordu."""
    c = dbm.baglan(_eski_db(tmp_path))
    c.close()


def test_yeni_sutunlar_eklenir(tmp_path):
    c = dbm.baglan(_eski_db(tmp_path))
    try:
        def sutunlar(t):
            return {r["name"] for r in c.execute("PRAGMA table_info(%s)" % t)}

        assert {"tur", "kod", "ad", "adet"} <= sutunlar("kuyruk")
        assert {"ad", "yeni_seri"} <= sutunlar("okutma")
        assert "okutma" in sutunlar("kuyruk_foto")
        # I2 kilidi, I4 yedek parça modu ve açık kap oturuma yazılıyor.
        assert {"sabit_kod", "yedek_parca", "acik_kutu", "acik_kutu_ilk"}             <= sutunlar("oturum")
    finally:
        c.close()


def test_kutu_tablosu_eski_veritabaninda_olusur(tmp_path):
    """Yeni TABLO eklemek yeni SÜTUN eklemekten farklı: `CREATE TABLE IF NOT
    EXISTS` eski dosyada da çalışır. Kap defteri ve indeksi kurulmalı ki
    yükseltilen bir kurulumda kap akışı çalışsın."""
    c = dbm.baglan(_eski_db(tmp_path))
    try:
        assert {r["name"] for r in c.execute("PRAGMA table_info(kutu)")} >= {
            "kod", "gosterim", "malzeme", "adet", "izleme", "raf", "ts",
            "ts_guncelle", "oturum"}
        adlar = {r["name"] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        assert "ix_kutu_malzeme" in adlar
        # Eski veritabanında `etiket` tablosu da yoktu; kap defteri listesi
        # onun üstüne kurulu, patlamamalı.
        from app import kutu as kutum
        assert kutum.liste(c) == []
    finally:
        c.close()


def test_ek_indeksler_kurulur(tmp_path):
    """Göç edilen sütuna dayanan indeks, sütun eklendikten sonra kurulmalı."""
    c = dbm.baglan(_eski_db(tmp_path))
    try:
        adlar = {r["name"] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        assert "ix_foto_ok" in adlar
    finally:
        c.close()


def test_mevcut_veri_korunur(tmp_path):
    """Göç veri kaybetmemeli — sayım geçmişi ve fotoğraflar yerinde kalsın."""
    c = dbm.baglan(_eski_db(tmp_path))
    try:
        assert c.execute("SELECT ham FROM okutma WHERE id=1").fetchone()["ham"] \
            == "ESKI-BARKOD"
        assert c.execute("SELECT veri FROM kuyruk_foto WHERE id=1").fetchone()["veri"] \
            == b"jpg"
        # eski kuyruk kaydı varsayılan türü alır
        q = c.execute("SELECT * FROM kuyruk WHERE id=1").fetchone()
        assert (q["tur"] or "bilinmiyor") == "bilinmiyor"
        # eski okutmada `yeni_seri` NULL kalır — rapor o satırlarda eski kurala
        # (`_yeni_seri(ham)`) düşer, yoksa geçmiş oturumların Tiger Düzeltme
        # sekmesi boşalırdı.
        assert c.execute("SELECT yeni_seri FROM okutma WHERE id=1"
                         ).fetchone()["yeni_seri"] is None
    finally:
        c.close()


def test_goc_iki_kez_calisabilir(tmp_path):
    """baglan() her açılışta göç ediyor; ikinci açılış hata vermemeli."""
    yol = _eski_db(tmp_path)
    dbm.baglan(yol).close()
    dbm.baglan(yol).close()


# --------------------------------------------- bölünmüş fazla kayıtlarının onarımı
def _bolunmus_db(tmp_path):
    """Hatanın ürettiği veriyi taşıyan bir veritabanı.

    Tek üründen okutulan iki barkod, aynı grupta İKİ ayrı fazla satırı olarak
    yazılmış — 2026-08-23'e kadarki davranış.
    """
    yol = str(tmp_path / "bolunmus.db")
    c = sqlite3.connect(yol)
    c.executescript(ESKI_SEMA)
    c.execute("ALTER TABLE okutma ADD COLUMN ad TEXT")
    c.execute("ALTER TABLE kuyruk_foto ADD COLUMN okutma INT")
    c.execute("INSERT INTO oturum(id,yukleme,ambar,basla,durum) "
              "VALUES(1,1,'1','2026-08-23T15:00:00','acik')")
    for i, h in enumerate(("198701689928", "EDBP0153231475674"), start=1):
        c.execute("INSERT INTO okutma(id,oturum,ts,ham,miktar,tip,raf,grup,not_,ad) "
                  "VALUES(?,1,'2026-08-23T15:01:00',?,1,'fazla','A1',7,"
                  "'kuyruktan fazla işaretlendi','Siyah 2m güç kablosu')", (i, h))
    # Fotoğraf ikinci satıra bağlı: onarımda kaybolmamalı
    c.execute("INSERT INTO kuyruk_foto(id,okutma,ts,tur,boyut,veri) "
              "VALUES(9,2,'2026-08-23T15:02:00','image/jpeg',3,?)", (b"jpg",))
    # Aynı gruptaki eşleşmiş satır dokunulmadan kalmalı
    c.execute("INSERT INTO okutma(id,oturum,ts,ham,miktar,tip,grup,beklenen_id) "
              "VALUES(5,1,'2026-08-23T15:03:00','BASKA',1,'eslesti',7,42)")
    c.commit()
    c.close()
    return yol


def test_bolunmus_fazla_tek_satira_iner(tmp_path):
    """Tek grup = tek ürün. Hiçbir barkod kaybolmadan birleşmeli."""
    c = dbm.baglan(_bolunmus_db(tmp_path))
    try:
        r = c.execute("SELECT * FROM okutma WHERE tip='fazla'").fetchall()
        assert len(r) == 1
        assert r[0]["ham"] == "198701689928 + EDBP0153231475674"
        assert r[0]["seri"] == "EDBP0153231475674"   # UPC değil gerçek S/N
        assert r[0]["ad"] == "Siyah 2m güç kablosu"
        assert r[0]["raf"] == "A1" and r[0]["miktar"] == 1
        # fotoğraf hayatta kalan satıra taşındı
        assert c.execute("SELECT okutma FROM kuyruk_foto WHERE id=9").fetchone()[0] == r[0]["id"]
        # eşleşmiş satıra dokunulmadı
        assert c.execute("SELECT COUNT(*) FROM okutma WHERE tip='eslesti'").fetchone()[0] == 1
    finally:
        c.close()


def test_onarim_idempotent(tmp_path):
    """İkinci açılışta hiçbir şey değişmemeli."""
    yol = _bolunmus_db(tmp_path)
    c = dbm.baglan(yol)
    once = c.execute("SELECT id,ham,seri FROM okutma ORDER BY id").fetchall()
    c.close()
    c = dbm.baglan(yol)
    try:
        sonra = c.execute("SELECT id,ham,seri FROM okutma ORDER BY id").fetchall()
        assert [tuple(x) for x in once] == [tuple(x) for x in sonra]
    finally:
        c.close()


def test_tek_satirlik_fazlaya_dokunulmaz(tmp_path):
    """Zaten doğru olan kayıt değişmemeli (eski db'de grup NULL)."""
    c = dbm.baglan(_eski_db(tmp_path))
    try:
        r = c.execute("SELECT ham FROM okutma WHERE tip='fazla'").fetchone()
        assert r["ham"] == "ESKI-BARKOD"
    finally:
        c.close()
