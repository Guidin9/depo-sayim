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
    ad: str | None = None


class FazlaKapat(BaseModel):
    """Fazla olarak kapatma. Malzeme kodu bilinmiyorsa `ad` zorunludur."""
    ad: str | None = None


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
            "not_": r["not_"] or "", "beklet": bool(r["beklet"]), "fotolar": fotolar,
            "tur": r["tur"] or "bilinmiyor", "kod": r["kod"], "ad": r["ad"],
            "aciklama": _aciklama(c, r["kod"])}


def _aciklama(c, kod):
    """Onay kartında malzeme adını göstermek için. Kod yoksa boş."""
    if not kod:
        return ""
    r = c.execute("SELECT aciklama FROM beklenen WHERE kod=? ORDER BY yukleme DESC "
                  "LIMIT 1", (kod,)).fetchone()
    return (r["aciklama"] if r else "") or ""


@router.get("/oturum/{oturum_id}/kuyruk")
def liste(oturum_id: int, hepsi: bool = False, c=DB):
    oturum_getir(oturum_id, c)
    sql = "SELECT * FROM kuyruk WHERE oturum=?" + ("" if hepsi else " AND cozuldu=0")
    return [_satir(c, r) for r in c.execute(sql + " ORDER BY id", (oturum_id,))]


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
    if istek.ad is not None:
        # Ürünün ne olduğu; fazla olarak kapatılırsa okutma kaydına taşınır.
        c.execute("UPDATE kuyruk SET ad=? WHERE id=?", (istek.ad.strip(), kuyruk_id))
    if istek.beklet is not None:
        c.execute("UPDATE kuyruk SET beklet=? WHERE id=?",
                  (1 if istek.beklet else 0, kuyruk_id))
    c.commit()
    return _satir(c, _kuyruk_getir(c, kuyruk_id))


@router.delete("/kuyruk/{kuyruk_id}")
def sil(kuyruk_id: int, istek: FazlaKapat | None = None, c=DB):
    """Kuyruktaki grubu fazla olarak kapatır (karşılığı gerçekten yoksa).

    'fazla_onay' kayıtlarında kullanıcının verdiği cevap budur: evet, gerçekten
    fazla. Fazla kaydı yalnızca bu yoldan ve ##FAZLA## komutundan oluşur.

    Malzeme kodu bilinmiyorsa `ad` zorunlu: kodu olmayan kaydın raporda
    açıklaması üretilemez, geriye yalnızca seri numarası ve raf kalır.
    """
    _kuyruk_getir(c, kuyruk_id)
    sonuc = matching.kuyruk_fazla(c, kuyruk_id, ad=istek.ad if istek else None)
    if sonuc.get("hata") == "ad_gerekli":
        raise HTTPException(400, {"hata": "ad_gerekli", "mesaj": sonuc["mesaj"]})
    if "hata" in sonuc:
        raise HTTPException(404, sonuc["hata"])
    c.commit()
    return sonuc


# ---------------------------------------------------------------- fotoğraflar
async def foto_yaz(c, dosya, kuyruk=None, okutma=None):
    """Yüklenen görseli saklar. Kuyruk kaydına ya da fazla okutmasına bağlanır."""
    veri = await dosya.read()
    if not veri:
        raise HTTPException(400, "Boş dosya")
    if len(veri) > FOTO_SINIR:
        raise HTTPException(413, "Fotoğraf çok büyük (en fazla 6 MB)")
    tur = (dosya.content_type or "").split(";")[0] or "image/jpeg"
    if tur not in FOTO_TURLER:
        raise HTTPException(400, "Sadece JPEG / PNG / WEBP")
    fid = c.execute("INSERT INTO kuyruk_foto(kuyruk,okutma,ts,tur,boyut,veri) "
                    "VALUES(?,?,?,?,?,?)",
                    (kuyruk, okutma, datetime.datetime.now().isoformat(), tur,
                     len(veri), veri)).lastrowid
    c.commit()
    return {"id": fid, "boyut": len(veri), "tur": tur}


@router.post("/kuyruk/{kuyruk_id}/foto")
async def foto_ekle(kuyruk_id: int, dosya: UploadFile = File(...), c=DB):
    _kuyruk_getir(c, kuyruk_id)
    return await foto_yaz(c, dosya, kuyruk=kuyruk_id)


@router.post("/okutma/{okutma_id}/foto")
async def okutma_fotosu(okutma_id: int, dosya: UploadFile = File(...), c=DB):
    """Fazla kaydının fotoğrafı.

    Fazla, sayım bittikten sonra kimsenin doğrulayamayacağı tek çıktıdır:
    ürün rafa geri konur, geriye yalnızca bir satır kalır (DEMO_FEEDBACK.md 6).
    """
    if not c.execute("SELECT 1 FROM okutma WHERE id=?", (okutma_id,)).fetchone():
        raise HTTPException(404, "Okutma #%s bulunamadı" % okutma_id)
    return await foto_yaz(c, dosya, okutma=okutma_id)


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
