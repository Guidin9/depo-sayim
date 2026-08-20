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


def oturum_getir(oturum_id, c):
    o = oturumlar.getir(c, oturum_id)
    if not o:
        raise HTTPException(404, "Oturum #%s bulunamadı" % oturum_id)
    return o


def yukleme_getir(yukleme_id, c):
    y = c.execute("SELECT * FROM yukleme WHERE id=?", (yukleme_id,)).fetchone()
    if not y:
        raise HTTPException(404, "Yükleme #%s bulunamadı" % yukleme_id)
    return y


DB = Depends(veritabani)
