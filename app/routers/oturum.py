"""Sayım ekranı: oturum yaşam döngüsü, okutma, durum, arama."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import matching, norm, oturumlar
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


class AdetAyar(BaseModel):
    """Sıradaki grubun adedi. 0 sıfırlar, öteki değerler mevcuda EKLENİR."""
    adet: int


class OkutmaGuncelle(BaseModel):
    """Kısmi güncelleme: sadece gönderilen alan değişir."""
    ad: str | None = None
    not_: str | None = None


class Coz(BaseModel):
    beklenen_id: int


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


@router.patch("/okutma/{okutma_id}")
def okutma_guncelle(okutma_id: int, istek: OkutmaGuncelle, c=DB):
    """Fazla kaydına ürün adı / not yaz.

    Tiger'da karşılığı olmayan bir ürün fazla işaretlendiğinde malzeme kodu
    boş kalır ve rapordaki açıklama üretilemez. Adı kullanıcı yazar; yoksa
    kayıt sonradan hiçbir işe yaramıyor (DEMO_FEEDBACK.md 3).
    """
    if not c.execute("SELECT 1 FROM okutma WHERE id=?", (okutma_id,)).fetchone():
        raise HTTPException(404, "Okutma #%s bulunamadı" % okutma_id)
    if istek.ad is not None:
        c.execute("UPDATE okutma SET ad=? WHERE id=?", (istek.ad.strip(), okutma_id))
    if istek.not_ is not None:
        c.execute("UPDATE okutma SET not_=? WHERE id=?", (istek.not_.strip(), okutma_id))
    c.commit()
    return dict(c.execute("SELECT * FROM okutma WHERE id=?", (okutma_id,)).fetchone())


@router.get("/oturum/{oturum_id}/esleme")
def esleme(oturum_id: int, c=DB):
    """Sayım sonu eşleştirme ekranı: solda fazlalar, sağda eksikler."""
    return matching.esleme_verisi(c, oturum_getir(oturum_id, c))


@router.post("/okutma/{okutma_id}/bagla")
def okutma_bagla(okutma_id: int, istek: Coz, c=DB):
    """Fazla kaydını eksik bir kayda bağla (sayım sonu eşleştirmesi)."""
    sonuc = matching.fazla_bagla(c, okutma_id, istek.beklenen_id)
    if "hata" in sonuc:
        raise HTTPException(400, sonuc["hata"])
    c.commit()
    return sonuc


@router.post("/okutma/{okutma_id}/coz-ayir")
def okutma_coz_ayir(okutma_id: int, c=DB):
    sonuc = matching.fazla_coz_ayir(c, okutma_id)
    if "hata" in sonuc:
        raise HTTPException(400, sonuc["hata"])
    c.commit()
    return sonuc


@router.post("/oturum/{oturum_id}/bitir")
def bitir(oturum_id: int, zorla: bool = False, c=DB):
    o = oturum_getir(oturum_id, c)
    # Tampon ÖNCE kapanır (matching.okut'taki ##BITIR## ile aynı sıra): grup_coz
    # yeni bir kuyruk kaydı yaratabilir ve kapılar onu da görmeli.
    #
    # commit şart: aşağıdaki HTTPException, DB bağımlılığının `yield`'ine
    # fırlatılıyor ve oradaki `c.commit()` hiç çalışmıyor — grup_coz'un yazdığı
    # kuyruk kaydı geri alınır, kullanıcıya var olmayan bir kayıt bildirilirdi.
    matching.grup_coz(c, o)
    c.commit()
    bekleyen = matching.bekleyen_kuyruk(c, oturum_id)
    if bekleyen and not zorla:
        raise HTTPException(409, {"mesaj": "Kuyrukta çözülmemiş %d ürün var."
                                           % len(bekleyen), "kuyruk": bekleyen})
    # Adsız fazla raporda kullanılamaz: geriye seri numarası ve raf kalır.
    adsiz = matching.adsiz_fazlalar(c, oturum_id)
    if adsiz and not zorla:
        raise HTTPException(409, {"mesaj": "%d fazla kaydının ne olduğu yazılmamış."
                                           % len(adsiz), "adsiz": adsiz})
    # Fotoğrafsız fazla, sonradan kimsenin doğrulayamayacağı bir satırdır.
    fotosuz = matching.fotosuz_fazlalar(c, oturum_id)
    if fotosuz and not zorla:
        raise HTTPException(409, {"mesaj": "%d fazla kaydının fotoğrafı yok."
                                           % len(fotosuz), "fotosuz": fotosuz})
    return dict(oturumlar.bitir(c, oturum_id))


@router.post("/oturum/{oturum_id}/raf")
def raf_ayarla(oturum_id: int, istek: RafAyar, c=DB):
    """Rafı okuyucusuz ayarla (telefondan). Kuyruk kapısı burada da işler."""
    o = oturum_getir(oturum_id, c)
    # Normalizasyon `norm.raf_adi()`de, tek yerde: kartta basılan değerle
    # burada elle yazılan değer aynı olmalı, yoksa `ÜST-1` ve `UST-1` iki ayrı
    # raf sayılır. Temizlikten sonra hiçbir şey kalmadıysa reddediyoruz —
    # sessizce boş rafa geçmek sayımın raf bilgisini yok ederdi.
    ad = norm.raf_adi(istek.raf)
    if not ad:
        raise HTTPException(400, "Raf adı harf ya da rakam içermeli.")
    sonuc = matching.okut(c, o, "##RAF-%s##" % ad, zorla=istek.zorla)
    c.commit()
    sonuc["durum"] = matching.durum(c, oturum_getir(oturum_id, c))
    return sonuc


@router.post("/oturum/{oturum_id}/adet")
def adet_ayarla(oturum_id: int, istek: AdetAyar, c=DB):
    """Sıradaki grubun adedini okuyucusuz gir (telefondaki tuş takımı).

    `##ADET-N##` komut barkoduyla BİREBİR aynı yoldan geçer (`matching.okut`) —
    iki giriş yolu iki ayrı davranışa ayrılmasın. Komut barkodu sabit adetlerle
    sınırlı; telefon ara değerleri girer.
    """
    o = oturum_getir(oturum_id, c)
    if o["durum"] != "acik":
        raise HTTPException(409, "Oturum kapalı.")
    if istek.adet < 0 or istek.adet > norm.ADET_TAVAN:
        raise HTTPException(400, "Adet 0 ile %d arasında olmalı." % norm.ADET_TAVAN)
    sonuc = matching.okut(c, o, "##ADET-%d##" % istek.adet)
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
def ara(oturum_id: int, q: str = "", limit: int = 0, offset: int = 0,
        sadece_acik: bool = False, kirli: bool | None = None,
        izleme: str | None = None, c=DB):
    """Malzeme arama / listeleme.

    "Bu olabilir" önerisinin yerini aldı (DEMO_FEEDBACK.md 4): öneri sahada
    doğru sonuç vermiyordu. Filtreler q boşken de çalışır, böylece kullanıcı
    listeyi gezebilir. Aktif raf sıralamayı etkiler, süzmez.

    limit=0 (varsayılan) sınırsız: eşleştirme listesi eksiksiz olmalı, aksi
    hâlde kullanıcı listede olmayan ürünü tahmin etmeye çalışır.
    """
    o = oturum_getir(oturum_id, c)
    return matching.ara(c, o["yukleme"], o["ambar"], q, limit=limit, offset=offset,
                        oturum=o["id"], sadece_acik=sadece_acik, kirli=kirli,
                        izleme=izleme, raf=o["aktif_raf"])
