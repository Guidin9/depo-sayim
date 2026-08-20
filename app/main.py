"""Depo Sayım Uygulaması — FastAPI uygulaması ve statik servis.

    uvicorn app.main:app

Arayüz web/ altındaki React kaynağından derlenip app/static'e çıkar. İnternet
bağlantısı gerekmez: hiçbir CDN çağrısı yok, her şey bundle'ın içinde.
"""
import contextlib
import io
import os

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import db as dbm
from . import olaylar
from .routers import kuyruk, oturum, rapor, yukleme

STATIK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
# Telefon monitörünün adresi. Arayüz bu yolu görünce sade izleme ekranını açar.
TELEFON_YOLU = "/telefon"


@contextlib.asynccontextmanager
async def yasam(app):
    """Açılışta şemayı kur; kapanışta yapılacak bir şey yok (SQLite dosyada)."""
    dbm.baglan().close()
    yield


app = FastAPI(title="Depo Sayım", version="1.0", lifespan=yasam,
              description="Barkod okuyucuyla ambar sayımı, Tiger raporlarıyla "
                          "karşılaştırma ve fark raporu.")

app.include_router(yukleme.router)
app.include_router(oturum.router)
app.include_router(kuyruk.router)
app.include_router(rapor.router)


@app.middleware("http")
async def degisikligi_yayinla(request: Request, sonraki):
    """Veriyi değiştiren her istekten sonra ekranlara haber ver.

    Tek tek uç noktalara serpiştirmek yerine burada: yeni bir uç nokta
    eklendiğinde canlı güncelleme kendiliğinden çalışır.
    """
    yanit = await sonraki(request)
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and yanit.status_code < 400:
        olaylar.bildir(request.headers.get("X-Istemci"))
    return yanit


@app.get("/api/olaylar")
async def olay_akisi(request: Request):
    """Canlı güncelleme kanalı — telefon ve laptop aynı anda güncel kalsın."""
    return StreamingResponse(
        olaylar.akis(request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"})


def _birincil_ip():
    """Dışarı çıkan arayüzün IP'si.

    Laptopta Hyper-V / VirtualBox sanal anahtarları da IP taşır (192.168.x.1
    gibi) ve isim çözümlemesinde çoğu zaman önce gelirler. Telefon bunlara
    ulaşamaz. Paket göndermeden yalnızca yönlendirme tablosuna sorarak gerçek
    Wi-Fi adresini buluyoruz.
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))       # UDP, paket gitmez
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _ag_adresleri(port):
    """Yerel ağ adresleri (127.* hariç), en olası olan başta."""
    import socket
    ipler = []
    birincil = _birincil_ip()
    if birincil and not birincil.startswith("127."):
        ipler.append(birincil)
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127.") and ip not in ipler:
                ipler.append(ip)
    except OSError:
        pass
    return ["http://%s:%d" % (ip, port) for ip in ipler]


@app.get("/api/ag")
def ag(request: Request):
    """Telefondan bağlanmak için bu makinenin ağ adresleri.

    Telefon aynı Wi-Fi'dan bu adrese girer. Sunucunun --host 0.0.0.0 ile
    başlatılmış olması gerekir (baslat.bat bunu yapar).
    """
    port = request.url.port or 8000
    adresler = _ag_adresleri(port)
    return {"adresler": adresler, "port": port,
            "yerel": "http://127.0.0.1:%d" % port,
            "telefon": [a + TELEFON_YOLU for a in adresler]}


@app.get("/api/telefon-qr.svg")
def telefon_qr(request: Request, adres: str = ""):
    """Telefon monitörünün adresini QR olarak döner.

    Depoda kimse IP'yi elle yazmasın diye: PC ekranındaki kodu okutan telefon
    doğrudan /telefon adresine düşer. segno kurulu değilse 501 döner, arayüz
    o zaman adresi büyük yazıyla gösterir — uygulama kırılmaz.
    """
    try:
        import segno
    except ImportError:
        raise HTTPException(501, "QR için segno gerekli: pip install segno")
    if not adres:
        adresler = _ag_adresleri(request.url.port or 8000)
        if not adresler:
            raise HTTPException(503, "Ağ adresi bulunamadı — sunucu 0.0.0.0'da mı?")
        adres = adresler[0] + TELEFON_YOLU
    if len(adres) > 300:
        raise HTTPException(400, "Adres çok uzun")
    f = io.BytesIO()
    # Arayüz koyu temalı; QR'ın kendi beyaz zemini olmalı yoksa kamera okumaz.
    segno.make(adres, error="m").save(f, kind="svg", scale=6, border=2,
                                      dark="#000000", light="#ffffff")
    return Response(f.getvalue(), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/saglik")
def saglik():
    c = dbm.baglan()
    try:
        y = c.execute("SELECT COUNT(*) n FROM yukleme").fetchone()["n"]
        b = c.execute("SELECT COUNT(*) n FROM beklenen").fetchone()["n"]
        o = c.execute("SELECT COUNT(*) n FROM oturum WHERE bitir IS NULL").fetchone()["n"]
    finally:
        c.close()
    return {"durum": "ok", "yukleme": y, "beklenen": b, "acik_oturum": o,
            "arayuz": os.path.isdir(STATIK)}


if os.path.isdir(STATIK):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIK, "assets")),
              name="assets")

    @app.get("/{tam_yol:path}")
    def spa(tam_yol: str):
        """Tek sayfa uygulaması — bilinmeyen yollar index.html'e düşer."""
        aday = os.path.join(STATIK, tam_yol)
        if tam_yol and os.path.isfile(aday):
            return FileResponse(aday)
        # index.html önbelleğe alınmamalı: telefon eski sayfayı tutarsa yeni
        # arayüzü ve canlı güncellemeyi hiç görmez. /assets/* dosyaları hash'li,
        # onlar önbellekte kalabilir.
        return FileResponse(os.path.join(STATIK, "index.html"),
                            headers={"Cache-Control": "no-store"})
else:
    @app.get("/")
    def arayuz_yok():
        return JSONResponse({
            "durum": "arayüz derlenmemiş",
            "yapilacak": "cd web && npm install && npm run build",
            "api": "/docs",
        })
