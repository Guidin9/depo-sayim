"""Rapor ekranı: sekme önizlemesi, Excel indirme, komut kartı."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .. import barkod, reports
from .ortak import DB, oturum_getir

router = APIRouter(prefix="/api", tags=["rapor"])


class KartIstek(BaseModel):
    raflar: list[str] = []


class RafEtiketIstek(BaseModel):
    raflar: list[str] = []
    kopya: int = 1
    atla: int = 0
    duzen: str = "a4"


@router.get("/oturum/{oturum_id}/rapor/onizleme")
def onizleme(oturum_id: int, limit: int = 200, c=DB):
    oturum_getir(oturum_id, c)
    veri = reports.rapor_verisi(c, oturum_id)
    for ad in reports.SEKME:
        s = veri[ad]
        s["toplam"] = len(s["satirlar"])
        s["satirlar"] = s["satirlar"][:limit]
    return veri


@router.get("/oturum/{oturum_id}/rapor.xlsx")
def indir(oturum_id: int, c=DB):
    oturum_getir(oturum_id, c)
    yol = reports.rapor_yolu(oturum_id)
    reports.excel_yaz(c, oturum_id, yol)
    return FileResponse(
        yol, filename="sayim_raporu_%s.xlsx" % oturum_id,
        media_type="application/vnd.openxmlformats-officedocument."
                   "spreadsheetml.sheet")


@router.post("/komut-karti", response_class=HTMLResponse)
def komut_karti(istek: KartIstek):
    return HTMLResponse(barkod.kart_html(istek.raflar))


@router.post("/raf-etiketi", response_class=HTMLResponse)
def raf_etiketi(istek: RafEtiketIstek):
    """Raf konum barkodlarını yapışkanlı 24'lük etiket sayfasına dizer.

    Komut kartından farkı: bunlar rafa doğrudan yapıştırılan yapışkanlı
    etiketler, laminatlanacak düz kâğıt kart değil. Defter kalemi değildir.
    """
    satirlar = barkod.raf_satirlari(istek.raflar, istek.kopya)
    if not satirlar:
        raise HTTPException(400, "Raf adı girilmedi.")
    try:
        return HTMLResponse(barkod.etiket_html(satirlar, istek.duzen, istek.atla))
    except ImportError as h:
        raise HTTPException(
            501, "Barkod üretimi için python-barcode gerekli: pip install "
                 "python-barcode") from h
