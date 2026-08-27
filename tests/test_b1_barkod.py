"""B1 — okutulan barkodun kayıttan düşmesi (gerçek sayım bildirimi).

Saha tarifi: ürünün üstünde fabrika barkodu var, önce o okutuluyor, sonra
üzerine bizim DS- etiketimiz yapıştırılıyor. Kayıt eşleşiyor ama okutulan
barkod `okutma` satırında görünmüyordu.

Kök sebep: `grup_coz` bir grubu TEK ÜRÜN kabul ediyor ama `eslesti` ve `slot`
dalları `okutma.ham` alanına grubun yalnızca bir barkodunu yazıyordu.
`kuyruk_coz` / `kuyruk_fazla` ise hepsini yazıyordu — üç dal aynı sözleşmede
değildi.

İkinci yarısı: `ham` iki iş birden yapıyordu (denetim izi + Tiger'a önerilecek
seri numarası). Gruba malzeme kodu da girince rapor onu seri no sanabilirdi —
ACIL_PLAN 3'te kapatılan hata. Karar `okutma.yeni_seri` sütununa taşındı.
"""
import pytest

from app import matching, reports
from tests.conftest import AMBAR

SONRAKI = "##SONRAKI##"
UPC = "190017273624"          # Tiger'da karşılığı yok


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


def _son(c, ot):
    return c.execute("SELECT * FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                     (ot["id"],)).fetchone()


def _satirlar(veri, sekme):
    return veri[sekme]["satirlar"]


# --------------------------------------------------------------- eslesti dalı
def test_eslesti_grubun_butun_barkodlarini_saklar(c, ot, yaz):
    """Fabrika barkodu + gerçek S/N birlikte okutuldu; ikisi de kayıtta."""
    b = _temiz_seri(c)
    r = yaz(UPC, b["seri"], SONRAKI)
    assert r["tip"] == "eslesti"

    x = _son(c, ot)
    assert UPC in x["ham"], "okutulan fabrika barkodu kayıttan düşmemeli"
    assert b["seri"] in x["ham"]
    assert x["ham"] == UPC + " + " + b["seri"], "okutma sırası korunmalı"


def test_eslesti_tiger_duzeltmesi_onermez(c, ot, yaz):
    """Birebir eşleşen kayıtta Tiger'ın seri numarası zaten doğru.

    Öneri BOŞ olmalı ama NULL OLMAMALI: NULL yalnızca "bu sütun eklenmeden
    önce yazılmış" demektir ve rapor orada eski kurala (`_yeni_seri(ham)`)
    düşer. `ham` malzeme kodunu da taşıdığı için o kural kodu seri no diye
    önerebiliyor — aşağıdaki test bunu gerçek veriyle kilitliyor.
    """
    b = _temiz_seri(c)
    yaz(UPC, b["seri"], SONRAKI)
    x = _son(c, ot)
    assert x["yeni_seri"] == "", "öneri yok"
    assert x["yeni_seri"] is not None, "NULL 'eski kayıt' demek — yeni satırda olamaz"


def test_gomulu_seri_kirli_kayitta_onerilir(c, ot, yaz):
    """5. adım: kirli kaydın içine gömülü gerçek S/N okutulunca önerilmeli."""
    r = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND kirli=1
                     AND izleme='seri' AND LENGTH(seri)>18 ORDER BY id LIMIT 1""",
                  (AMBAR,)).fetchone()
    if not r:
        pytest.skip("uzun kirli kayıt yok")
    gomulu = r["seri"][-10:]
    assert yaz(gomulu, SONRAKI)["tip"] == "eslesti"
    assert _son(c, ot)["yeni_seri"] == gomulu


def test_eslesti_malzeme_kodunu_tigera_seri_diye_yazmaz(c, ot, yaz):
    """REGRESYON: malzeme kodu seri numarasından UZUNSA eski kural onu seçiyordu.

    Gerçek veriyle üretildi (2026-08-27):
      900-5G144-2200-000 TD SYNNEX 8000USD 2  ->  900-5G144-2200-000
    Yani uygulama Tiger'a tam da temizlemeye çalıştığı deseni yazdırıyordu
    (`kirli_mi(kod, kod)` KİRLİ döner). ACIL_PLAN 3'ün aynısı, bu kez
    `eslesti` dalında.
    """
    r = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND kirli=1
                     AND izleme='seri' AND LENGTH(kod)>=10
                     AND LENGTH(seri)>LENGTH(kod)+8
                     ORDER BY LENGTH(kod) DESC LIMIT 1""", (AMBAR,)).fetchone()
    if not r:
        pytest.skip("malzeme kodu uzun olan kirli kayıt yok")
    # Koddan KISA, boşluksuz bir parça: uzunluk yarışını malzeme kodu kazanmalı
    # ki eski kuralın hatası ortaya çıksın.
    from app.norm import norm
    gomulu = norm(r["seri"])[-8:]
    assert not norm(gomulu).startswith(norm(r["kod"]))
    assert len(gomulu) < len(r["kod"]), "test kurgusu: kod daha uzun olmalı"
    assert yaz(r["kod"], gomulu, SONRAKI)["tip"] == "eslesti"

    duz = _satirlar(reports.rapor_verisi(c, ot["id"]), "Tiger Düzeltme")
    onerilen = [s[3] for s in duz]
    assert r["kod"] not in onerilen, "malzeme kodu Tiger'a seri no diye önerildi"
    assert onerilen == [gomulu]


def test_kirli_oneri_tigera_ulasmaz(c, ot, yaz):
    """Son savunma: önerilen değerin KENDİSİ kirliyse rapora girmez.

    Bu sayfanın tek işi kirli seri numaralarını temizlemek; kirli bir değer
    önermek yeni bir kirlilik yazdırmak olurdu.
    """
    kod = _kirli_malzeme(c)
    yaz(kod, SONRAKI)                        # slot dolar, öneri yok
    slot = c.execute("""SELECT o.id FROM okutma o JOIN beklenen b ON b.id=o.beklenen_id
                        WHERE o.oturum=? AND b.kirli=1 ORDER BY o.id DESC LIMIT 1""",
                     (ot["id"],)).fetchone()
    # motoru atlayıp doğrudan kirli bir öneri yazalım — ağ tutmalı
    c.execute("UPDATE okutma SET yeni_seri=? WHERE id=?", (kod + "SAYIM9", slot["id"]))
    veri = reports.rapor_verisi(c, ot["id"])
    assert _satirlar(veri, "Tiger Düzeltme") == []
    assert any("elendi" in d for d in veri["Tiger Düzeltme"]["dipnot"]),         "eleme sessiz kalmamalı"


# ------------------------------------------------------------------ slot dalı
def test_slot_grubun_butun_barkodlarini_saklar(c, ot, yaz):
    kod = _kirli_malzeme(c)
    r = yaz(kod, UPC, SONRAKI)
    assert r["tip"] == "slot"

    x = _son(c, ot)
    assert kod in x["ham"] and UPC in x["ham"]
    assert x["yeni_seri"] == UPC, "Tiger'a önerilen numara ayrı sütunda"


def test_slot_malzeme_kodunu_tigera_seri_diye_yazmaz(c, ot, yaz):
    """`ham` artık malzeme kodunu da taşıyor — rapor ona bakmamalı.

    Bu testin varlık sebebi: B1 düzeltmesi ACIL_PLAN 3'ün kapattığı hatayı
    geri getirebilirdi. `_yeni_seri(ham)` en uzun adayı seçer; grup
    "MALZEMEKODU + DS-000001" ise malzeme kodu daha uzun olabilir.
    """
    kod = _kirli_malzeme(c)
    yaz(kod, SONRAKI)                       # yalnız malzeme kodu okutuldu
    x = _son(c, ot)
    assert x["ham"] == kod, "denetim izi okutulanı taşır"
    assert x["yeni_seri"] == "", "ama Tiger'a öneri ÜRETİLMEZ"

    duz = _satirlar(reports.rapor_verisi(c, ot["id"]), "Tiger Düzeltme")
    assert all(kod not in str(s[3]) for s in duz), \
        "malzeme kodu YENİ seri no sütununda görünemez"


def test_slot_uretici_seri_numarasi_kazanir(c, ot, yaz):
    """Üretici S/N okutulduysa havuz etiketi değil O yazılır (garanti izi)."""
    from app import etiketler
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "seri", adet=3)
    yaz(kod, UPC, "DS-000001", SONRAKI)
    x = _son(c, ot)
    assert x["yeni_seri"] == UPC
    for parca in (kod, UPC, "DS-000001"):
        assert parca in x["ham"], "%s denetim izinden düşmüş" % parca


# ---------------------------------------------------------------------- rapor
def test_eslesen_sekmesinde_okutulan_barkodlar_var(c, ot, yaz):
    b = _temiz_seri(c)
    yaz(UPC, b["seri"], SONRAKI)
    veri = reports.rapor_verisi(c, ot["id"])
    i = veri["Eşleşen"]["basliklar"].index("Okutulan Barkodlar")
    assert any(UPC in str(s[i]) for s in _satirlar(veri, "Eşleşen"))


def test_eski_kayitlar_hala_raporlanir(c, ot, yaz):
    """`yeni_seri` sütunu eklenmeden yazılmış satırlarda eski kural sürer.

    Göç sütunu NULL bırakır; o satırlarda `ham` hâlâ tek değerdi.
    """
    kod = _kirli_malzeme(c)
    yaz(kod, UPC, SONRAKI)
    c.execute("UPDATE okutma SET yeni_seri=NULL, ham=? WHERE oturum=?", (UPC, ot["id"]))
    duz = _satirlar(reports.rapor_verisi(c, ot["id"]), "Tiger Düzeltme")
    assert [s[3] for s in duz] == [UPC]
