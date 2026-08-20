"""Sayım dışı kalem filtresi (CLAUDE.md 3.4) — düzenlenebilir kural seti."""
from app import importer, matching


def test_varsayilan_kurallar_yuklendi(c):
    kurallar = importer.kural_ozeti(c, 1)
    desenler = {(k["tip"], k["desen"]) for k in kurallar}
    assert ("tur", "YAZILIM") in desenler
    assert ("aciklama", "LİSANS") in desenler
    assert all(k["varsayilan"] and k["aktif"] for k in kurallar)


def test_kural_ozeti_etkiyi_gosterir(c):
    """Kurulum ekranı kuralın kaç satırı sayım dışı bıraktığını göstermeli.

    Bu veride 'LIC' deseni 'SLIC' geçen bir malzemeyi de yakalıyor — kullanıcı
    kuralı kapatabilsin diye özet böyle sunuluyor.
    """
    ozet = {k["desen"]: k for k in importer.kural_ozeti(c, 1)}
    assert ozet["LIC"]["satir"] == 1
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE haric=1").fetchone()["n"] == 1


def test_kural_kapatilinca_kalem_geri_gelir(c, ot):
    onceki = matching.sayaclar(c, ot)["toplam"]
    c.execute("UPDATE haric_kural SET aktif=0 WHERE desen='LIC'")
    importer.haric_uygula(c, 1)
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE haric=1").fetchone()["n"] == 0
    assert matching.sayaclar(c, ot)["toplam"] == onceki + 1


def test_yeni_kural_eklenebilir(c, ot):
    c.execute("INSERT INTO haric_kural(tip,desen,aktif,varsayilan) VALUES('tur','TK',1,0)")
    sayim = importer.haric_uygula(c, 1)
    kid = c.execute("SELECT id FROM haric_kural WHERE desen='TK'").fetchone()["id"]
    assert sayim[kid]["satir"] == 10          # deneme.XLSX'te 10 satır TK türünde
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE haric=1 AND haric_sebep='tur:TK'"
                     ).fetchone()["n"] == 10


def test_haric_kalem_sayaci_sismez(c, ot):
    """Hariç kalemler 'kalan'a girmez ama okutulabilir (fiziksel olarak varsa)."""
    top = matching.sayaclar(c, ot)["toplam"]
    haric = c.execute("SELECT COUNT(*) n FROM beklenen WHERE ambar='1'").fetchone()["n"]
    assert top == haric - 1
