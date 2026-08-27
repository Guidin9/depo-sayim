"""Lot ve izlemesiz kalemlerin adet bazlı sayımı (CLAUDE.md 2.4).

Bu dosya ACIL_PLAN.md 1. maddesinin regresyon takımıdır. Düzeltmeden önceki
davranış: lot numarası okutulunca satır `miktar=1` ile KAPANIYOR, ikinci okutma
`tekrar` uyarısı alıp hiç işlenmiyordu. 77 adetlik bir lot raporda "sayılan 1 /
beklenen 77" olarak çıkıyordu — Ambar 1'in 271 lot adedinin tamamı bu yoldan
eksik görünüyordu.

Üç ayrı kural sınanıyor:
  * `kapasite_kaldi()` — lot satırı tek okutmayla bitmez, `sayılan < beklenen`
    olduğu sürece kabul edilir.
  * `_adet_dagit()` — bir malzemenin birden çok lotu olabilir; hep ilk satıra
    yazmak o lotu şişirip ötekileri eksik bırakır.
  * `##ADET-N##` / `POST /oturum/{id}/adet` — 77 adedi 77 kez okutmamak için
    miktar girişi. İki giriş yolu da aynı koddan geçer.
"""
import pytest

from app import matching, reports
from tests.conftest import oturum_taze

SONRAKI = "##SONRAKI##"


def _lot_satiri(c, ambar="1", en_az=2):
    """Miktarı `en_az`'dan büyük bir lot satırı."""
    r = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                     AND izleme='lot' AND miktar>=? ORDER BY miktar DESC LIMIT 1""",
                  (ambar, en_az)).fetchone()
    if not r:
        pytest.skip("test verisinde %g adetten büyük lot satırı yok" % en_az)
    return r


def _cok_lotlu(c, ambar="1", en_az=3):
    """Birden çok lot satırı olan bir malzeme kodu."""
    r = c.execute("""SELECT kod, COUNT(*) n FROM beklenen WHERE yukleme=1 AND ambar=?
                     AND haric=0 AND izleme='lot' GROUP BY kod
                     HAVING n>=? ORDER BY n DESC LIMIT 1""", (ambar, en_az)).fetchone()
    if not r:
        pytest.skip("test verisinde %d lotlu malzeme yok" % en_az)
    return r["kod"], r["n"]


def test_lot_ayni_barkodla_defalarca_sayilir(c, ot, yaz):
    """Lot numarasını üç kez okutmak üç adet saymalı — 'tekrar' DEĞİL.

    Düzeltmeden önce ikinci okutma {'tip': 'tekrar'} dönüyor ve hiç
    işlenmiyordu.
    """
    lot = _lot_satiri(c, en_az=3)
    for beklenen_toplam in (1, 2, 3):
        r = yaz(lot["seri"], SONRAKI)
        assert r["tip"] == "adet"
        assert r["toplam"] == beklenen_toplam
        assert r["beklenen"] == lot["miktar"]
        assert r["seri"] == lot["seri"]

    okunan = c.execute("SELECT COALESCE(SUM(miktar),0) s FROM okutma WHERE oturum=? "
                       "AND beklenen_id=?", (ot["id"], lot["id"])).fetchone()["s"]
    assert okunan == 3


def test_lot_kapasitesi_dolunca_tekrar_uyarir(c, ot, yaz):
    """Beklenen adede ulaşıldıktan sonraki okutma reddedilmeli."""
    lot = _lot_satiri(c, en_az=2)
    adet = int(lot["miktar"])
    for _ in range(adet):
        assert yaz(lot["seri"], SONRAKI)["tip"] == "adet"
    r = yaz(lot["seri"], SONRAKI)
    assert r["tip"] == "tekrar"
    assert r["seri"] == lot["seri"]


def test_lot_tam_sayilinca_eksikte_gorunmez(c, ot, yaz):
    """Kapasite dolduğunda satır ne eksikte ne adet fazlasında olmalı."""
    lot = _lot_satiri(c, en_az=2)
    for _ in range(int(lot["miktar"])):
        yaz(lot["seri"], SONRAKI)
    eksik, adet_fazlasi, _ = reports.eksik_kayitlar(c, ot["id"])
    assert not [e for e in eksik if e["id"] == lot["id"]]
    assert not [e for e in adet_fazlasi if e["id"] == lot["id"]]


def test_lot_eksik_sayilinca_kalan_adet_raporlanir(c, ot, yaz):
    """Yarım kalan lot, kalan adet kadar eksik yazmalı."""
    lot = _lot_satiri(c, en_az=3)
    yaz(lot["seri"], SONRAKI)
    eksik, _, _ = reports.eksik_kayitlar(c, ot["id"])
    satir = next(e for e in eksik if e["id"] == lot["id"])
    assert satir["miktar"] == lot["miktar"] - 1
    assert "adet farkı" in satir["not_"]


def test_cok_lotlu_malzeme_satirlara_dagitilir(c, ot, yaz):
    """Malzeme kodu okutulunca hep İLK lota değil, açık olan satıra yazılmalı.

    Örnek veride bir malzemenin 57 ayrı lot satırı var, her biri 1 adet.
    Düzeltmeden önce hepsi ilk satıra yığılıyor, o satır adet fazlası veriyor
    ve diğer 56 satır eksik çıkıyordu.
    """
    kod, lot_sayisi = _cok_lotlu(c, en_az=3)
    dene = min(lot_sayisi, 4)
    for _ in range(dene):
        assert yaz(kod, SONRAKI)["tip"] == "adet"

    dokunulan = c.execute("SELECT COUNT(DISTINCT beklenen_id) n FROM okutma "
                          "WHERE oturum=? AND kod=?", (ot["id"], kod)).fetchone()["n"]
    assert dokunulan == dene

    _, adet_fazlasi, _ = reports.eksik_kayitlar(c, ot["id"])
    assert not [e for e in adet_fazlasi if e["kod"] == kod]


def test_lot_okutmasi_seri_dalina_girmez(c, ot, yaz):
    """Lot satırı `eslesti` (miktar=1, satırı kapat) dalına düşmemeli."""
    lot = _lot_satiri(c, en_az=2)
    r = yaz(lot["seri"], SONRAKI)
    assert r["tip"] == "adet"
    assert r["izleme"] == "lot"
    tip = c.execute("SELECT tip FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                    (ot["id"],)).fetchone()["tip"]
    assert tip == "kod"


def test_seri_takiplide_tekrar_kurali_degismedi(c, ot, yaz):
    """Regresyon: seri takipli satır hâlâ tek okutmayla kapanmalı."""
    b = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar='1' AND haric=0
                     AND izleme='seri' AND kirli=0 AND seri<>'' ORDER BY id LIMIT 1"""
                  ).fetchone()
    assert yaz(b["seri"], SONRAKI)["tip"] == "eslesti"
    assert yaz(b["seri"], SONRAKI)["tip"] == "tekrar"


def test_coz_lot_satirinda_kapasiteye_bakar(c, ot, yaz):
    """`coz()` doğrudan çağrıldığında da aynı kuralı uygulamalı."""
    lot = _lot_satiri(c, en_az=2)
    ilk = matching.coz(c, lot["seri"], ot["yukleme"], ot["ambar"], ot["id"])
    assert ilk["t"] == "seri" and ilk["izleme"] == "lot"

    for _ in range(int(lot["miktar"])):
        yaz(lot["seri"], SONRAKI)
    dolu = matching.coz(c, lot["seri"], ot["yukleme"], ot["ambar"], ot["id"])
    assert dolu["t"] == "tekrar"


# --------------------------------------------------------------- adet girişi
# `##ADET-N##` komut barkodu ve telefondaki tuş takımı (POST /oturum/{id}/adet)
# AYNI yoldan geçer — iki giriş iki ayrı davranışa ayrılmasın.

def test_adet_barkodu_lot_miktarini_yazar(c, ot, yaz):
    lot = _lot_satiri(c, en_az=5)
    n = int(lot["miktar"]) - 1
    yaz(lot["seri"], "##ADET-%d##" % n)
    r = yaz(SONRAKI)
    assert r["tip"] == "adet"
    assert r["miktar"] == n
    assert r["toplam"] == n
    assert r["beklenen"] == lot["miktar"]
    assert r["satir"] == 1


def test_adet_birikir(c, ot, yaz):
    """##ADET-25## iki kez okutulursa 50 olmalı — komut kartında ara değer yok."""
    lot = _lot_satiri(c, en_az=4)
    assert yaz("##ADET-2##")["miktar"] == 2
    assert yaz("##ADET-2##")["miktar"] == 4
    r = yaz(lot["seri"], SONRAKI)
    assert r["miktar"] == 4 and r["toplam"] == 4


def test_adet_sifir_temizler(c, ot, yaz):
    assert yaz("##ADET-9##")["miktar"] == 9
    assert yaz("##ADET-0##")["miktar"] == 0
    assert c.execute("SELECT bekleyen_adet FROM oturum WHERE id=?",
                     (ot["id"],)).fetchone()["bekleyen_adet"] == 0


def test_adet_grupla_birlikte_tukenir(c, ot, yaz):
    """Bir sonraki ürüne sızmamalı."""
    lot = _lot_satiri(c, en_az=4)
    yaz(lot["seri"], "##ADET-3##", SONRAKI)
    assert c.execute("SELECT bekleyen_adet FROM oturum WHERE id=?",
                     (ot["id"],)).fetchone()["bekleyen_adet"] == 0
    r = yaz(lot["seri"], SONRAKI)
    assert r["miktar"] == 1 and r["toplam"] == 4


def test_bos_tamponda_sonraki_adedi_yakmaz(c, ot, yaz):
    """Yanlışlıkla SONRAKI'ye basmak girilen adedi silmemeli."""
    yaz("##ADET-30##")
    assert yaz(SONRAKI)["tip"] == "bos"
    assert c.execute("SELECT bekleyen_adet FROM oturum WHERE id=?",
                     (ot["id"],)).fetchone()["bekleyen_adet"] == 30


def test_iptal_bekleyen_adedi_siler(c, ot, yaz):
    yaz("##ADET-40##")
    yaz("##IPTAL##")
    assert c.execute("SELECT bekleyen_adet FROM oturum WHERE id=?",
                     (ot["id"],)).fetchone()["bekleyen_adet"] == 0


def test_adet_cok_lotlu_malzemede_dagitilir(c, ot, yaz):
    """##ADET-5## 57 lotluk malzemede beş ayrı satıra gitmeli, hepsi bir lota değil."""
    kod, lot_sayisi = _cok_lotlu(c, en_az=4)
    n = min(lot_sayisi, 4)
    yaz(kod, "##ADET-%d##" % n)
    r = yaz(SONRAKI)
    assert r["satir"] == n
    assert c.execute("SELECT COUNT(DISTINCT beklenen_id) x FROM okutma WHERE oturum=? "
                     "AND kod=?", (ot["id"], kod)).fetchone()["x"] == n
    _, adet_fazlasi, _ = reports.eksik_kayitlar(c, ot["id"])
    assert not [e for e in adet_fazlasi if e["kod"] == kod]


def test_adet_seri_takiplide_uyarir(c, ot, yaz):
    """Seri takipli kalemde adet anlamsız — sessizce yutulmamalı."""
    b = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar='1' AND haric=0
                     AND izleme='seri' AND kirli=0 AND seri<>'' ORDER BY id LIMIT 1"""
                  ).fetchone()
    r = yaz(b["seri"], "##ADET-25##", SONRAKI)
    assert r["tip"] == "eslesti"
    assert r["adet_yersiz"] == 25
    assert c.execute("SELECT SUM(miktar) s FROM okutma WHERE oturum=? AND beklenen_id=?",
                     (ot["id"], b["id"])).fetchone()["s"] == 1


def test_adet_tavani_asilmaz(c, ot, yaz):
    from app.norm import ADET_TAVAN
    yaz("##ADET-%d##" % ADET_TAVAN)
    r = yaz("##ADET-1##")
    assert r["tip"] == "adet_tavan"
    assert c.execute("SELECT bekleyen_adet FROM oturum WHERE id=?",
                     (ot["id"],)).fetchone()["bekleyen_adet"] == ADET_TAVAN


def test_bozuk_adet_barkodu_komut_sayilmaz(c, ot, yaz):
    """##ADET-ABC## komut değil: tampona düşüp kullanıcıya görünmeli."""
    from app.norm import komut_coz
    assert komut_coz("##ADET-ABC##") == (None, None)
    assert komut_coz("##ADET-99999##") == (None, None)
    assert komut_coz("##ADET-25##") == ("adet", 25)
    assert yaz("##ADET-ABC##")["tip"] == "tampon"


def test_adet_ucu_komut_barkoduyla_ayni(c, ot):
    """POST /oturum/{id}/adet ile ##ADET-N## aynı sonucu vermeli."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.routers.ortak import veritabani

    app.dependency_overrides[veritabani] = lambda: c
    try:
        ist = TestClient(app)
        assert ist.post("/api/oturum/%s/adet" % ot["id"],
                        json={"adet": 12}).json()["miktar"] == 12
        assert ist.post("/api/oturum/%s/adet" % ot["id"],
                        json={"adet": 3}).json()["miktar"] == 15
        assert ist.post("/api/oturum/%s/adet" % ot["id"],
                        json={"adet": 0}).json()["miktar"] == 0
        assert ist.post("/api/oturum/%s/adet" % ot["id"],
                        json={"adet": -1}).status_code == 400
    finally:
        app.dependency_overrides.clear()


# -------------------------------------------- B4: sayaç lot adedini saymalı
def test_sayac_lot_adedini_sayar(c, ot, yaz):
    """Regresyon (2026-08-27, gerçek veriyle üretildi).

    Sayaç satır bazındaydı: 77 adetlik bir lot BİR kez okutulunca
    `COUNT(DISTINCT beklenen_id)` onu "okutulmuş" sayıyordu. 870 satırın hepsi
    birer kez okutulduğunda ekran "OKUTULAN 870 / KALAN 0" diyor, rapor ise
    202 adet eksik gösteriyordu — ekranla rapor iki ayrı gerçek söylüyordu ve
    kullanıcı depodan "bitti" diye çıkıyordu.
    """
    rows = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar='1'
                        AND haric=0 ORDER BY id""").fetchall()
    for r in rows:
        yaz(r["seri"], "##SONRAKI##")          # lotlarda ADET GİRİLMEDEN

    sayac = matching.sayaclar(c, oturum_taze(c, ot))
    eksik, _, _ = reports.eksik_kayitlar(c, ot["id"])
    rapor_eksik = sum(e["miktar"] for e in eksik)

    assert rapor_eksik > 0, "test verisi çok adetli lot içermiyor"
    assert sayac["kalan"] == rapor_eksik, "ekran ile rapor aynı sayıyı söylemeli"
    assert sayac["satir"] == len(rows), "satır sayısı ayrı alanda korunmalı"


def test_eksik_lot_bitirmede_uyarir(c, ot, yaz):
    """77 adetlik lotu bir kez okutmak onu bitirmez — kullanıcı uyarılmalı."""
    b = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar='1'
                     AND izleme='lot' AND miktar>5 ORDER BY id LIMIT 1""").fetchone()
    if not b:
        pytest.skip("test verisinde çok adetli lot yok")
    yaz(b["seri"], "##SONRAKI##")

    eksikler = matching.eksik_lotlar(c, oturum_taze(c, ot))
    assert any(x["kod"] == b["kod"] for x in eksikler)

    r = yaz("##BITIR##")
    assert r["tip"] == "bitir_uyari", "eksik lot sessizce geçilmemeli"
    assert any(x["kod"] == b["kod"] for x in r["eksik_lot"])


def test_tamamlanan_lot_uyarmaz(c, ot, yaz):
    b = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar='1'
                     AND izleme='lot' AND miktar>5 ORDER BY id LIMIT 1""").fetchone()
    if not b:
        pytest.skip("test verisinde çok adetli lot yok")
    yaz("##ADET-%d##" % int(b["miktar"]), b["seri"], "##SONRAKI##")
    assert not [x for x in matching.eksik_lotlar(c, oturum_taze(c, ot))
                if x["kod"] == b["kod"]]


def test_eksik_lot_uyarisi_engel_degil(c, ot, yaz):
    """Uyarı bilgi verir, kapatmayı ENGELLEMEZ: sayımın kendisi doğru.

    İki kapı (yumuşak uyarı + çift onay) ayrı olsaydı ikinci ##BITIR## de
    uyarıya takılır ve oturum hiç kapanmazdı.
    """
    from tests.conftest import bitir
    b = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar='1'
                     AND izleme='lot' AND miktar>5 ORDER BY id LIMIT 1""").fetchone()
    if not b:
        pytest.skip("test verisinde çok adetli lot yok")
    yaz(b["seri"], "##SONRAKI##")
    assert yaz("##BITIR##")["tip"] == "bitir_uyari"
    assert yaz("##BITIR##")["tip"] == "bitti", "ikinci okutma kapatmalı"
    assert oturum_taze(c, ot)["durum"] == "bitti"
