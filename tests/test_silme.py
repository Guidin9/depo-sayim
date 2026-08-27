"""I1 — akış listesinden okutma silme.

`##GERIAL##` yalnızca SONUNCUYU alır; sahada yanlış okutma birkaç ürün sonra
fark ediliyor ve o noktada geri alınacak bir şey kalmıyor.

Silme, `gerial` ile aynı yan etki sözleşmesini kullanır
(`_yan_etkileri_geri_al`): öğrenilen barkod unutulur, etiket havuza döner,
kuyruk kaydı yeniden açılır. Ayrı bir temizleme yolu YOKTUR — olsaydı ikisi
zamanla ayrışırdı.
"""
import pytest

from app import etiketler, matching, oturumlar
from tests.conftest import AMBAR, oturum_taze

SONRAKI = "##SONRAKI##"
UPC = "190017273624"


def _temiz_seri(c):
    return c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                        AND izleme='seri' AND kirli=0 AND seri<>'' ORDER BY id LIMIT 1""",
                     (AMBAR,)).fetchone()


def _kirli_malzeme(c):
    r = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                     AND izleme='seri' AND kirli=1 GROUP BY kod ORDER BY COUNT(*) DESC
                     LIMIT 1""", (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde kirli slotu olan malzeme yok")
    return r["kod"]


def _lot_malzeme(c):
    r = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                     AND izleme='lot' GROUP BY kod HAVING COUNT(*)>1
                     ORDER BY COUNT(*) DESC LIMIT 1""", (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde çok lotlu malzeme yok")
    return r["kod"]


def _okutmalar(c, ot):
    return c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"]


# ------------------------------------------------------------------ temel
def test_akis_satiri_id_tasir(c, ot, yaz):
    """Arayüz silmek için satırı adlandırabilmeli."""
    b = _temiz_seri(c)
    yaz(b["seri"], SONRAKI)
    akis = matching.durum(c, oturum_taze(c, ot))["akis"]
    assert akis and akis[0]["id"] and "grup" in akis[0]


def test_ortadaki_okutma_silinebilir(c, ot, yaz):
    """gerial'den asıl farkı: sondan başkası da silinebiliyor."""
    b = _temiz_seri(c)
    yaz(b["seri"], SONRAKI)
    hedef = matching.durum(c, oturum_taze(c, ot))["akis"][0]["id"]
    yaz(_kirli_malzeme(c), SONRAKI)          # araya başka bir ürün

    r = matching.okutma_sil(c, oturum_taze(c, ot), hedef)
    assert r["tip"] == "silindi" and r["silinen"] == 1
    kalan = [a["id"] for a in matching.durum(c, oturum_taze(c, ot))["akis"]]
    assert hedef not in kalan and len(kalan) == 1


def test_sayac_geri_duser(c, ot, yaz):
    b = _temiz_seri(c)
    yaz(b["seri"], SONRAKI)
    once = matching.sayaclar(c, oturum_taze(c, ot))["okutulan"]
    hedef = matching.durum(c, oturum_taze(c, ot))["akis"][0]["id"]
    matching.okutma_sil(c, oturum_taze(c, ot), hedef)
    assert matching.sayaclar(c, oturum_taze(c, ot))["okutulan"] == once - 1


def test_olmayan_okutma_hata_doner(c, ot):
    assert matching.okutma_sil(c, ot, 999999).get("hata")


def test_baska_oturumun_okutmasi_silinemez(c, ot, yaz):
    """Oturum sınırı: yanlış oturumun kaydına dokunulmamalı."""
    b = _temiz_seri(c)
    yaz(b["seri"], SONRAKI)
    hedef = matching.durum(c, oturum_taze(c, ot))["akis"][0]["id"]
    baska = oturumlar.ac(c, 1, "3") if c.execute(
        "SELECT 1 FROM beklenen WHERE yukleme=1 AND ambar='3'").fetchone() else None
    if not baska:
        pytest.skip("test verisinde ikinci ambar yok")
    assert matching.okutma_sil(c, baska, hedef).get("hata")


# ------------------------------------------------------- yan etkiler geri alınır
def test_ogrenilen_barkod_unutulur(c, ot, yaz):
    """Yoksa yanlış barkod Barkod Tablosu'ndan Tiger'a taşınırdı (ACIL_PLAN A5)."""
    b = _temiz_seri(c)
    yaz(UPC, b["seri"], SONRAKI)
    from app.norm import norm
    assert c.execute("SELECT 1 FROM eslesme WHERE barkod=?", (norm(UPC),)).fetchone()

    hedef = matching.durum(c, oturum_taze(c, ot))["akis"][0]["id"]
    r = matching.okutma_sil(c, oturum_taze(c, ot), hedef)
    assert UPC in r["unutulan"]
    assert not c.execute("SELECT 1 FROM eslesme WHERE barkod=?", (norm(UPC),)).fetchone()


def test_etiket_havuza_doner(c, ot, yaz):
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "seri", adet=3)
    yaz(kod, "DS-000001", SONRAKI)
    assert c.execute("SELECT malzeme FROM etiket WHERE kod='DS000001'"
                     ).fetchone()["malzeme"] == kod

    hedef = matching.durum(c, oturum_taze(c, ot))["akis"][0]["id"]
    r = matching.okutma_sil(c, oturum_taze(c, ot), hedef)
    assert r["etiket_cozuldu"] == "DS-000001"
    e = c.execute("SELECT * FROM etiket WHERE kod='DS000001'").fetchone()
    assert e is not None, "numara TÜKETİLMEZ, defter kaydı durur"
    assert e["malzeme"] is None and e["beklenen_id"] is None


def test_kuyruktan_dogan_fazla_silinince_kayit_kuyruga_doner(c, ot, yaz):
    yaz(UPC, SONRAKI)
    kid = c.execute("SELECT id FROM kuyruk WHERE oturum=?", (ot["id"],)).fetchone()["id"]
    matching.kuyruk_fazla(c, kid, ad="deneme ürünü")
    assert c.execute("SELECT cozuldu FROM kuyruk WHERE id=?", (kid,)).fetchone()["cozuldu"] == 1

    hedef = matching.durum(c, oturum_taze(c, ot))["akis"][0]["id"]
    r = matching.okutma_sil(c, oturum_taze(c, ot), hedef)
    assert r["kuyruk_acildi"] == kid
    assert c.execute("SELECT cozuldu FROM kuyruk WHERE id=?", (kid,)).fetchone()["cozuldu"] == 0


# ------------------------------------------------------------------- grup kapsamı
def test_cok_satirli_adet_grubu_tek_seferde_gider(c, ot, yaz):
    """`_adet_dagit` bir grubu birden çok satıra yazar; hepsi birlikte silinmeli.

    Satır bazlı silinseydi miktarın bir kısmı geride kalır, `geri` yalnızca
    ilk satırda durduğu için öğrenme de ortada kalırdı.
    """
    kod = _lot_malzeme(c)
    yaz("##ADET-5##", kod, SONRAKI)
    satirlar = c.execute("SELECT id,grup FROM okutma WHERE oturum=?",
                         (ot["id"],)).fetchall()
    if len(satirlar) < 2:
        pytest.skip("adet tek satıra dağıldı")

    r = matching.okutma_sil(c, oturum_taze(c, ot), satirlar[-1]["id"])
    assert r["silinen"] == len(satirlar)
    assert _okutmalar(c, ot) == 0


def test_satir_kapsami_yalniz_o_satiri_alir(c, ot, yaz):
    kod = _lot_malzeme(c)
    yaz("##ADET-5##", kod, SONRAKI)
    satirlar = c.execute("SELECT id FROM okutma WHERE oturum=?", (ot["id"],)).fetchall()
    if len(satirlar) < 2:
        pytest.skip("adet tek satıra dağıldı")
    n = len(satirlar)
    r = matching.okutma_sil(c, oturum_taze(c, ot), satirlar[0]["id"], kapsam="satir")
    assert r["silinen"] == 1 and _okutmalar(c, ot) == n - 1


def test_grup_null_eski_satirda_satira_duser(c, ot, yaz):
    """`grup` sütunu sonradan eklendi; eski satırlarda boş."""
    b = _temiz_seri(c)
    yaz(b["seri"], SONRAKI)
    hedef = matching.durum(c, oturum_taze(c, ot))["akis"][0]["id"]
    c.execute("UPDATE okutma SET grup=NULL WHERE id=?", (hedef,))
    r = matching.okutma_sil(c, oturum_taze(c, ot), hedef)
    assert r["silinen"] == 1 and _okutmalar(c, ot) == 0
