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


def oturum_taze(c, ot):
    """aktif_raf gibi alanlar değişebildiği için oturum satırını tazeler."""
    return c.execute("SELECT * FROM oturum WHERE id=?", (ot["id"],)).fetchone()
