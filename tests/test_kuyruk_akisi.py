"""Kuyruk birikmesini önleyen davranışlar.

Sahadaki sorun: gün sonunda kuyrukta onlarca kayıt oluyor ve hangi ürünün
hangi rafta okutulduğu hatırlanamıyor. Çözüm sırası:
  1. raftan ayrılmadan çözmeye zorla (raf_engel / bitir_engel)
  2. kuyruğa düşerken aday malzeme öner (isteğe bağlı)
  3. not ve fotoğraf (isteğe bağlı hatırlatıcılar)
"""
from app import matching
from tests.conftest import oturum_taze

SONRAKI = "##SONRAKI##"
BILINMEYEN = ("198701689928", "EDBP0153231475674")


def _kuyruga_at(yaz, raf=None):
    if raf:
        yaz("##RAF-%s##" % raf)
    return yaz(*BILINMEYEN, SONRAKI)


# ---------------------------------------------------------------- 1. raf kapısı
def test_raf_degistirmek_cozulmemis_kuyrukta_engellenir(c, ot, yaz):
    r = _kuyruga_at(yaz, "A1")
    assert r["tip"] == "kuyruk"

    engel = yaz("##RAF-B2##")
    assert engel["tip"] == "raf_engel"
    assert engel["eski_raf"] == "A1" and engel["yeni_raf"] == "B2"
    assert engel["kuyruk"][0]["barkodlar"] == list(BILINMEYEN)
    assert engel["ses"] == "uyari"
    # raf değişmedi — hâlâ A1'desin
    assert oturum_taze(c, ot)["aktif_raf"] == "A1"


def test_kuyruk_cozulunce_raf_degisir(c, ot, yaz):
    _kuyruga_at(yaz, "A1")
    kid = c.execute("SELECT id FROM kuyruk WHERE oturum=?", (ot["id"],)).fetchone()["id"]
    hedef = c.execute("SELECT id FROM beklenen WHERE seri='0WGP72SAYIM1'").fetchone()["id"]
    matching.kuyruk_coz(c, kid, hedef)

    assert yaz("##RAF-B2##")["tip"] == "raf"
    assert oturum_taze(c, ot)["aktif_raf"] == "B2"


def test_baska_rafin_kuyrugu_engellemez(c, ot, yaz):
    """A1'de takılan kayıt, B2'den C3'e geçmeyi engellememeli."""
    _kuyruga_at(yaz, "A1")
    matching.okut(c, oturum_taze(c, ot), "##RAF-B2##", zorla=True)
    assert yaz("##RAF-C3##")["tip"] == "raf"
    assert oturum_taze(c, ot)["aktif_raf"] == "C3"


def test_zorla_ile_gecilebilir(c, ot, yaz):
    _kuyruga_at(yaz, "A1")
    r = matching.okut(c, oturum_taze(c, ot), "##RAF-B2##", zorla=True)
    assert r["tip"] == "raf"
    assert oturum_taze(c, ot)["aktif_raf"] == "B2"


def test_ayni_rafi_tekrar_okutmak_engellenmez(c, ot, yaz):
    """A1'deyken yine A1 okutmak raf değişimi değildir."""
    _kuyruga_at(yaz, "A1")
    assert yaz("##RAF-A1##")["tip"] == "raf"


def test_bitirmek_cozulmemis_kuyrukta_engellenir(c, ot, yaz):
    _kuyruga_at(yaz, "A1")
    engel = yaz("##BITIR##")
    assert engel["tip"] == "bitir_engel"
    assert len(engel["kuyruk"]) == 1
    assert oturum_taze(c, ot)["durum"] == "acik"

    r = matching.okut(c, oturum_taze(c, ot), "##BITIR##", zorla=True)
    assert r["tip"] == "bitti"
    assert oturum_taze(c, ot)["durum"] == "bitti"


def test_rafsiz_sayimda_kapi_calisir(c, ot, yaz):
    """Raf hiç kullanılmıyorsa da bitirirken kuyruk uyarısı gelmeli."""
    yaz(*BILINMEYEN, SONRAKI)
    assert yaz("##BITIR##")["tip"] == "bitir_engel"


# ---------------------------------------------------------------- 2. aday önerisi
def test_kuyruga_dusunce_aday_onerilir(c, ot, yaz):
    r = _kuyruga_at(yaz, "A1")
    assert r["kuyruk_id"]
    kodlar = [a["kod"] for a in r["adaylar"]]
    assert len(kodlar) == 5 and len(set(kodlar)) == 5      # malzeme başına tek satır
    # açık kirli slotu olanlar üstte
    assert r["adaylar"][0]["acik_kirli"] > 0


def test_ayni_rafta_sayilan_malzeme_aday_listesinde_one_gecer(c, ot, yaz):
    yaz("##RAF-A1##", "0C5RNH", SONRAKI)          # A1'de lot kalemi sayıldı
    r = yaz(*BILINMEYEN, SONRAKI)
    assert r["adaylar"][0]["kod"] == "0C5RNH"
    assert r["adaylar"][0]["ayni_raf"] == 1


def test_sayilan_satir_aday_sayisindan_dusulur(c, ot, yaz):
    """210-ACXU-TİP2'nin 3 serisi var; biri sayılınca açık satır 2'ye iner."""
    once = next(a for a in matching.adaylar(c, ot, limit=500)
                if a["kod"] == "210-ACXU-TİP2")
    assert once["acik_satir"] == 3

    yaz("5S47WC2", SONRAKI)
    sonra = next(a for a in matching.adaylar(c, oturum_taze(c, ot), limit=500)
                 if a["kod"] == "210-ACXU-TİP2")
    assert sonra["acik_satir"] == 2


def test_tamamlanmis_seri_malzeme_aday_olmaz(c, ot, yaz):
    """Tek serisi olan malzeme sayılınca aday listesinden tamamen çıkar."""
    b = c.execute("""SELECT kod FROM beklenen WHERE izleme='seri' AND ambar='1'
                     GROUP BY kod HAVING COUNT(*)=1 LIMIT 1""").fetchone()["kod"]
    seri = c.execute("SELECT seri FROM beklenen WHERE kod=?", (b,)).fetchone()["seri"]
    yaz(seri, SONRAKI)
    assert all(a["kod"] != b for a in matching.adaylar(c, oturum_taze(c, ot), limit=500))


def test_lot_kalemi_yarim_sayilinca_aday_kalir(c, ot, yaz):
    """77 beklenen lottan 1 okutulduysa malzeme hâlâ aday olmalı."""
    yaz("0C5RNH", SONRAKI)
    assert any(a["kod"] == "0C5RNH"
               for a in matching.adaylar(c, oturum_taze(c, ot), limit=500))


def test_aday_secince_kuyruk_kapanir(c, ot, yaz):
    r = _kuyruga_at(yaz, "A1")
    aday = r["adaylar"][0]
    matching.kuyruk_coz(c, r["kuyruk_id"], aday["id"])
    assert matching.bekleyen_kuyruk(c, ot["id"]) == []
    assert matching.sayaclar(c, ot)["kuyruk"] == 0


def test_haric_kalem_aday_olmaz(c, ot, yaz):
    r = _kuyruga_at(yaz)
    assert all(a["kod"] != "303-195-100C-001" for a in matching.adaylar(c, ot, limit=50))
    assert r["adaylar"]


# ---------------------------------------------------------------- 3. not
def test_kuyruga_not_yazilir(c, ot, yaz):
    _kuyruga_at(yaz, "A1")
    kid = matching.bekleyen_kuyruk(c, ot["id"])[0]["id"]
    c.execute("UPDATE kuyruk SET not_=? WHERE id=?", ("siyah kutu, üst raf", kid))
    assert matching.bekleyen_kuyruk(c, ot["id"])[0]["not_"] == "siyah kutu, üst raf"
