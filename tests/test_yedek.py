"""I4 — yedek parça modu.

Yedek parçalar Tiger'da kayıtlı değil. Aranmaları yalnızca yanlış eşleşme
üretiyordu: yedek parçanın üstündeki üretici kodu başka bir malzemenin önekine
takılıp o malzemenin slotunu dolduruyordu.

Mod açıkken okutulan grup veritabanında ARANMAZ. `okutma.tip` bu yüzden
dördüncü değerini aldı (`yedek`); testlerin yarısı o değerin mevcut sorguların
HİÇBİRİNE sızmadığını kilitliyor.
"""
import pytest

from app import matching, reports
from tests.conftest import AMBAR, oturum_taze

SONRAKI = "##SONRAKI##"
YEDEK = "##YEDEK##"


def _temiz_seri(c):
    return c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                        AND izleme='seri' AND kirli=0 AND seri<>'' ORDER BY id LIMIT 1""",
                     (AMBAR,)).fetchone()


def _sekme(c, ot, ad):
    return reports.rapor_verisi(c, ot["id"])[ad]["satirlar"]


# ------------------------------------------------------------------- mod
def test_mod_acilip_kapanir(c, ot, yaz):
    assert yaz(YEDEK)["acik"] is True
    assert oturum_taze(c, ot)["yedek_parca"] == 1
    assert yaz(YEDEK)["acik"] is False, "aynı barkod kapatmalı"
    assert oturum_taze(c, ot)["yedek_parca"] == 0


def test_kapat_barkodu_her_zaman_kapatir(c, ot, yaz):
    yaz(YEDEK)
    yaz("##YEDEKKAPAT##")
    assert oturum_taze(c, ot)["yedek_parca"] == 0


# --------------------------------------------------------------- davranış
def test_kayitli_bir_seri_bile_aranmaz(c, ot, yaz):
    """Asıl kural: mod açıkken arama YAPILMAZ. Tiger'da karşılığı olan bir
    seri numarası okutulsa bile yedek parça yazılır."""
    b = _temiz_seri(c)
    yaz(YEDEK)
    r = yaz(b["seri"], SONRAKI)
    assert r["tip"] == "yedek"
    x = c.execute("SELECT * FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                  (ot["id"],)).fetchone()
    assert x["tip"] == "yedek" and x["beklenen_id"] is None
    assert x["ham"] == b["seri"]


def test_ogrenme_yapilmaz(c, ot, yaz):
    """Barkodu bir malzemeye bağlamak tam da kaçındığımız şey."""
    yaz(YEDEK)
    yaz("YEDEKPARCA-0001", SONRAKI)
    assert c.execute("SELECT COUNT(*) n FROM eslesme").fetchone()["n"] == 0


def test_kuyruga_dusmez(c, ot, yaz):
    yaz(YEDEK)
    yaz("HICBIRSEYE-UYMAZ-9999", SONRAKI)
    assert c.execute("SELECT COUNT(*) n FROM kuyruk WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0


def test_adet_uygulanir(c, ot, yaz):
    yaz(YEDEK)
    r = yaz("##ADET-20##", "VIDA-M3", SONRAKI)
    assert r["tip"] == "yedek" and r["miktar"] == 20


def test_grup_tek_satir_yazar(c, ot, yaz):
    """Bir grup bir üründür — barkod başına satır yazılmaz (CLAUDE.md 4.4)."""
    yaz(YEDEK)
    yaz("A-BARKOD", "B-BARKOD", SONRAKI)
    satirlar = c.execute("SELECT * FROM okutma WHERE oturum=?", (ot["id"],)).fetchall()
    assert len(satirlar) == 1
    assert satirlar[0]["ham"] == "A-BARKOD + B-BARKOD"


def test_kilit_yedek_moda_karismaz(c, ot, yaz):
    """Mod açıkken `coz()` hiç çağrılmıyor; kilit de devreye girmemeli."""
    kod = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                       AND izleme='seri' AND kirli=1 LIMIT 1""", (AMBAR,)).fetchone()
    if not kod:
        pytest.skip("kirli malzeme yok")
    yaz(kod["kod"], "##KILIT##", YEDEK)
    r = yaz("SN-XYZ", SONRAKI)
    assert r["tip"] == "yedek"


# ---------------------------------------------- diğer sorgulara sızmıyor mu
def test_sayaclara_girmez(c, ot, yaz):
    once = matching.sayaclar(c, oturum_taze(c, ot))
    yaz(YEDEK)
    yaz("YEDEK-1", SONRAKI)
    sonra = matching.sayaclar(c, oturum_taze(c, ot))
    assert sonra == once, "yedek parça sayaçları bozmamalı"


def test_fazla_ve_eslesen_sekmelerine_girmez(c, ot, yaz):
    yaz(YEDEK)
    yaz("YEDEK-1", SONRAKI)
    assert _sekme(c, ot, "Fazla") == []
    assert _sekme(c, ot, "Eşleşen") == []


def test_esleme_ekranina_girmez(c, ot, yaz):
    yaz(YEDEK)
    yaz("YEDEK-1", SONRAKI)
    assert matching.esleme_verisi(c, oturum_taze(c, ot))["fazla"] == []


def test_bitirme_kapilarini_kilitlemez(c, ot, yaz):
    """Yedek parçadan fotoğraf ya da ad istenmez — kendi sekmesinde duruyor."""
    yaz(YEDEK)
    yaz("YEDEK-1", SONRAKI)
    o = oturum_taze(c, ot)
    assert matching.adsiz_fazlalar(c, o["id"]) == []
    assert matching.fotosuz_fazlalar(c, o["id"]) == []
    assert matching.bekleyen_kuyruk(c, o["id"]) == []


# --------------------------------------------------------------- rapor
def test_kendi_sekmesinde_cikar(c, ot, yaz):
    veri = reports.rapor_verisi(c, ot["id"])
    assert "Yedek Parça" in veri and "Yedek Parça" in reports.SEKME

    yaz(YEDEK)
    yaz("##ADET-3##", "VIDA-M3", SONRAKI)
    oid = c.execute("SELECT id FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                    (ot["id"],)).fetchone()["id"]
    c.execute("UPDATE okutma SET ad=? WHERE id=?", ("M3 vida", oid))

    s = _sekme(c, ot, "Yedek Parça")
    assert len(s) == 1
    basliklar = reports.rapor_verisi(c, ot["id"])["Yedek Parça"]["basliklar"]
    assert s[0][basliklar.index("Okutulan Barkodlar")] == "VIDA-M3"
    assert s[0][basliklar.index("Ürün Adı")] == "M3 vida"
    assert s[0][basliklar.index("Adet")] == 3


def test_excel_yazilabilir(c, ot, yaz, tmp_path):
    yaz(YEDEK)
    yaz("VIDA-M3", SONRAKI)
    yol = tmp_path / "r.xlsx"
    ozet = reports.excel_yaz(c, ot["id"], str(yol))
    assert yol.exists() and ozet["sayilar"]["Yedek Parça"] == 1


def test_yedek_modda_fazla_ve_atla_reddedilir(c, ot, yaz):
    """Mod açıkken bu iki komut modu delmemeli.

    Sessizce `fazla` yazılırsa ekranda kırmızı "YEDEK PARÇA MODU" bandı
    dururken kayıt Tiger sayım fazlası fişine girerdi.
    """
    yaz(YEDEK)
    for komut in ("##FAZLA##", "##ATLA##"):
        r = yaz("YEDEK-BARKOD", komut)
        assert r["tip"] == "yedek_modda_gecersiz"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0
    assert c.execute("SELECT COUNT(*) n FROM kuyruk WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0


def test_reddedilen_komutta_tampon_korunur(c, ot, yaz):
    """Kullanıcı modu kapatıp tekrar basabilmeli — okutmaları kaybetmemeli."""
    yaz(YEDEK)
    yaz("YEDEK-BARKOD", "##FAZLA##")
    assert [t["ham"] for t in matching.durum(c, oturum_taze(c, ot))["tampon"]] \
        == ["YEDEK-BARKOD"]
    yaz("##YEDEKKAPAT##")
    assert yaz("##FAZLA##")["tip"] == "fazla_elle"
