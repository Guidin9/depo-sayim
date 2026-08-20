"""Canlı güncelleme yayını (Server-Sent Events).

Amaç: laptopta okutulan barkod, telefondaki ekranda F5'e basmadan görünsün;
telefondan yapılan seçim de laptopta anında yansısın.

Neden SSE: tek yönlü bildirim yetiyor (eylemler normal POST ile gidiyor),
düz HTTP üzerinde çalışıyor — telefon için HTTPS/sertifika derdi yok — ve
tarayıcı bağlantı koptuğunda kendi kendine yeniden bağlanıyor.

Yayın gövdesi kasten küçük: sadece "bir şey değişti" der, istemci kendi
ihtiyacı olan veriyi çeker. Böylece ekranlar tek gerçeğe (sunucuya) bakar.
"""
import asyncio
import itertools
import json

_sayac = itertools.count(1)
_surum = 0
_kaynak = None          # değişikliği yapan istemcinin kimliği


def bildir(istemci=None):
    """Veri değişti — dinleyen tüm ekranlara haber ver."""
    global _surum, _kaynak
    _surum = next(_sayac)
    _kaynak = istemci
    return _surum


def surum():
    return _surum, _kaynak


async def akis(baglanti_kopuk=None, aralik=0.25, kalp=10.0):
    """SSE gövdesi üretir.

    baglanti_kopuk: istemci gitti mi diye sorulan awaitable (Request.is_disconnected)
    """
    gorulen = -1
    bekleyen = 0.0
    yield ": bagli\n\n"
    while True:
        if baglanti_kopuk is not None and await baglanti_kopuk():
            return
        s, kaynak = surum()
        if s != gorulen:
            gorulen = s
            bekleyen = 0.0
            yield "event: guncel\ndata: %s\n\n" % json.dumps(
                {"surum": s, "istemci": kaynak})
        else:
            bekleyen += aralik
            if bekleyen >= kalp:
                bekleyen = 0.0
                yield ": kalp\n\n"      # vekil sunucular bağlantıyı kesmesin
        await asyncio.sleep(aralik)
