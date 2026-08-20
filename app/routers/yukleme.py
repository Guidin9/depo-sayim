"""Kurulum ekranı: Tiger raporu yükleme, özet, sayım dışı kural yönetimi."""
import os
import shutil
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .. import db as dbm
from .. import importer
from .ortak import DB, yukleme_getir

router = APIRouter(prefix="/api", tags=["yukleme"])
IZINLI = (".xlsx", ".xls", ".xlsm", ".json")


class Kural(BaseModel):
    id: int | None = None
    tip: str | None = None
    desen: str | None = None
    aktif: bool | None = None


class KuralGuncelle(BaseModel):
    yukleme: int
    kurallar: list[Kural] = []
    silinecek: list[int] = []


@router.post("/yukleme")
async def yukle(dosya: UploadFile = File(...), yukleme: int | None = Form(None),
                c=DB):
    ad = os.path.basename(dosya.filename or "rapor.xlsx")
    if not ad.lower().endswith(IZINLI):
        raise HTTPException(400, "Sadece Excel (.xlsx) veya JSON dosyası yükleyin.")
    klasor = os.path.join(dbm.VERI, "yuklenen")
    os.makedirs(klasor, exist_ok=True)
    yol = os.path.join(klasor, "%d_%s" % (time.time(), ad))
    with open(yol, "wb") as f:
        shutil.copyfileobj(dosya.file, f)
    try:
        ozet = importer.yukle(c, yol, yukleme_id=yukleme, dosya_adi=ad)
    except importer.YuklemeHatasi as e:
        raise HTTPException(400, str(e))
    ozet["kurallar"] = importer.kural_ozeti(c, ozet["yukleme"])
    return ozet


@router.get("/yukleme")
def liste(c=DB):
    return [dict(r) for r in c.execute(
        "SELECT * FROM yukleme ORDER BY id DESC")]


@router.get("/yukleme/{yukleme_id}/ozet")
def ozet(yukleme_id: int, c=DB):
    yukleme_getir(yukleme_id, c)
    o = importer.ozetle(c, yukleme_id)
    o["kurallar"] = importer.kural_ozeti(c, yukleme_id)
    return o


@router.get("/yukleme/{yukleme_id}/kurallar")
def kurallar(yukleme_id: int, c=DB):
    yukleme_getir(yukleme_id, c)
    return importer.kural_ozeti(c, yukleme_id)


@router.put("/yukleme/{yukleme_id}/kurallar")
def kurallari_guncelle(yukleme_id: int, istek: KuralGuncelle, c=DB):
    """Kuralları aç/kapat/ekle/sil, sonra yüklemeye yeniden uygula."""
    yukleme_getir(yukleme_id, c)
    for k in istek.kurallar:
        if k.id:
            if k.aktif is not None:
                c.execute("UPDATE haric_kural SET aktif=? WHERE id=?",
                          (1 if k.aktif else 0, k.id))
            if k.desen:
                c.execute("UPDATE haric_kural SET desen=? WHERE id=?", (k.desen, k.id))
        elif k.desen and k.tip in ("tur", "aciklama"):
            c.execute("INSERT OR IGNORE INTO haric_kural(tip,desen,aktif,varsayilan) "
                      "VALUES(?,?,?,0)", (k.tip, k.desen, 1 if k.aktif is not False else 0))
    for kid in istek.silinecek:
        c.execute("DELETE FROM haric_kural WHERE id=? AND varsayilan=0", (kid,))
    importer.haric_uygula(c, yukleme_id)
    return importer.kural_ozeti(c, yukleme_id)


@router.get("/yukleme/{yukleme_id}/ambarlar")
def ambarlar(yukleme_id: int, c=DB):
    yukleme_getir(yukleme_id, c)
    return [dict(r) for r in c.execute(
        """SELECT ambar, COUNT(*) satir, SUM(miktar) adet,
           SUM(CASE WHEN haric=1 THEN 1 ELSE 0 END) haric,
           SUM(kirli) kirli, COUNT(DISTINCT kod) malzeme
           FROM beklenen WHERE yukleme=? GROUP BY ambar ORDER BY 2 DESC""",
        (yukleme_id,))]
