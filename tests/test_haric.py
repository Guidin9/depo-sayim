"""Sayım dışı kalem filtresi (CLAUDE.md 3.4) — düzenlenebilir kural seti.

Bu dosya 2026-08-26'da yeniden yazıldı. Eski hâli varsayılan `LIC` kuralının
örnek veride tek bir satır yakalamasına dayanıyordu — ama o satır bir lisans
DEĞİL, gerçek bir ağ kartıydı (`303-195-100C-001`, "EMC ... Dual Port 10GB
Ethernet S-LIC-E Optical"). Testler hatayı doğru davranış diye kilitlemişti.

Artık iki şey ayrı ayrı sınanıyor:
  * Varsayılan kurallar YANLIŞ POZİTİF vermemeli (LIC → LICENSE düzeltmesi).
  * Hariç mekanizması, veriye gerçekten uyan bir kuralla doğru çalışmalı
    (`conftest.haric_kur`).
"""
from app import db as dbm
from app import importer, matching
from tests.conftest import haric_kur, oturum_taze

SONRAKI = "##SONRAKI##"


def test_varsayilan_kurallar_yuklendi(c):
    kurallar = importer.kural_ozeti(c, 1)
    desenler = {(k["tip"], k["desen"]) for k in kurallar}
    assert ("tur", "YAZILIM") in desenler
    assert ("aciklama", "LİSANS") in desenler
    assert ("aciklama", "LICENSE") in desenler
    assert ("aciklama", "LIC") not in desenler        # fazla geniş, kaldırıldı
    assert all(k["varsayilan"] and k["aktif"] for k in kurallar)


def test_varsayilan_kurallar_gercek_donanimi_haric_etmez(c):
    """Regresyon: üç harflik `LIC` deseni bir ağ kartını lisans sanıyordu.

    Desenler `norm()` çıktısında alt dize olarak aranıyor; normalize edilmiş
    metinde kelime sınırı yok ("...ETHERNETSLICOPTICAL"). Ambar 1'de hariç
    edilen TEK satır buydu — üstelik gerçek yazılım lisansları (OEM MICROSOFT
    SQL SERVER) filtreye hiç takılmıyordu. Filtre tam tersini yapıyordu.
    """
    kart = c.execute("SELECT haric, haric_sebep FROM beklenen "
                     "WHERE kod='303-195-100C-001' LIMIT 1").fetchone()
    if kart:
        assert not kart["haric"], "gerçek donanım sayım dışı bırakıldı"
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE haric=1").fetchone()["n"] == 0


def test_lic_kurali_mevcut_veritabaninda_duzeltilir(tmp_path):
    """`kurallari_tohumla` yalnızca tablo boşken çalışır — göç şart.

    Varsayılan listesini düzeltmek mevcut veritabanlarına ulaşmıyor;
    `lic_kuralini_duzelt()` ulaştırıyor ve hariç bayraklarını yeniden
    hesaplıyor.
    """
    yol = str(tmp_path / "eski.db")
    c = dbm.baglan(yol)
    c.execute("UPDATE haric_kural SET desen='LIC' WHERE desen='LICENSE'")
    c.commit()
    c.close()

    c = dbm.baglan(yol)
    try:
        desenler = {r["desen"] for r in c.execute(
            "SELECT desen FROM haric_kural WHERE tip='aciklama'")}
        assert "LIC" not in desenler and "LICENSE" in desenler
    finally:
        c.close()

    # Idempotent: ikinci açılış hiçbir şey bozmamalı.
    c = dbm.baglan(yol)
    try:
        assert c.execute("SELECT COUNT(*) n FROM haric_kural WHERE tip='aciklama' "
                         "AND desen='LICENSE'").fetchone()["n"] == 1
    finally:
        c.close()


def test_lic_duzeltmesi_elle_yazilan_kurala_dokunmaz(tmp_path):
    """Kullanıcı deseni bilerek `LIC` yaptıysa kararı onundur."""
    yol = str(tmp_path / "elle.db")
    c = dbm.baglan(yol)
    c.execute("INSERT OR IGNORE INTO haric_kural(tip,desen,aktif,varsayilan) "
              "VALUES('aciklama','LIC',1,0)")
    c.commit()
    c.close()

    c = dbm.baglan(yol)
    try:
        assert c.execute("SELECT varsayilan FROM haric_kural WHERE desen='LIC'"
                         ).fetchone()["varsayilan"] == 0
    finally:
        c.close()


def test_kural_ozeti_etkiyi_gosterir(c):
    """Kurulum ekranı kuralın kaç satırı sayım dışı bıraktığını göstermeli."""
    _, satir, _ = haric_kur(c)
    ozet = {k["desen"]: k for k in importer.kural_ozeti(c, 1)}
    assert ozet["TK"]["satir"] == satir == 10
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE haric=1"
                     ).fetchone()["n"] == satir


def test_kural_kapatilinca_kalem_geri_gelir(c, ot):
    onceki = matching.sayaclar(c, ot)["toplam"]
    kid, satir, _ = haric_kur(c)
    assert matching.sayaclar(c, ot)["toplam"] == onceki - satir

    c.execute("UPDATE haric_kural SET aktif=0 WHERE id=?", (kid,))
    importer.haric_uygula(c, 1)
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE haric=1").fetchone()["n"] == 0
    assert matching.sayaclar(c, ot)["toplam"] == onceki


def test_yeni_kural_eklenebilir(c, ot):
    kid, satir, _ = haric_kur(c)
    assert satir == 10          # deneme.XLSX'te 10 satır TK türünde
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE haric=1 "
                     "AND haric_sebep='tur:TK'").fetchone()["n"] == 10


def test_haric_kalem_sayaci_sismez(c, ot):
    """Hariç kalemler 'toplam'a girmez."""
    tum = c.execute("SELECT COUNT(*) n FROM beklenen WHERE ambar='1'").fetchone()["n"]
    _, satir, _ = haric_kur(c)
    assert matching.sayaclar(c, ot)["toplam"] == tum - satir


def test_haric_kalem_okutulunca_uyarir(c, ot, yaz):
    """Sayım dışı kalem okutulunca SESSİZ kalınmaz ve hiçbir şey yazılmaz.

    Regresyon (ACIL_PLAN.md A3): `coz()` `haric` alanına bakmıyordu. Kalem
    normal gibi işleniyor, ekran yeşil yanıp "eşleşti" sesi veriyor, ama
    `sayaclar()` hariç satırları saymadığı için sayaç dönmüyordu. Raporda da
    yoktu — `eksik_kayitlar` hariç satırları atlıyor. Kullanıcı elindeki
    fiziksel ürünü okutup "tamam" sesini duyuyor, ürün mutabakattan tamamen
    buharlaşıyordu.
    """
    _, _, kod = haric_kur(c)
    b = c.execute("SELECT * FROM beklenen WHERE kod=? AND haric=1 AND seri<>'' "
                  "ORDER BY id LIMIT 1", (kod,)).fetchone()

    r = yaz(b["seri"], SONRAKI)
    assert r["tip"] == "haric"
    assert r["kod"] == b["kod"]
    assert r["sebep"] == "tur:TK"
    assert r["ses"] == "uyari"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0


def test_haric_kalem_malzeme_koduyla_da_uyarir(c, ot, yaz):
    """Seri değil malzeme kodu okutulduğunda da aynı kapı işlemeli."""
    _, _, kod = haric_kur(c)
    r = yaz(kod, SONRAKI)
    assert r["tip"] == "haric"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0


def test_kural_kapatilinca_kalem_okutulabilir(c, ot, yaz):
    """Kullanıcı kuralı kapatırsa kalem normal sayılmalı — çıkış yolu var."""
    kid, _, kod = haric_kur(c)
    b = c.execute("SELECT * FROM beklenen WHERE kod=? AND haric=1 AND seri<>'' "
                  "ORDER BY id LIMIT 1", (kod,)).fetchone()
    assert yaz(b["seri"], SONRAKI)["tip"] == "haric"

    c.execute("UPDATE haric_kural SET aktif=0 WHERE id=?", (kid,))
    importer.haric_uygula(c, 1)
    r = matching.okut(c, oturum_taze(c, ot), b["seri"])
    assert matching.okut(c, oturum_taze(c, ot), SONRAKI)["tip"] == "eslesti"
    assert r["coz"] == "seri"
