"""Kap defteri uçları (KUTU_TASARIM.md).

Kabın içeriği KALICIDIR ve oturuma bağlı değildir — bu yüzden uçlar da
oturumun altında değil, kendi başına duruyor. Sayım tarafındaki tek bağ
`matching.kutu_coz`: kuyruğa düşmüş bir kap kaydını hem tanımlar hem sayar.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import etiketler
from .. import kutu as kutum
from .ortak import DB

router = APIRouter(prefix="/api", tags=["kutu"])


class KutuIcerik(BaseModel):
    """Kabın içeriği. `izleme` İSTENMEZ — cevabı Tiger'da (beklenen.izleme).

    Bug dosyası (I3) "bu ürün seri numarası gerektiriyor mu" diye kullanıcıya
    soruyordu; sormak, yanlış cevaplanabilen bir soru eklemek olurdu.
    """
    malzeme: str
    adet: float | None = None
    yukleme: int
    ambar: str
    raf: str | None = None
    oturum: int | None = None


@router.get("/kutu")
def liste(q: str | None = None, sadece_tanimli: bool = False, limit: int = 500,
          c=DB):
    return kutum.liste(c, q=q, sadece_tanimli=sadece_tanimli, limit=limit)


@router.get("/kutu/{kod}")
def getir(kod: str, yukleme: int | None = None, ambar: str | None = None, c=DB):
    """Tek kap. Tazelik kararı (`oneri_adet`) burada verilir, arayüzde değil."""
    if etiketler.etiket_turu(kod) != "kutu":
        raise HTTPException(400, "%s bir kap etiketi değil" % kod)
    satir = kutum.getir(c, kod)
    if not satir:
        raise HTTPException(404, "Kap %s tanımlı değil" % kod)
    return kutum.gorunum(c, satir, yukleme, ambar)


@router.post("/kutu/{kod}")
def tanimla(kod: str, istek: KutuIcerik, c=DB):
    """Kabın içeriğini yaz / güncelle.

    İzleme yöntemi malzemeden KOPYALANIR, kullanıcıdan alınmaz. Malzeme bu
    ambarda kayıtlı değilse reddedilir: uygulama sayılan ambarın dışına çıkmaz
    (CLAUDE.md 3.5).
    """
    if etiketler.etiket_turu(kod) != "kutu":
        raise HTTPException(400, "%s bir kap etiketi değil" % kod)
    b = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                  "ORDER BY id LIMIT 1",
                  (istek.yukleme, istek.ambar, istek.malzeme.strip())).fetchone()
    if not b:
        raise HTTPException(400, "%s bu ambarda kayıtlı değil" % istek.malzeme)
    if b["haric"]:
        raise HTTPException(400, "Bu kalem sayım dışı: %s" % (b["haric_sebep"] or ""))
    satir = kutum.tanimla(c, kod, b["kod"], istek.adet, b["izleme"] or "yok",
                          raf=istek.raf, oturum=istek.oturum)
    c.commit()
    return kutum.gorunum(c, satir, istek.yukleme, istek.ambar)


@router.delete("/kutu/{kod}")
def bosalt(kod: str, c=DB):
    """Kap boşaldı / başka işe ayrıldı: içerik bağı silinir, numara kalır."""
    satir = kutum.bosalt(c, kod)
    if not satir:
        raise HTTPException(404, "Kap %s tanımlı değil" % kod)
    c.commit()
    return kutum.gorunum(c, satir)
