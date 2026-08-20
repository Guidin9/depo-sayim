"""Yükleyici — deneme.XLSX (Ambar 1) üzerinde doğrulanmış rakamlar."""
import json
import os

import pytest

from app import db as dbm
from app import importer
from tests.conftest import VERI_DOSYA


def _kirilim(ozet):
    return {r["izleme"]: r for r in ozet["izleme"]}


def test_satir_sayilari(c):
    ozet = importer.ozetle(c, 1)
    assert ozet["satir"] == 870
    k = _kirilim(ozet)
    assert k["seri"]["satir"] == 801 and k["seri"]["malzeme"] == 152
    assert k["lot"]["satir"] == 69 and k["lot"]["malzeme"] == 9
    assert k["lot"]["adet"] == 271
    assert ozet["ambarlar"] == [{"ambar": "1", "satir": 870, "adet": 1072.0}]


def test_kirli_dagilimi(c):
    ozet = importer.ozetle(c, 1)
    assert ozet["kirli"] == 394
    sebep = {r["sebep"]: r["satir"] for r in ozet["kirli_sebep"]}
    assert sebep == {"kod+sayac": 210, "placeholder": 120, "bosluk": 60,
                     "asiri uzun": 4}


def test_lot_kayitlari_kirli_sayilmaz(c):
    """Kirli tespiti sadece seri izlemeli kayıtlara uygulanır (prototipteki gibi)."""
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE izleme='lot' AND kirli=1"
                     ).fetchone()["n"] == 0


def test_normalize_alanlar_yazildi(c):
    r = c.execute("SELECT * FROM beklenen WHERE seri='5S47WC2'").fetchone()
    assert r["kod_n"] == "210ACXUTIP2"
    assert r["seri_n"] == "5S47WC2"
    assert r["seri_n0"] is None          # alfanümerik -> sıfır varyantı yok
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE kod_n IS NULL OR kod_n=''"
                     ).fetchone()["n"] == 0


def test_seri_aciklamasi_neredeyse_bos(c):
    """801 seri kaydının sadece 5'inde doğru alan dolu (CLAUDE.md 2.3)."""
    assert c.execute("SELECT COUNT(*) n FROM beklenen WHERE seri_aciklama<>''"
                     ).fetchone()["n"] == 5


def test_json_ile_excel_ayni_sonucu_verir(tmp_path):
    alanlar, satirlar = importer.excel_satirlar(VERI_DOSYA)
    ters = {v: k for k, v in importer.BASLIK.items()}
    basliklar = {"tur": "Malzeme Türü", "kod": "Malzeme Kodu",
                 "aciklama": "Malzeme Açıklaması", "izleme_ham": "İzleme Yöntemi",
                 "ambar": "Ambar Maliyet Grubu", "ambar_no": "Ambar No.",
                 "seri": "Seri/Lot No.", "seri_aciklama": "Seri/Lot Açıklaması",
                 "miktar": "Envanter Miktarı", "birim": "Birim"}
    assert set(basliklar) >= alanlar and set(ters) >= alanlar
    kayitlar = [{basliklar[a]: (v if v is not None else "") for a, v in d.items()}
                for d in satirlar]
    yol = tmp_path / "rapor.json"
    yol.write_text(json.dumps({"rows": kayitlar}, ensure_ascii=False, default=str),
                   encoding="utf-8")

    c = dbm.baglan(str(tmp_path / "json.db"))
    ozet = importer.yukle(c, str(yol))
    assert ozet["satir"] == 870
    assert ozet["kirli"] == 394
    assert _kirilim(ozet)["lot"]["adet"] == 271
    c.close()


def test_envanter_raporu_ikinci_dosya_olarak(c, tmp_path):
    """Seri takipsiz kalemler ikinci rapordan gelir; çakışanlar atlanır."""
    kayitlar = [
        {"Malzeme Kodu": "0C5RNH", "Malzeme Açıklaması": "ÇAKIŞAN",
         "Ambar Maliyet Grubu": "1", "Envanter Miktarı": 77, "Birim": "AD"},
        {"Malzeme Kodu": "SWITCH-48P", "Malzeme Açıklaması": "48 PORT SWITCH",
         "Ambar Maliyet Grubu": "1", "Envanter Miktarı": 12, "Birim": "AD"},
    ]
    yol = tmp_path / "envanter.json"
    yol.write_text(json.dumps(kayitlar, ensure_ascii=False), encoding="utf-8")

    ozet = importer.yukle(c, str(yol), yukleme_id=1)
    assert ozet["kaynak"] == "envanter"
    assert ozet["eklenen"] == 1 and ozet["atlanan"] == 1
    assert ozet["satir"] == 871
    r = c.execute("SELECT * FROM beklenen WHERE kod='SWITCH-48P'").fetchone()
    assert r["izleme"] == "yok" and r["miktar"] == 12
    assert c.execute("SELECT kaynak FROM yukleme WHERE id=1").fetchone()["kaynak"] == "karma"


def test_takipsiz_kalem_adet_sayilir(c, ot, yaz, tmp_path):
    kayitlar = [{"Malzeme Kodu": "SWITCH-48P", "Malzeme Açıklaması": "48 PORT SWITCH",
                 "Ambar Maliyet Grubu": "1", "Envanter Miktarı": 12, "Birim": "AD"}]
    yol = tmp_path / "envanter.json"
    yol.write_text(json.dumps(kayitlar, ensure_ascii=False), encoding="utf-8")
    importer.yukle(c, str(yol), yukleme_id=ot["yukleme"])

    r = yaz("SWITCH-48P", "##SONRAKI##")
    assert r["tip"] == "adet" and r["beklenen"] == 12


def test_bozuk_dosya_reddedilir(tmp_path):
    yol = tmp_path / "yanlis.json"
    yol.write_text(json.dumps([{"Alakasiz": 1}]), encoding="utf-8")
    c = dbm.baglan(str(tmp_path / "x.db"))
    with pytest.raises(importer.YuklemeHatasi):
        importer.yukle(c, str(yol))
    c.close()


def test_dosya_adi_kaydedilir(c):
    assert os.path.basename(VERI_DOSYA) == c.execute(
        "SELECT dosya_adi FROM yukleme WHERE id=1").fetchone()["dosya_adi"]
