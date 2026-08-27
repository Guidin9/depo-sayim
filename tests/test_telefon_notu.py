"""`okutma.not_` metni — TELEFON EKRANIYLA SÖZLEŞME.

Telefon `OkutmaSonucu` görmez, akış satırını görür: barkodu laptoptaki okuyucu
okutuyor, telefon izliyor. Bu yüzden "sayıldı ama bir şey söylenmeli" kararını
`not_` alanındaki METİNDEN okuyor (`web/src/ekranlar/Telefon.tsx`,
`DIKKAT_NOT`).

Kırılganlığı burada: buradaki metin değişirse telefon sessizce YEŞİLE döner ve
rafın başındaki kullanıcı uyarıyı hiç görmez — ne test kırılır ne de tip
denetimi bunu görür, çünkü sözleşme iki ayrı dilde duran iki dize.

Bu dosya arka uç yarısını tutar; `web/src/ekranlar/Telefon.not.test.ts` arayüz
yarısını. Metni değiştirmek isteyen ikisini birden görmek zorunda.
"""
import pytest

from app import matching
from tests.conftest import AMBAR, oturum_taze

SONRAKI = "##SONRAKI##"

# `Telefon.tsx` -> DIKKAT_NOT ile BİREBİR aynı olmalı.
DIKKAT_NOT = ["çelişkili grup", "seri no seçilmedi"]


def _son_notlar(c, ot):
    return [r["not_"] or "" for r in c.execute(
        "SELECT not_ FROM okutma WHERE oturum=? ORDER BY id DESC", (ot["id"],))]


def test_celiskili_grup_notu_telefonun_aradigi_metni_tasir(c, ot, yaz):
    rs = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                      AND izleme='seri' AND kirli=0 AND seri<>'' ORDER BY id LIMIT 2""",
                   (AMBAR,)).fetchall()
    if len(rs) < 2:
        pytest.skip("test verisinde yeterli temiz seri kaydı yok")

    assert yaz(rs[0]["seri"], rs[1]["seri"], SONRAKI)["tip"] == "coklu"
    notlar = _son_notlar(c, ot)
    assert notlar, "çelişkili grup hiç satır yazmamış"
    for n in notlar:
        assert DIKKAT_NOT[0] in n, (
            "telefon bu satırı sarı yakamaz — `%s` metni notta yok" % DIKKAT_NOT[0])


def test_secilmemis_seri_notu_telefonun_aradigi_metni_tasir(c, ot, yaz):
    kod = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                       AND izleme='seri' AND kirli=1 GROUP BY kod
                       ORDER BY COUNT(*) DESC LIMIT 1""", (AMBAR,)).fetchone()
    if not kod:
        pytest.skip("test verisinde kirli slotu olan malzeme yok")

    # İki tanınmayan alfanümerik barkod -> hangisinin cihaza ait olduğu belirsiz.
    r = yaz(kod["kod"], "PN-ABCDEF-01", "SN-9911-XYZ-7745", SONRAKI)
    assert r["tip"] == "slot" and r["sn_secim"], "belirsizlik oluşmadı"

    n = _son_notlar(c, ot)[0]
    assert DIKKAT_NOT[1] in n, (
        "telefon bu satırı sarı yakamaz — `%s` metni notta yok" % DIKKAT_NOT[1])


def test_normal_slot_notu_dikkat_istemez(c, ot, yaz):
    """Tek aday varsa soru yok: telefon yeşil kalmalı, boş yere uyarmamalı."""
    kod = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                       AND izleme='seri' AND kirli=1 GROUP BY kod
                       ORDER BY COUNT(*) DESC LIMIT 1""", (AMBAR,)).fetchone()
    if not kod:
        pytest.skip("test verisinde kirli slotu olan malzeme yok")

    assert yaz(kod["kod"], "SN-TEK-ADAY-01", SONRAKI)["tip"] == "slot"
    n = _son_notlar(c, ot)[0]
    assert not any(x in n for x in DIKKAT_NOT), "gereksiz uyarı: %s" % n


def test_sozlesme_metinleri_arayuzdeki_listeyle_ayni():
    """Arayüzdeki `DIKKAT_NOT` ile buradaki liste birebir aynı olmalı.

    Dosyayı okuyup karşılaştırıyoruz: iki dilde duran bir sözleşmeyi ancak
    böyle kilitleyebiliyoruz. Arayüz dosyası yoksa (yalnız arka uç kurulumu)
    test atlanır.
    """
    import os
    import re

    yol = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "web", "src", "ekranlar", "Telefon.tsx")
    if not os.path.exists(yol):
        pytest.skip("arayüz kaynağı yok")
    with open(yol, encoding="utf-8") as f:
        kaynak = f.read()
    m = re.search(r"DIKKAT_NOT\s*=\s*\[(.*?)\]", kaynak, re.S)
    assert m, "Telefon.tsx içinde DIKKAT_NOT bulunamadı — sözleşme taşınmış olabilir"
    arayuz = re.findall(r'"([^"]+)"', m.group(1))
    assert arayuz == DIKKAT_NOT, (
        "Telefon.tsx ile bu dosya ayrıştı: arayüz %s, arka uç %s" % (arayuz, DIKKAT_NOT))
