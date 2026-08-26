"""ACIL_PLAN.md C grubu — sayım verisini bozmayan ama yanıltan davranışlar.

Hiçbiri sahada yanlış sayıma yol açmıyordu; hepsi ya listeyi kirletiyor, ya
kullanıcıyı yanlış yönlendiriyor, ya da geri almayı yarım bırakıyordu.
"""
import pytest

from app import importer, matching, reports
from tests.conftest import AMBAR, oturum_taze

SONRAKI = "##SONRAKI##"
BILINMEYEN = ("198701689928", "EDBP0153231475674")


def _kuyruga_at(yaz):
    return yaz(*BILINMEYEN, SONRAKI)


# ------------------------------------------------- kuyruk geri alma (A5 sınırı)
def test_gerial_kuyruktan_cozuleni_yeniden_acar(c, ot, yaz):
    """A5'in bilinen sınırıydı: kuyruk kaydı "çözüldü" kalıyordu.

    Okutma siliniyor ama kuyruk kaydı kapalı kaldığı için ürün hem sayımdan
    hem kuyruktan düşüyordu — yani hiçbir yerde görünmüyordu.
    """
    r = _kuyruga_at(yaz)
    hedef = matching.ara(c, ot["yukleme"], ot["ambar"], "0WGP72",
                         oturum=ot["id"], sadece_acik=True)["satirlar"][0]
    matching.kuyruk_coz(c, r["kuyruk_id"], hedef["id"])
    assert matching.bekleyen_kuyruk(c, ot["id"]) == []

    matching.gerial(c, oturum_taze(c, ot))
    assert len(matching.bekleyen_kuyruk(c, ot["id"])) == 1
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0


def test_gerial_kuyruktan_fazlayi_yeniden_acar(c, ot, yaz):
    r = _kuyruga_at(yaz)
    matching.kuyruk_fazla(c, r["kuyruk_id"], ad="bilinmeyen kutu")
    assert matching.bekleyen_kuyruk(c, ot["id"]) == []

    matching.gerial(c, oturum_taze(c, ot))
    assert len(matching.bekleyen_kuyruk(c, ot["id"])) == 1
    assert matching.sayaclar(c, ot)["fazla"] == 0


def test_gerial_sarkan_fotograf_birakmaz(c, ot, yaz):
    """Silinen okutmaya bağlı fotoğraf kuyruk kaydında kalmalı."""
    r = _kuyruga_at(yaz)
    fid = c.execute("INSERT INTO kuyruk_foto(kuyruk,ts,tur,boyut,veri) "
                    "VALUES(?,'t','image/jpeg',3,?)",
                    (r["kuyruk_id"], b"abc")).lastrowid
    matching.kuyruk_fazla(c, r["kuyruk_id"], ad="kutu")
    ok_id = c.execute("SELECT id FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                      (ot["id"],)).fetchone()["id"]
    assert c.execute("SELECT okutma FROM kuyruk_foto WHERE id=?",
                     (fid,)).fetchone()["okutma"] == ok_id

    matching.gerial(c, oturum_taze(c, ot))
    f = c.execute("SELECT * FROM kuyruk_foto WHERE id=?", (fid,)).fetchone()
    assert f is not None, "fotoğraf silinmemeli"
    assert f["okutma"] is None, "silinmiş okutmaya işaret etmemeli"
    assert f["kuyruk"] == r["kuyruk_id"]


# ------------------------------------------------------------- LIKE kaçışı
@pytest.mark.parametrize("q", ["%", "%%", "0WGP72%", "_WGP72"])
def test_arama_joker_karakteri_harf_gibi_arar(c, ot, q):
    """Kullanıcının yazdığı `%` ve `_` joker DAVRANMAMALI.

    `%` tek başına tüm tabloyu çekiyordu; kullanıcı aramanın çalıştığını sanıp
    listeden yanlış kaydı seçebilirdi.
    """
    r = matching.ara(c, ot["yukleme"], ot["ambar"], q, oturum=ot["id"])
    assert r["toplam"] == 0, "%r joker gibi davrandı" % q


def test_arama_alt_cizgiyi_harf_olarak_arar(c, ot):
    """`_` bu veride GERÇEKTEN geçiyor (`R730_2X`, `A-3660_W_16`).

    Joker olsaydı "en az bir karakter" demek olur ve neredeyse tüm tabloyu
    döndürürdü; artık yalnızca gerçekten alt çizgi taşıyan satırlar geliyor.
    """
    tum = matching.ara(c, ot["yukleme"], ot["ambar"], "", oturum=ot["id"])["toplam"]
    r = matching.ara(c, ot["yukleme"], ot["ambar"], "_", oturum=ot["id"])
    assert 0 < r["toplam"] < tum / 10
    for s in r["satirlar"]:
        assert "_" in (s["kod"] + (s["aciklama"] or "") + (s["seri"] or ""))


def test_arama_normal_sorgu_bozulmadi(c, ot):
    r = matching.ara(c, ot["yukleme"], ot["ambar"], "0WGP72", oturum=ot["id"])
    assert r["toplam"] > 0


def test_arama_tire_ve_bosluk_iceren_kodu_bulur(c, ot):
    """Regresyon: kaçış normal noktalamayı bozmamalı."""
    for q in ("210-ACXU", "BRODCOM 57414"):
        assert matching.ara(c, ot["yukleme"], ot["ambar"], q,
                            oturum=ot["id"])["toplam"] > 0


# ------------------------------------------------------- Barkod Tablosu kapsamı
def test_barkod_tablosu_baska_ambari_listelemez(c, ot, yaz):
    """Sekmenin işi "Tiger'da HANGİ karta ne yazacağım".

    Eskiden `eslesme` tablosunun tamamı dökülüyordu: başka ambarların
    malzemeleri, önceki sayımlardan öğrenilen her şey ve basılmış her `DM-`
    etiketi her raporda yeniden çıkıyordu.
    """
    c.execute("INSERT OR REPLACE INTO eslesme VALUES('YABANCIBARKOD','YOK-BOYLE-KOD','','t')")
    b = c.execute("""SELECT * FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                     AND izleme='seri' AND kirli=0 AND seri<>'' ORDER BY id LIMIT 1""",
                  (AMBAR,)).fetchone()
    yaz(b["seri"], "190017273624", SONRAKI)

    satirlar = reports.rapor_verisi(c, ot["id"])["Barkod Tablosu"]["satirlar"]
    kodlar = {s[0] for s in satirlar}
    assert "190017273624" in kodlar, "bu ambarda öğrenilen barkod listede olmalı"
    assert "YABANCIBARKOD" not in kodlar, "başka ambarın barkodu sızdı"


def test_barkod_tablosu_haric_kalemi_listelemez(c, ot):
    from tests.conftest import haric_kur
    _, _, kod = haric_kur(c)
    c.execute("INSERT OR REPLACE INTO eslesme VALUES('HARICBARKOD',?,'','t')", (kod,))
    satirlar = reports.rapor_verisi(c, ot["id"])["Barkod Tablosu"]["satirlar"]
    assert "HARICBARKOD" not in {s[0] for s in satirlar}


def test_barkod_tablosu_dipnotu_kapsami_soyluyor(c, ot):
    dip = reports.rapor_verisi(c, ot["id"])["Barkod Tablosu"]["dipnot"]
    assert any("ambarındaki" in d for d in dip)


# ------------------------------------------------------- ölü 'bilinmiyor' tipi
def test_bilinmiyor_tipi_hicbir_yerde_yazilmiyor(c, ot, yaz):
    """Üç ayrı sorgu bu tipi sayıyordu ama hiçbir sürüm onu yazmamış."""
    yaz(*BILINMEYEN, SONRAKI)
    yaz("HICBIRSEYEUYMAYAN1", "##FAZLA##")
    tipler = {r["tip"] for r in c.execute("SELECT DISTINCT tip FROM okutma")}
    assert "bilinmiyor" not in tipler
    assert tipler <= {"eslesti", "kod", "fazla"}


# ------------------------------------------------------- malzeme türü görünürlüğü
def test_ozet_gercek_malzeme_turlerini_bildirir(c):
    """§7b: tür kuralları neden tutmuyor, kullanıcı görebilmeli.

    Örnek raporda `Malzeme Türü` sütunu `TM` / `TK` kısa kodları döndürüyor;
    varsayılan desenlerin (`YAZILIM`, `HİZMET`…) hiçbiri tutmuyor. Türler
    özette olmadan kullanıcı NEDEN tutmadığını göremiyordu.
    """
    o = importer.ozetle(c, 1)
    assert o["turler"], "malzeme türleri özette olmalı"
    assert sum(t["satir"] for t in o["turler"]) == o["satir"]
    assert all("tur" in t and "satir" in t for t in o["turler"])
