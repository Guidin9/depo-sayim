"""Canlı güncelleme kanalı (SSE)."""
import asyncio

from app import olaylar


def _topla(adet, kopuk=None, aralik=0.01, kalp=0.03):
    async def calis():
        cikti = []
        akis = olaylar.akis(kopuk, aralik=aralik, kalp=kalp)
        async for parca in akis:
            cikti.append(parca)
            if len(cikti) >= adet:
                await akis.aclose()
                break
        return cikti
    return asyncio.run(calis())


def test_bildirim_yayinlanir():
    olaylar.bildir("laptop")
    parcalar = _topla(2)
    assert parcalar[0].startswith(":")            # bağlandı yorumu
    assert "event: guncel" in parcalar[1]
    assert '"istemci": "laptop"' in parcalar[1]


def test_degisiklik_yoksa_kalp_atisi_gider():
    olaylar.bildir(None)
    parcalar = _topla(4)
    assert any(p.strip() == ": kalp" for p in parcalar[2:])


def test_surum_artar():
    a = olaylar.bildir("a")
    b = olaylar.bildir("b")
    assert b > a
    assert olaylar.surum() == (b, "b")


def test_baglanti_kopunca_akis_biter():
    async def kopuk():
        return True

    async def calis():
        return [p async for p in olaylar.akis(kopuk, aralik=0.01)]

    assert asyncio.run(calis()) == [": bagli\n\n"]
