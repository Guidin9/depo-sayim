"""`##GERIAL##`, boş `##FAZLA##` ve slot doldurmanın yan etkileri.

ACIL_PLAN.md A4, A5 ve A6'nın regresyon takımı. Üçü de aynı sınıftan: motor,
okutmanın KENDİ SATIRI DIŞINDA bir şey yaratıyor (öğrenilen barkod, bağlanan
etiket, Tiger'a yazılacak seri numarası, hayalet fazla kaydı) ve bu yan etki
ya geri alınamıyor ya da hiç istenmemişti.
"""
import json

import pytest

from app import etiketler, matching, reports
from tests.conftest import AMBAR, bitir, oturum_taze

SONRAKI = "##SONRAKI##"
YENI_UPC = "190017273624"          # Tiger'da karşılığı yok — öğrenilecek


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


# ------------------------------------------------------------------ A4
def test_bos_tamponda_fazla_kayit_yaratmaz(c, ot, yaz):
    """Regresyon (A4): tek tuş (F3) oturumu kilitliyordu.

    `##ATLA##` boş tamponu kontrol ediyordu, `##FAZLA##` etmiyordu. Barkodu
    olmayan bir fazla kaydı oluşuyor, ne olduğu sorulamıyor (sorulacak bir şey
    yok) ama `adsiz_fazlalar` onu adsız sayıp bitirme kapısını kilitliyordu.
    """
    r = yaz("##FAZLA##")
    assert r["tip"] == "bos"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0
    assert matching.adsiz_fazlalar(c, ot["id"]) == []
    assert bitir(yaz)["tip"] == "bitti"


def test_dolu_tamponda_fazla_hala_calisir(c, ot, yaz):
    r = yaz("HICBIRSEYEUYMAYAN1", "##FAZLA##")
    assert r["tip"] == "fazla_elle"
    assert len(r["okutma"]) == 1


# ------------------------------------------------------------------ A5
def test_gerial_ogrenilen_barkodu_unutur(c, ot, yaz):
    """Regresyon (A5): geri alınan öğrenme kalıcı kalıyordu.

    Yanlış ürüne okutulan bir barkod Ctrl+Z ile geri alınsa bile o malzemeye
    bağlı kalıyor ve Barkod Tablosu sekmesinden Tiger'ın malzeme kartına
    yazılmak üzere listeleniyordu.
    """
    b = _temiz_seri(c)
    r = yaz(b["seri"], YENI_UPC, SONRAKI)
    assert r["tip"] == "eslesti" and r["ogrenilen"] == [YENI_UPC]
    assert c.execute("SELECT 1 FROM eslesme WHERE barkod=?", (YENI_UPC,)).fetchone()

    g = yaz("##GERIAL##")
    assert g["tip"] == "gerial"
    assert g["unutulan"] == [YENI_UPC]
    assert not c.execute("SELECT 1 FROM eslesme WHERE barkod=?", (YENI_UPC,)).fetchone()
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0


def test_gerial_sonrasi_barkod_rapora_girmez(c, ot, yaz):
    """Asıl zarar buradaydı: Barkod Tablosu Tiger'a yazılacak listeyi üretiyor."""
    b = _temiz_seri(c)
    yaz(b["seri"], YENI_UPC, SONRAKI)
    barkodlar = reports.rapor_verisi(c, ot["id"])["Barkod Tablosu"]["satirlar"]
    assert any(s[0] == YENI_UPC for s in barkodlar)

    yaz("##GERIAL##")
    barkodlar = reports.rapor_verisi(c, ot["id"])["Barkod Tablosu"]["satirlar"]
    assert not any(s[0] == YENI_UPC for s in barkodlar)


def test_gerial_etiket_baglamasini_cozer(c, ot, yaz):
    """Etiket havuza geri döner — numara tüketilmez, defter kaydı durur."""
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "seri", adet=3)
    r = yaz(kod, "DS-000001", SONRAKI)
    assert r["tip"] == "slot" and r["etiket"] == "DS-000001"
    e = c.execute("SELECT * FROM etiket WHERE kod='DS000001'").fetchone()
    assert e["malzeme"] == kod and e["beklenen_id"]

    g = yaz("##GERIAL##")
    assert g["etiket_cozuldu"] == "DS-000001"
    e = c.execute("SELECT * FROM etiket WHERE kod='DS000001'").fetchone()
    assert e is not None, "etiket defterden SİLİNMEMELİ, yalnızca çözülmeli"
    assert e["malzeme"] is None and e["beklenen_id"] is None


def test_gerial_grup_kapsaminda_da_temizler(c, ot, yaz):
    b = _temiz_seri(c)
    yaz(b["seri"], YENI_UPC, SONRAKI)
    g = matching.gerial(c, oturum_taze(c, ot), kapsam="grup")
    assert g["kapsam"] == "grup"
    assert g["unutulan"] == [YENI_UPC]
    assert not c.execute("SELECT 1 FROM eslesme WHERE barkod=?", (YENI_UPC,)).fetchone()


def test_gerial_baskasinin_ogrettigi_barkoda_dokunmaz(c, ot, yaz):
    """Yalnızca kendi yan etkisini siler."""
    b1 = _temiz_seri(c)
    yaz(b1["seri"], YENI_UPC, SONRAKI)
    b2 = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                      AND izleme='seri' AND kirli=0 AND seri<>'' AND id<>?
                      ORDER BY id LIMIT 1""", (AMBAR, b1["id"])).fetchone()
    yaz(b2["seri"], "198701689928", SONRAKI)

    yaz("##GERIAL##")               # yalnızca ikinci grubu geri al
    assert c.execute("SELECT 1 FROM eslesme WHERE barkod='198701689928'").fetchone() is None
    assert c.execute("SELECT 1 FROM eslesme WHERE barkod=?", (YENI_UPC,)).fetchone()


def test_geri_sutunu_yan_etki_yoksa_bos(c, ot, yaz):
    b = _temiz_seri(c)
    yaz(b["seri"], SONRAKI)
    assert c.execute("SELECT geri FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                     (ot["id"],)).fetchone()["geri"] is None


def test_geri_sutunu_okunabilir_json(c, ot, yaz):
    b = _temiz_seri(c)
    yaz(b["seri"], YENI_UPC, SONRAKI)
    ham = c.execute("SELECT geri FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                    (ot["id"],)).fetchone()["geri"]
    assert json.loads(ham) == {"ogrenilen": [YENI_UPC]}


# ------------------------------------------------------------------ A6
def test_slot_seri_numarasi_yoksa_malzeme_kodu_yazilmaz(c, ot, yaz):
    """Regresyon (A6): Tiger'a "seri numarasını 04RW5H yap" deniyordu.

    Yalnızca malzeme kodu okutulduğunda (ne üretici S/N, ne DS- etiketi)
    `okutma.ham` alanına MALZEME KODU yazılıyordu. Rapor o alanı "Tiger'a
    yazılacak gerçek seri no" diye kullanıyor; `kirli_mi(kod, kod)` KİRLİ
    döner, yani uygulamanın temizlemeye çalıştığı deseni Tiger'a kendisi
    yazdırıyordu.

    Karar artık `okutma.yeni_seri` sütununda (B1): `ham` grubun denetim izidir
    ve okutulan malzeme kodunu TAŞIR — yasak olan şey onu Tiger'a seri
    numarası diye önermek.
    """
    kod = _kirli_malzeme(c)
    r = yaz(kod, SONRAKI)
    assert r["tip"] == "slot"
    assert r["yeni"] == ""
    assert r["sn_yok"] is True
    assert r["ses"] == "uyari", "sessiz yeşil geçilmemeli"

    x = c.execute("SELECT ham, yeni_seri FROM okutma WHERE oturum=? "
                  "ORDER BY id DESC LIMIT 1", (ot["id"],)).fetchone()
    assert x["yeni_seri"] == "", "malzeme kodu seri numarası diye önerilmemeli"
    assert x["ham"] == kod, "okutulan barkod denetim izinde durmalı"


def test_slot_seri_numarasi_yoksa_tiger_duzeltmesi_uretilmez(c, ot, yaz):
    kod = _kirli_malzeme(c)
    yaz(kod, SONRAKI)
    duz = reports.rapor_verisi(c, ot["id"])["Tiger Düzeltme"]["satirlar"]
    assert duz == []


def test_slot_seri_numarasi_yoksa_sayim_yine_islenir(c, ot, yaz):
    """Saymak birincil iş; Tiger'ın seri numarasını düzeltmek ikincil."""
    kod = _kirli_malzeme(c)
    onceki = matching.sayaclar(c, ot)["okutulan"]
    yaz(kod, SONRAKI)
    assert matching.sayaclar(c, ot)["okutulan"] == onceki + 1


def test_slot_seri_numarasi_varsa_duzeltme_uretilir(c, ot, yaz):
    """Regresyon: normal yol bozulmadı."""
    kod = _kirli_malzeme(c)
    r = yaz(kod, "GERCEKSN12345", SONRAKI)
    assert r["tip"] == "slot" and r["yeni"] == "GERCEKSN12345"
    assert r["sn_yok"] is False and r["ses"] == "ok"
    duz = reports.rapor_verisi(c, ot["id"])["Tiger Düzeltme"]["satirlar"]
    assert len(duz) == 1 and duz[0][3] == "GERCEKSN12345"


def test_tiger_duzeltmesi_asla_malzeme_kodunu_onermez(c, ot, yaz):
    """Genel kural: "YENİ seri no" sütunu malzeme kodunun kendisi olamaz.

    Olursa `kirli_mi` onu bir sonraki sayımda yine kirli sayar — düzeltme
    kendi kendini bozar.
    """
    from app.norm import norm
    for kod in [r["kod"] for r in c.execute(
            """SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
               AND izleme='seri' AND kirli=1 GROUP BY kod LIMIT 5""", (AMBAR,))]:
        yaz(kod, SONRAKI)
    for satir in reports.rapor_verisi(c, ot["id"])["Tiger Düzeltme"]["satirlar"]:
        assert norm(satir[3]) != norm(satir[0]), satir


# ------------------------------------------------- B7: ##GERIAL## grup kapsamı
def test_gerial_cok_satirli_adedi_tamamen_geri_alir(c, ot, yaz):
    """Regresyon (2026-08-27).

    `##ADET-5##` çok lotlu bir malzemede 5 ayrı satır açıyor (`_adet_dagit`).
    `gerial` son SATIRI siliyordu: kullanıcı geri aldığını sanıyor, 4 adet
    sayımda kalıyordu. Üstelik `geri` (öğrenme / etiket) yalnızca ilk satırda
    durduğu için yan etkiler de temizlenmiyordu. `okutma_sil` bunu zaten grup
    bazlı yapıyordu — iki yol aynı sözleşmede değildi.
    """
    kod = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar='1'
                       AND izleme='lot' GROUP BY kod HAVING COUNT(*)>3
                       ORDER BY COUNT(*) DESC LIMIT 1""").fetchone()
    if not kod:
        pytest.skip("test verisinde çok lotlu malzeme yok")

    r = yaz("##ADET-5##", kod["kod"], "##SONRAKI##")
    assert r["tip"] == "adet" and r["satir"] > 1, "adet tek satıra yazıldı"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == r["satir"]

    g = matching.gerial(c, oturum_taze(c, ot))
    assert g["silinen"] == r["satir"]
    assert c.execute("SELECT COALESCE(SUM(miktar),0) s FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["s"] == 0, "adet yarım kaldı"
