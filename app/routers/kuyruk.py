"""Kuyruk ekranı: çözülmeyi bekleyen gruplar, notlar, fotoğraflar.

Kuyruk kaydı "bunu sonra hatırlarım" demek değildir — asıl çözüm ürün hâlâ
raftayken çözmektir (bkz. matching.okut, raf_engel). Not ve fotoğraf, raftan
ayrılmadan çözülemeyen kayıtlar için hatırlatıcıdır.
"""
import datetime
import json

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from .. import matching
from .ortak import DB, oturum_getir

router = APIRouter(prefix="/api", tags=["kuyruk"])

FOTO_SINIR = 6 * 1024 * 1024          # 6 MB — telefon fotoğrafı için fazlasıyla yeter
FOTO_TURLER = ("image/jpeg", "image/png", "image/webp")


class Coz(BaseModel):
    beklenen_id: int


class Not(BaseModel):
    """Kısmi güncelleme: sadece gönderilen alan değişir."""
    not_: str | None = None
    beklet: bool | None = None


def _kuyruk_getir(c, kuyruk_id):
    q = c.execute("SELECT * FROM kuyruk WHERE id=?", (kuyruk_id,)).fetchone()
    if not q:
        raise HTTPException(404, "Kuyruk kaydı #%s bulunamadı" % kuyruk_id)
    return q


def _satir(c, r):
    fotolar = [x["id"] for x in c.execute(
        "SELECT id FROM kuyruk_foto WHERE kuyruk=? ORDER BY id", (r["id"],))]
    return {"id": r["id"], "barkodlar": json.loads(r["barkodlar"]), "raf": r["raf"],
            "ts": (r["ts"] or "")[:19].replace("T", " "), "cozuldu": bool(r["cozuldu"]),
            "not_": r["not_"] or "", "beklet": bool(r["beklet"]), "fotolar": fotolar}


@router.get("/oturum/{oturum_id}/kuyruk")
def liste(oturum_id: int, hepsi: bool = False, c=DB):
    oturum_getir(oturum_id, c)
    sql = "SELECT * FROM kuyruk WHERE oturum=?" + ("" if hepsi else " AND cozuldu=0")
    return [_satir(c, r) for r in c.execute(sql + " ORDER BY id", (oturum_id,))]


@router.get("/oturum/{oturum_id}/adaylar")
def aday_listesi(oturum_id: int, limit: int = 5, c=DB):
    """Tanınmayan bir grup için olası malzemeler — yalnızca öneri."""
    return matching.adaylar(c, oturum_getir(oturum_id, c), limit=limit)


@router.post("/kuyruk/{kuyruk_id}/coz")
def coz(kuyruk_id: int, istek: Coz, c=DB):
    sonuc = matching.kuyruk_coz(c, kuyruk_id, istek.beklenen_id)
    if "hata" in sonuc:
        raise HTTPException(404, sonuc["hata"])
    c.commit()
    return sonuc


@router.patch("/kuyruk/{kuyruk_id}")
def guncelle(kuyruk_id: int, istek: Not, c=DB):
    """Kısa hatırlatma notu ve 'sonra çöz' işareti.

    beklet=1: telefonda fotoğrafı çekildi, ürün rafa bırakıldı, çözümü PC
    başında toplu yapılacak. Kayıt kuyrukta kalır; sadece telefon ekranını
    ve raf kapısını meşgul etmez.
    """
    _kuyruk_getir(c, kuyruk_id)
    if istek.not_ is not None:
        c.execute("UPDATE kuyruk SET not_=? WHERE id=?", (istek.not_.strip(), kuyruk_id))
    if istek.beklet is not None:
        c.execute("UPDATE kuyruk SET beklet=? WHERE id=?",
                  (1 if istek.beklet else 0, kuyruk_id))
    c.commit()
    return _satir(c, _kuyruk_getir(c, kuyruk_id))


@router.delete("/kuyruk/{kuyruk_id}")
def sil(kuyruk_id: int, c=DB):
    """Kuyruktaki grubu fazla olarak kapatır (karşılığı gerçekten yoksa)."""
    q = _kuyruk_getir(c, kuyruk_id)
    ts = datetime.datetime.now().isoformat()
    grup = matching._yeni_grup(c, q["oturum"])
    for h in json.loads(q["barkodlar"]):
        c.execute("INSERT INTO okutma(oturum,ts,ham,miktar,tip,raf,grup,not_) "
                  "VALUES(?,?,?,1,'fazla',?,?,'kuyruktan fazla işaretlendi')",
                  (q["oturum"], ts, h, q["raf"], grup))
    c.execute("UPDATE kuyruk SET cozuldu=1 WHERE id=?", (kuyruk_id,))
    return {"tip": "fazla"}


# ---------------------------------------------------------------- fotoğraflar
@router.post("/kuyruk/{kuyruk_id}/foto")
async def foto_ekle(kuyruk_id: int, dosya: UploadFile = File(...), c=DB):
    _kuyruk_getir(c, kuyruk_id)
    veri = await dosya.read()
    if not veri:
        raise HTTPException(400, "Boş dosya")
    if len(veri) > FOTO_SINIR:
        raise HTTPException(413, "Fotoğraf çok büyük (en fazla 6 MB)")
    tur = (dosya.content_type or "").split(";")[0] or "image/jpeg"
    if tur not in FOTO_TURLER:
        raise HTTPException(400, "Sadece JPEG / PNG / WEBP")
    fid = c.execute("INSERT INTO kuyruk_foto(kuyruk,ts,tur,boyut,veri) "
                    "VALUES(?,?,?,?,?)",
                    (kuyruk_id, datetime.datetime.now().isoformat(), tur,
                     len(veri), veri)).lastrowid
    c.commit()
    return {"id": fid, "boyut": len(veri), "tur": tur}


@router.get("/foto/{foto_id}")
def foto_getir(foto_id: int, c=DB):
    r = c.execute("SELECT tur, veri FROM kuyruk_foto WHERE id=?", (foto_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Fotoğraf yok")
    return Response(content=r["veri"], media_type=r["tur"],
                    headers={"Cache-Control": "max-age=86400"})


@router.delete("/foto/{foto_id}")
def foto_sil(foto_id: int, c=DB):
    if not c.execute("SELECT 1 FROM kuyruk_foto WHERE id=?", (foto_id,)).fetchone():
        raise HTTPException(404, "Fotoğraf yok")
    c.execute("DELETE FROM kuyruk_foto WHERE id=?", (foto_id,))
    c.commit()
    return {"silindi": foto_id}
