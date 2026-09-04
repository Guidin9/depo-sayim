"""Router'ların paylaştığı bağımlılıklar."""
from fastapi import Depends, HTTPException

from .. import db as dbm
from .. import oturumlar


def veritabani():
    c = dbm.baglan()
    try:
        yield c
        c.commit()
    finally:
        c.close()


def oturum_getir(oturum_id, c, acik=False):
    """Oturumu getirir. `acik=True` ise kapalı oturumda 409 verir.

    Kapalı oturumun raporu üretilmiş, çoğu zaman Tiger'a da girilmiştir; kaydı
    değiştirmek geriye dönük olarak başka bir gerçek yaratır. Kapı `POST /okut`
    ve mod uçlarında hep vardı ama SİLME / GERİ ALMA / DÜZELTME uçlarında yoktu
    (DENETIM_20260904.md O2): kapanmış bir oturumdan okutma silmek 200
    dönüyordu.

    Oturumu gerçekten düzeltmek gerekiyorsa yol bellidir ve iz bırakır:
    Geçmiş ekranından "Yeniden aç".

    Eşleştirme uçları (`/bagla`, `/coz-ayir`) bilerek DIŞARIDA: eşleştirme
    sayım sonu adımıdır ve oturum kapandıktan sonra da yapılabilir.
    """
    o = oturumlar.getir(c, oturum_id)
    if not o:
        raise HTTPException(404, "Oturum #%s bulunamadı" % oturum_id)
    if acik and o["durum"] != "acik":
        raise HTTPException(
            409, "Oturum #%s kapalı. Değiştirmek için Geçmiş ekranından "
                 "'Yeniden aç' deyin." % oturum_id)
    return o


def yukleme_getir(yukleme_id, c):
    y = c.execute("SELECT * FROM yukleme WHERE id=?", (yukleme_id,)).fetchone()
    if not y:
        raise HTTPException(404, "Yükleme #%s bulunamadı" % yukleme_id)
    return y


DB = Depends(veritabani)
