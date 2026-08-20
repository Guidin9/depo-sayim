"""Sayım ekranı: oturum yaşam döngüsü, okutma, durum, arama."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import matching, oturumlar
from .ortak import DB, oturum_getir, yukleme_getir

router = APIRouter(prefix="/api", tags=["oturum"])


class OturumAc(BaseModel):
    yukleme: int
    ambar: str


class Okutma(BaseModel):
    ham: str
    zorla: bool = False      # raf/bitir kapısını bilinçli olarak aş


class GeriAl(BaseModel):
    kapsam: str = "okutma"      # "okutma" | "grup"


class RafAyar(BaseModel):
    raf: str
    zorla: bool = False


@router.post("/oturum")
def ac(istek: OturumAc, c=DB):
    yukleme_getir(istek.yukleme, c)
    var = oturumlar.acik(c)
    if var and (var["yukleme"] != istek.yukleme or var["ambar"] != istek.ambar):
        raise HTTPException(409, "Zaten açık bir oturum var (#%s, ambar %s). Önce "
                                 "onu bitirin." % (var["id"], var["ambar"]))
    if not c.execute("SELECT 1 FROM beklenen WHERE yukleme=? AND ambar=? LIMIT 1",
                     (istek.yukleme, istek.ambar)).fetchone():
        raise HTTPException(400, "Ambar %s bu yüklemede yok." % istek.ambar)
    return dict(oturumlar.ac(c, istek.yukleme, istek.ambar))


@router.get("/oturum/acik")
def acik(c=DB):
    o = oturumlar.acik(c)
    return matching.durum(c, o) if o else None


@router.get("/oturumlar")
def gecmis(c=DB):
    return oturumlar.gecmis(c)


@router.get("/oturum/{oturum_id}/durum")
def durum(oturum_id: int, akis: int = 40, c=DB):
    return matching.durum(c, oturum_getir(oturum_id, c), akis=akis)


@router.post("/oturum/{oturum_id}/okut")
def okut(oturum_id: int, istek: Okutma, c=DB):
    o = oturum_getir(oturum_id, c)
    if o["durum"] != "acik":
        raise HTTPException(409, "Oturum kapalı.")
    sonuc = matching.okut(c, o, istek.ham, zorla=istek.zorla)
    c.commit()
    sonuc["durum"] = matching.durum(c, oturum_getir(oturum_id, c))
    return sonuc


@router.post("/oturum/{oturum_id}/gerial")
def gerial(oturum_id: int, istek: GeriAl, c=DB):
    o = oturum_getir(oturum_id, c)
    sonuc = matching.gerial(c, o, kapsam=istek.kapsam)
    c.commit()
    sonuc["durum"] = matching.durum(c, o)
    return sonuc


@router.post("/oturum/{oturum_id}/bitir")
def bitir(oturum_id: int, zorla: bool = False, c=DB):
    o = oturum_getir(oturum_id, c)
    bekleyen = matching.bekleyen_kuyruk(c, oturum_id)
    if bekleyen and not zorla:
        raise HTTPException(409, {"mesaj": "Kuyrukta çözülmemiş %d ürün var."
                                           % len(bekleyen), "kuyruk": bekleyen})
    matching.grup_coz(c, o)          # tampondaki son grup kaybolmasın
    return dict(oturumlar.bitir(c, oturum_id))


@router.post("/oturum/{oturum_id}/raf")
def raf_ayarla(oturum_id: int, istek: RafAyar, c=DB):
    """Rafı okuyucusuz ayarla (telefondan). Kuyruk kapısı burada da işler."""
    o = oturum_getir(oturum_id, c)
    sonuc = matching.okut(c, o, "##RAF-%s##" % istek.raf.strip().upper(),
                          zorla=istek.zorla)
    c.commit()
    sonuc["durum"] = matching.durum(c, oturum_getir(oturum_id, c))
    return sonuc


@router.get("/oturum/{oturum_id}/raflar")
def raflar(oturum_id: int, c=DB):
    """Bu oturumda kullanılmış raflar — telefonda hızlı seçim için."""
    oturum_getir(oturum_id, c)
    return [r["raf"] for r in c.execute(
        "SELECT DISTINCT raf FROM okutma WHERE oturum=? AND raf IS NOT NULL "
        "AND raf<>'' ORDER BY raf", (oturum_id,))]


@router.get("/oturum/{oturum_id}/ara")
def ara(oturum_id: int, q: str = "", limit: int = 25, c=DB):
    o = oturum_getir(oturum_id, c)
    return matching.ara(c, o["yukleme"], o["ambar"], q, limit=limit, oturum=o["id"])
