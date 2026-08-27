"""Test altyapısı.

deneme.XLSX (Ambar 1 Seri/Lot Envanter Raporu, 870 satır) bir kez yüklenip
şablon veritabanı olarak saklanır; her test bu şablonun kopyasıyla çalışır.
"""
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db as dbm  # noqa: E402
from app import importer, oturumlar  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERI_DOSYA = os.path.join(KOK, "deneme.XLSX")
AMBAR = "1"


def pytest_collection_modifyitems(config, items):
    """Veri dosyasi yoksa butun paketi atla.

    deneme.XLSX gercek stok miktarlari, seri numaralari ve tutarlar iceriyor;
    bu yuzden depoda degil (.gitignore). Testleri calistirmak icin kendi Tiger
    Seri/Lot Envanter Raporu ciktinizi proje kokune bu adla koyun.
    """
    if os.path.exists(VERI_DOSYA):
        return
    atla = pytest.mark.skip(
        reason="deneme.XLSX yok - kendi Tiger Seri/Lot Envanter Raporu "
               "ciktinizi proje kokune 'deneme.XLSX' adiyla koyun."
    )
    for madde in items:
        madde.add_marker(atla)


@pytest.fixture(scope="session")
def sablon(tmp_path_factory):
    yol = str(tmp_path_factory.mktemp("sablon") / "sablon.db")
    c = dbm.baglan(yol)
    importer.yukle(c, VERI_DOSYA)
    c.close()
    return yol


@pytest.fixture
def c(sablon, tmp_path):
    yol = str(tmp_path / "sayim.db")
    shutil.copy(sablon, yol)
    con = dbm.baglan(yol)
    yield con
    con.commit()
    con.close()


@pytest.fixture
def ot(c):
    """Ambar 1 için açık oturum."""
    return oturumlar.ac(c, 1, AMBAR)


@pytest.fixture
def yaz(c, ot):
    """Barkod dizisini sırayla okutur, son sonucu döner."""
    from app import matching

    def _yaz(*barkodlar):
        sonuc = None
        for b in barkodlar:
            sonuc = matching.okut(c, oturum_taze(c, ot), b)
        return sonuc
    return _yaz


def haric_kur(c, yukleme=1, tip="tur", desen="TK"):
    """Test verisinde GERÇEKTEN satır yakalayan bir sayım dışı kuralı kurar.

    Testler eskiden varsayılan `LIC` kuralına dayanıyordu: örnek veride tek bir
    satırı yakalıyordu ve o satır bir LİSANS DEĞİL, gerçek bir ağ kartıydı
    (`303-195-100C-001`, "...Ethernet S-LIC-E Optical"). Yani testler hatayı
    doğru davranış diye kilitlemişti. Artık hariç davranışı, veriye gerçekten
    uyan bir kuralla sınanıyor.

    (kural_id, satir_sayisi, ornek_kod) döner.
    """
    from app import importer
    c.execute("INSERT OR IGNORE INTO haric_kural(tip,desen,aktif,varsayilan) "
              "VALUES(?,?,1,0)", (tip, desen))
    kid = c.execute("SELECT id FROM haric_kural WHERE tip=? AND desen=?",
                    (tip, desen)).fetchone()["id"]
    sayim = importer.haric_uygula(c, yukleme)
    kod = c.execute("SELECT kod FROM beklenen WHERE yukleme=? AND haric=1 "
                    "ORDER BY id LIMIT 1", (yukleme,)).fetchone()["kod"]
    return kid, sayim[kid]["satir"], kod


def bitir(yaz):
    """##BITIR##'i İKİ KEZ okutur — komut kartı için çift onay kuralı.

    Kart sahada taşınıyor ve kazara okutulan tek bir barkod günlerce süren bir
    sayımı kapatabiliyordu (üstelik kapanan oturumu geri açan yol da yoktu).
    İlk okutma `bitir_onay` döner, 60 sn içindeki ikincisi kapatır.

    `bitir_uyari` de aynı damgayı kurar (eksik lot / seçilmemiş seri no):
    uyarı ENGEL değil, "bir kez daha okut" demek. İkisi ayrı kapı olsaydı
    ikinci okutma da uyarıya takılır, oturum hiç kapanmazdı.

    SERT kapılara (`bitir_engel` / `ad_engel` / `foto_engel`) takılırsa İLK
    sonucu döner: onlar onaydan ÖNCE bakıyor ve gerçekten engelliyor.
    """
    r = yaz("##BITIR##")
    if r.get("tip") not in ("bitir_onay", "bitir_uyari"):
        return r
    return yaz("##BITIR##")


def oturum_taze(c, ot):
    """aktif_raf gibi alanlar değişebildiği için oturum satırını tazeler."""
    return c.execute("SELECT * FROM oturum WHERE id=?", (ot["id"],)).fetchone()
