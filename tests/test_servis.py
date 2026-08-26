"""Statik servis ve barkod üretimi — ACIL_PLAN.md B1 ve B2.

İkisi de sayım verisini bozmuyor ama depoya gitmeden kapatılmalıydı:
komut kartı depoda değil, ofiste basılıyor; sunucu ise `--host 0.0.0.0` ile
açık ve kimlik doğrulaması yok.
"""
import os

import pytest
from fastapi.testclient import TestClient

from app import barkod
from app.main import STATIK, app

pytestmark = pytest.mark.skipif(
    not os.path.isdir(STATIK),
    reason="arayüz derlenmemiş (cd web && npm run build) — statik servis sınanamaz")


@pytest.fixture
def ist():
    return TestClient(app)


# ------------------------------------------------------------------ B2
# Dizin geçişi. `os.path.join(STATIK, tam_yol)` + `isfile` yeterli değildi:
# `..` normalize edilmiyordu. Tarayıcı düz `../` yolunu düzeltiyor ama
# YÜZDE-KODLANMIŞINI düzeltmiyor, sunucu da hiç düzeltmiyordu.
KACIS = [
    "/..%2f..%2fCLAUDE.md",
    "/..%2f..%2fdata%2fsayim.db",
    "/..%2f..%2fdeneme.XLSX",
    "/..%2fmain.py",
    "/..%2f..%2f.venv%2fpyvenv.cfg",
    "/..%2f..%2f..%2fWindows%2fwin.ini",
    "/../CLAUDE.md",
    "/%2e%2e%2f%2e%2e%2fCLAUDE.md",
]


@pytest.mark.parametrize("yol", KACIS)
def test_dizin_gecisi_engellendi(ist, yol):
    """Kök dışındaki hiçbir dosya servis edilmemeli.

    404 DEĞİL, index.html beklenir: bilinmeyen yollar SPA'ya düşer, davranış
    korunuyor. Önemli olan gövdenin dosya İÇERİĞİ olmaması.
    """
    r = ist.get(yol)
    assert r.status_code == 200
    assert r.content.startswith(b"<!doctype html>"), "kök dışı dosya sızdı"
    assert b"SQLite format" not in r.content
    assert b"# Depo Say" not in r.content


def test_statik_dosyalar_hala_servis_ediliyor(ist):
    """Regresyon: koruma normal yolları kırmamalı."""
    for yol in ("/", "/telefon", "/logo.png", "/olmayan-sayfa"):
        assert ist.get(yol).status_code == 200
    assert ist.get("/logo.png").headers["content-type"] == "image/png"
    assert ist.get("/").headers["cache-control"] == "no-store"


def test_assets_klasoru_calisiyor(ist):
    import glob
    js = glob.glob(os.path.join(STATIK, "assets", "*.js"))
    if not js:
        pytest.skip("derlenmiş assets yok")
    r = ist.get("/assets/" + os.path.basename(js[0]))
    assert r.status_code == 200 and len(r.content) > 1000


# ------------------------------------------------------------------ B1
def test_turkce_raf_adi_kart_bastirir():
    """Regresyon: `ÜST-1` python-barcode'u patlatıp 500 veriyordu.

    Türkçe bir depoda `ÜST`, `ÖN`, `ÇIKIŞ` raf adı yazmak en doğal şey;
    kullanıcı boş sayfa ve stack trace görüyordu.
    """
    h = barkod.kart_html(["ÜST-1", "ÖN ÇIKIŞ"])
    assert "##RAF-UST-1##" in h
    assert "##RAF-ON CIKIS##" in h


def test_turkce_raf_adi_etiket_bastirir():
    satirlar = barkod.raf_satirlari(["ÇIKIŞ-2"])
    assert satirlar[0]["gosterim"] == "##RAF-CIKIS-2##"
    assert "##RAF-CIKIS-2##" in barkod.etiket_html(satirlar)


def test_raf_adi_html_kacisi():
    """`_kart()` kaçmıyordu, `_etiket()` kaçıyordu — tutarsızdı."""
    h = barkod.kart_html(["<script>alert(1)</script>"])
    assert "<script>alert(1)</script>" not in h


def test_bos_raf_adi_kartta_atlanir():
    h = barkod.kart_html(["", "   ", "<>"])
    assert "##RAF-" not in h
    assert "##SONRAKI##" in h          # kartın kendisi yine basılmalı


def test_komut_karti_ucu_turkce_raf_ile_200(ist):
    r = ist.post("/api/komut-karti", json={"raflar": ["ÜST-1"]})
    assert r.status_code == 200
    assert "##RAF-UST-1##" in r.text


def test_raf_etiketi_ucu_turkce_raf_ile_200(ist):
    r = ist.post("/api/raf-etiketi", json={"raflar": ["ÖN ÇIKIŞ"], "kopya": 1})
    assert r.status_code == 200
    assert "##RAF-ON CIKIS##" in r.text


def test_raf_etiketi_ucu_bos_adda_400(ist):
    r = ist.post("/api/raf-etiketi", json={"raflar": ["<>", "  "]})
    assert r.status_code == 400


def test_komut_karti_adet_barkodlarini_basar(ist):
    r = ist.post("/api/komut-karti", json={"raflar": []})
    assert r.status_code == 200
    for a in barkod.ADET_VARSAYILAN:
        assert "##ADET-%d##" % a in r.text
    assert "##ADET-0##" in r.text


def test_komut_karti_adet_barkodlari_kapatilabilir(ist):
    r = ist.post("/api/komut-karti", json={"raflar": [], "adetler": []})
    assert r.status_code == 200
    assert "##ADET-" not in r.text
