"""I5 — barkodu olmayan ürünler.

Bazı cihazlarda okutulacak hiçbir şey yok: üstünde yalnızca elle yazılmış bir
seri numarası ya da benzeri bir tanımlayıcı var. İki katman:

  a) değeri elle yaz -> `okut()` borusundan geçer, tutarsa sayılır
  b) tutmazsa ürünü listeden bul -> `elle_say()`

(a) için yeni kod YOK — telefondaki kutu `POST /okut`'a gidiyor, yani
eşleştirme, öğrenme ve grup mantığı birebir aynı kalıyor.
"""
import pytest

from app import matching, oturumlar
from tests.conftest import AMBAR, oturum_taze

SONRAKI = "##SONRAKI##"


def _acik_kayit(c, kirli=0):
    return c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                        AND izleme='seri' AND kirli=? AND seri<>'' ORDER BY id LIMIT 1""",
                     (AMBAR, kirli)).fetchone()


def _say(c, ot, bid, ham=None):
    return matching.elle_say(c, oturum_taze(c, ot), bid, ham=ham)


# ------------------------------------------------------- (a) elle yazılan değer
def test_elle_yazilan_seri_okutma_gibi_islenir(c, ot, yaz):
    b = _acik_kayit(c)
    r = yaz(b["seri"], SONRAKI)
    assert r["tip"] == "eslesti" and r["seri"] == b["seri"]


# --------------------------------------------------------- (b) listeden seçme
def test_listeden_secilen_kayit_sayilir(c, ot):
    b = _acik_kayit(c)
    r = _say(c, ot, b["id"])
    assert r["tip"] == "eslesti" and r["kod"] == b["kod"]
    assert not matching.kapasite_kaldi(
        c, ot["id"], c.execute("SELECT * FROM beklenen WHERE id=?", (b["id"],)).fetchone())


def test_sayac_artar(c, ot):
    once = matching.sayaclar(c, oturum_taze(c, ot))["okutulan"]
    _say(c, ot, _acik_kayit(c)["id"])
    assert matching.sayaclar(c, oturum_taze(c, ot))["okutulan"] == once + 1


def test_yazilan_deger_ogrenilir(c, ot):
    """Bir dahaki sefere sorusuz tanınsın."""
    from app.norm import norm
    b = _acik_kayit(c)
    r = _say(c, ot, b["id"], ham="ELLE-YAZILAN-9911")
    assert r["ogrenilen"] == ["ELLE-YAZILAN-9911"]
    e = c.execute("SELECT kod FROM eslesme WHERE barkod=?",
                  (norm("ELLE-YAZILAN-9911"),)).fetchone()
    assert e["kod"] == b["kod"]


def test_seri_etiketi_ogrenilmez_ama_BAGLANIR(c, ot):
    """DS- etiketi tekil cihaza ait, malzeme seviyesine yükseltilemez
    (`kuyruk_coz` ile aynı ayrım) — ama defterde boş kalmamalı.

    Bağlanmazsa Etiketler sekmesi "havuzda bekliyor" der, oysa etiket fiziksel
    olarak ürünün üstündedir; ertesi yıl aynı numara ikinci kez basılabilirdi.
    """
    from app import etiketler
    etiketler.bas(c, "seri", adet=3)
    b = _acik_kayit(c)
    r = _say(c, ot, b["id"], ham="DS-000001")
    assert r["ogrenilen"] == [], "malzeme seviyesine yükseltilmemeli"
    assert c.execute("SELECT COUNT(*) n FROM eslesme").fetchone()["n"] == 0
    assert r["etiket"] == "DS-000001"
    e = c.execute("SELECT * FROM etiket WHERE kod='DS000001'").fetchone()
    assert e["malzeme"] == b["kod"] and e["beklenen_id"] == b["id"]


def test_baglanan_etiket_gerial_ile_havuza_doner(c, ot):
    from app import etiketler
    etiketler.bas(c, "seri", adet=3)
    b = _acik_kayit(c)
    _say(c, ot, b["id"], ham="DS-000001")
    matching.gerial(c, oturum_taze(c, ot))
    e = c.execute("SELECT * FROM etiket WHERE kod='DS000001'").fetchone()
    assert e is not None and e["malzeme"] is None, "numara tükenmez, bağ çözülür"


def test_dolu_kayda_ikinci_urun_baglanmaz(c, ot):
    """Yoksa iki fiziksel ürün tek kayda düşerdi (CLAUDE.md 5)."""
    b = _acik_kayit(c)
    _say(c, ot, b["id"])
    assert _say(c, ot, b["id"]).get("hata")


def test_haric_kalem_reddedilir(c, ot):
    from tests.conftest import haric_kur
    _, _, kod = haric_kur(c)
    b = c.execute("SELECT * FROM beklenen WHERE yukleme=1 AND kod=? AND haric=1 LIMIT 1",
                  (kod,)).fetchone()
    assert _say(c, ot, b["id"]).get("hata")


def test_baska_ambarin_kaydi_reddedilir(c, ot):
    b = c.execute("SELECT * FROM beklenen WHERE yukleme=1 AND ambar<>? LIMIT 1",
                  (AMBAR,)).fetchone()
    if not b:
        pytest.skip("test verisinde ikinci ambar yok")
    assert _say(c, ot, b["id"]).get("hata")


def test_olmayan_kayit_reddedilir(c, ot):
    assert _say(c, ot, 999999).get("hata")


def test_gerial_ile_geri_alinir(c, ot):
    """`geri` doldurulmazsa öğrenilen değer kalıcı olarak yanlış malzemede
    kalır ve Barkod Tablosu'ndan Tiger'a taşınır (ACIL_PLAN A5)."""
    from app.norm import norm
    b = _acik_kayit(c)
    _say(c, ot, b["id"], ham="ELLE-YAZILAN-9912")
    r = matching.gerial(c, oturum_taze(c, ot))
    assert "ELLE-YAZILAN-9912" in (r.get("unutulan") or [])
    assert not c.execute("SELECT 1 FROM eslesme WHERE barkod=?",
                         (norm("ELLE-YAZILAN-9912"),)).fetchone()


def test_kirli_slot_da_secilebilir(c, ot):
    b = _acik_kayit(c, kirli=1)
    if not b:
        pytest.skip("kirli kayıt yok")
    assert _say(c, ot, b["id"])["tip"] == "eslesti"
