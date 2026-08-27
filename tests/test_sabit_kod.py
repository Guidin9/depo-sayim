"""I2 — sabit malzeme kodu kilidi ("bu malzemeye okut").

Sahadaki sorun: seri takipli bir malzemenin 21 cihazı sayılırken malzeme kodu
21 kez okutuluyordu. Kilit açıkken kod bir kez okutulur, ardından yalnızca
seri numaraları gelir.

Kilit `bekleyen_adet`in aksine grup kapanınca TÜKENMEZ — açıkça kapatılır ya
da oturumla biter.
"""
import pytest

from app import matching, oturumlar
from tests.conftest import AMBAR, oturum_taze

SONRAKI = "##SONRAKI##"
KILIT = "##KILIT##"
UPC = "190017273624"          # Tiger'da karşılığı yok


def _kirli_malzeme(c):
    r = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                     AND izleme='seri' AND kirli=1 GROUP BY kod HAVING COUNT(*)>1
                     ORDER BY COUNT(*) DESC LIMIT 1""", (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde çok kirli slotlu malzeme yok")
    return r["kod"]


def _kilit(c, ot):
    return oturum_taze(c, ot)["sabit_kod"]


# --------------------------------------------------------------- kilitleme
def test_tampondan_kilitlenir(c, ot, yaz):
    kod = _kirli_malzeme(c)
    r = yaz(kod, KILIT)
    assert r["tip"] == "kilit" and r["kod"] == kod
    assert _kilit(c, ot) == kod


def test_kilitlenen_kod_tampondan_duser(c, ot, yaz):
    """Kilit kodu temsil ediyor; grupta ikinci kez durursa her cihaza malzeme
    kodu okutulmuş gibi görünürdü."""
    kod = _kirli_malzeme(c)
    yaz(kod, KILIT)
    assert matching.durum(c, oturum_taze(c, ot))["tampon"] == []


def test_kilitlenecek_kod_yoksa_sessiz_kalmaz(c, ot, yaz):
    """Sessizce kilitlenmemek şart: kullanıcı kilitlendiğini sanıp onlarca
    seri numarası okutur ve hepsi kuyruğa düşerdi."""
    r = yaz(UPC, KILIT)
    assert r["tip"] == "kilit_yok" and r["ses"] == "uyari"
    assert _kilit(c, ot) is None


def test_bos_tamponda_son_okutmanin_kodu_kilitlenir(c, ot, yaz):
    kod = _kirli_malzeme(c)
    yaz(kod, SONRAKI)                    # bir cihaz sayıldı
    r = yaz(KILIT)
    assert r["tip"] == "kilit" and r["kod"] == kod


def test_kilit_acilir(c, ot, yaz):
    kod = _kirli_malzeme(c)
    yaz(kod, KILIT)
    r = yaz("##KILITAC##")
    assert r["tip"] == "kilitac" and _kilit(c, ot) is None


# ------------------------------------------------------------- asıl davranış
def test_kilitliyken_yalniz_seri_okutmak_slot_doldurur(c, ot, yaz):
    kod = _kirli_malzeme(c)
    yaz(kod, KILIT)
    r = yaz(UPC, SONRAKI)
    assert r["tip"] == "slot", "kilit devreye girmedi"
    assert r["kod"] == kod and r["yeni"] == UPC and r["sabit_kod"] == kod


def test_kilitsizken_ayni_okutma_kuyruga_duser(c, ot, yaz):
    """Karşılaştırma testi — kilidin gerçekten fark yarattığını gösterir."""
    r = yaz(UPC, SONRAKI)
    assert r["tip"] == "kuyruk"


def test_kilit_grup_kapaninca_tukenmez(c, ot, yaz):
    """`bekleyen_adet`ten farkı bu: art arda cihaz sayılabilmeli."""
    kod = _kirli_malzeme(c)
    yaz(kod, KILIT)
    for sn in ("SN-AAAA1111", "SN-BBBB2222"):
        assert yaz(sn, SONRAKI)["tip"] == "slot"
    assert _kilit(c, ot) == kod


def test_elle_okutulan_kod_kilidi_yener(c, ot, yaz):
    """Kilit açıkken başka bir ürün sayılabilmeli, yoksa kilidi açmak zorunlu
    olurdu."""
    kod = _kirli_malzeme(c)
    yaz(kod, KILIT)
    baska = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                         AND izleme='seri' AND kirli=1 AND kod<>? GROUP BY kod
                         LIMIT 1""", (AMBAR, kod)).fetchone()
    if not baska:
        pytest.skip("ikinci kirli malzeme yok")
    r = yaz(baska["kod"], SONRAKI)
    assert r["kod"] == baska["kod"], "elle okutulan kod kazanmalı"
    assert _kilit(c, ot) == kod, "kilit yerinde kalmalı"


def test_kilitli_kod_notta_gorunur(c, ot, yaz):
    """Denetim izi: bu satır kilitle mi sayıldı, elle mi?"""
    kod = _kirli_malzeme(c)
    yaz(kod, KILIT)
    yaz(UPC, SONRAKI)
    n = c.execute("SELECT not_ FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                  (ot["id"],)).fetchone()["not_"]
    assert "sabit kod" in n and kod in n


# ---------------------------------------------------------------------- API
def test_sabit_kod_ucu(c, ot):
    """Telefondan açık kod gönderme — Code128'e girmeyen kodlar için tek yol."""
    kod = _kirli_malzeme(c)
    r = matching.okut(c, oturum_taze(c, ot), "##KILIT-%s##" % kod)
    assert r["tip"] == "kilit" and _kilit(c, ot) == kod
