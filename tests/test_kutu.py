"""Kap barkoduyla toplu sayım (KUTU_TASARIM.md).

Malzeme kodları test verisine göre değiştiği için hiçbiri sabit yazılmadı;
her senaryo ihtiyacı olan kaydı veritabanından bulur.
"""
import datetime

import pytest

from app import etiketler, kutu as kutum, matching, reports
from app.norm import norm

from tests.test_api import kurulu, istemci  # noqa: F401

from .conftest import AMBAR, oturum_taze

SONRAKI = "##SONRAKI##"


# --------------------------------------------------------------- yardımcılar
def _lot_malzeme(c):
    r = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=?
                     AND haric=0 AND izleme='lot' ORDER BY id LIMIT 1""",
                  (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde lot izlemeli malzeme yok")
    return r["kod"]


def _seri_malzeme(c):
    r = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=?
                     AND haric=0 AND izleme='seri' ORDER BY id LIMIT 1""",
                  (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde seri izlemeli malzeme yok")
    return r["kod"]


def _kap_bas(c, adet=1):
    """`adet` kadar anonim kap etiketi basar, gösterim hâllerini döner."""
    _, satirlar = etiketler.bas(c, "kutu", adet=adet)
    return [s["gosterim"] for s in satirlar]


def _yaz(c, ot, *barkodlar):
    sonuc = None
    for b in barkodlar:
        sonuc = matching.okut(c, oturum_taze(c, ot), b)
    return sonuc


def _eskit(c, kap, gun):
    """Kap kaydının adet doğrulamasını `gun` gün geriye alır."""
    eski = (datetime.datetime.now() - datetime.timedelta(days=gun)).isoformat()
    c.execute("UPDATE kutu SET ts_guncelle=? WHERE kod=?", (eski, norm(kap)))


# ------------------------------------------------------------ etiket sınıfı
def test_etiket_turu_ters_arama(c):
    """DK 'seri' DEĞİL 'kutu' döner (KUTU_TASARIM.md 4).

    Eskiden `etiket_turu` "DM değilse seri" diyordu; üçüncü sınıf eklendiği an
    kap kodu sessizce seri etiketi sayılırdı ve `reports._yeni_seri` onu
    Tiger'a gerçek seri numarası diye yazdırırdı.
    """
    assert etiketler.etiket_turu("DM-000123") == "malzeme"
    assert etiketler.etiket_turu("DS-000045") == "seri"
    assert etiketler.etiket_turu("DK-000007") == "kutu"
    assert etiketler.etiket_turu("ARK-1250L-S5A1") is None


def test_kap_kodu_ogrenilmez(c):
    """Kap kodu `eslesme`'ye — yani Tiger'ın malzeme kartına — hiç girmez."""
    assert etiketler.ogrenilebilir("DK-000007") is False
    assert etiketler.ogrenilebilir("DS-000045") is False
    assert etiketler.ogrenilebilir("198701689928") is True


def test_kap_basimi_anonim(c):
    kaplar = _kap_bas(c, 3)
    assert len(kaplar) == 3 and all(k.startswith("DK-") for k in kaplar)
    for k in kaplar:
        r = c.execute("SELECT * FROM etiket WHERE kod=?", (norm(k),)).fetchone()
        assert r["tur"] == "kutu" and r["malzeme"] is None
        # Malzeme etiketi basımda `eslesme`'ye yazılır; kap YAZILMAZ.
        assert not c.execute("SELECT 1 FROM eslesme WHERE barkod=?",
                             (norm(k),)).fetchone()


# ------------------------------------------------------------ tanımsız kap
def test_tanimsiz_kap_kuyruga_duser(c, ot):
    kap = _kap_bas(c)[0]
    s = _yaz(c, ot, kap, SONRAKI)
    assert s["tip"] == "kutu_tanimsiz" and s["kutu"] == kap
    q = c.execute("SELECT * FROM kuyruk WHERE id=?", (s["kuyruk_id"],)).fetchone()
    assert q["tur"] == "kutu" and q["cozuldu"] == 0
    # Hiçbir sayım yazılmadı: kabın içinde ne olduğu henüz bilinmiyor.
    assert not c.execute("SELECT 1 FROM okutma WHERE oturum=?", (ot["id"],)).fetchone()


def test_kap_cozulunce_hem_tanimlanir_hem_sayilir(c, ot):
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    s = _yaz(c, ot, kap, SONRAKI)
    sonuc = matching.kutu_coz(c, s["kuyruk_id"], malzeme=kod, adet=12)
    assert sonuc["tip"] == "adet" and sonuc["sayildi"] is True

    top = c.execute("SELECT COALESCE(SUM(miktar),0) s FROM okutma WHERE oturum=? "
                    "AND kod=?", (ot["id"], kod)).fetchone()["s"]
    assert top == 12
    k = kutum.getir(c, kap)
    assert k["malzeme"] == kod and k["adet"] == 12 and k["izleme"] == "lot"
    assert c.execute("SELECT cozuldu FROM kuyruk WHERE id=?",
                     (s["kuyruk_id"],)).fetchone()["cozuldu"] == 1
    # Denetim izi: satır hangi kaptan geldiğini söylüyor (KUTU_TASARIM.md 8).
    assert "kutu: %s" % kap in c.execute(
        "SELECT not_ FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
        (ot["id"],)).fetchone()["not_"]


def test_kap_adet_gerekli(c, ot):
    """Serisiz kapta adet uydurulmaz — sabit 1 yazmak yanlış sayım olurdu."""
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    s = _yaz(c, ot, kap, SONRAKI)
    assert matching.kutu_coz(c, s["kuyruk_id"], malzeme=kod)["hata"] == \
        "kap_adet_gerekli"


def test_kap_ambar_disina_cikmaz(c, ot):
    """Kapta bu ambarda kayıtlı olmayan bir şey varsa cevap 'fazla'dır."""
    kap = _kap_bas(c)[0]
    s = _yaz(c, ot, kap, SONRAKI)
    sonuc = matching.kutu_coz(c, s["kuyruk_id"], malzeme="YOK-BOYLE-KOD", adet=5)
    assert "ambarda kayıtlı değil" in sonuc["hata"]


# --------------------------------------------------------------- tanımlı kap
def test_tanimli_kap_adetle_sayilir(c, ot):
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 150, "lot")

    s = _yaz(c, ot, "##ADET-130##", kap, SONRAKI)
    assert s["tip"] == "adet" and s["miktar"] == 130 and s["kutu"] == kap
    # Kabın son bilinen adedi bu sayımla tazelenir — bir sonraki sayımın
    # VARSAYILANI olarak, gerçek olarak değil.
    assert kutum.getir(c, kap)["adet"] == 130


def test_tanimli_kap_adet_yoksa_sorar(c, ot):
    """Kayıttaki adet sorusuz uygulanmaz: içerik ayda bir değişiyor."""
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 150, "lot")

    s = _yaz(c, ot, kap, SONRAKI)
    assert s["tip"] == "kutu_sor" and s["kod"] == kod
    assert s["oneri_adet"] == 150            # az önce yazıldı, taze
    assert not c.execute("SELECT 1 FROM okutma WHERE oturum=?", (ot["id"],)).fetchone()


def test_bayat_kap_adet_onermez(c, ot):
    """30 günden eski kayıt bilgi değil tahmindir — alan boş açılır."""
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 150, "lot")
    _eskit(c, kap, kutum.TAZELIK_GUN + 5)

    s = _yaz(c, ot, kap, SONRAKI)
    assert s["tip"] == "kutu_sor"
    assert s["taze"] is False and s["oneri_adet"] is None
    assert s["adet"] == 150                  # son bilinen değer ipucu olarak durur


def test_seri_takipli_kap_tek_basina_saymaz(c, ot):
    """Kap kodunu okutup ##SONRAKI## demek 'bir cihaz saydım' demek değildir."""
    kod = _seri_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 21, "seri")

    s = _yaz(c, ot, kap, SONRAKI)
    assert s["tip"] == "kutu_seri" and s["kod"] == kod
    assert not c.execute("SELECT 1 FROM okutma WHERE oturum=?", (ot["id"],)).fetchone()


def test_seri_takipli_kapla_birlikte_seri_okutulursa_sayilir(c, ot):
    """Kap + gerçek S/N: kap yalnızca bağlam, sayımı seri numarası yapar."""
    r = c.execute("""SELECT kod, seri FROM beklenen WHERE yukleme=1 AND ambar=?
                     AND haric=0 AND izleme='seri' AND kirli=0 AND seri<>''
                     ORDER BY id LIMIT 1""", (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde temiz seri kaydı yok")
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, r["kod"], 21, "seri")

    s = _yaz(c, ot, kap, r["seri"], SONRAKI)
    assert s["tip"] == "eslesti" and s["seri"] == r["seri"]


def test_yabanci_kap_kuyruga_duser(c, ot):
    """Kayıtlı malzemesi bu ambarda yoksa uygulama tahmin yürütmez."""
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, "BASKA-DEPO-KODU", 5, "lot")
    s = _yaz(c, ot, kap, SONRAKI)
    assert s["tip"] == "kutu_yabanci" and s["eski_kod"] == "BASKA-DEPO-KODU"
    assert c.execute("SELECT tur FROM kuyruk WHERE id=?",
                     (s["kuyruk_id"],)).fetchone()["tur"] == "kutu"


def test_ayni_kap_iki_kez_okutulunca_tek_soru(c, ot):
    """Soruyu görüp ##ADET-N## okutan kullanıcı ikinci bir soru bırakmamalı."""
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 150, "lot")

    ilk = _yaz(c, ot, kap, SONRAKI)
    assert ilk["tip"] == "kutu_sor"
    ikinci = _yaz(c, ot, kap, SONRAKI)
    assert ikinci["kuyruk_id"] == ilk["kuyruk_id"]        # ikinci kayıt açılmadı

    son = _yaz(c, ot, "##ADET-130##", kap, SONRAKI)
    assert son["tip"] == "adet" and son["miktar"] == 130
    # Cevaplanmış soru kuyrukta durmaz: oturum kapanırken sorulmamalı.
    assert matching.bekleyen_kuyruk(c, ot["id"]) == []


def test_kaptaki_sayim_disi_kalem_sessiz_kalmaz(c, ot):
    """Sayım dışı kalem dolu bir kapta da olabilir; kap onu gizlememeli."""
    from .conftest import haric_kur

    _, _, kod = haric_kur(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 10, "yok")
    s = _yaz(c, ot, kap, SONRAKI)
    assert s["tip"] == "haric" and s["kod"] == kod
    assert not c.execute("SELECT 1 FROM okutma WHERE oturum=?", (ot["id"],)).fetchone()


def test_elle_okutulan_kod_kabi_yener(c, ot):
    """Kap yanlış ürüne yapışmış olabilir: elle okutulan kod kazanır."""
    kodlar = [r["kod"] for r in c.execute(
        """SELECT DISTINCT kod FROM beklenen WHERE yukleme=1 AND ambar=?
           AND haric=0 AND izleme='lot' ORDER BY kod LIMIT 2""", (AMBAR,))]
    if len(kodlar) < 2:
        pytest.skip("test verisinde iki ayrı lot malzemesi yok")
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kodlar[0], 150, "lot")

    s = _yaz(c, ot, "##ADET-5##", kap, kodlar[1], SONRAKI)
    assert s["tip"] == "adet" and s["kod"] == kodlar[1]
    # Kap kaydı ELLENMEZ: sayım onun malzemesine yazılmadı.
    k = kutum.getir(c, kap)
    assert k["malzeme"] == kodlar[0] and k["adet"] == 150


# ------------------------------------------------------------------ geri al
def test_gerial_kap_kaydini_da_geri_alir(c, ot):
    """Reddedilen adet kayıtta taze görünmeye devam etmemeli."""
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 150, "lot")
    _eskit(c, kap, 90)
    onceki = kutum.getir(c, kap)["ts_guncelle"]

    _yaz(c, ot, "##ADET-130##", kap, SONRAKI)
    assert kutum.getir(c, kap)["adet"] == 130

    matching.gerial(c, oturum_taze(c, ot))
    k = kutum.getir(c, kap)
    assert k["adet"] == 150 and k["ts_guncelle"] == onceki


def test_gerial_tanimlanmamis_kabi_siler(c, ot):
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    s = _yaz(c, ot, kap, SONRAKI)
    matching.kutu_coz(c, s["kuyruk_id"], malzeme=kod, adet=7)
    assert kutum.getir(c, kap) is not None

    matching.gerial(c, oturum_taze(c, ot))
    assert kutum.getir(c, kap) is None
    # Kuyruk kaydı da yeniden açılır: ürün hâlâ sayılmadı.
    assert c.execute("SELECT cozuldu FROM kuyruk WHERE id=?",
                     (s["kuyruk_id"],)).fetchone()["cozuldu"] == 0


# -------------------------------------------------------------------- rapor
def test_raporda_kutu_turu_ve_seri_onerisi(c, ot):
    """Kap kodu Tiger'a seri numarası diye YAZILMAZ, Etiketler'de 'Kutu' olur."""
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 150, "lot")

    assert reports._yeni_seri("%s + X9Y/0000Z" % kap) == "X9Y/0000Z"
    assert reports._yeni_seri(kap) == kap        # tek parça: elemeye takılmaz

    veri = reports.rapor_verisi(c, ot["id"])
    satir = next(s for s in veri["Etiketler"]["satirlar"] if s[0] == kap)
    assert satir[1] == "Kutu" and satir[2] == kod


# ------------------------------------------------------- sıfırlamaya dayanma
def test_kap_defteri_csvden_geri_gelir(c, ot):
    """sifirla.bat data/etiket'e dokunmaz: kap bağları hayatta kalmalı."""
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 150, "lot")

    c.execute("DELETE FROM kutu")
    c.execute("DELETE FROM etiket")
    assert kutum.csv_geri_yukle(c) == 1
    k = kutum.getir(c, kap)
    assert k["malzeme"] == kod and k["adet"] == 150
    # Etiket defteri de tamamlanır, yoksa sayaç aynı numarayı ikinci kez verir.
    assert etiketler.sonraki_no(c, "kutu") > int(kap.split("-")[1])


def test_defterde_kap_malzemesi_gorunur(c):
    """Ekrandaki defter ile rapordaki Etiketler sekmesi aynı şeyi göstermeli."""
    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 150, "lot")

    satir = next(x for x in etiketler.defter(c, tur="kutu") if x["gosterim"] == kap)
    assert satir["malzeme"] == kod and satir["aciklama"]
    # Kap malzemesiyle de aranabilmeli.
    assert any(x["gosterim"] == kap for x in etiketler.defter(c, q=kod))


# ------------------------------------------------------------- basılan etiket
def test_kap_etiketi_adet_basmaz(c):
    """Etikete adet basmak, ayda bir değişen içerikte yalancı şahit olurdu."""
    pytest.importorskip("barcode")
    from app import barkod

    kod = _lot_malzeme(c)
    kap = _kap_bas(c)[0]
    kutum.tanimla(c, kap, kod, 150, "lot")

    _, satirlar = etiketler.bas(c, "kutu", adet=1, kapsam="tanimli")
    h = barkod.etiket_html(satirlar, "a4")
    assert kap in h and kod in h
    # Adet etikete girmez. Çıplak "150" aranmıyor: malzeme açıklamasında da
    # geçebilir (ARK-1250 gibi) ve test veriye bağımlı hâle gelirdi.
    assert "150 AD" not in h and ">150<" not in h
    # Yeniden basım yeni numara tüketmez: aynı kap hep aynı kodu taşır.
    assert [x["gosterim"] for x in satirlar] == [kap]


# ---------------------------------------------------------------------- API
def test_api_kap_akisi(kurulu):
    ist, ozet, o = kurulu
    oid = o["id"]
    kod = ist.get("/api/oturum/%s/ara?izleme=lot&limit=1" % oid).json()["satirlar"]
    if not kod:
        pytest.skip("test verisinde lot izlemeli malzeme yok")
    kod = kod[0]["kod"]

    r = ist.post("/api/etiket/basim", json={"tur": "kutu", "adet": 1})
    assert r.status_code == 200
    kap = ist.get("/api/etiket?tur=kutu").json()[0]["gosterim"]

    ist.post("/api/oturum/%s/okut" % oid, json={"ham": kap})
    s = ist.post("/api/oturum/%s/okut" % oid, json={"ham": SONRAKI}).json()
    assert s["tip"] == "kutu_tanimsiz"

    # Kuyruk satırı paneli besleyecek kap bilgisini taşır.
    kuy = ist.get("/api/oturum/%s/kuyruk" % oid).json()[0]
    assert kuy["tur"] == "kutu" and kuy["kutu"]["gosterim"] == kap

    r = ist.post("/api/kuyruk/%s/kutu" % kuy["id"], json={"malzeme": kod, "adet": 9})
    assert r.status_code == 200, r.text
    assert r.json()["tip"] == "adet"

    g = ist.get("/api/kutu/%s?yukleme=%s&ambar=1" % (kap, ozet["yukleme"])).json()
    assert g["malzeme"] == kod and g["adet"] == 9 and g["taze"] is True
    assert g["oneri_adet"] == 9

    # İçerik değişti: kap boşaltılır, numara kalır.
    assert ist.delete("/api/kutu/%s" % kap).json()["malzeme"] is None
    assert ist.get("/api/kutu/%s" % kap).status_code == 200


def test_api_barkod_oturumsuz_basilir(istemci):
    """Barkod ekranı Tiger raporu YÜKLENMEDEN çalışmalı (saha isteği).

    Sayıma çıkmadan basılacak şeylerin çoğu yüklemeye bağlı değil: komut kartı,
    raf barkodları, kap etiketi, seri etiketi ve kodu hiç olmayan ürünler için
    boş malzeme havuzu. Yüklemeye bağlı olan tek şey "ambardaki malzemelerin
    etiketi" — hangi malzemelerin bastırılacağı o rapordan geliyor.
    """
    pytest.importorskip("barcode")
    kap = istemci.post("/api/etiket/basim", json={"tur": "kutu", "adet": 2})
    assert kap.status_code == 200 and "DK-000001" in kap.text
    assert istemci.post("/api/etiket/basim",
                        json={"tur": "seri", "adet": 2}).status_code == 200
    assert istemci.post("/api/etiket/basim",
                        json={"tur": "malzeme", "adet": 2,
                              "kapsam": "bos"}).status_code == 200
    assert istemci.post("/api/raf-etiketi",
                        json={"raflar": ["A1", "ÜST-1"], "kopya": 1,
                              "atla": 0}).status_code == 200
    assert istemci.post("/api/komut-karti",
                        json={"raflar": ["A1"]}).status_code == 200


def test_api_kap_tanimlama_ambar_disini_reddeder(kurulu):
    ist, ozet, _ = kurulu
    ist.post("/api/etiket/basim", json={"tur": "kutu", "adet": 1})
    kap = ist.get("/api/etiket?tur=kutu").json()[0]["gosterim"]
    r = ist.post("/api/kutu/%s" % kap,
                 json={"malzeme": "YOK-BOYLE-KOD", "adet": 5,
                       "yukleme": ozet["yukleme"], "ambar": "1"})
    assert r.status_code == 400
