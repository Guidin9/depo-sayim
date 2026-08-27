"""Tanınmayan üründe girilen adedin kaybolması (saha bildirimi 2026-08-27).

Belirti: kullanıcı 150 girdi, barkodu okuttu, SONRAKI dedi, ürün Tiger'da
yoktu, "fazla" işaretledi — ve 150 hiçbir yere yazılmadı.

Kök sebep dört yerdeydi:
  1. `grup_coz` `bekleyen_adet`i grup başında tüketip sıfırlıyor, ama ürün
     tanınmayınca kuyruk satırına hiç yazmıyordu (`kuyruk` tablosunda adet
     sütunu yoktu).
  2. `kuyruk_fazla` miktarı sabit 1 yazıyordu.
  3. `##FAZLA##` miktarı sabit 1 yazıyor VE adedi tüketmiyordu — girilen 150
     ayakta kalıp SONRAKİ ürüne sızıyordu.
  4. `##ATLA##` da aynı şekilde sızdırıyordu.
"""
import pytest

from app import matching, reports
from tests.conftest import AMBAR, oturum_taze

SONRAKI = "##SONRAKI##"
YOK = "HICBIR-KAYITTA-YOK-7788"


def _kuyruk(c, ot):
    return c.execute("SELECT * FROM kuyruk WHERE oturum=? ORDER BY id DESC LIMIT 1",
                     (ot["id"],)).fetchone()


def _son_okutma(c, ot):
    return c.execute("SELECT * FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                     (ot["id"],)).fetchone()


def _lot_malzeme(c):
    r = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                     AND izleme='lot' ORDER BY miktar DESC LIMIT 1""",
                  (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde lot kalemi yok")
    return r["kod"]


# ------------------------------------------------- kullanıcının bildirdiği akış
def test_bildirilen_akis_bastan_sona(c, ot, yaz):
    """150 gir · okut · SONRAKI · Tiger'da yok · fazla işaretle -> 150 yazmalı."""
    yaz("##ADET-150##", YOK, SONRAKI)
    q = _kuyruk(c, ot)
    assert q["adet"] == 150, "adet kuyruk kaydına taşınmalı"

    matching.kuyruk_fazla(c, q["id"], ad="deneme ürünü")
    x = _son_okutma(c, ot)
    assert x["tip"] == "fazla" and x["miktar"] == 150

    veri = reports.rapor_verisi(c, ot["id"])
    i = veri["Fazla"]["basliklar"].index("Miktar")
    assert [s[i] for s in veri["Fazla"]["satirlar"]] == [150]


# ----------------------------------------------------------- adet taşınıyor mu
def test_kuyruga_dusen_adet_saklanir(c, ot, yaz):
    r = yaz("##ADET-150##", YOK, SONRAKI)
    assert r["tip"] == "kuyruk" and r["miktar"] == 150
    assert _kuyruk(c, ot)["adet"] == 150


def test_adet_girilmezse_sifir_kalir(c, ot, yaz):
    """0 ile 1 ayrı şeyler: "girilmedi" ile "1 tane" aynı değil."""
    yaz(YOK, SONRAKI)
    assert _kuyruk(c, ot)["adet"] == 0
    matching.kuyruk_fazla(c, _kuyruk(c, ot)["id"], ad="x")
    assert _son_okutma(c, ot)["miktar"] == 1


def test_atla_adedi_kuyruga_tasir(c, ot, yaz):
    r = yaz("##ADET-40##", YOK, "##ATLA##")
    assert r["tip"] == "kuyruk" and r["miktar"] == 40
    assert _kuyruk(c, ot)["adet"] == 40


def test_elle_fazla_adedi_kullanir(c, ot, yaz):
    r = yaz("##ADET-12##", YOK, "##FAZLA##")
    assert r["tip"] == "fazla_elle" and r["miktar"] == 12
    assert _son_okutma(c, ot)["miktar"] == 12


# ------------------------------------------------- adet sonraki ürüne SIZMAMALI
@pytest.mark.parametrize("komut", ["##FAZLA##", "##ATLA##"])
def test_adet_sonraki_urune_sizmaz(c, ot, yaz, komut):
    """`##SONRAKI##` adedi tüketiyordu ama bu ikisi tüketmiyordu."""
    yaz("##ADET-150##", YOK, komut)
    assert oturum_taze(c, ot)["bekleyen_adet"] == 0


# --------------------------------------------------------- kuyruk çözülürken
def test_lot_kaydina_baglanan_adet_uygulanir(c, ot, yaz):
    """Malzeme çözülünce izleme belli olur; lotta adet miktara döner."""
    kod = _lot_malzeme(c)
    yaz("##ADET-7##", YOK, SONRAKI)
    hedef = c.execute("""SELECT id FROM beklenen WHERE yukleme=1 AND ambar=? AND kod=?
                         ORDER BY id LIMIT 1""", (AMBAR, kod)).fetchone()["id"]
    r = matching.kuyruk_coz(c, _kuyruk(c, ot)["id"], hedef)
    assert r["miktar"] == 7
    assert _son_okutma(c, ot)["miktar"] == 7


def test_seri_takipli_kayitta_adet_uygulanmaz_ama_bildirilir(c, ot, yaz):
    """Her adet Tiger'da ayrı satır — ama sessizce yutulmaz."""
    b = c.execute("""SELECT id FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                     AND izleme='seri' AND kirli=0 AND seri<>'' ORDER BY id LIMIT 1""",
                  (AMBAR,)).fetchone()
    yaz("##ADET-9##", YOK, SONRAKI)
    r = matching.kuyruk_coz(c, _kuyruk(c, ot)["id"], b["id"])
    assert r["miktar"] == 1 and r["adet_yersiz"] == 9


def test_adet_duzeltilebilir(c, ot, yaz):
    """Kutuda 150 sanıp 130 çıkabilir."""
    yaz("##ADET-150##", YOK, SONRAKI)
    kid = _kuyruk(c, ot)["id"]
    c.execute("UPDATE kuyruk SET adet=130 WHERE id=?", (kid,))
    matching.kuyruk_fazla(c, kid, ad="x")
    assert _son_okutma(c, ot)["miktar"] == 130
