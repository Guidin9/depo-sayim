"""Kendi bastığımız etiketler (CLAUDE.md 12).

Malzeme kodları test verisine göre değiştiği için hiçbiri sabit yazılmadı;
her senaryo ihtiyacı olan kaydı veritabanından bulur.
"""
import pytest

from app import etiketler, matching, reports
from app.norm import kirli_mi, norm

from tests.test_api import kurulu, istemci  # noqa: F401

from .conftest import AMBAR


# --------------------------------------------------------------- yardımcılar
def _kirli_malzeme(c, en_az=1):
    """Açık kirli seri slotu `en_az` taneden fazla olan bir malzeme kodu."""
    r = c.execute("""SELECT kod, COUNT(*) n FROM beklenen
                     WHERE yukleme=1 AND ambar=? AND haric=0
                       AND izleme='seri' AND kirli=1
                     GROUP BY kod HAVING n>=? ORDER BY n DESC, kod LIMIT 1""",
                  (AMBAR, en_az)).fetchone()
    if not r:
        pytest.skip("test verisinde %d açık kirli slotu olan malzeme yok" % en_az)
    return r["kod"]


def _lot_malzeme(c):
    r = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=?
                     AND haric=0 AND izleme='lot' ORDER BY id LIMIT 1""",
                  (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde lot izlemeli malzeme yok")
    return r["kod"]


def _malzeme_etiketi(c, kod):
    r = c.execute("SELECT gosterim FROM etiket WHERE tur='malzeme' AND malzeme=?",
                  (kod,)).fetchone()
    return r["gosterim"]


# ------------------------------------------------------------------- numara
def test_seri_basimi_ardisik_numara_verir(c):
    _, s1 = etiketler.bas(c, "seri", adet=20)
    assert len(s1) == 20
    assert s1[0]["gosterim"] == "DS-000001"
    assert s1[-1]["gosterim"] == "DS-000020"
    # ikinci parti kaldığı yerden devam eder, numara tekrar etmez
    _, s2 = etiketler.bas(c, "seri", adet=5)
    assert s2[0]["gosterim"] == "DS-000021"
    assert c.execute("SELECT COUNT(*) n FROM etiket").fetchone()["n"] == 25


def test_malzeme_basimi_her_malzemeye_bir_etiket(c):
    _, s = etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    tekil = c.execute("SELECT COUNT(DISTINCT kod) n FROM beklenen "
                      "WHERE yukleme=1 AND ambar=? AND haric=0",
                      (AMBAR,)).fetchone()["n"]
    assert len(s) == tekil
    assert len({x["gosterim"] for x in s}) == tekil


def test_malzeme_yeniden_basimi_numara_tuketmez(c):
    _, s1 = etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    _, s2 = etiketler.bas(c, "malzeme", kapsam="hepsi", yukleme=1, ambar=AMBAR)
    assert [x["gosterim"] for x in s1] == [x["gosterim"] for x in s2]
    assert all(not x["yeni"] for x in s2)


def test_ihtiyac_ust_sinir_verir(c):
    """Kesin sayı değil tavan: kutusunda kodu olan ürüne etiket gerekmiyor."""
    ih = etiketler.ihtiyac(c, 1, AMBAR)
    kirli = c.execute("SELECT COUNT(*) n FROM beklenen WHERE yukleme=1 AND ambar=? "
                      "AND haric=0 AND izleme='seri' AND kirli=1",
                      (AMBAR,)).fetchone()["n"]
    assert ih["seri"]["kirli_kayit"] == kirli
    assert ih["seri"]["ust_sinir"] == kirli
    assert ih["malzeme"]["eksik"] == ih["malzeme"]["tekil"]

    # havuzda bekleyen etiket tavandan düşer
    etiketler.bas(c, "seri", adet=10)
    ih = etiketler.ihtiyac(c, 1, AMBAR)
    assert ih["seri"]["havuzda"] == 10
    assert ih["seri"]["ust_sinir"] == kirli - 10


def test_malzeme_kopya_yeni_numara_uretmez(c):
    """Aynı malzeme iki rafta duruyorsa aynı kod iki kez basılır."""
    _, tek = etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    n = c.execute("SELECT COUNT(*) n FROM etiket WHERE tur='malzeme'").fetchone()["n"]

    _, uc = etiketler.bas(c, "malzeme", kopya=3, kapsam="hepsi",
                          yukleme=1, ambar=AMBAR)   # adet yok = hepsi
    assert len(uc) == 3 * len(tek)
    assert len({x["gosterim"] for x in uc}) == len(tek)
    # kopya basmak defteri büyütmez
    assert c.execute("SELECT COUNT(*) n FROM etiket WHERE tur='malzeme'"
                     ).fetchone()["n"] == n
    assert c.execute("SELECT adet FROM basim ORDER BY id DESC LIMIT 1"
                     ).fetchone()["adet"] == 3 * len(tek)


def test_malzeme_adet_sinirlar_ve_kaldigi_yerden_surer(c):
    """160 malzemenin hepsine etiket gerekmiyor: az bas, devam et."""
    _, ilk = etiketler.bas(c, "malzeme", adet=24, yukleme=1, ambar=AMBAR)
    assert len(ilk) == 24

    _, ikinci = etiketler.bas(c, "malzeme", adet=24, yukleme=1, ambar=AMBAR)
    assert len(ikinci) == 24
    # kapsam="eksik" varsayılan: ikinci parti ilkiyle çakışmaz
    assert not ({x["gosterim"] for x in ilk} & {x["gosterim"] for x in ikinci})
    assert c.execute("SELECT COUNT(*) n FROM etiket WHERE tur='malzeme'"
                     ).fetchone()["n"] == 48

    # adet verilmezse kalan hepsi
    tekil = etiketler.ihtiyac(c, 1, AMBAR)["malzeme"]["tekil"]
    _, kalan = etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    assert len(kalan) == tekil - 48
    assert etiketler.ihtiyac(c, 1, AMBAR)["malzeme"]["eksik"] == 0


def test_barkod_olamayan_kodlar_basa_alinir(c):
    """Kodunda boşluk/Türkçe karakter olanın kutusunda taranabilir kod olamaz."""
    barkodsuz = [r["kod"] for r in c.execute(
        "SELECT DISTINCT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0",
        (AMBAR,)) if not etiketler.kod_barkodlanabilir(r["kod"])]
    if not barkodsuz:
        pytest.skip("test verisinde barkoda çevrilemeyen malzeme kodu yok")

    _, ilk = etiketler.bas(c, "malzeme", adet=len(barkodsuz), yukleme=1, ambar=AMBAR)
    assert sorted(x["malzeme"] for x in ilk) == sorted(barkodsuz)
    assert etiketler.ihtiyac(c, 1, AMBAR)["malzeme"]["barkodsuz"] == len(barkodsuz)


def test_kod_barkodlanabilir():
    assert etiketler.kod_barkodlanabilir("BC-U6030")
    assert etiketler.kod_barkodlanabilir("P00924-B21")
    assert not etiketler.kod_barkodlanabilir("210-ACXU-TİP2")   # Türkçe İ
    assert not etiketler.kod_barkodlanabilir("0,70MM TEL")      # boşluk
    assert not etiketler.kod_barkodlanabilir("")


def test_malzeme_kapsam_eksik_yalniz_etiketsizleri_basar(c):
    _, hepsi = etiketler.bas(c, "malzeme", kapsam="hepsi", yukleme=1, ambar=AMBAR)
    assert hepsi
    _, ikinci = etiketler.bas(c, "malzeme", kapsam="eksik", yukleme=1, ambar=AMBAR)
    assert ikinci == []          # hepsinin etiketi var, basılacak yeni kod yok
    _, tekrar = etiketler.bas(c, "malzeme", kapsam="hepsi", yukleme=1, ambar=AMBAR)
    assert [x["gosterim"] for x in tekrar] == [x["gosterim"] for x in hepsi]


# --------------------------------------------------------- malzeme etiketi
def test_malzeme_etiketi_koda_cozulur(c, ot):
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    r = matching.coz(c, _malzeme_etiketi(c, kod), 1, AMBAR, ot["id"])
    assert r["t"] == "ogrenilmis"
    assert r["kod"] == kod


def test_malzeme_etiketi_barkod_tablosuna_duser(c, ot):
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    veri = reports.rapor_verisi(c, ot["id"])
    barkodlar = {s[0]: s[1] for s in veri["Barkod Tablosu"]["satirlar"]}
    assert barkodlar[norm(_malzeme_etiketi(c, kod))] == kod


# ------------------------------------------------------------- seri etiketi
def test_bos_etiket_kirli_slotu_doldurur(c, ot, yaz):
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    etiketler.bas(c, "seri", adet=5)
    slot = c.execute("""SELECT seri FROM beklenen WHERE yukleme=1 AND ambar=?
                        AND kod=? AND kirli=1 ORDER BY id LIMIT 1""",
                     (AMBAR, kod)).fetchone()["seri"]

    r = yaz(_malzeme_etiketi(c, kod), "DS-000001", "##SONRAKI##")
    assert r["tip"] == "slot"
    assert r["eski"] == slot
    assert r["yeni"] == "DS-000001"

    veri = reports.rapor_verisi(c, ot["id"])
    duz = [s for s in veri["Tiger Düzeltme"]["satirlar"] if s[0] == kod]
    assert [slot, "DS-000001"] == [duz[0][2], duz[0][3]]


def test_bos_etiket_malzeme_barkodu_olarak_ogrenilmez(c, ot, yaz):
    """Seri etiketi tekil cihaza aittir; `eslesme` malzeme seviyesidir.

    Oraya girseydi Barkod Tablosu sekmesi onu Tiger'ın malzeme kartına
    yazılacak barkod diye listelerdi.
    """
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    etiketler.bas(c, "seri", adet=5)
    yaz(_malzeme_etiketi(c, kod), "DS-000001", "##SONRAKI##")
    assert not c.execute("SELECT 1 FROM eslesme WHERE barkod=?",
                         ("DS000001",)).fetchone()


def test_ayni_etiket_ikinci_okutmada_tekrar_der(c, ot, yaz):
    """Regresyon: bağlı etiket ikinci kez okutulunca ikinci slotu yememeli."""
    kod = _kirli_malzeme(c, en_az=2)
    etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    etiketler.bas(c, "seri", adet=5)
    mlz_et = _malzeme_etiketi(c, kod)

    yaz(mlz_et, "DS-000001", "##SONRAKI##")
    sayilan = c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND kod=?",
                        (ot["id"], kod)).fetchone()["n"]

    r = matching.coz(c, "DS-000001", 1, AMBAR, ot["id"])
    assert r["t"] == "tekrar"

    ikinci = yaz(mlz_et, "DS-000001", "##SONRAKI##")
    assert ikinci["tip"] == "tekrar"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND kod=?",
                     (ot["id"], kod)).fetchone()["n"] == sayilan


def test_etiket_deftere_baglanir(c, ot, yaz):
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    etiketler.bas(c, "seri", adet=5)
    yaz("##RAF-A1##", _malzeme_etiketi(c, kod), "DS-000001", "##SONRAKI##")
    e = c.execute("SELECT * FROM etiket WHERE kod='DS000001'").fetchone()
    assert e["malzeme"] == kod
    assert e["beklenen_id"] is not None
    assert e["raf"] == "A1"


def test_uretici_seri_numarasi_etiketi_yener(c, ot, yaz):
    """Kullanıcı kararı: garanti/RMA izi uydurma numarayla değiştirilmez."""
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    etiketler.bas(c, "seri", adet=5)
    r = yaz(_malzeme_etiketi(c, kod), "GERCEKSN12345", "DS-000001", "##SONRAKI##")
    assert r["tip"] == "slot"
    assert r["yeni"] == "GERCEKSN12345"
    # etiket yine de o kayda bağlanır — fiziksel etiket ürünün üstünde
    assert c.execute("SELECT malzeme FROM etiket WHERE kod='DS000001'"
                     ).fetchone()["malzeme"] == kod


def test_lot_malzemesinde_etiket_baglanmaz(c, ot, yaz):
    kod = _lot_malzeme(c)
    etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    etiketler.bas(c, "seri", adet=5)
    r = yaz(_malzeme_etiketi(c, kod), "DS-000001", "##SONRAKI##")
    assert r["tip"] == "adet"
    assert r["etiket_yersiz"] == "DS-000001"
    assert c.execute("SELECT malzeme FROM etiket WHERE kod='DS000001'"
                     ).fetchone()["malzeme"] is None


def test_yalniz_bos_etiket_kuyruga_duser(c, ot, yaz):
    etiketler.bas(c, "seri", adet=5)
    r = yaz("DS-000001", "##SONRAKI##")
    assert r["tip"] == "kuyruk"
    assert r["bos_etiket"] == ["DS-000001"]
    k = c.execute("SELECT not_ FROM kuyruk WHERE id=?", (r["kuyruk_id"],)).fetchone()
    assert "boş etiket" in k["not_"]


def test_kuyruktan_cozulunce_etiket_baglanir_ogrenilmez(c, ot, yaz):
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "seri", adet=5)
    r = yaz("DS-000001", "BILINMEYENBARKOD1", "##SONRAKI##")
    hedef = c.execute("""SELECT id FROM beklenen WHERE yukleme=1 AND ambar=?
                         AND kod=? AND kirli=1 ORDER BY id LIMIT 1""",
                      (AMBAR, kod)).fetchone()["id"]
    s = matching.kuyruk_coz(c, r["kuyruk_id"], hedef)
    assert s["etiket"] == "DS-000001"
    assert s["ogrenilen"] == ["BILINMEYENBARKOD1"]
    assert not c.execute("SELECT 1 FROM eslesme WHERE barkod='DS000001'").fetchone()
    assert c.execute("SELECT beklenen_id FROM etiket WHERE kod='DS000001'"
                     ).fetchone()["beklenen_id"] == hedef


# ----------------------------------------------------------------- rapor
def test_yeni_seri_raf_etiketini_secmez(c):
    """Regresyon: iki parça aynı uzunlukta, max() ilkini alıyordu."""
    assert reports._yeni_seri("DM-000123 + DS-000045") == "DS-000045"
    assert reports._yeni_seri("DM-000123 + GERCEKSN99") == "GERCEKSN99"
    assert reports._yeni_seri("DS-000045") == "DS-000045"


def test_etiketler_sekmesi(c, ot, yaz):
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    etiketler.bas(c, "seri", adet=3)
    yaz(_malzeme_etiketi(c, kod), "DS-000001", "##SONRAKI##")

    veri = reports.rapor_verisi(c, ot["id"])
    assert "Etiketler" in veri
    satir = {s[0]: s for s in veri["Etiketler"]["satirlar"]}
    assert satir["DS-000001"][1] == "Seri"
    assert satir["DS-000001"][2] == kod
    assert satir["DS-000002"][2] == ""          # havuzda bekliyor
    assert satir[_malzeme_etiketi(c, kod)][1] == "Malzeme"


# ------------------------------------------------------------ Tiger'a dönüş
def test_etiket_ertesi_yil_temiz_seri_olarak_gelir(c):
    """Düzeltme Tiger'a işlendikten sonra etiket normal seri numarası olur."""
    kod = _kirli_malzeme(c)
    assert kirli_mi("DS-000045", kod) == (0, "")
    assert kirli_mi("DM-000123", kod) == (0, "")


def test_yukleme_ozeti_defterde_olmayan_etiketi_bildirir(c):
    from app import importer
    c.execute("UPDATE beklenen SET seri='DS-009999', seri_n='DS009999' "
              "WHERE yukleme=1 AND ambar=? AND izleme='seri' "
              "AND id=(SELECT MIN(id) FROM beklenen WHERE yukleme=1)", (AMBAR,))
    cak = importer.ozetle(c, 1)["etiket_cakisma"]
    assert any(x["kod_n"] == "DS009999" for x in cak)

    etiketler.bas(c, "seri", adet=9999)
    assert not importer.ozetle(c, 1)["etiket_cakisma"]


# ------------------------------------------------------------ basılan sayfa
@pytest.mark.parametrize("duzen", ["a4", "rulo"])
def test_etiket_sayfasi_uretilir(c, duzen):
    pytest.importorskip("barcode")
    from app import barkod
    _, s = etiketler.bas(c, "seri", adet=4, duzen=duzen)
    h = barkod.etiket_html(s, duzen)
    assert h.count("data:image/svg+xml;base64,") == 4
    assert "DS-000004" in h
    if duzen == "a4":
        assert "size:A4" in h
    else:
        assert "size:50mm 25mm" in h and "break-after:page" in h


def test_a4_atlanan_hucreler_bos_basilir(c):
    pytest.importorskip("barcode")
    from app import barkod
    _, s = etiketler.bas(c, "seri", adet=2)
    h = barkod.etiket_html(s, "a4", atla=5)
    assert h.count('class="k bos"') == 5
    # rulo düzeninde ızgara yok, atlama da yok
    assert 'class="k bos"' not in barkod.etiket_html(s, "rulo", atla=5)


def test_malzeme_etiketinde_kod_da_basilir(c):
    pytest.importorskip("barcode")
    from app import barkod
    kod = _kirli_malzeme(c)
    _, s = etiketler.bas(c, "malzeme", yukleme=1, ambar=AMBAR)
    h = barkod.etiket_html([x for x in s if x["malzeme"] == kod], "a4")
    assert kod in h


# ----------------------------------------------------- sıfırlamaya dayanma
def test_defter_csvden_geri_yuklenir(sablon, tmp_path):
    """sifirla.bat veritabanını taşır; basılı etiket numarası kaybolmamalı.

    Fiziksel etiket veritabanından uzun ömürlü: sayaç sıfırlanıp aynı numarayı
    ikinci kez verirse depoda iki ayrı ürün aynı kodu taşır.
    """
    import os
    import shutil

    from app import db as dbm

    yol = str(tmp_path / "sayim.db")
    shutil.copy(sablon, yol)
    c1 = dbm.baglan(yol)
    etiketler.bas(c1, "seri", adet=7)
    c1.commit()
    c1.close()

    # sifirla.bat data\*.db dosyalarını yedeğe taşır, data/etiket'e dokunmaz
    for ek in ("", "-wal", "-shm"):
        if os.path.exists(yol + ek):
            os.remove(yol + ek)
    assert os.path.isdir(str(tmp_path / "etiket"))

    c2 = dbm.baglan(yol)
    assert c2.execute("SELECT COUNT(*) n FROM etiket").fetchone()["n"] == 7
    assert etiketler.sonraki_no(c2, "seri") == 8
    # basım tarihi de geri gelmeli, yoksa defterde ne zaman basıldığı kaybolur
    assert c2.execute("SELECT ts FROM etiket WHERE kod='DS000001'").fetchone()["ts"]
    c2.close()


# ------------------------------------------------------------------- API
def test_api_etiket_uclari(kurulu):
    pytest.importorskip("barcode")
    ist, ozet, ot = kurulu
    y = ozet["yukleme"]

    ih = ist.get("/api/etiket/ihtiyac", params={"yukleme": y, "ambar": "1"}).json()
    assert ih["seri"]["kirli_kayit"] > 0
    assert ih["seri"]["ust_sinir"] == ih["seri"]["kirli_kayit"]
    assert ih["malzeme"]["eksik"] == ih["malzeme"]["tekil"]

    r = ist.post("/api/etiket/basim",
                 json={"tur": "seri", "adet": 6, "duzen": "a4", "atla": 2})
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers["content-type"]
    assert r.text.count("data:image/svg+xml;base64,") == 6
    assert r.text.count('class="k bos"') == 2

    r = ist.post("/api/etiket/basim",
                 json={"tur": "malzeme", "yukleme": y, "ambar": "1", "duzen": "rulo",
                       "adet": 5, "kopya": 2})
    assert r.status_code == 200, r.text
    assert "size:50mm 25mm" in r.text
    assert len(ist.get("/api/etiket", params={"tur": "malzeme"}).json()) == 5
    assert r.text.count("data:image/svg+xml;base64,") == 10   # 5 kod x 2 kopya

    defter = ist.get("/api/etiket", params={"tur": "seri"}).json()
    assert len(defter) == 6
    assert defter[0]["gosterim"] == "DS-000001"

    basimlar = ist.get("/api/etiket/basimlar").json()
    assert [b["tur"] for b in basimlar] == ["malzeme", "seri"]


def test_api_gecersiz_basim_400_doner(kurulu):
    ist, ozet, _ = kurulu
    assert ist.post("/api/etiket/basim", json={"tur": "seri", "adet": 0}).status_code == 400
    assert ist.post("/api/etiket/basim", json={"tur": "sey", "adet": 1}).status_code == 400
    assert ist.post("/api/etiket/basim",
                    json={"tur": "seri", "adet": 1, "duzen": "poster"}).status_code == 400
    assert ist.post("/api/etiket/basim",
                    json={"tur": "seri", "adet": 1, "kopya": 0}).status_code == 400
    assert ist.post("/api/etiket/basim",
                    json={"tur": "malzeme", "yukleme": ozet["yukleme"], "ambar": "1",
                          "kapsam": "sey"}).status_code == 400
    # malzeme etiketi ambar bilmeden basılamaz
    assert ist.post("/api/etiket/basim", json={"tur": "malzeme"}).status_code == 400


# ------------------------------------------------- kodu hiç olmayan ürünler
def test_bos_malzeme_etiketi_kuyruktan_ogrenilir(c, ot, yaz):
    """5 m kablo: Tiger'da kodu yok. Etiket bir kez çözülür, sonra tanınır."""
    etiketler.bas(c, "malzeme", kapsam="bos", adet=2)
    etiketler.bas(c, "seri", adet=5)

    # 1. kablo: ikisi de tanınmıyor -> kuyruk
    r = yaz("DM-000001", "DS-000001", "##SONRAKI##")
    assert r["tip"] == "kuyruk"

    hedef = c.execute("""SELECT id FROM beklenen WHERE yukleme=1 AND ambar=?
                         AND kirli=1 AND izleme='seri' ORDER BY id LIMIT 1""",
                      (AMBAR,)).fetchone()["id"]
    kod = c.execute("SELECT kod FROM beklenen WHERE id=?", (hedef,)).fetchone()["kod"]
    coz = matching.kuyruk_coz(c, r["kuyruk_id"], hedef)

    # malzeme etiketi ÖĞRENİLİR, seri etiketi öğrenilmez
    assert coz["ogrenilen"] == ["DM-000001"]
    assert c.execute("SELECT kod FROM eslesme WHERE barkod='DM000001'"
                     ).fetchone()["kod"] == kod
    assert not c.execute("SELECT 1 FROM eslesme WHERE barkod='DS000001'").fetchone()

    # 2. kablo: aynı malzeme etiketi + farklı seri -> artık tanınıyor
    assert matching.coz(c, "DM-000001", 1, AMBAR, ot["id"])["t"] == "ogrenilmis"
    r2 = yaz("DM-000001", "DS-000002", "##SONRAKI##")
    assert r2["tip"] == "slot"
    assert r2["kod"] == kod
    assert r2["yeni"] == "DS-000002"


def test_bos_malzeme_basimi_tigera_bagli_degil(c):
    _, s = etiketler.bas(c, "malzeme", kapsam="bos", adet=3)
    assert [x["gosterim"] for x in s] == ["DM-000001", "DM-000002", "DM-000003"]
    assert all(x["malzeme"] is None for x in s)
    # boş etiket öğrenilmiş barkod tablosuna yazılmaz — bağlanacağı malzeme yok
    assert not c.execute("SELECT 1 FROM eslesme").fetchone()
