"""norm / upc_mi / kirli_mi — prototipten taşınan kuralların regresyon testi."""
import pytest

from app.norm import izleme_coz, kirli_mi, komut_coz, norm, sifirsiz, upc_mi


@pytest.mark.parametrize("giris,cikis", [
    ("210-ACXU-TİP2", "210ACXUTIP2"),
    ("ARK-1250L-S5A1", "ARK1250LS5A1"),
    ("hj6g8x3", "HJ6G8X3"),
    ("0,70MM TEL", "070MMTEL"),
    ("Şeker Ğ Çınar", "SEKERGCINAR"),
    (None, ""),
])
def test_norm(giris, cikis):
    assert norm(giris) == cikis


@pytest.mark.parametrize("kod,gecerli", [
    ("198701689928", True),
    ("190017273624", True),
    ("198701689929", False),      # kontrol hanesi bozuk
    ("5S47WC2", False),           # rakam değil
    ("12345678901", False),       # 11 hane
])
def test_upc(kod, gecerli):
    assert upc_mi(kod) is gecerli


@pytest.mark.parametrize("seri,kod,sebep", [
    # sıra önemli: boşluk -> placeholder kelimesi -> kod+sayaç -> aşırı uzun
    ("470-ABDL STOK 2026 3", "470-ABDL", "bosluk"),
    ("XR11 DEN ÇIKAN ÜRÜN", "XR11", "bosluk"),
    ("0WGP72SAYIM1", "0WGP72", "placeholder"),
    ("303-092-102BSAYIMFAZLASI1", "303-092-102B", "placeholder"),
    ("303-391-000A-051WW31", "303-391-000A-05", "kod+sayac"),
    ("920-007925KIYIEMNIYETARTTIRIM9", "920-007925", "kod+sayac"),
    ("KB5021522OEMMICROSOFTSQLSERVER2022STANDARTOEM1", "04RW5H", "asiri uzun"),
    ("", "0WGP72", "bos"),
    ("5S47WC2", "210-ACXU-TİP2", ""),
    ("KSA7658744", "ARK-1250LS5A1ATR/8641924", ""),
])
def test_kirli_mi(seri, kod, sebep):
    kirli, s = kirli_mi(seri, kod)
    assert s == sebep
    assert kirli == (1 if sebep else 0)


def test_asiri_uzun():
    kirli, sebep = kirli_mi("A" * 26, "ZZZZ")
    assert (kirli, sebep) == (1, "asiri uzun")


def test_sifirsiz():
    assert sifirsiz("00008682122630086") == "8682122630086"
    assert sifirsiz("8682122630086") == "8682122630086"
    assert sifirsiz("0WGP72") is None       # alfanümerik -> varyant üretilmez
    assert sifirsiz("0000") is None
    assert sifirsiz("") is None


@pytest.mark.parametrize("ham,komut,raf", [
    ("##SONRAKI##", "sonraki", None),
    ("##sonraki##", "sonraki", None),
    ("##IPTAL##", "iptal", None),
    ("##RAF-A1##", "raf", "A1"),
    ("##RAF-b12##", "raf", "B12"),
    ("5S47WC2", None, None),
    ("##RAF-##", None, None),
])
def test_komut_coz(ham, komut, raf):
    assert komut_coz(ham) == (komut, raf)


@pytest.mark.parametrize("deger,izleme", [
    ("Seri No.", "seri"),
    ("Lot (Parti) No.", "lot"),
    ("İzleme Yapılmayacak", "yok"),
    ("", "yok"),
    (None, "yok"),
])
def test_izleme_coz(deger, izleme):
    assert izleme_coz(deger) == izleme
