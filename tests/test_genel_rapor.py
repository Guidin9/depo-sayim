"""Yükleyici deneme.XLSX'e bağlı olmamalı.

Bu testler sentetik, kasten farklı biçimli raporlar üretir: sütun sırası başka,
başlık satırı başka satırda, rapor ikinci sayfada, tanınmayan fazladan sütunlar
var, ambar bilgisi 'Ambar No.' sütunundan geliyor, başlıklar eş anlamlı.
Hepsi okunabilmeli — aksi halde uygulama tek bir örnek dosyaya bağlı demektir.
"""
import pytest
from openpyxl import Workbook

from app import db as dbm
from app import importer, matching, oturumlar


def _yaz(yol, sayfalar):
    """sayfalar: [(sayfa_adi, [satır listesi]), ...]"""
    wb = Workbook()
    wb.remove(wb.active)
    for ad, satirlar in sayfalar:
        ws = wb.create_sheet(ad)
        for s in satirlar:
            ws.append(s)
    wb.save(yol)
    return str(yol)


def _db(tmp_path, ad="x.db"):
    return dbm.baglan(str(tmp_path / ad))


def test_farkli_sutun_duzeni_ve_ikinci_sayfa(tmp_path):
    yol = _yaz(tmp_path / "baska_depo.xlsx", [
        ("Kapak", [["Rapor"], ["Ambar 7 — 2026"], []]),
        ("Veri", [
            ["Firma raporu"], [],
            # sütun sırası bambaşka + tanınmayan iki sütun
            ["Proje Kodu", "Seri/Lot No.", "Stok Kodu", "Ambar No.", "Malzeme Adı",
             "İzleme Yöntemi", "Miktar", "Ana Birim", "Raf Yeri"],
            ["P1", "SN-AAA-001", "SRV-100", 7, "SUNUCU 1U", "Seri No.", 1, "AD", "A1"],
            ["P1", "SN-AAA-002", "SRV-100", 7, "SUNUCU 1U", "Seri No.", 1, "AD", "A1"],
            ["P2", "LOT-2026-1", "KABLO-CAT6", 7, "CAT6 KABLO", "Lot (Parti) No.",
             250, "MT", "B2"],
        ]),
    ])
    c = _db(tmp_path)
    ozet = importer.yukle(c, yol)
    assert ozet["satir"] == 3
    assert ozet["ambarlar"] == [{"ambar": "7", "satir": 3, "adet": 252.0}]
    k = {r["izleme"]: r for r in ozet["izleme"]}
    assert k["seri"]["satir"] == 2 and k["lot"]["adet"] == 250

    r = c.execute("SELECT * FROM beklenen WHERE seri='SN-AAA-001'").fetchone()
    assert (r["kod"], r["aciklama"], r["birim"]) == ("SRV-100", "SUNUCU 1U", "AD")
    c.close()


def test_baska_ambarda_sayim(tmp_path):
    """Ambar 7 verisiyle motor aynı şekilde çalışmalı — ambar sabit değil."""
    yol = _yaz(tmp_path / "a7.xlsx", [("S", [
        ["Seri/Lot Envanter Raporu"],
        ["Malzeme Kodu", "Malzeme Açıklaması", "İzleme Yöntemi",
         "Ambar Maliyet Grubu", "Seri/Lot No.", "Envanter Miktarı", "Birim"],
        ["SRV-100", "SUNUCU 1U", "Seri No.", 7, "SN-AAA-001", 1, "AD"],
        ["SRV-100", "SUNUCU 1U", "Seri No.", 7, "SRV-100SAYIM1", 1, "AD"],
        ["KABLO-CAT6", "CAT6 KABLO", "Lot (Parti) No.", 7, "LOT-2026-1", 250, "MT"],
    ])])
    c = _db(tmp_path)
    importer.yukle(c, yol)
    ot = oturumlar.ac(c, 1, "7")

    assert matching.okut(c, ot, "SN-AAA-001")["coz"] == "seri"
    assert matching.okut(c, ot, "##SONRAKI##")["tip"] == "eslesti"

    matching.okut(c, ot, "SRV-100")
    matching.okut(c, ot, "GERCEK-SN-XYZ-42")
    r = matching.okut(c, ot, "##SONRAKI##")
    assert r["tip"] == "slot" and r["eski"] == "SRV-100SAYIM1"

    matching.okut(c, ot, "KABLO-CAT6")
    r = matching.okut(c, ot, "##SONRAKI##")
    assert r["tip"] == "adet" and r["beklenen"] == 250
    c.close()


def test_ayni_dosyada_birden_cok_ambar(tmp_path):
    yol = _yaz(tmp_path / "cok.xlsx", [("S", [
        ["Malzeme Kodu", "Ambar Maliyet Grubu", "Seri/Lot No.", "İzleme Yöntemi",
         "Envanter Miktarı"],
        ["SRV-100", 1, "SN-1", "Seri No.", 1],
        ["SRV-100", 3, "SN-2", "Seri No.", 1],
        ["SRV-100", 3, "SN-3", "Seri No.", 1],
    ])])
    c = _db(tmp_path)
    ozet = importer.yukle(c, yol)
    assert ozet["ambarlar"] == [{"ambar": "3", "satir": 2, "adet": 2.0},
                                {"ambar": "1", "satir": 1, "adet": 1.0}]

    ot = oturumlar.ac(c, 1, "3")
    # başka ambarın serisi bu oturumda eşleşmemeli
    assert matching.coz(c, "SN-1", ot["yukleme"], ot["ambar"], ot["id"])["t"] != "seri"
    assert matching.coz(c, "SN-2", ot["yukleme"], ot["ambar"], ot["id"])["t"] == "seri"
    c.close()


def test_ondalikli_ve_metin_miktar(tmp_path):
    yol = _yaz(tmp_path / "ondalik.xlsx", [("S", [
        ["Malzeme Kodu", "Ambar No.", "Envanter Miktarı", "Birim"],
        ["0,70MM TEL", 2, "1.250,50", "MT"],
        ["KABLO", 2, 3.5, "MT"],
    ])])
    c = _db(tmp_path)
    importer.yukle(c, yol)
    assert c.execute("SELECT miktar FROM beklenen WHERE kod='0,70MM TEL'"
                     ).fetchone()["miktar"] == 1250.5
    assert c.execute("SELECT miktar FROM beklenen WHERE kod='KABLO'"
                     ).fetchone()["miktar"] == 3.5
    c.close()


def test_ambar_sutunu_yoksa_reddedilir(tmp_path):
    yol = _yaz(tmp_path / "eksik.xlsx", [("S", [
        ["Malzeme Kodu", "Envanter Miktarı"],
        ["SRV-100", 1],
    ])])
    c = _db(tmp_path)
    with pytest.raises(importer.YuklemeHatasi) as e:
        importer.yukle(c, yol)
    assert "ambar" in str(e.value)
    c.close()


def test_malzeme_kodu_sutunu_yoksa_reddedilir(tmp_path):
    yol = _yaz(tmp_path / "alakasiz.xlsx", [("S", [
        ["Tarih", "Tutar"], ["2026-01-01", 100],
    ])])
    c = _db(tmp_path)
    with pytest.raises(importer.YuklemeHatasi):
        importer.yukle(c, yol)
    c.close()


def test_bos_ambar_sessizce_1e_karismaz(tmp_path):
    yol = _yaz(tmp_path / "bosambar.xlsx", [("S", [
        ["Malzeme Kodu", "Ambar Maliyet Grubu", "Envanter Miktarı"],
        ["SRV-100", 1, 1],
        ["SRV-200", None, 1],
    ])])
    c = _db(tmp_path)
    ozet = importer.yukle(c, yol)
    assert {a["ambar"] for a in ozet["ambarlar"]} == {"1", "?"}
    c.close()
