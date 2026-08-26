"""Etiket basımı ve defteri (CLAUDE.md 12).

Basım ucu — komut kartında olduğu gibi — JSON değil yazdırılabilir HTML döner;
arayüz onu yeni sekmede açıp yazdırma penceresini çağırır.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .. import barkod, etiketler
from .ortak import DB, yukleme_getir

router = APIRouter(prefix="/api", tags=["etiket"])


class BasimIstek(BaseModel):
    tur: str = "seri"
    adet: int | None = None          # kaç etiket (malzeme: None = hepsi)
    kopya: int = 1                   # malzeme: her koddan kaç kopya
    kapsam: str = "eksik"            # malzeme: "eksik" | "hepsi" | "bos"
    yukleme: int | None = None
    ambar: str | None = None
    duzen: str = "a4"
    atla: int = 0
    not_: str | None = None


@router.get("/etiket/ihtiyac")
def ihtiyac(yukleme: int, ambar: str, c=DB):
    """Kaç etiket gerekebileceğinin üst sınırı. Karar kullanıcının."""
    yukleme_getir(yukleme, c)
    return etiketler.ihtiyac(c, yukleme, ambar)


@router.post("/etiket/basim", response_class=HTMLResponse)
def basim(istek: BasimIstek, c=DB):
    if istek.yukleme:
        yukleme_getir(istek.yukleme, c)
    try:
        _, satirlar = etiketler.bas(
            c, istek.tur, adet=istek.adet, kopya=istek.kopya,
            kapsam=istek.kapsam, yukleme=istek.yukleme,
            ambar=istek.ambar, duzen=istek.duzen, not_=istek.not_)
    except ValueError as h:
        raise HTTPException(400, str(h)) from h
    if not satirlar:
        raise HTTPException(400, "Basılacak etiket yok.")
    try:
        return HTMLResponse(barkod.etiket_html(satirlar, istek.duzen, istek.atla))
    except ImportError as h:
        raise HTTPException(
            501, "Barkod üretimi için python-barcode gerekli: pip install "
                 "python-barcode") from h
    except Exception as h:
        raise HTTPException(400, "Etiket sayfası üretilemedi: %s" % h) from h


@router.get("/etiket")
def defter(tur: str | None = None, basim: int | None = None,
           q: str | None = None, limit: int = 500, c=DB):
    return etiketler.defter(c, tur=tur, basim=basim, q=q, limit=limit)


@router.get("/etiket/basimlar")
def basim_gecmisi(limit: int = 50, c=DB):
    return etiketler.basimlar(c, limit)
