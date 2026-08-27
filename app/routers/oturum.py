"""Sayım ekranı: oturum yaşam döngüsü, okutma, durum, arama."""
import json

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


class ElleSay(BaseModel):
    """Listeden seçerek sayma (I5). `ham` varsa öğrenilir."""
    beklenen_id: int
    ham: str | None = None


class SabitKod(BaseModel):
    """Sabit malzeme kodu kilidi (I2). None / boş = kilidi aç."""
    kod: str | None = None


class YedekMod(BaseModel):
    acik: bool


class OkutmaSil(BaseModel):
    """Varsayılan kapsam GRUP: bir grup bir üründür (CLAUDE.md 4.4)."""
    kapsam: str = "grup"        # "grup" | "satir"


class Coz(BaseModel):
    beklenen_id: int


class SeriSec(BaseModel):
    """Belirsiz kalan seri numarası kararı (CLAUDE.md 4.4 — `sn_adaylar`)."""
    seri: str


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


@router.delete("/okutma/{okutma_id}")
def okutma_sil(okutma_id: int, istek: OkutmaSil | None = None, c=DB):
    """Akış listesinden bir okutmayı sil (I1).

    `##GERIAL##` yalnızca sonuncuyu alır; sahada yanlış okutma birkaç ürün
    sonra fark ediliyor. Yan etkiler aynı yoldan geri alınır.
    """
    x = c.execute("SELECT oturum FROM okutma WHERE id=?", (okutma_id,)).fetchone()
    if not x:
        raise HTTPException(404, "Okutma #%s bulunamadı" % okutma_id)
    o = oturum_getir(x["oturum"], c)
    sonuc = matching.okutma_sil(c, o, okutma_id,
                                kapsam=(istek.kapsam if istek else "grup"))
    if sonuc.get("hata"):
        raise HTTPException(400, sonuc["hata"])
    c.commit()
    sonuc["durum"] = matching.durum(c, oturum_getir(x["oturum"], c))
    return sonuc


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
    # Yumuşak uyarılar — `##BITIR##` komut barkoduyla aynı kapılar, iki yol
    # aynı şeyi söylesin diye. Sayım doğru; eksik olan bilgi.
    eksik_lot = matching.eksik_lotlar(c, o)
    secilmemis = matching.sn_secilmemisler(c, oturum_id)
    if (eksik_lot or secilmemis) and not zorla:
        raise HTTPException(409, {
            "mesaj": "Bitirmeden önce bakın: %s%s%s" % (
                ("%d lot satırında sayılan < beklenen" % len(eksik_lot))
                if eksik_lot else "",
                " · " if (eksik_lot and secilmemis) else "",
                ("%d kayıtta seri numarası seçilmedi" % len(secilmemis))
                if secilmemis else ""),
            "eksik_lot": eksik_lot, "sn_secilmemis": secilmemis})
    return dict(oturumlar.bitir(c, oturum_id))


@router.post("/oturum/{oturum_id}/yeniden-ac")
def yeniden_ac(oturum_id: int, c=DB):
    """Kazara kapanan oturumu geri aç.

    `##BITIR##` komut kartında basılı ve sayım günlerce sürüyor; kapanan
    oturumu diriltmenin yolu yoktu, yeni oturum açmak o ana kadar sayılan her
    şeyi "eksik" yapardı.
    """
    oturum_getir(oturum_id, c)
    ot, hata = oturumlar.yeniden_ac(c, oturum_id)
    if hata:
        raise HTTPException(409, hata)
    c.commit()
    return matching.durum(c, ot)


@router.post("/okutma/{okutma_id}/seri-sec")
def seri_sec(okutma_id: int, istek: SeriSec, c=DB):
    """Belirsiz kalan seri numarasını seç (Tiger Düzeltme'ye bu değer gider).

    Üründe birden çok tanınmayan alfanümerik barkod varsa (P/N + S/N gibi)
    hangisinin cihaza özel olduğu bilinemez; motor geçici olarak en uzunu yazıp
    adayları `okutma.sn_adaylar`'da bırakır. Burada karar veriliyor.

    Öğrenme (`eslesme`) DEĞİŞMEZ: gruptaki bütün barkodlar zaten malzemeye
    bağlandı, seçim yalnızca "Tiger'a hangi değer seri no diye önerilecek"
    sorusunu kapatır.
    """
    x = c.execute("SELECT * FROM okutma WHERE id=?", (okutma_id,)).fetchone()
    if not x:
        raise HTTPException(404, "Okutma #%s bulunamadı" % okutma_id)
    try:
        adaylar = json.loads(x["sn_adaylar"] or "[]")
    except ValueError:
        adaylar = []
    secim = (istek.seri or "").strip()
    # Boş seçim = "hiçbiri seri numarası değil": öneri üretilmez, satır Tiger
    # Düzeltme'ye hiç girmez (`sn_yok` sözleşmesiyle aynı sonuç).
    if secim and adaylar and secim not in adaylar:
        raise HTTPException(400, "Seçilen değer bu okutmanın adayları arasında değil.")
    c.execute("UPDATE okutma SET yeni_seri=?, sn_adaylar=NULL WHERE id=?",
              (secim, okutma_id))
    c.commit()
    return dict(c.execute("SELECT * FROM okutma WHERE id=?", (okutma_id,)).fetchone())


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


@router.post("/oturum/{oturum_id}/say")
def elle_say(oturum_id: int, istek: ElleSay, c=DB):
    """Barkodu olmayan ürünü listeden seçerek sayıldı işaretle (I5)."""
    o = oturum_getir(oturum_id, c)
    if o["durum"] != "acik":
        raise HTTPException(409, "Oturum kapalı")
    sonuc = matching.elle_say(c, o, istek.beklenen_id, ham=istek.ham)
    if sonuc.get("hata"):
        raise HTTPException(400, sonuc["hata"])
    c.commit()
    sonuc["durum"] = matching.durum(c, oturum_getir(oturum_id, c))
    return sonuc


@router.post("/oturum/{oturum_id}/sabit-kod")
def sabit_kod_ayarla(oturum_id: int, istek: SabitKod, c=DB):
    """Malzeme kodunu kilitle / kilidi aç (I2).

    `##KILIT##` komut barkodunun ikizi: içeride aynı komutu üretip
    `matching.okut()`'a verir — iki kod yolu oluşmasın (`/raf` ve `/adet` ile
    aynı desen).
    """
    o = oturum_getir(oturum_id, c)
    if o["durum"] != "acik":
        raise HTTPException(409, "Oturum kapalı")
    kod = (istek.kod or "").strip()
    sonuc = matching.okut(c, o, ("##KILIT-%s##" % kod) if kod else "##KILITAC##")
    if sonuc.get("tip") == "kilit_yok":
        raise HTTPException(400, "%s bir malzeme kodu değil" % kod)
    c.commit()
    sonuc["durum"] = matching.durum(c, oturum_getir(oturum_id, c))
    return sonuc


@router.post("/oturum/{oturum_id}/kutu-kapat")
def kutu_kapat(oturum_id: int, c=DB):
    """Açık seri takipli kabı kapat (KUTU_TASARIM.md 5).

    `##KUTUKAPAT##` komut barkodunun ikizi: içeride aynı komutu üretip
    `matching.okut()`'a verir — `/raf`, `/adet` ve `/sabit-kod` ile aynı desen,
    iki kod yolu oluşmasın.
    """
    o = oturum_getir(oturum_id, c)
    if o["durum"] != "acik":
        raise HTTPException(409, "Oturum kapalı")
    sonuc = matching.okut(c, o, "##KUTUKAPAT##")
    c.commit()
    sonuc["durum"] = matching.durum(c, oturum_getir(oturum_id, c))
    return sonuc


@router.post("/oturum/{oturum_id}/yedek-parca")
def yedek_parca_ayarla(oturum_id: int, istek: YedekMod, c=DB):
    """Yedek parça modunu aç / kapat (I4)."""
    o = oturum_getir(oturum_id, c)
    if o["durum"] != "acik":
        raise HTTPException(409, "Oturum kapalı")
    sonuc = matching.okut(c, o, "##YEDEK##" if istek.acik else "##YEDEKKAPAT##")
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
