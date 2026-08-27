"""B1 — ##SONRAKI## unutulunca okutmaların sessizce kaybolması.

Saha tarifi: kullanıcı üç cihazın seri numarasını arka arkaya okutur ve
aradaki `##SONRAKI##`'yi unutur. Sahadaki en olası hata bu.

Eski davranış (2026-08-27'de çalışan uygulamada üretildi): `grup_coz`
`seri_h = next(...)` ile İLK eşleşmeyi alıp gerisini atıyordu. Sayaç `0 -> 1`,
ekran yeşil, ses normal; kalan iki cihaz raporda "eksik" çıkıyor ve gerçekten
depoda olmayan bir üründen ayırt edilemiyordu.

Yeni davranış: hepsi sayılır, hiçbir okutma kaybolmaz, kullanıcı uyarılır.
"""
import json

import pytest

from app import matching, reports
from tests.conftest import AMBAR, oturum_taze

SONRAKI = "##SONRAKI##"
UPC = "190017273624"


def _temiz(c, n=3):
    rs = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                      AND izleme='seri' AND kirli=0 AND seri<>'' ORDER BY id LIMIT ?""",
                   (AMBAR, n)).fetchall()
    if len(rs) < n:
        pytest.skip("test verisinde yeterli temiz seri kaydı yok")
    return rs


def test_uc_cihaz_tek_grupta_hepsi_sayilir(c, ot, yaz):
    rs = _temiz(c, 3)
    r = yaz(*[x["seri"] for x in rs], SONRAKI)

    assert r["tip"] == "coklu", "çelişki fark edilmedi"
    assert r["sayi"] == 3
    assert r["ses"] == "uyari", "sessiz kalmamalı"

    # Üçü de sayıldı — üçü de KENDİ grubunda.
    for x in rs:
        assert matching._sayildi(c, ot["id"], x["id"]), \
            "%s sayılmadı — okutma buharlaştı" % x["seri"]
    gruplar = {g["grup"] for g in c.execute(
        "SELECT grup FROM okutma WHERE oturum=?", (ot["id"],))}
    assert len(gruplar) == 3, "her cihaz kendi grubunda olmalı (##GERIAL## için)"


def test_celiskili_grup_sayaci_dogru_arttirir(c, ot, yaz):
    rs = _temiz(c, 3)
    onceki = matching.sayaclar(c, ot)["okutulan"]
    yaz(*[x["seri"] for x in rs], SONRAKI)
    assert matching.sayaclar(c, oturum_taze(c, ot))["okutulan"] == onceki + 3


def test_celiskili_grup_raporda_eksik_birakmaz(c, ot, yaz):
    rs = _temiz(c, 3)
    yaz(*[x["seri"] for x in rs], SONRAKI)
    eksik, _, _ = reports.eksik_kayitlar(c, ot["id"])
    kalan = {e["seri"] for e in eksik}
    for x in rs:
        assert x["seri"] not in kalan, "sayılan cihaz raporda eksik görünüyor"


def test_celiskili_grup_denetim_izini_korur(c, ot, yaz):
    """Her satır kendi barkodunu taşır, grubun tamamı `not_`'ta durur."""
    rs = _temiz(c, 2)
    yaz(rs[0]["seri"], rs[1]["seri"], SONRAKI)
    satirlar = c.execute("SELECT * FROM okutma WHERE oturum=? ORDER BY id",
                         (ot["id"],)).fetchall()
    assert {s["ham"] for s in satirlar} == {rs[0]["seri"], rs[1]["seri"]}
    for s in satirlar:
        assert "çelişkili grup" in s["not_"]
        for x in rs:
            assert x["seri"] in s["not_"], "okutulanların tamamı notta olmalı"


def test_celiskili_grupta_ogrenme_yapilmaz(c, ot, yaz):
    """Tanınmayan barkod hangi cihaza ait belli değil — bağlanmamalı.

    Yanlış malzemeye bağlanan bir barkod Barkod Tablosu üzerinden Tiger'ın
    malzeme kartına yazılır ve gelecek yılın sayımına taşınır (CLAUDE.md 12.6).
    """
    rs = _temiz(c, 2)
    r = yaz(rs[0]["seri"], rs[1]["seri"], UPC, SONRAKI)
    assert r["tip"] == "coklu"
    assert UPC in r["ogrenilmedi"]
    assert not c.execute("SELECT 1 FROM eslesme WHERE barkod=?", (UPC,)).fetchone()


def test_celiskili_grup_geri_alinabilir(c, ot, yaz):
    """Kullanıcı gerçekten yanlış yaptıysa Ctrl+Z son cihazı geri almalı."""
    rs = _temiz(c, 3)
    yaz(*[x["seri"] for x in rs], SONRAKI)
    matching.gerial(c, oturum_taze(c, ot))
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 2, \
        "grup başına bir cihaz geri alınmalı"


# --------------------------------------------------- öğrenme akışı BOZULMAMALI
def test_bir_seri_iki_taninmayan_normal_akis(c, ot, yaz):
    """Asıl öğrenme akışı: bir barkod tuttu, kalanları öğren.

    Çelişki dalı YALNIZCA birden çok FARKLI beklenen seri kaydına eşleşen
    barkod varsa çalışır. Buradaki barkodlar `bilinmiyor` / `upc` tipinde,
    `seri` değil — o dala hiç girmezler.
    """
    b = _temiz(c, 1)[0]
    r = yaz(b["seri"], UPC, "EDBP0153231475674", SONRAKI)
    assert r["tip"] == "eslesti", "normal akış çelişki sanıldı"
    assert set(r["ogrenilen"]) == {UPC, "EDBP0153231475674"}
    assert c.execute("SELECT kod FROM eslesme WHERE barkod=?",
                     (UPC,)).fetchone()["kod"] == b["kod"]


def test_ayni_kaydin_iki_barkodu_celiski_degildir(c, ot, yaz):
    """Aynı beklenen satırına eşleşen iki değer tek cihazdır — çelişki yok."""
    b = _temiz(c, 1)[0]
    r = yaz(b["seri"], b["seri"].lower(), SONRAKI)
    assert r["tip"] == "eslesti"
