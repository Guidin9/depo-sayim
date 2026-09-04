"""Eşleştirme motoru.

depo_sayim.py:188 coz() ve depo_sayim.py:232 grup_coz() BİREBİR taşındı.
Çözümleme sırası, kirli kayıt tespiti, grup mantığı ve kod öneki eşleşmesi
sahada doğrulandı — değiştirmeyin (CLAUDE.md 4.2, 4.4).

Tek işlevsel eklenti: baştaki sıfır varyantı (CLAUDE.md 4.1). Yalnızca birebir
seri eşleşmesi boş döndüğünde VE okutulan değer tamamen rakam olduğunda dener,
bu yüzden mevcut senaryoların sonucunu değiştirmez.

Prototipe göre tek yapısal fark performans: her okutmada beklenen listesini
Python'da taramak yerine indeksli SQL kullanılıyor (kod_n / seri_n0 alanları
yükleme anında yazılıyor). ORDER BY id şart — prototip satırları ekleme
sırasında tarayıp ilk tutanı döndürüyordu.
"""
import datetime
import json

from . import etiketler
from . import kutu as kutum
from .norm import ADET_TAVAN, komut_coz, norm, sifirsiz, upc_mi

# Beklenen adet: satırın kendi miktarı. Seri takiplide en az 1 — Tiger'dan
# 0 miktarla gelen bir satır hiç sayılamaz hâle gelmesin.
#
# Eskiden seri takiplide SABİT 1 sayılıyordu ("Tiger'da miktar hep 1"). Gerçek
# veride yanlış: `izleme='seri'` olduğu hâlde miktarı 2 ve 4 olan 32 satır var.
# O satırlarda bir okutma satırı kapatıyor, ikinci cihaz "tekrar" deyip
# sayılmıyor ve eksik listesine de girmiyordu — adet sessizce buharlaşıyordu.
#
# `beklenen_adet()` bunun Python karşılığıdır; ikisi AYNI KURALI söylemeli.
BEKLENEN_ADET = ("CASE WHEN b.izleme='seri' THEN MAX(COALESCE(b.miktar,0),1) "
                 "ELSE COALESCE(b.miktar,0) END")

# "Bu beklenen satırına hâlâ yazılabilir mi?" — `kapasite_kaldi()`nin SQL
# karşılığı. Aday satır arayan sorgulara `AND` olarak eklenir; tek parametre
# alır (oturum).
#
# BURASI BİR DÖNEM `SAYILMADI` İDİ ("hiç okutulmamış"). D1 düzeltmesi ölçütü
# `beklenen_adet`e taşırken `kapasite_kaldi`, `sayaclar`, `ara`, `eksik_lotlar`
# ve `reports.eksik_kayitlar` geçirildi; ADAY ARAYAN İKİ SORGU geçirilmedi —
# `grup_coz`'un slot sorgusu ve `coz()` 5. adımı (DENETIM_20260904.md Y1).
# Sonuç: miktarı 2 olan kirli bir seri satırında ilk cihaz slotu dolduruyor,
# İKİNCİ cihaz kapasite dururken `fazla_onay` kuyruğuna düşüyordu — satır hem
# 1 adet eksik hem 1 adet onay bekler görünüyordu.
#
# miktar=1 satırlarda (Ambar 1'in tamamı) davranış eskisiyle BİREBİR aynı:
# bir okutmadan sonra kapasite 0. Fark yalnızca D1'in bulduğu 32 satırda —
# ambar 0/13/14, yani sıradaki ambarlarda.
KAPASITE_VAR = ("AND COALESCE((SELECT SUM(o.miktar) FROM okutma o "
                "WHERE o.oturum=? AND o.beklenen_id=b.id), 0) < " + BEKLENEN_ADET)


def _ts():
    return datetime.datetime.now().isoformat()


def _sayildi(c, oturum, bid):
    return bool(c.execute("SELECT 1 FROM okutma WHERE oturum=? AND beklenen_id=? LIMIT 1",
                          (oturum, bid)).fetchone())


def beklenen_adet(b):
    """Bu beklenen satırında Tiger kaç adet diyor?

    Seri takiplide satır normalde bir cihazdır (miktar=1) ama GERÇEK VERİDE
    2 ve 4 miktarlı seri satırları da var. `miktar` neyse o geçerlidir; 0 ya
    da eksik miktar seri takiplide 1'e yuvarlanır, yoksa satır hiç sayılamazdı.
    """
    m = b["miktar"] or 0
    if b["izleme"] == "seri":
        return m if m > 0 else 1
    return m


def kapasite_kaldi(c, oturum, b):
    """Bu beklenen kayda bu oturumda HÂLÂ bağlanabilir mi?

    Elle eşleştirmenin tek doğruluk ölçütü. `_sayildi` tek başına yetmez:

    Ölçüt tek: **sayılan adet < beklenen adet** (`beklenen_adet`). Seri
    takiplide beklenen normalde 1'dir, o yüzden davranış "bir kez okutulur"la
    aynı kalır.

    SERİ TAKİPLİDE DE `miktar` OKUNUR — "seri satırında miktar hep 1"
    varsayımı GERÇEK VERİDE YANLIŞ. Örnek Tiger çıktısında `izleme='seri'`
    olduğu hâlde miktarı 2 ve 4 olan 32 satır var (ambar 0/13/14). Eski
    ölçüt `not _sayildi()` idi: 2 adetlik satır TEK okutmayla kapanıyor,
    ikinci cihaz "tekrar" deyip sayılmıyor, eksik listesine de girmiyordu —
    bir adet ne sayaçta ne eksikte ne fazlada görünüyordu.

    `beklenen_adet` seri takiplide en az 1 döner: Tiger'dan 0 miktarla gelen
    bir satır bu yüzden hiç sayılamaz hâle gelmesin.

    Bu ölçüt `ara(sadece_acik=True)` içindeki SQL ile birebir aynı olmalı —
    arayüzün gösterdiği liste ile sunucunun kabul ettiği bağlama aynı kuralı
    kullanmazsa kullanıcı listede gördüğü kaydı bağlayamaz.
    """
    sayilan = c.execute("SELECT COALESCE(SUM(miktar),0) n FROM okutma "
                        "WHERE oturum=? AND beklenen_id=?",
                        (oturum, b["id"])).fetchone()["n"]
    return sayilan < beklenen_adet(b)


def _geri_json(ogrenilen=None, etiket=None, kuyruk=None, kutu=None,
               fazla_ad=None, malzeme_etiket=None):
    """`okutma.geri` gövdesi: bu okutmanın KENDİ SATIRI DIŞINDA ne yarattığı.

    `##GERIAL##` bunu okuyup temizler. Olmadan geri alma yarım kalıyordu:
    okutma siliniyor ama öğrenilen barkod kalıcı olarak yanlış malzemeye bağlı
    kalıyor ve Barkod Tablosu sekmesinden Tiger'ın malzeme kartına yazılmak
    üzere listeleniyordu — sessiz, kalıcı ve gelecek yılın sayımına taşınan
    bir bozulma.
    """
    d = {}
    if ogrenilen:
        d["ogrenilen"] = list(ogrenilen)
    if fazla_ad:
        d["fazla_ad"] = list(fazla_ad)
    if etiket:
        d["etiket"] = etiket
    # Boş havuzdan bir malzemeye bağlanan DM- etiketi. `etiket`ten AYRI
    # anahtar: ikisi aynı grupta birlikte bulunabilir (DM-000001 + DS-000045).
    if malzeme_etiket:
        d["malzeme_etiket"] = malzeme_etiket
    if kuyruk:
        d["kuyruk"] = kuyruk
    if kutu:
        # {"kod": "DK000007", "onceki": {...} | None} — kabın okutmadan
        # ÖNCEKİ hâli. Geri alma bunu geri yazar; yoksa reddedilen adet
        # kayıtta taze görünmeye devam ederdi.
        d["kutu"] = kutu
    return json.dumps(d, ensure_ascii=False) if d else None


def _geri_ekle(c, okutma_id, **yeni):
    """`okutma.geri`ye anahtar EKLER — üzerine yazmaz.

    `geri` bir satırın kendi dışında ne yarattığının tek kaydı ve birden çok
    adımda büyüyebiliyor: kayıt kuyruktan doğar (`kuyruk`), fazla yazılırken
    etiket bağlar ve ad öğrenir (`etiket`, `fazla_ad`), sayım sonunda bir
    malzemeye bağlanır (`ogrenilen`). Her adım kendi anahtarını EKLEMELİ.

    `fazla_bagla` bunu yapmıyordu: `geri`yi düpedüz yeni bir JSON'la
    değiştiriyor ve önceki anahtarların hepsini düşürüyordu. Sonuç, bağlanmış
    bir fazla satırı silindiğinde ortaya çıkıyordu — öğrenilen ad `fazla_ad`da
    kalıyor (yanlış ürün bir daha sorulmadan fazla yazılıyor), etiket defterde
    bağlı görünmeye devam ediyor (numara boşa gidiyor) ve kuyruk kaydı
    kayboluyordu.
    """
    r = c.execute("SELECT geri FROM okutma WHERE id=?", (okutma_id,)).fetchone()
    if not r:
        return None
    try:
        d = json.loads(r["geri"] or "") or {}
    except (TypeError, ValueError):
        d = {}
    for k, v in yeni.items():
        if not v:
            continue
        if k in ("ogrenilen", "fazla_ad"):
            d[k] = sorted(set((d.get(k) or []) + list(v)))
        else:
            d[k] = v
    g = json.dumps(d, ensure_ascii=False) if d else None
    c.execute("UPDATE okutma SET geri=? WHERE id=?", (g, okutma_id))
    return d


def _yan_etkileri_geri_al(c, satir, kuyruga_geri=True):
    """`okutma.geri` içindeki yan etkileri temizler. Ne temizlendiğini döner.

    `kuyruga_geri`: kaydı doğuran kuyruk satırı yeniden AÇILSIN mı?

    İki ayrı niyet var ve 2026-08-28'e kadar ikisi de tek yola bağlıydı:

      * ##GERIAL## / "yanlış çözdüm"  -> True. Ürün gerçek, karar yanlıştı;
        kayıt kuyruğa dönmeli ve yeniden çözülmeli.
      * Akış listesindeki Sil tuşu    -> False. Kullanıcı "bu satır hiç
        olmasın" diyor (yanlış okuma, çift okutma). True'da kayıt siliniyor
        ama kuyrukta yeniden beliriyordu ve kullanıcı Sil tuşunun ÇALIŞMADIĞINI
        düşünüyordu — sahada bildirildi (S5). Üstelik oturum kapanmadan
        kuyruk boşalmak zorunda olduğu için kayıttan kurtulmanın yolu yoktu.
    """
    try:
        d = json.loads(satir["geri"] or "") or {}
    except (TypeError, ValueError):
        return {}
    for h in d.get("ogrenilen") or []:
        c.execute("DELETE FROM eslesme WHERE barkod=?", (norm(h),))
    # Tiger'da karşılığı olmayan ürünün öğrenilmiş adı (`fazla_ad`) da bir yan
    # etkidir: geri alınmazsa silinen kaydın adı sonraki okutmalarda yaşamaya
    # devam eder ve yanlış ürün otomatik "fazla" yazılır.
    for h in d.get("fazla_ad") or []:
        c.execute("DELETE FROM fazla_ad WHERE barkod=?", (norm(h),))
    if d.get("etiket"):
        etiketler.coz_bagla(c, d["etiket"])
    if d.get("malzeme_etiket"):
        etiketler.coz_bagla(c, d["malzeme_etiket"])
    if d.get("kutu"):
        kutum.geri_al(c, d["kutu"]["kod"], d["kutu"].get("onceki"))
    if d.get("kuyruk") and kuyruga_geri:
        # Kuyruktan çözülmüş / fazla yazılmış kayıt yeniden açılır. Yoksa
        # okutma siliniyor ama kuyruk kaydı "çözüldü" kalıyor ve ürün hem
        # sayımdan hem kuyruktan düşüyordu.
        c.execute("UPDATE kuyruk SET cozuldu=0 WHERE id=?", (d["kuyruk"],))
    # Silinecek okutmaya bağlı fotoğraf sarkmasın: kuyruk bağlantısı duruyor.
    c.execute("UPDATE kuyruk_foto SET okutma=NULL WHERE okutma=?", (satir["id"],))
    return d


LIKE_KACIS = "!"


def _like_kacir(q):
    """LIKE deseninde joker karakterleri sıradan harfe çevirir.

    Sorgu doğrudan `%...%` içine gömülüyor; `%` ve `_` yazan kullanıcı farkında
    olmadan joker kullanmış oluyordu — `%` tek başına tüm tabloyu çekiyordu.

    Kaçış karakteri `!`, ters bölü DEĞİL: `ESCAPE '\\'` yazmak hem Python
    kaynağında hem SQL metninde ayrı ayrı kaçış istiyor ve sessizce boş dizeye
    dönüşüp "ESCAPE expression must be a single character" veriyor. `!` malzeme
    kodlarında ve seri numaralarında geçmiyor, geçse de kendisi kaçırılıyor.
    """
    s = str(q).replace(LIKE_KACIS, LIKE_KACIS * 2)
    return s.replace("%", LIKE_KACIS + "%").replace("_", LIKE_KACIS + "_")


def _sn_karar(adaylar, yedek=""):
    """Tiger'a önerilecek seri numarası kararı. `(seçilen, belirsiz_adaylar)`.

    İki kural, ikisi de gerçek veriyle üretilmiş hatalardan çıktı:

    1. **UPC asla seri numarası adayı değildir.** `grup_coz`'un `slot` dalı
       eskiden düpedüz `max(bilinmeyen, key=len)` diyordu ve perakende barkodu
       çoğu zaman gerçek S/N'den uzundur. Sonuç 2026-08-27'de üretildi:
       `0WGP72 + 198701689928 + W3S2000G7745` grubunda Tiger'a
       `0WGP72SAYIM1 -> 198701689928` yazılıyordu — o malzemenin 21 cihazının
       hepsi aynı UPC'yi taşıdığı için 21 cihaza aynı "tekil" numara. Uygulamanın
       temizlemeye çalıştığı kirliliğin ta kendisi. Aynı eleme `reports._yeni_seri`
       içinde ZATEN vardı; `slot` dalı tek başına onu kullanmıyordu.

    2. **İki aday kalırsa uygulama TAHMİN ETMEZ.** P/N + S/N gibi iki tanınmayan
       alfanümerik barkodda hangisinin cihaza özel olduğu bilinemez. Geçici
       olarak en uzunu yazılır (sayım durmasın) ama adaylar geri döner ve
       kullanıcıya sorulur — `okutma.sn_adaylar` dolu kaldığı sürece o satırın
       önerisi bir tahmindir ve rapor bunu dipnotta söyler.

    `yedek`: hiç aday kalmazsa kullanılacak değer (havuzdaki DS- etiketi).
    Üretici S/N her zaman kazanır, havuz etiketi son çaredir (CLAUDE.md 12.6).
    """
    temiz = [h for h in adaylar if h and not upc_mi(h)]
    if not temiz:
        return yedek, []
    if len(temiz) == 1:
        return temiz[0], []
    return max(temiz, key=len), temiz


def _adet_dagit(c, oturum, yukleme, ambar, kod, adet):
    """`adet` kadar miktarı bu malzemenin AÇIK satırlarına sırayla dağıtır.

    `[(beklenen_satiri, miktar), ...]` döner.

    Bir malzemenin birden çok lotu olabilir — örnek veride `BRODCOM 57414`
    tek başına 57 ayrı lot satırı taşıyor, her biri 1 adet. Eskiden adet dalı
    `ORDER BY id LIMIT 1` ile hep ilk satıra yazıyordu: o lot şişiyor, diğer
    56 satır eksik çıkıyordu.

    Açık satır bitince artan miktar SON paya eklenir (hiç pay çıkmadıysa ilk
    satıra yazılır). Fazlalık böylece `reports.eksik_kayitlar` tarafından adet
    fazlası olarak raporlanır — sessizce kaybolmaz.
    """
    pay, kalan, ilk = [], adet, None
    for r in c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                       "ORDER BY id", (yukleme, ambar, kod)):
        if ilk is None:
            ilk = r
        if kalan <= 0:
            break
        sayilan = c.execute("SELECT COALESCE(SUM(miktar),0) n FROM okutma "
                            "WHERE oturum=? AND beklenen_id=?",
                            (oturum, r["id"])).fetchone()["n"]
        bosluk = (r["miktar"] or 0) - sayilan
        if bosluk <= 0:
            continue
        al = min(kalan, bosluk)
        pay.append((r, al))
        kalan -= al
    if kalan > 0:
        if pay:
            son, m = pay[-1]
            pay[-1] = (son, m + kalan)
        elif ilk is not None:
            pay.append((ilk, kalan))
    return pay


def _adet_islemi(c, ot, kod, adet, hamlar, raf, grup, ts, seri_b=None,
                 ek_not="", geri=None, aciklama=None, izleme="yok"):
    """Lot / izlemesiz miktarı DOĞRU satır(lar)a yazar, sayacı hesaplar.

    İki giriş yolu paylaşıyor: normal grup çözümlemesi (`grup_coz`) ve kap
    okutması (`_kutu_grup` / `kutu_coz`). Ortak olması şart — kap sayımı
    "aynı işi başka türlü yapan ikinci bir dal" olsaydı, çok lotlu malzemede
    dağıtım kuralı (`_adet_dagit`) yalnızca bir yolda düzeltilir ve fark ancak
    raporda görülürdü.

    Hangi satır(lar)a yazılacağı önemli:

    Lot numarası okutulduysa (`seri_b`) miktarın TAMAMI o satıra yazılır —
    başka lota taşınmaz. Tiger'da 77 yazan lotta 80 sayıldıysa bu gerçek bir
    bulgudur; rapor onu adet fazlası olarak gösterir, biz örtmeyiz.

    Yalnızca malzeme kodu biliniyorsa miktar açık satırlara dağıtılır
    (`_adet_dagit`): 57 lotluk malzemede ##ADET-5## beş ayrı satıra gider.
    """
    oturum, yukleme, ambar = ot["id"], ot["yukleme"], ot["ambar"]
    pay = ([(seri_b, adet)] if seri_b is not None
           else _adet_dagit(c, oturum, yukleme, ambar, kod, adet))
    if not pay:                       # beklenen satırı yok (öğrenilmiş koddan)
        pay = [(None, adet)]
    for i, (satir, m) in enumerate(pay):
        # `geri` yalnızca İLK satıra: öğrenme grup başına bir kez oldu, miktar
        # birden çok satıra dağılmış olabilir. İki kez silmeye çalışmayalım.
        # `yeni_seri=''`: lot / izlemesiz kalemde Tiger'a yazılacak seri no
        # yoktur. NULL bırakılırsa rapor eski kurala düşer ve `ham`'daki
        # malzeme kodunu seri no diye önerebilir.
        c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,tip,
                     raf,grup,not_,geri,yeni_seri)
                     VALUES(?,?,?,?,?,?,?,'kod',?,?,?,?,'')""",
                  (oturum, ts, " + ".join(hamlar), kod,
                   satir["seri"] if satir else "", m,
                   satir["id"] if satir else None, raf, grup,
                   "adet +%g" % m + ek_not,
                   geri if i == 0 else None))

    # Sayaç satır bazında: malzeme geneli değil. Çok lotlu malzemede
    # "sayılan 12 / beklenen 1" gibi anlamsız bir oran çıkıyordu. Miktar birden
    # çok satıra dağıldıysa tek satırın oranı yanıltıcı olur — malzeme geneline
    # çıkılır ve `seri` boş bırakılır (arayüz "N satıra dağıtıldı" der).
    if len(pay) == 1 and pay[0][0] is not None:
        b = pay[0][0]
        top = c.execute("SELECT COALESCE(SUM(miktar),0) s FROM okutma WHERE oturum=? "
                        "AND beklenen_id=?", (oturum, b["id"])).fetchone()["s"]
        bek, lot = b["miktar"], b["seri"]
    else:
        top = c.execute("SELECT COALESCE(SUM(miktar),0) s FROM okutma WHERE oturum=? "
                        "AND kod=?", (oturum, kod)).fetchone()["s"]
        bek = c.execute("SELECT COALESCE(SUM(miktar),0) s FROM beklenen WHERE "
                        "yukleme=? AND ambar=? AND kod=?",
                        (yukleme, ambar, kod)).fetchone()["s"]
        lot = ""
    return {"tip": "adet", "kod": kod, "aciklama": aciklama, "toplam": top,
            "beklenen": bek, "seri": lot, "izleme": izleme, "miktar": adet,
            "satir": len(pay), "raf": raf}


# ---------------------------------------------------------------- tekil çözümleme
def coz(c, ham, yukleme, ambar, oturum):
    """Tek bir okutmayı çözer: seri / kod / ogrenilmis / upc / bilinmiyor."""
    n = norm(ham)
    if not n:
        return {"t": "bos"}

    # 1) Birebir seri eşleşmesi
    r = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND seri_n=? "
                  "ORDER BY id LIMIT 1", (yukleme, ambar, n)).fetchone()
    notu = None

    # 1b) Baştaki sıfır varyantı (CLAUDE.md 4.1)
    if not r:
        n0 = sifirsiz(n)
        if n0:
            r = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND "
                          "seri_n0=? ORDER BY id LIMIT 1", (yukleme, ambar, n0)).fetchone()
            if r:
                notu = "baştaki sıfır varyantı"

    if r:
        # `tekrar` kararı `_sayildi` ile verilemez: lot satırı TEK satırda ÇOK
        # adet taşır (77 adetlik lot bir okutmayla bitmez). Ölçüt tek yerde
        # duruyor — `kapasite_kaldi()`. Seri takipli satırda zaten
        # `not _sayildi()` ile aynı sonucu veriyor.
        d = {"t": "seri" if kapasite_kaldi(c, oturum, r) else "tekrar", "id": r["id"],
             "kod": r["kod"], "aciklama": r["aciklama"], "seri": r["seri"],
             "izleme": r["izleme"], "birim": r["birim"],
             "haric": r["haric"], "haric_sebep": r["haric_sebep"]}
        if notu:
            d["not"] = notu
        return d

    # 1c) Kendi bastığımız SERİ etiketi (CLAUDE.md 12)
    #
    # Bağlanmış etiket burada yakalanmazsa ikinci okutulduğunda 'bilinmiyor'a
    # düşer ve aynı malzemenin BİR SONRAKİ kirli slotunu doldurur — çift sayım.
    # Gerçek S/N'lerde bu sorun yok çünkü onlar Tiger'da yazılı; bizim
    # etiketimiz ise henüz yalnızca raporda duruyor.
    #
    # Malzeme etiketleri buraya girmez: onlar basımda `eslesme`'ye yazılıyor ve
    # aşağıdaki 4. adımdan normal öğrenilmiş barkod gibi geçiyor.
    # (etiket.tur='seri' bu satırdaki r["t"]=="seri" ile aynı şey değil: biri
    # etiketin türü, diğeri çözümleme sonucu.)
    e = c.execute("SELECT * FROM etiket WHERE kod=? AND tur='seri'", (n,)).fetchone()
    if e:
        if e["beklenen_id"]:
            r = c.execute("SELECT * FROM beklenen WHERE id=?",
                          (e["beklenen_id"],)).fetchone()
            if r:
                return {"t": "seri" if kapasite_kaldi(c, oturum, r) else "tekrar",
                        "id": r["id"], "kod": r["kod"], "aciklama": r["aciklama"],
                        "seri": r["seri"], "izleme": r["izleme"], "birim": r["birim"],
                        "haric": r["haric"], "haric_sebep": r["haric_sebep"],
                        "not": "etiket %s" % e["gosterim"]}
        # 1c-2) TIGER KAYDI OLMADAN TÜKENMİŞ ETİKET — bu oturumda fazla yazıldı.
        #
        # `beklenen_id` yalnızca Tiger'da karşılığı OLAN kayda bağlanınca
        # dolar. Fazla yolundan geçen etikette NULL kalır, ama `oturum` dolar
        # (`fazla_ogren` -> `etiketler.bagla(..., beklenen_id=None)`): yani
        # uygulama etiketin tükendiğini BİLİYOR ve o bilgiyi hiç okumuyordu.
        #
        # Sonuç sessiz çift sayımdı (DENETIM_20260904.md K2, gerçek veriyle
        # üretildi): aynı DS- etiketi ikinci kez okutulunca ikinci bir fazla
        # satırı doğuyor, `ad` da öğrenilmiş olduğu için `fazla_bilinen` dalı
        # onu sorusuz yazıyor — ne `ad_engel` ne `fotosuz` kapısı yakalıyor.
        # Canlı sayımda oldu: DS-000054 -> okutma #23 ve #26, 36 saniye arayla.
        #
        # DS- ETİKETİNE ÖZEL, DM-/UPC'ye değil: seri etiketi TEKİL cihaza
        # aittir, ikinci kez okutulması ikinci cihaz olamaz. Aynı DM- etiketi
        # ya da UPC ikinci kez okutulduğunda ikinci kayıt DOĞRU olabilir —
        # aynı üründen iki adet olabilir.
        #
        # OTURUMA BAĞLI: gelecek yılın sayımında aynı etiket ürünün üstünde
        # duruyor ve normal okutulabilmeli. `coz()`'un bütün `tekrar`
        # kararları gibi ölçüt bu oturumdur.
        if e["oturum"] == oturum:
            return {"t": "tekrar", "kod": e["malzeme"] or e["gosterim"],
                    "seri": e["gosterim"], "aciklama": None,
                    "not": "etiket %s bu oturumda zaten kullanıldı — seri "
                           "etiketi tek cihaza aittir" % e["gosterim"]}
        return {"t": "etiket_bos", "ham": ham, "etiket": e["gosterim"]}

    # 1d) Kendi bastığımız KUTU etiketi (KUTU_TASARIM.md 5)
    #
    # Kap kodu ne `eslesme`'ye girer ne de 'bilinmiyor' döner — üç kutu
    # sonucundan birini verir. Sebep: kap bir malzeme değil, malzemenin
    # durduğu yerdir. Öğrenilseydi 4. adım onu kalıcı bir malzeme barkodu
    # sayar, Barkod Tablosu sekmesi Tiger'ın malzeme kartına yazdırır ve kap
    # ertesi ay başka bir ürünle dolduğunda yanlış eşleşme kalıcı olurdu.
    #
    # Desene bakılıyor, yalnızca `etiket` tablosuna değil: defteri sıfırlanmış
    # bir makinede basılı DK etiketi hâlâ okutulabilmeli — tanımsız kap olarak
    # sorulur, sessizce "bilinmiyor" olup kuyruğa düşmez.
    if etiketler.etiket_turu(n) == "kutu":
        k = kutum.getir(c, n)
        e = c.execute("SELECT gosterim FROM etiket WHERE kod=?", (n,)).fetchone()
        gosterim = ((k["gosterim"] if k else None) or (e["gosterim"] if e else None)
                    or str(ham).strip().upper())
        if not k or not k["malzeme"]:
            return {"t": "kutu_bos", "ham": ham, "kutu": gosterim}
        r = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                      "ORDER BY id LIMIT 1", (yukleme, ambar, k["malzeme"])).fetchone()
        if not r:
            # Kap tanımlı ama malzemesi BU ambarda kayıtlı değil. Uygulama
            # sayılan ambarın dışına çıkmaz (CLAUDE.md 3.5) — "aslında öteki
            # depodaki kayıt olabilir" tam da kaldırdığımız tahmindir. Kayıt
            # kuyruğa düşer, kararı kullanıcı verir.
            return {"t": "kutu_yabanci", "ham": ham, "kutu": gosterim,
                    "kod": k["malzeme"], "adet": k["adet"]}
        return {"t": "kutu", "ham": ham, "kutu": gosterim, "kod": r["kod"],
                "aciklama": r["aciklama"], "izleme": r["izleme"], "birim": r["birim"],
                "haric": r["haric"], "haric_sebep": r["haric_sebep"],
                "adet": k["adet"], "taze": kutum.taze_mi(k),
                "not": "kutu %s" % gosterim}

    # 2) Birebir malzeme kodu
    r = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod_n=? "
                  "ORDER BY id LIMIT 1", (yukleme, ambar, n)).fetchone()
    if r:
        return {"t": "kod", "kod": r["kod"], "aciklama": r["aciklama"],
                "izleme": r["izleme"], "birim": r["birim"],
                "haric": r["haric"], "haric_sebep": r["haric_sebep"]}

    # 3) Kod öneki: ARK-1250L-S5A1 -> ARK1250LS5A1ATR8641924 (her iki taraf >= 8)
    if len(n) >= 8:
        r = c.execute("""SELECT * FROM beklenen WHERE yukleme=? AND ambar=?
                         AND LENGTH(kod_n)>=8
                         AND (kod_n LIKE ?||'%' OR ? LIKE kod_n||'%')
                         ORDER BY id LIMIT 1""",
                      (yukleme, ambar, n, n)).fetchone()
        if r:
            return {"t": "kod", "kod": r["kod"], "aciklama": r["aciklama"],
                    "izleme": r["izleme"], "birim": r["birim"],
                    "haric": r["haric"], "haric_sebep": r["haric_sebep"],
                    "not": "önek eşleşmesi"}

    # 3b) BU OTURUMDA Tiger'a zaten bu seri numarası önerildi mi?
    #
    # Kirli slot doldurulurken okutulan gerçek S/N `eslesme`'ye de öğrenilir
    # (kutudaki bütün barkodlar kaydedilsin diye — bilinçli karar). Ama o
    # öğrenme, aynı cihazın S/N'i kazara ikinci kez okutulduğunda 4. adımdan
    # `ogrenilmis` olarak geçip malzemenin BİR SONRAKİ kirli slotunu
    # dolduruyordu: tek cihaz iki kez sayılıyor, üstelik uyarı bile çıkmıyordu
    # (gerçek veriyle üretildi, 2026-08-27: BC-U6030 + ABC123XYZ -> iki slot).
    #
    # Temiz kayıtlarda bu korumayı 1. adım zaten veriyor (`tekrar`). Kirli
    # kayıtlarda karşılığı yoktu — yani deponun tam da yarısında.
    #
    # `yeni_seri` ile karşılaştırılıyor, `ham` ile değil: `ham` grubun bütün
    # barkodlarını taşıyor ve içinde malzeme kodu da var; koda göre eşleşseydi
    # aynı malzemenin ikinci cihazı "tekrar" sanılırdı.
    # SQL'de karşılaştırılamaz: `norm()` Python'da. Aday kümesi küçük —
    # yalnızca kirli slot doldurmuş satırlar `yeni_seri` taşır.
    for r in c.execute("""SELECT o.seri, o.kod, o.yeni_seri, b.aciklama
                          FROM okutma o LEFT JOIN beklenen b ON b.id=o.beklenen_id
                          WHERE o.oturum=? AND COALESCE(o.yeni_seri,'')<>''
                          ORDER BY o.id DESC""", (oturum,)):
        if norm(r["yeni_seri"]) == n:
            return {"t": "tekrar", "kod": r["kod"], "seri": r["seri"],
                    "aciklama": r["aciklama"],
                    "not": "bu seri numarası az önce %s slotuna yazıldı"
                           % (r["seri"] or "?")}

    # 4) Öğrenilmiş eşleşme
    e = c.execute("SELECT * FROM eslesme WHERE barkod=?", (n,)).fetchone()
    if e:
        r = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                      "ORDER BY id LIMIT 1", (yukleme, ambar, e["kod"])).fetchone()
        if r:
            return {"t": "ogrenilmis", "kod": r["kod"], "aciklama": r["aciklama"],
                    "izleme": r["izleme"], "birim": r["birim"],
                    "haric": r["haric"], "haric_sebep": r["haric_sebep"]}

    # 4b) Tiger'da karşılığı OLMAYAN, daha önce fazla yazılıp adlandırılmış ürün
    #
    # Kendi bastığımız DM- etiketiyle sisteme giren ürünlerin yolu bu. Tiger'da
    # kaydı yok, dolayısıyla 1-4 arası hiçbir adım tutmuyor ve her okutmada
    # kuyruğa düşüp adı yeniden soruluyordu: 2026-08-28 sayımında `DM-000001`
    # 47 kez okutuldu, 47 kez "DM-160 bas konuş" yazıldı (saha bildirimi S2).
    #
    # 4. adımdan SONRA duruyor, çünkü Tiger her zaman kazanır: ürün sonradan
    # Tiger'a girilirse (fazla fişi işlendikten sonra) 2/3/4 tutar ve bu adım
    # hiç çalışmaz. Öğrenilmiş ad yalnızca boşluğu doldurur, kural koymaz.
    f = c.execute("SELECT * FROM fazla_ad WHERE barkod=?", (n,)).fetchone()
    if f:
        return {"t": "fazla_bilinen", "ham": ham, "ad": f["ad"]}

    # 5) İçerme: gerçek S/N kirli kaydın içine gömülmüş olabilir
    #
    # Ölçüt `KAPASITE_VAR`, "hiç okutulmamış" DEĞİL — miktarı 2 olan bir kirli
    # satır ikinci cihazı da almalı (D1 / Y1). Aynı değerin ikinci kez
    # okutulması buraya hiç gelmez: 3b adımı `yeni_seri` üzerinden `tekrar`
    # döndürüyor ve bu adımdan ÖNCE duruyor.
    if len(n) >= 6:
        r = c.execute("""SELECT * FROM beklenen b WHERE yukleme=? AND ambar=?
                         AND izleme='seri' AND kirli=1 AND INSTR(seri_n, ?)>0
                         AND kod_n<>? """ + KAPASITE_VAR + " ORDER BY id LIMIT 1",
                      (yukleme, ambar, n, n, oturum)).fetchone()
        if r:
            return {"t": "seri", "id": r["id"], "kod": r["kod"],
                    "aciklama": r["aciklama"], "seri": r["seri"],
                    "izleme": r["izleme"], "birim": r["birim"],
                    "haric": r["haric"], "haric_sebep": r["haric_sebep"],
                    "not": "gömülü S/N"}

    # 6/7) UPC ya da bilinmiyor
    return {"t": "upc" if upc_mi(ham) else "bilinmiyor", "ham": ham}


def kutu_sayaci(c, ot):
    """Açık seri takipli kabın durumu — "150'nin 12'si" sayacı.

    `sayilan`, kap AÇILDIKTAN SONRA o malzemeye yazılan okutma sayısıdır
    (`acik_kutu_ilk` işaretinden büyük id'ler). Kap kapanınca `beklenen` ile
    karşılaştırılır; eksik kalırsa UYARILIR, örtülmez.

    `beklenen` kabın SON BİLİNEN adedidir, bir gerçek değil: içerik ayda bir
    değişiyor (KUTU_TASARIM.md 3). Bu yüzden sayacın kapanışta yaptığı şey
    engellemek değil, söylemek.
    """
    if not ot["acik_kutu"]:
        return None
    k = kutum.getir(c, ot["acik_kutu"])
    if not k or not k["malzeme"]:
        return None
    sayilan = c.execute(
        "SELECT COUNT(*) n FROM okutma WHERE oturum=? AND id>? AND kod=?",
        (ot["id"], ot["acik_kutu_ilk"] or 0, k["malzeme"])).fetchone()["n"]
    bek = k["adet"]
    return {"kutu": k["gosterim"], "kod": k["malzeme"], "sayilan": sayilan,
            "beklenen": bek, "taze": kutum.taze_mi(k),
            "eksik": (bek - sayilan) if (bek and sayilan < bek) else 0,
            "aciklama": (c.execute(
                "SELECT aciklama FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                "LIMIT 1", (ot["yukleme"], ot["ambar"], k["malzeme"])).fetchone()
                or {"aciklama": None})["aciklama"]}


def _kutu_ac(c, ot, kutu_ad, kod):
    """Seri takipli kabı açar: malzemeyi KİLİTLER ve sayacı sıfırlar.

    Kilit elle basılmıyor (I2'nin `##KILIT##` kartı), kap açılınca kuruluyor:
    21 cihazlı bir kapta malzeme kodunu 21 kez okutmak zaten kaldırılmıştı;
    kap okutulduğunda kodu bir kez daha okutmak da aynı gereksiz adım.

    Sayaç işareti okutma ID'sidir, zaman damgası değil: aynı saniyede iki
    okutma olabilir, aynı id olamaz.

    Başka bir kap açıksa o KAPANIR — iki kap aynı anda açık olamaz, yoksa
    sayaç hangisine ait belli olmaz. Kapanan kabın özeti geri döner.
    """
    if ot["acik_kutu"] and norm(ot["acik_kutu"]) == norm(kutu_ad):
        # AYNI kap yeniden okutuldu — kullanıcı ne kadar saydığını görmek için
        # ya da elindeki kabı yeniden doğrulamak için. Sayaç işareti KORUNUR:
        # sıfırlamak o ana kadar sayılan cihazları görünmez yapar ve kapanışta
        # kabın adedini eksik yazardı (5 okutulmuşken 0'dan başlayıp 3 daha
        # okutulursa kap "3 adet" olarak kaydedilirdi).
        c.execute("UPDATE oturum SET sabit_kod=? WHERE id=?", (kod, ot["id"]))
        return None
    onceki = None
    if ot["acik_kutu"]:
        onceki = _kutu_kapat(c, ot)
    ilk = c.execute("SELECT COALESCE(MAX(id),0) n FROM okutma WHERE oturum=?",
                    (ot["id"],)).fetchone()["n"]
    c.execute("UPDATE oturum SET acik_kutu=?, acik_kutu_ilk=?, sabit_kod=? WHERE id=?",
              (norm(kutu_ad), ilk, kod, ot["id"]))
    return onceki


def _kutu_kapat(c, ot, ts=None):
    """Açık kabı kapatır: kilidi bırakır, kabın son bilinen adedini tazeler.

    Sayılan < beklenen ise UYARIR ama ENGELLEMEZ: "kapta 150 yazıyordu, 12
    okuttun" bir bulgudur, hata değil — eksik gerçekten eksikse rapor zaten
    gösterecek. Uygulamanın hiçbir yerinde sayımı örtmüyoruz.

    Kilit yalnızca kabın kendi malzemesindeyse bırakılır: kullanıcı arada
    başka bir kodu elle kilitlemiş olabilir, o kararı bozmayalım.

    `sayilan == 0` iken kabın adedi GÜNCELLENMEZ. Yanlışlıkla açılıp hemen
    kapatılan bir kap, son bilinen adedini kaybetmemeli.
    """
    if not ot["acik_kutu"]:
        return None
    d = kutu_sayaci(c, ot)
    c.execute("UPDATE oturum SET acik_kutu=NULL, acik_kutu_ilk=0 WHERE id=?",
              (ot["id"],))
    # Kilidi kap kurmuştu, o yüzden kap kaydı OKUNAMASA DA bırakılır. Kayıt
    # arada silinmiş / boşaltılmış olabilir (Barkod ekranındaki "Boşalt");
    # o zaman `kutu_sayaci` None döner ve eski kod işareti hiç temizlemiyordu:
    # oturum artık adı bile bilinmeyen bir malzemeye kilitli kalıyor, sonraki
    # her okutma oraya yazılıyordu. ##KUTUKAPAT## de "açık kap yok" diyordu.
    if ot["sabit_kod"] and (d is None or norm(ot["sabit_kod"]) == norm(d["kod"])):
        c.execute("UPDATE oturum SET sabit_kod=NULL WHERE id=?", (ot["id"],))
    if d and d["sayilan"] > 0:
        kutum.tanimla(c, d["kutu"], d["kod"], d["sayilan"], "seri",
                      raf=ot["aktif_raf"], oturum=ot["id"], ts=ts)
    return d


def _acik_kutu_kuyrugu(c, oturum, kutu_ad):
    """Bu kap için bu oturumda AÇIK bir kuyruk kaydı var mı?

    Aynı kap iki kez okutulabilir — hatta okutulması normaldir: kullanıcı
    "kaç adet?" sorusunu görüp ##ADET-130## okutur ve kabı yeniden okutur.
    İkinci okutma yeni bir kuyruk kaydı açsaydı, ilki açık kalır ve oturum
    kapanmadan cevaplanması istenirdi — cevabı çoktan verilmiş bir soru.
    """
    n = norm(kutu_ad)
    for r in c.execute("SELECT * FROM kuyruk WHERE oturum=? AND cozuldu=0 "
                       "AND tur='kutu' ORDER BY id", (oturum,)):
        for h in json.loads(r["barkodlar"]):
            if etiketler.etiket_turu(h) == "kutu" and norm(h) == n:
                return r
    return None


def _ayni_kuyruk(c, oturum, hamlar):
    """Bu barkod kümesi bu oturumda ZATEN çözülmemiş kuyrukta duruyor mu?

    UYARIR, ENGELLEMEZ ve BİRLEŞTİRMEZ. Üç seçenekten doğru olan bu:

      * birleştirmek -> aynı barkodlu İKİ fiziksel ürün varsa biri kaybolur
      * engellemek   -> aynısı, üstelik kullanıcı ikinciyi hiç kaydedemez
      * susmak       -> kazara iki kez okutulan ürün iki kez sayılır ve bu
                        ancak Excel'de görülür

    Canlı sayımda oldu (DENETIM_20260904.md O5): `kuyruk#125` ve `#126` birebir
    aynı (`MIC-75GF10-00A1 + KMAA700581`), 16:05 ve 16:07. Kap kayıtlarında bu
    koruma zaten vardı (`_acik_kutu_kuyrugu`), normal kuyrukta yoktu.

    Ölçüt normalize edilmiş KÜME: okutma sırası ürünü değiştirmez.
    """
    hedef = {norm(h) for h in hamlar if norm(h)}
    if not hedef:
        return None
    for r in c.execute("SELECT * FROM kuyruk WHERE oturum=? AND cozuldu=0 "
                       "ORDER BY id", (oturum,)):
        try:
            var = {norm(h) for h in json.loads(r["barkodlar"]) if norm(h)}
        except (TypeError, ValueError):
            continue
        if var == hedef:
            return {"id": r["id"], "raf": r["raf"],
                    "ts": (r["ts"] or "")[:19].replace("T", " ")}
    return None


def _kutu_kuyrugu_kapat(c, oturum, kutu_ad):
    """Kap sayıldı: o kaba ait açık soru varsa kapanır."""
    r = _acik_kutu_kuyrugu(c, oturum, kutu_ad)
    if r:
        c.execute("UPDATE kuyruk SET cozuldu=1 WHERE id=?", (r["id"],))
    return r["id"] if r else None


# ---------------------------------------------------------------- grup çözümleme
def _yeni_grup(c, oturum):
    r = c.execute("SELECT COALESCE(MAX(grup),0)+1 g FROM okutma WHERE oturum=?",
                  (oturum,)).fetchone()
    return r["g"]


def _celiskili_grup(c, ot, farkli, hamlar, raf, ts, bilinmeyen=(), tekrar=None,
                    bekleyen_adet=0):
    """##SONRAKI## unutulmuş: tek grupta birden çok cihaz. Hepsini sayar.

    Her cihaz KENDİ grup numarasıyla ayrı satır olur — grup numarası "bir ürün"
    demek, o yüzden çelişkili tamponu tek gruba sıkıştırmak hatayı kalıcı hale
    getirirdi (`##GERIAL##` ve `okutma_sil` grup bazlı çalışıyor; tek grup
    olsaydı bir cihazı geri almak hepsini geri alırdı).

    `ham` her satırda KENDİ barkodudur, grubun tamamı değil: burada grup zaten
    tek ürün değil, dolayısıyla "grubun bütün barkodları bu cihazın üstündeydi"
    sözleşmesi (CLAUDE.md 4.4) geçerli değil. Grubun tamamı `not_` alanına
    denetim izi olarak yazılır.

    Tanınmayan barkodlar ÖĞRENİLMEZ: hangi cihaza ait oldukları belirsiz ve
    yanlış malzemeye bağlanan bir barkod gelecek yılın sayımına taşınır
    (CLAUDE.md 12.6 ile aynı gerekçe). Sonuçta `ogrenilmedi` ile bildirilir.

    `bekleyen_adet` BURADA DA UYGULANMAZ ama SESSİZ KALMAZ: her satır bir
    cihazdır (Tiger'da ayrı satır), yani ##ADET-25## anlamsızdır — `eslesti` ve
    `slot` dallarındaki `adet_yersiz` sözleşmesinin aynısı. Bu dal tek başına
    onu bildirmiyordu ve girilen adet sessizce yanıyordu
    (DENETIM_20260904.md Y5).
    """
    oturum = ot["id"]
    izi = " + ".join(hamlar)
    kayitlar = []
    for h, r in farkli:
        grup = _yeni_grup(c, oturum)
        yeni_es = "" if norm(h) == norm(r["seri"] or "") else h
        oid = c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,
                           tip,raf,grup,not_,yeni_seri)
                           VALUES(?,?,?,?,?,1,?,'eslesti',?,?,?,?)""",
                        (oturum, ts, h, r["kod"], r["seri"], r["id"], raf, grup,
                         "çelişkili grup — SIRADAKİ ÜRÜN unutulmuş olabilir | "
                         "okutulanlar: " + izi, yeni_es)).lastrowid
        kayitlar.append({"okutma": oid, "kod": r["kod"], "seri": r["seri"],
                         "aciklama": r["aciklama"], "ham": h})
    ogrenilmedi = list(bilinmeyen)
    return {"tip": "coklu", "sayi": len(kayitlar), "kayitlar": kayitlar,
            "barkodlar": hamlar, "raf": raf,
            "tekrar": tekrar[1]["seri"] if tekrar else None,
            "adet_yersiz": bekleyen_adet if bekleyen_adet > 1 else None,
            "ogrenilmedi": ogrenilmedi, "ses": "uyari"}


def _tamponu_geri_yaz(c, oturum, hamlar, bekleyen_adet, ts):
    """Grup HİÇBİR SATIR YAZMADAN döndüyse tamponu ve adedi geri koyar.

    `grup_coz` tamponu en başta siliyor. Yazan dallarda bu doğru, ama iki dal
    hiçbir şey yazmadan dönüyor — `tekrar` ve `haric` — ve orada tamponun
    tükenmesi ürünü BUHARLAŞTIRIYORDU: kullanıcı elindeki cihaz için hâlâ bir
    karar vermek isterken (##FAZLA##, ##ATLA##) tampon boş kaldığı için
    ##FAZLA## `bos` dönüyordu.

    Sahada üretildi (2026-08-28, S4): daha önce bağlanmış bir DS- etiketi
    okutulup ##SONRAKI## denince `tekrar` dönüyor, ardından Fazla'ya basmak
    hiçbir şey yapmıyordu. Kullanıcı etiketi söküp yenisini yapıştırınca
    çalışıyordu — çünkü yeni etiket `tekrar` dalına hiç girmiyor.

    Grup numarası `_yeni_grup` ile zaten tüketildi; onu geri almaya gerek yok
    (grup numarası yalnızca satırları kümeler, sıralı olmak zorunda değil).
    """
    for h in hamlar:
        c.execute("INSERT INTO tampon(oturum,ts,ham) VALUES(?,?,?)", (oturum, ts, h))
    if bekleyen_adet:
        c.execute("UPDATE oturum SET bekleyen_adet=? WHERE id=?",
                  (bekleyen_adet, oturum))


def grup_coz(c, ot, raf=None):
    """Tampondaki barkodları TEK ÜRÜN kabul edip çözer (##SONRAKI##)."""
    oturum, yukleme, ambar = ot["id"], ot["yukleme"], ot["ambar"]
    raf = raf if raf is not None else ot["aktif_raf"]
    ts = _ts()
    hamlar = [r["ham"] for r in c.execute(
        "SELECT ham FROM tampon WHERE oturum=? ORDER BY id", (oturum,))]
    c.execute("DELETE FROM tampon WHERE oturum=?", (oturum,))
    if not hamlar:
        return {"tip": "bos"}

    # Sıradaki grubun adedi (##ADET-25## ya da telefondaki tuş takımı). Tampon
    # gibi grupla birlikte tükenir — bir sonraki ürüne sızmamalı. Boş tamponda
    # SONRAKI'ye basmak adedi YAKMAZ: yukarıdaki erken dönüşün altındayız.
    bekleyen_adet = int(ot["bekleyen_adet"] or 0)
    if bekleyen_adet:
        c.execute("UPDATE oturum SET bekleyen_adet=0 WHERE id=?", (oturum,))

    grup = _yeni_grup(c, oturum)

    # YEDEK PARÇA MODU (I4) — `coz()` hiç çağrılmadan kısa devre.
    #
    # Yedek parçalar Tiger'da kayıtlı değil. Aranmaları yalnızca yanlış
    # eşleşme üretiyordu: bir yedek parçanın üstündeki üretici kodu başka bir
    # malzemenin önekine takılıp o malzemenin slotunu dolduruyordu. Kullanıcı
    # "bunu arama, yedek parça yaz" diyebilmeli (saha bildirimi I4).
    #
    # Öğrenme YOK: bu barkodu bir malzemeye bağlamak tam da kaçındığımız şey.
    # Kuyruk YOK: karar zaten verilmiş. Sayaçlara girmez, Eksik/Fazla'ya
    # girmez — kendi rapor sekmesinde durur.
    if ot["yedek_parca"]:
        oid = c.execute(
            """INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,tip,raf,grup,not_,
               yeni_seri) VALUES(?,?,?,?,'',?,'yedek',?,?,?,'')""",
            (oturum, ts, " + ".join(hamlar), None, bekleyen_adet or 1, raf, grup,
             "yedek parça modu")).lastrowid
        return {"tip": "yedek", "okutma": [oid], "barkodlar": hamlar, "raf": raf,
                "miktar": bekleyen_adet or 1, "ses": "ok"}

    coz_list = [(h, coz(c, h, yukleme, ambar, oturum)) for h in hamlar]

    seri_h = next((x for x in coz_list if x[1]["t"] == "seri"), None)
    kod_h = next((x for x in coz_list if x[1]["t"] in ("kod", "ogrenilmis")), None)
    # SABİT KOD KİLİDİ (I2): malzeme kodu bir kez okutuldu, sonrasında yalnız
    # seri numaraları geliyor. Kilit yalnızca grupta kod YOKKEN devreye girer —
    # elle okutulan kod her zaman kilidi yener, yoksa kullanıcı kilidi açmadan
    # başka bir ürünü sayamazdı.
    #
    # KİLİT, "BU ÜRÜN TIGER'DA YOK" BİLGİSİNİ DE YENEMEZ.
    #
    # Kilidin dayanağı tek cümle: "grupta malzeme kodu yok, demek ki elimdeki
    # kilitli malzemenin bir cihazı." Grupta `fazla_ad`'a yazılmış bir barkod
    # varsa o dayanak YANLIŞTIR — kullanıcı o barkod için "Tiger'da karşılığı
    # yok, adı şudur" kararını zaten açıkça vermiştir.
    #
    # Eskiden kilit `kod_h`'yi doldurup `kaynak`'ı doğru yapıyor ve aşağıdaki
    # `fazla_bilinen` dalı (`if not kaynak`) hiç çalışmıyordu. Sonuç sessiz
    # yanlış sayım (DENETIM_20260904.md K3, üretildi): adı "SARF KABLO" diye
    # öğrenilmiş bir kablo, kilitli `04RW5H` (SQL Server lisansı) kirli
    # slotuna yazılıyor, ekran YEŞİL yanıyordu. Kilit kalıcı bir kip; bir rafta
    # unutulursa bütün raf bu yoldan gider.
    #
    # Açık karar, ortam kipini yener. ELLE OKUTULAN kod ise hâlâ her ikisini de
    # yener: `kod_h` doluysa buraya zaten girilmiyor.
    sabit = None
    if not kod_h and ot["sabit_kod"] and not any(
            r["t"] == "fazla_bilinen" for _, r in coz_list):
        t = coz(c, ot["sabit_kod"], yukleme, ambar, oturum)
        if t.get("kod"):
            sabit = ot["sabit_kod"]
            kod_h = (ot["sabit_kod"], t)
    tekrar = next((x for x in coz_list if x[1]["t"] == "tekrar"), None)
    bilinmeyen = [h for h, r in coz_list if r["t"] in ("bilinmiyor", "upc")]
    # Boş seri etiketi tanınmayan barkod DEĞİLDİR: bilinmeyen listesine girerse
    # aşağıda `eslesme`'ye yazılır ve tekil cihaza özgü numara malzeme
    # seviyesine yükselir — üstelik Barkod Tablosu sekmesi onu Tiger'ın malzeme
    # kartına yazılacak barkod diye listeler.
    bos_etiket = [h for h, r in coz_list if r["t"] == "etiket_bos"]
    # Birebir eşleşme "bu satır bitti" demek DEĞİLDİR: lot / izlemesiz satırda
    # tek satır çok adet taşır. Seri dalına (miktar=1, satırı kapat) yalnızca
    # izleme='seri' satırları girer; lot numarası okutulmuş grup aşağıdaki adet
    # dalına düşer ve orada DOĞRU satıra yazılır (CLAUDE.md 2.4).
    seri_kaydi = seri_h if seri_h and seri_h[1].get("izleme") == "seri" else None

    # ÇELİŞKİLİ GRUP: bir grup bir üründür (CLAUDE.md 4.4), ama tek bir cihazın
    # üstünde Tiger'daki İKİ FARKLI beklenen seri kaydına eşleşen iki barkod
    # olamaz. Bu ancak ##SONRAKI## unutulduğunda olur — sahadaki en olası hata.
    #
    # Eski davranış: `seri_h = next(...)` ilk eşleşmeyi alıp GERİSİNİ SESSİZCE
    # ATIYORDU. Üç cihaz okutulup bir tanesi sayılıyor, ekran yeşil yanıyor, ses
    # aynı; kalan iki cihaz raporda "eksik" çıkıyor ve gerçekten depoda olmayan
    # bir üründen ayırt edilemiyordu. Çalışan uygulamada üretildi (2026-08-27):
    # sayaç 0 -> 1.
    #
    # Yeni davranış: hepsi sayılır, hiçbir okutma kaybolmaz, kullanıcı UYARILIR.
    # Yanlışsa Ctrl+Z zaten son grubu geri alıyor.
    #
    # Bu dal ÖĞRENME AKIŞINA DOKUNMAZ: "bir barkod tuttu, kalanları öğren"
    # akışındaki barkodlar `bilinmiyor` / `upc` tipindedir, `seri` değil —
    # buradaki kümeye hiç girmezler.
    seri_hepsi = [x for x in coz_list
                  if x[1]["t"] == "seri" and x[1].get("izleme") == "seri"]
    farkli = []
    for x in seri_hepsi:
        if x[1]["id"] not in [y[1]["id"] for y in farkli]:
            farkli.append(x)
    if len(farkli) > 1:
        return _celiskili_grup(c, ot, farkli, hamlar, raf, ts,
                               bilinmeyen=bilinmeyen, tekrar=tekrar,
                               bekleyen_adet=bekleyen_adet)

    if tekrar and not seri_h:
        # Hiçbir satır yazılmadı: tampon TÜKENMEZ (bkz. `_tamponu_geri_yaz`).
        # Kullanıcı elinde ikinci bir fiziksel cihaz tutuyor olabilir ve
        # ##FAZLA## ile devam edebilmeli.
        _tamponu_geri_yaz(c, oturum, hamlar, bekleyen_adet, ts)
        return {"tip": "tekrar", "kod": tekrar[1]["kod"], "seri": tekrar[1]["seri"],
                "aciklama": tekrar[1].get("aciklama"), "not": tekrar[1].get("not"),
                "tampon_duruyor": True, "barkodlar": hamlar, "ses": "uyari"}

    # KAP OKUTMASI (KUTU_TASARIM.md 5-6)
    #
    # Kural tek cümle: KAP KODU, MALZEME KODU OKUTMAKLA AYNI ŞEYDİR. Kap
    # malzemeyi, izleme yöntemini ve son bilinen adedi getirir; sayımın kendisi
    # mevcut dallardan geçer (slot doldurma, adet dağıtımı, fazla onayı). Ayrı
    # bir sayım yolu YAZILMADI — olsaydı `_adet_dagit` gibi kurallar iki yerde
    # ayrı ayrı düzeltilir ve fark ancak raporda görülürdü.
    #
    # Tek fark kabın TEK BAŞINA ne anlama geldiği: o an elde bir cihaz değil bir
    # kap var ve "kaç tane" sorusunun cevabı uygulamada YOK — kayıttaki adet
    # bayat olabilir (kutu.TAZELIK_GUN). Bu yüzden aşağıdaki iki dal soruyor,
    # varsaymıyor.
    kutu_h = next((x for x in coz_list if str(x[1]["t"]).startswith("kutu")), None)
    kutu_t = kutu_h[1] if kutu_h else None
    kutu_ad = kutu_t.get("kutu") if kutu_t else None
    if (kutu_t and kutu_t["t"] in ("kutu_bos", "kutu_yabanci")
            and not seri_h and not kod_h):
        # Bu dala YALNIZCA grupta başka hiçbir şey tanınmadıysa girilir. Kap
        # tanınan bir ürünle birlikte okutulduysa (kap + gerçek S/N gibi) o
        # ürün normal yoldan SAYILIR ve kap yalnızca denetim izine girer:
        # eskiden buraya düşülüyor, grup kuyruğa yazılıyor ve seri takipli
        # cihaz hiç sayılmıyordu — kuyruk kaydı kap olarak çözülünce de
        # sayılmıyor, çünkü seri takipli kapta sayım seri numaralarıyla olur.
        # Okutma sessizce buharlaşıyordu.
        #
        # Tanımsız kap KUYRUĞA yazılır, doğrudan bir tanımlama ekranına
        # DEĞİL. Arayüz paneli hemen açar; ama kullanıcı cevaplamadan raftan
        # ayrılırsa kayıt kuyrukta durur ve oturum kapanmadan sorulur. Ekrana
        # bırakılsaydı kap sessizce sayılmamış olurdu — uygulamanın hiçbir
        # yerde yapmadığı şey.
        yabanci = kutu_t["t"] == "kutu_yabanci"
        # Kayıtlı ama BU AMBARDA OLMAYAN malzeme öneri değildir: arayüz onu
        # doldurup gönderirse sunucu 400 verir (ambar dışına çıkmıyoruz,
        # CLAUDE.md 3.5). Eski kod yalnızca notta ve yanıtta durur, kullanıcı
        # ne olduğunu görsün diye.
        oneri = kod_h[1]["kod"] if kod_h else None
        notu = (("kap %s: kayıtlı malzemesi (%s) bu ambarda yok"
                 % (kutu_ad, kutu_t.get("kod"))) if yabanci
                else "kap %s tanımsız: içinde ne var?" % kutu_ad)
        var = _acik_kutu_kuyrugu(c, oturum, kutu_ad)
        if var:
            # Aynı kap yeniden okutuldu: ikinci soru açma, duranı tazele.
            c.execute("""UPDATE kuyruk SET ts=?, barkodlar=?, raf=?, kod=COALESCE(?,kod),
                         not_=?, adet=CASE WHEN ?>0 THEN ? ELSE adet END WHERE id=?""",
                      (ts, json.dumps(hamlar, ensure_ascii=False), raf, oneri, notu,
                       bekleyen_adet, bekleyen_adet, var["id"]))
            kid = var["id"]
        else:
            kid = c.execute("""INSERT INTO kuyruk(oturum,ts,barkodlar,raf,tur,kod,not_,
                               adet) VALUES(?,?,?,?,'kutu',?,?,?)""",
                            (oturum, ts, json.dumps(hamlar, ensure_ascii=False), raf,
                             oneri, notu, bekleyen_adet)).lastrowid
        return {"tip": "kutu_yabanci" if yabanci else "kutu_tanimsiz",
                "kuyruk_id": kid, "kutu": kutu_ad, "kod": oneri,
                "eski_kod": kutu_t.get("kod") if yabanci else None,
                "barkodlar": hamlar, "raf": raf,
                "miktar": bekleyen_adet or None, "ses": "kuyruk"}

    kutu_kaynak = None
    if kutu_t and kutu_t["t"] == "kutu":
        if not kod_h:
            kod_h = (kutu_h[0], kutu_t)          # kap = malzeme kodu okutmak
        # Kap kaydı yalnızca sayım GERÇEKTEN o kabın malzemesine yazıldığında
        # tazelenir. Grupta başka bir malzeme kodu da okutulmuşsa (kap yanlış
        # ürüne yapışmış olabilir) elle okutulan kazanır ve kaba dokunulmaz.
        if kutu_t.get("kod") == kod_h[1].get("kod"):
            kutu_kaynak = kutu_ad
        # Sayım dışı kalem dolu bir kapta da olabilir. Kap dallarına girmeden
        # normal akışa bırakılır: `haric` dalı hiçbir şey yazmadan uyarır,
        # yoksa kap "tanınmayan" gibi kuyruğa düşerdi.
        if kutu_t.get("haric"):
            pass
        elif kutu_t.get("izleme") == "seri" and len(hamlar) == 1 and not seri_h:
            # Seri takipli kapta kabın kendisi bir sayım DEĞİLDİR: her adet
            # Tiger'da ayrı satır. Kap malzemeyi söyler, cihazları kullanıcı
            # okutur — otomatik kilit ve "150'nin 12'si" sayacı I2 sahada
            # denendikten sonra yazılacak (KUTU_TASARIM.md 9.2, 10).
            #
            # Buradan tek satır bile yazılmaz: kap kodunu okutup ##SONRAKI##
            # demek "bir cihaz saydım" anlamına gelmemeli. Onun yerine KAP
            # AÇILIR: malzeme kilitlenir ve sayaç başlar, kullanıcı art arda
            # yalnızca seri numaralarını okutur (##KUTUKAPAT## ile kapatır).
            zaten = norm(ot["acik_kutu"] or "") == norm(kutu_ad)
            onceki = _kutu_ac(c, ot, kutu_ad, kutu_t["kod"])
            sayac = kutu_sayaci(c, c.execute("SELECT * FROM oturum WHERE id=?",
                                             (oturum,)).fetchone())
            return {"tip": "kutu_acildi", "kutu": kutu_ad, "kod": kutu_t["kod"],
                    "zaten_acik": zaten,
                    "sayilan": sayac["sayilan"] if sayac else 0,
                    "aciklama": kutu_t.get("aciklama"),
                    "adet": kutu_t.get("adet"), "taze": kutu_t.get("taze"),
                    "sabit_kod": kutu_t["kod"], "onceki_kutu": onceki,
                    # Girilen adet burada uygulanamaz (her cihaz Tiger'da ayrı
                    # satır) ama sessizce yutulmaz — grup_coz'un her yerinde
                    # aynı sözleşme.
                    "adet_yersiz": bekleyen_adet if bekleyen_adet > 1 else None,
                    "raf": raf, "ses": "ok"}
        elif kutu_t.get("izleme") == "seri" and seri_h:
            # Kap + gerçek S/N aynı grupta: sayımı seri numarası yapıyor, ama
            # kap yine AÇILIR — kullanıcı zaten o kabı saymaya başlamış.
            # Sayaç işareti bu okutmadan ÖNCE alınır, yani bu cihaz da sayılır.
            if norm(ot["acik_kutu"] or "") != norm(kutu_ad):
                _kutu_ac(c, ot, kutu_ad, kutu_t["kod"])
            _kutu_kuyrugu_kapat(c, oturum, kutu_ad)
        elif kutu_kaynak and kutu_t.get("izleme") != "seri" and not bekleyen_adet:
            # "Kapta 150 yazıyor" bir sayım sonucu değil, bir varsayımdır:
            # içerik ayda bir değişiyor, sayım yılda bir yapılıyor. Kaydı
            # sorusuz uygulamak, uygulamanın kendi bayat verisini onaylaması
            # olurdu (CLAUDE.md 6'daki Sayım Miktarı tuzağı, bizim tarafımızda).
            #
            # Sabit 1 yazmak da yanlış: kabın içinde 1 tane olduğu bilgisi
            # hiçbir yerden gelmiyor.
            #
            # Soru YALNIZCA sayım kaptan geliyorsa sorulur (`kutu_kaynak`).
            # Kullanıcı grupta başka bir malzeme kodu okuttuysa elindeki o
            # üründür; kabın adedini sormak yanlış soruyu sormak olurdu.
            notu = "kap %s: kaç adet sayıldı?" % kutu_ad
            var = _acik_kutu_kuyrugu(c, oturum, kutu_ad)
            if var:
                c.execute("UPDATE kuyruk SET ts=?, barkodlar=?, raf=?, kod=?, not_=? "
                          "WHERE id=?",
                          (ts, json.dumps(hamlar, ensure_ascii=False), raf,
                           kutu_t["kod"], notu, var["id"]))
                kid = var["id"]
            else:
                kid = c.execute("""INSERT INTO kuyruk(oturum,ts,barkodlar,raf,tur,kod,
                                   not_,adet) VALUES(?,?,?,?,'kutu',?,?,0)""",
                                (oturum, ts, json.dumps(hamlar, ensure_ascii=False),
                                 raf, kutu_t["kod"], notu)).lastrowid
            return {"tip": "kutu_sor", "kuyruk_id": kid, "kutu": kutu_ad,
                    "kod": kutu_t["kod"], "aciklama": kutu_t.get("aciklama"),
                    "izleme": kutu_t.get("izleme"), "adet": kutu_t.get("adet"),
                    "taze": kutu_t.get("taze"), "oneri_adet": (
                        kutu_t.get("adet") if kutu_t.get("taze") else None),
                    "barkodlar": hamlar, "raf": raf, "ses": "kuyruk"}

    kaynak = seri_h or kod_h
    if not kaynak:
        # ÖĞRENİLMİŞ FAZLA: Tiger'da karşılığı olmayan, daha önce adlandırılmış
        # ürün. Kuyruğa DÜŞMEZ, doğrudan fazla yazılır ve adı hazır gelir.
        #
        # "Fazla onaydan geçmeden oluşmaz" kuralını (CLAUDE.md 4.4) delmiyor:
        # o kural malzemesi Tiger'da BULUNAN kayıt için — orada "eşleşmedi"
        # ile "stokta yok" farklı şeyler. Burada malzeme Tiger'da hiç yok ve
        # kullanıcı bu barkod için kararını bir kez zaten verdi, adını da
        # yazdı. İkinci, üçüncü, kırk yedinci kez sormak o kararı tekrarlatmak
        # olurdu — sahada tam olarak bu oldu (S2).
        bilinen = next((r for _, r in coz_list if r["t"] == "fazla_bilinen"), None)
        if bilinen:
            oid = c.execute(
                """INSERT INTO okutma(oturum,ts,ham,seri,miktar,tip,raf,grup,not_,ad,
                   yeni_seri) VALUES(?,?,?,?,?,'fazla',?,?,?,?,'')""",
                (oturum, ts, " + ".join(hamlar), _fazla_seri(hamlar, None),
                 bekleyen_adet or 1, raf, grup, "öğrenilmiş fazla",
                 bilinen["ad"])).lastrowid
            # Bu gruptaki YENİ barkodlar da aynı ada bağlanır ve DS- etiketi
            # deftere işlenir — kutunun üstündeki her barkod bir sonraki sefere
            # tanınsın diye.
            yan = fazla_ogren(c, oid, ts)
            return dict({"tip": "fazla_bilinen", "okutma": [oid], "ad": bilinen["ad"],
                         "barkodlar": hamlar, "raf": raf,
                         "miktar": bekleyen_adet or 1, "ses": "uyari"}, **yan)

        # Girilen adet kuyruk satırına TAŞINIR, burada harcanmaz.
        #
        # Malzeme bilinmiyor, yani seri takipli mi lot mu bilinmiyor; adedin
        # anlamlı olup olmadığına ancak kayıt çözülünce karar verilebilir.
        # Eskiden `bekleyen_adet` grup kapanırken sıfırlanıyor ve buraya hiç
        # yazılmıyordu: kullanıcı "150 tane var" diyor, ürün tanınmıyor,
        # 150 hiçbir yere düşmeden kayboluyordu (saha bildirimi 2026-08-27).
        # Aynı barkod kümesi kuyrukta zaten duruyorsa kayıt YİNE yazılır
        # (iki fiziksel ürün olabilir) ama kullanıcı UYARILIR — `_ayni_kuyruk`.
        onceki = _ayni_kuyruk(c, oturum, hamlar)
        kid = c.execute("INSERT INTO kuyruk(oturum,ts,barkodlar,raf,not_,adet) "
                        "VALUES(?,?,?,?,?,?)",
                        (oturum, ts, json.dumps(hamlar, ensure_ascii=False), raf,
                         "boş etiket okutuldu, malzeme belirtilmedi"
                         if bos_etiket else None, bekleyen_adet)).lastrowid
        # `miktar`, `adet` DEĞİL: yanıttaki `adet` tampondaki BARKOD sayısını
        # söylüyor (satır ~741), buradaki ise kaç ÜRÜN olduğunu.
        return {"tip": "kuyruk", "kuyruk_id": kid, "barkodlar": hamlar, "raf": raf,
                "bos_etiket": bos_etiket, "miktar": bekleyen_adet or None,
                "kuyruk_tekrar": onceki, "ses": "kuyruk"}

    # SAYIM DIŞI KALEM: hiçbir şey yazmadan uyar.
    #
    # `coz()` `haric` alanına bakmıyordu ve kalem normal gibi işleniyordu:
    # ekran yeşil yanıp "eşleşti" sesi veriyor, ama `sayaclar()` hariç satırları
    # saymadığı için sayaç hiç dönmüyordu. Raporda da yoktu — `eksik_kayitlar`
    # hariç satırları atlıyor. Kullanıcı elindeki fiziksel ürünü okutup "tamam"
    # sesini duyuyor, ürün mutabakattan tamamen buharlaşıyordu.
    #
    # Doğrusu kararı kullanıcıya bırakmak: sayması gerekiyorsa Kurulum
    # ekranından o kuralı kapatıp yeniden okutur.
    if kaynak[1].get("haric"):
        # Burada da hiçbir satır yazılmıyor — tampon korunur. Kullanıcı
        # Kurulum'dan kuralı kapatıp ##SONRAKI## diyebilsin, ürünü yeniden
        # okutmak zorunda kalmasın.
        _tamponu_geri_yaz(c, oturum, hamlar, bekleyen_adet, ts)
        return {"tip": "haric", "kod": kaynak[1]["kod"],
                "aciklama": kaynak[1]["aciklama"],
                "sebep": kaynak[1].get("haric_sebep") or "",
                "tampon_duruyor": True,
                "barkodlar": hamlar, "raf": raf, "ses": "uyari"}

    kod = kaynak[1]["kod"]
    aciklama = kaynak[1]["aciklama"]
    # ##ADET-N## seri takipli kalemde anlamsız: her adet ayrı bir cihaz, Tiger'da
    # ayrı bir satır. Sessizce yok saymak yerine söylenir — kullanıcı yanlış
    # barkod okutmuş olabilir ve 25 adedin uçtuğunu bilmeli.
    adet_yersiz = (bekleyen_adet if bekleyen_adet > 1
                   and kaynak[1].get("izleme") == "seri" else None)
    # Kaptan gelen sayım denetim izinde görünmek zorunda: rapordaki satıra
    # bakan kişi "bu 150 adet nereden geldi" diye sorduğunda cevabı kap
    # numarasıdır (KUTU_TASARIM.md 8). Kap TANIMSIZ olsa da yazılır — okutuldu.
    kutu_notu = (" | kutu: %s" % kutu_ad) if kutu_ad else ""

    # bilinmeyen barkodları bu malzemeye öğret
    ogrenilen = []
    for h in bilinmeyen:
        c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)", (norm(h), kod, "", ts))
        ogrenilen.append(h)

    if seri_kaydi:
        r = seri_kaydi[1]
        notu = (r.get("not") or "")
        if ogrenilen:
            notu += " | öğrenildi: " + ",".join(ogrenilen)
        if bos_etiket:
            etiketler.bagla(c, bos_etiket[0], kod, r["id"], oturum, ts, raf)
            notu += " | etiket: " + bos_etiket[0]
        notu += kutu_notu
        # `ham`e grubun TAMAMI yazılır, yalnızca eşleşen seri no değil.
        #
        # Bir grup bir üründür (CLAUDE.md 4.4): kullanıcı o cihazın üstündeki
        # bütün barkodları okutur. Buraya tek değer yazılınca fabrika barkodu
        # kayıttan düşüyordu — ürün eşleşiyor ama hangi barkodun okutulduğu
        # kayboluyordu (saha bildirimi B1). `kuyruk_coz` ve `kuyruk_fazla` zaten
        # böyle yazıyordu; üç dal artık aynı sözleşmede.
        #
        # Tiger'a önerilecek seri numarası: KAYDI EŞLEŞTİREN değer, `ham`'dan
        # yeniden türetilmiş bir şey değil.
        #
        # `yeni_seri` NULL BIRAKILAMAZ. NULL yalnızca "bu sütun eklenmeden önce
        # yazılmış" demektir ve rapor orada eski kurala (`_yeni_seri(ham)`)
        # düşer. `ham` artık malzeme kodunu da taşıdığı için o kural en uzun
        # aday olarak MALZEME KODUNU seçebiliyordu — Tiger'a "bu cihazın seri
        # numarası 900-5G144-2200-000 olsun" deniyordu, ki `kirli_mi(kod, kod)`
        # KİRLİ döner. ACIL_PLAN 3'te kapatılan hatanın aynısı, gerçek veriyle
        # üretildi (2026-08-27).
        #
        # Eşleşen değer kaydın mevcut seri numarasıyla AYNIYSA öneri yoktur
        # (1. adım birebir eşleşme: Tiger zaten doğru). Farklıysa gerçek bir
        # düzeltmedir: 5. adım kirli kaydın içine gömülü gerçek S/N'i bulmuştur
        # ya da 1c bağlanmış DS- etiketini.
        yeni_es = "" if norm(seri_h[0]) == norm(r["seri"] or "") else seri_h[0]
        c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,tip,
                     raf,grup,not_,geri,yeni_seri)
                     VALUES(?,?,?,?,?,1,?,'eslesti',?,?,?,?,?)""",
                  (oturum, ts, " + ".join(hamlar), kod, r["seri"], r["id"], raf,
                   grup, notu,
                   _geri_json(ogrenilen, bos_etiket[0] if bos_etiket else None),
                   yeni_es))
        return {"tip": "eslesti", "kod": kod, "aciklama": aciklama, "seri": r["seri"],
                "ogrenilen": ogrenilen, "etiket": bos_etiket[0] if bos_etiket else None,
                "raf": raf, "not": notu.strip(" |"), "adet_yersiz": adet_yersiz,
                # Grupta hem yeni bir seri hem DAHA ÖNCE OKUTULMUŞ bir barkod
                # varsa tekrar uyarısı yutulmamalı: yukarıdaki `tekrar` dalı
                # `not seri_h` koşuluyla korunuyor, bu satır olmadan kullanıcı
                # aynı cihazı ikinci kez elinde tuttuğunu hiç öğrenmiyordu.
                "tekrar_seri": tekrar[1]["seri"] if tekrar else None,
                "sabit_kod": sabit, "ses": "uyari" if tekrar else "ok"}

    # Malzeme belli ama seri eşleşmedi
    izleme = kaynak[1].get("izleme", "yok")
    if izleme == "seri":
        # Ölçüt `KAPASITE_VAR`, "hiç okutulmamış" DEĞİL (D1 / Y1). Miktarı 2
        # olan kirli bir satırda ilk cihaz slotu doldurduktan sonra ikincisi
        # kapasite dururken `fazla_onay` kuyruğuna düşüyor, satır hem eksik hem
        # onay bekler görünüyordu. miktar=1 satırlarda davranış aynı.
        slot = c.execute("""SELECT * FROM beklenen b WHERE yukleme=? AND ambar=? AND kod=?
                            AND kirli=1 """ + KAPASITE_VAR + " ORDER BY id LIMIT 1",
                         (yukleme, ambar, kod, oturum)).fetchone()
        # Tiger'a yazılacak seri numarası seçimi. Üretici S/N okutulduysa ya da
        # elle yazıldıysa O kazanır; havuz etiketi son çaredir. Cihazın gerçek
        # seri numarası garanti/RMA izidir, uydurma numarayla değiştirilmez.
        #
        # Karar `_sn_karar`'da: UPC elenir (perakende barkodu cihaza özel
        # değildir) ve iki aday kalırsa tahmin edilmez, kullanıcıya sorulur.
        yeni_sn, sn_adaylar = _sn_karar(
            bilinmeyen, bos_etiket[0] if bos_etiket else "")
        if slot:
            # `yeni_sn or kod` DEĞİL.
            #
            # Yalnızca malzeme kodu okutulduğunda (ne üretici S/N, ne DS-
            # etiketi) `yeni_sn` boş kalıyor ve eskiden `ham` alanına MALZEME
            # KODU yazılıyordu. Rapor o alanı "Tiger'a yazılacak gerçek seri
            # no" diye kullanıyor, yani Tiger'a "bu cihazın seri numarasını
            # 04RW5H yap" deniyordu — `kirli_mi("04RW5H","04RW5H")` KİRLİ
            # döner (kod+sayaç deseni). Uygulamanın tek işi kirli kaydı
            # temizlemekken Tiger'a yeni bir kirli kayıt yazdırıyordu; aynı
            # malzemenin birden çok slotu bu yoldan dolarsa aynı seri
            # numarasından birden çok tane.
            #
            # `yeni_seri` boş bırakılıyor: `reports` boş öneriyi atlıyor, yani
            # Tiger Düzeltme satırı ÜRETİLMEZ. Sayım yine işlenir —
            # saymak birincil iş, Tiger'ın seri numarasını düzeltmek ikincil —
            # ama kullanıcı `sn_yok` ile uyarılır ve ne yapacağını öğrenir.
            if bos_etiket:
                etiketler.bagla(c, bos_etiket[0], kod, slot["id"], oturum, ts, raf)
            # `ham` = grubun tamamı (denetim izi), `yeni_seri` = Tiger'a
            # önerilecek numara. İkisi ayrı: `ham`e malzeme kodu da girdiği
            # için tek alanda tutulsalardı rapor kodu seri no sanabilirdi.
            oid = c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,
                         beklenen_id,tip,raf,grup,not_,geri,yeni_seri,sn_adaylar)
                         VALUES(?,?,?,?,?,1,?,'eslesti',?,?,?,?,?,?)""",
                      (oturum, ts, " + ".join(hamlar), kod, slot["seri"],
                       slot["id"], raf, grup,
                       ("slot dolduruldu" if yeni_sn
                        else "sayıldı — seri numarası verilmedi, Tiger düzeltmesi yok")
                       + (" | seri no seçilmedi, tahmin edildi" if sn_adaylar else "")
                       + (" | etiket: " + bos_etiket[0] if bos_etiket else "")
                       + (" | sabit kod: " + sabit if sabit else "") + kutu_notu,
                       _geri_json(ogrenilen,
                                  bos_etiket[0] if bos_etiket else None),
                       yeni_sn,
                       json.dumps(sn_adaylar, ensure_ascii=False)
                       if sn_adaylar else None)).lastrowid
            return {"tip": "slot", "kod": kod, "aciklama": aciklama, "eski": slot["seri"],
                    "yeni": yeni_sn, "sn_yok": not yeni_sn, "kutu": kutu_kaynak,
                    "etiket": bos_etiket[0] if bos_etiket else None,
                    # Sayım işlendi; belirsiz olan yalnızca Tiger'a hangi değerin
                    # önerileceği. Bu yüzden akış DURMAZ — panel açılır, cevap
                    # sonra da verilebilir (`POST /okutma/{id}/seri-sec`).
                    #
                    # Alan adı `okutma` DEĞİL: o ad `fazla_elle` / `yedek`
                    # dallarında okutma id'si LİSTESİ taşıyor (arayüz hepsine
                    # aynı adı yazıyor). Tek satır için ayrı ad.
                    "sn_okutma": oid, "sn_secim": sn_adaylar,
                    "raf": raf, "adet_yersiz": adet_yersiz, "sabit_kod": sabit,
                    "ses": "uyari" if (not yeni_sn or sn_adaylar) else "ok"}
        # Karşılığı bulunamadı. Burada FAZLA YAZILMAZ — onay kuyruğuna düşer.
        #
        # Eski davranış sessizce fazla yazıyordu ve sahada yanlış çıktı
        # (DEMO_FEEDBACK.md 5): bu dala düşmek "stokta yok" demek değil,
        # "Tiger'daki seri numaralarıyla eşleşmedi" demektir. Malzemenin
        # sayılmamış TEMİZ satırları dururken de buraya düşülüyor — kullanıcı
        # o satırlardan birini seçebilmeli. Etiket bağlama da çözüm anına
        # ertelenir; onay reddedilirse etiket boş yere tükenmesin.
        kid = c.execute("""INSERT INTO kuyruk(oturum,ts,barkodlar,raf,tur,kod,not_,adet)
                           VALUES(?,?,?,?,'fazla_onay',?,?,?)""",
                        (oturum, ts, json.dumps(hamlar, ensure_ascii=False), raf,
                         kod, "seri takipli, karşılığı bulunamadı" + kutu_notu,
                         bekleyen_adet)).lastrowid
        return {"tip": "onay", "kuyruk_id": kid, "kod": kod, "aciklama": aciklama,
                "yeni": yeni_sn, "sn_secim": sn_adaylar, "barkodlar": hamlar,
                "etiket": bos_etiket[0] if bos_etiket else None,
                "raf": raf, "adet_yersiz": adet_yersiz, "sabit_kod": sabit,
                "ses": "uyari"}

    # Lot / izlemesiz: Tiger'da adet başına seri saklanmıyor, boş etiketi
    # bağlayacak kayıt yok. Sayımı yine de işleriz — malzeme doğru tanındı —
    # ama etiket bağlanmaz ve kullanıcı uyarılır, yoksa etiket havuzu sessizce
    # tükenir.
    adet = bekleyen_adet or 1
    etiket_notu = ((" | etiket bağlanmadı: izleme=%s" % izleme) if bos_etiket else "")         + (" | sabit kod: " + sabit if sabit else "") + kutu_notu
    # Kabın SON BİLİNEN adedi bu sayımla tazelenir — ama ancak sayım kaptan
    # geldiyse. Kapla ilgisi olmayan bir okutma kabın kaydını değiştirmemeli.
    kutu_geri = ({"kod": norm(kutu_kaynak), "onceki": kutum.anlik(c, kutu_kaynak)}
                 if kutu_kaynak else None)
    # Lot numarası okutulduysa hedef satır bellidir; yoksa `_adet_islemi`
    # miktarı açık satırlara dağıtır.
    seri_b = (c.execute("SELECT * FROM beklenen WHERE id=?",
                        (seri_h[1]["id"],)).fetchone() if seri_h else None)
    sonuc = _adet_islemi(c, ot, kod, adet, hamlar, raf, grup, ts, seri_b=seri_b,
                         ek_not=etiket_notu,
                         geri=_geri_json(ogrenilen, kutu=kutu_geri),
                         aciklama=aciklama, izleme=izleme)
    if kutu_kaynak:
        kutum.tanimla(c, kutu_kaynak, kod, adet, izleme, raf=raf, oturum=oturum, ts=ts)
        # Kap sayıldı: "kaç adet?" sorusu cevaplanmış oldu. Açık bırakılırsa
        # oturum kapanmadan aynı soru bir daha sorulurdu.
        sonuc["kuyruk_kapandi"] = _kutu_kuyrugu_kapat(c, oturum, kutu_kaynak)
        sonuc["kutu"] = kutu_kaynak
    sonuc.update({"ogrenilen": ogrenilen, "sabit_kod": sabit,
                  "etiket_yersiz": bos_etiket[0] if bos_etiket else None,
                  "ses": "uyari" if bos_etiket else "ok"})
    return sonuc


# ---------------------------------------------------------------- okutma girişi
def bekleyen_kuyruk(c, oturum, raf=None, bekletilen_haric=False):
    """Çözülmemiş kuyruk kayıtları; raf verilirse sadece o rafa aitler.

    bekletilen_haric: telefondan "sonra çözerim" diye işaretlenmiş kayıtları
    dışarıda bırakır. Raf kapısının amacı ürün eldeyken karar verdirmek;
    fotoğrafını çekip bilerek erteleyen kullanıcı o kararı zaten vermiştir,
    her raf değişiminde aynı uyarıyı yemesin. Sayımı bitirme kapısı ise
    hepsini sayar — oturum kapanmadan kuyruk boşalmalı.
    """
    sql = "SELECT * FROM kuyruk WHERE oturum=? AND cozuldu=0"
    par = [oturum]
    if raf is not None:
        sql += " AND COALESCE(raf,'')=?"
        par.append(raf or "")
    if bekletilen_haric:
        sql += " AND COALESCE(beklet,0)=0"
    return [{"id": r["id"], "barkodlar": json.loads(r["barkodlar"]), "raf": r["raf"],
             "ts": (r["ts"] or "")[:19].replace("T", " "), "not_": r["not_"],
             "beklet": bool(r["beklet"]), "tur": r["tur"] or "bilinmiyor",
             "kod": r["kod"], "ad": r["ad"]}
            for r in c.execute(sql + " ORDER BY id", par)]


def okut(c, ot, ham, zorla=False):
    """Bir okutmayı işler: komut barkodu mu, tampona mı gider.

    depo_sayim.py:619-674 yonlendir() mantığı. İki fark:
      * raf istemciden gelmiyor, oturum.aktif_raf alanında tutuluyor
      * raf değiştirmek ve oturumu bitirmek, o rafta çözülmemiş kuyruk varsa
        engellenir (zorla=True ile bilinçli olarak aşılır)
    """
    oturum, yukleme, ambar = ot["id"], ot["yukleme"], ot["ambar"]
    ham = (ham or "").strip()
    ts = _ts()
    komut, deger = komut_coz(ham)
    raf_adi = deger if komut == "raf" else None

    # ##BITIR## çift okutma damgası: araya BAŞKA bir şey girdiyse iptal.
    # Yoksa sabahki kazara okutma öğleden sonraki ##BITIR##'i onaylamış olurdu.
    if komut != "bitir" and ot["bitir_istegi"]:
        c.execute("UPDATE oturum SET bitir_istegi=NULL WHERE id=?", (oturum,))
        ot = c.execute("SELECT * FROM oturum WHERE id=?", (oturum,)).fetchone()

    if komut == "adet":
        # Lot / izlemesiz kalemde "bu üründen N tane var" (CLAUDE.md 2.4).
        # BİRİKİR: ##ADET-25## iki kez okutulursa 50 olur — komut kartında
        # sabit adetler basılı olduğu için ara değere ancak böyle ulaşılır.
        # ##ADET-0## sıfırlar; telefondaki tuş takımı da bu yoldan geçer.
        yeni = 0 if deger == 0 else (ot["bekleyen_adet"] or 0) + deger
        if yeni > ADET_TAVAN:
            return {"tip": "adet_tavan", "miktar": ot["bekleyen_adet"] or 0,
                    "tavan": ADET_TAVAN, "ses": "uyari"}
        c.execute("UPDATE oturum SET bekleyen_adet=? WHERE id=?", (yeni, oturum))
        # `miktar`, `adet` DEĞİL: tampon yanıtındaki "adet" kaç BARKOD
        # okutulduğunu söylüyor, buradaki ise kaç ÜRÜN sayıldığını.
        return {"tip": "adet_bekliyor", "miktar": yeni, "ses": "tik"}

    if komut == "sonraki":
        return grup_coz(c, ot)

    if komut == "kilit":
        # Kartta basılı hâli PARAMETRESİZ: malzeme kodlarının 57'si boşluk ya da
        # Türkçe karakter taşıyor ve Code128'e girmiyor (CLAUDE.md 2.1). Kod
        # okutulur, kilit tampondan alınır. Arayüz açık kod gönderdiğinde
        # (##KILIT-<kod>##) o kullanılır.
        if deger:
            aday, kaynak = deger, coz(c, deger, yukleme, ambar, oturum)
        else:
            aday, kaynak, tamponda_var = None, None, False
            for r in c.execute("SELECT ham FROM tampon WHERE oturum=? ORDER BY id",
                               (oturum,)):
                tamponda_var = True
                t = coz(c, r["ham"], yukleme, ambar, oturum)
                # Tanımlı kap da bir malzeme kodudur (KUTU_TASARIM.md 5):
                # "kabı okut, kilitle, seri numaralarını okut" seri takipli
                # kaptaki asıl akış. Kart PARAMETRESİZ basıldığı için kilit
                # tampondan okunuyor; kap burada tanınmazsa kartla kilit
                # kurulamaz ve kullanıcı `kilit_yok` uyarısı alırdı —
                # arayüzdeki düğme (##KILIT-<kod>##) çalışırken kart çalışmaz.
                if t["t"] in ("kod", "ogrenilmis", "kutu"):
                    aday, kaynak = r["ham"], t
                    break
            # Son çare YALNIZCA tampon BOŞKEN: "az önce saydığım ürüne kilitle".
            #
            # Tamponda bir şey varsa kullanıcı ELİNDEKİ ürünü kilitlemek
            # istiyor demektir. O ürün tanınmadıysa doğru cevap `kilit_yok`;
            # son çareye düşmek BİR ÖNCEKİ ürünün koduna kilitler ve bunu
            # yeşil "ok" sesiyle yapardı.
            #
            # Sahada üretildi (2026-08-28, S2/S1): Tiger'da olmayan bir ürünün
            # DM- etiketi okutulup ##KILIT## denince, bir önceki ürün olan
            # `0C5RNH` (SFP, lot takipli) kilitlendi. Ardından okutulan her
            # seri numarası o malzemeye gider ve sayım sessizce bozulur —
            # kullanıcı kilidin doğru kurulduğunu sanır.
            if not aday and not tamponda_var:
                x = c.execute("SELECT kod FROM okutma WHERE oturum=? AND kod<>'' "
                              "AND kod IS NOT NULL ORDER BY id DESC LIMIT 1",
                              (oturum,)).fetchone()
                if x:
                    aday, kaynak = x["kod"], coz(c, x["kod"], yukleme, ambar, oturum)
        if not kaynak or not kaynak.get("kod"):
            # Sessizce kilitlememek şart: kullanıcı kilitlendiğini sanıp
            # onlarca seri numarası okutur ve hepsi kuyruğa düşerdi.
            #
            # Tampon KORUNUR: kullanıcı ürünü yeniden okutmak zorunda kalmasın,
            # ##FAZLA## / ##ATLA## ile devam edebilsin.
            bekleyen = [r["ham"] for r in c.execute(
                "SELECT ham FROM tampon WHERE oturum=? ORDER BY id", (oturum,))]
            return {"tip": "kilit_yok", "barkodlar": bekleyen, "ses": "uyari"}
        kod = kaynak["kod"]
        c.execute("UPDATE oturum SET sabit_kod=? WHERE id=?", (kod, oturum))
        # Kilitlenen kod tampondan düşer: kilit onu zaten temsil ediyor, grupta
        # ikinci kez durursa her ürüne malzeme kodu okutulmuş gibi görünürdü.
        if aday is not None:
            c.execute("DELETE FROM tampon WHERE oturum=? AND ham=?", (oturum, aday))
        return {"tip": "kilit", "kod": kod, "aciklama": kaynak.get("aciklama"),
                "izleme": kaynak.get("izleme"), "ses": "ok"}

    if komut == "kilitac":
        # Açık kap varsa kilit ONUN kilidi: yalnızca kilidi açmak, ekranda
        # "kap açık" yazarken sayacın donmasına yol açardı (sonraki okutmalar
        # başka malzemeye gider, sayaç saymaz). Kabı da kapatıyoruz.
        kapanan = _kutu_kapat(c, ot) if ot["acik_kutu"] else None
        c.execute("UPDATE oturum SET sabit_kod=NULL WHERE id=?", (oturum,))
        return {"tip": "kilitac", "kutu_kapandi": kapanan, "ses": "tik"}

    if komut == "kutukapat":
        # Kabı kapatmak: kilidi bırak, sayacı özetle. Eksik kaldıysa söyle —
        # engelleme, örtme. Kap zaten kapalıysa sessiz kalmıyoruz: kullanıcı
        # kapattığını sanıp başka bir ürünü kilitli malzemeye okutabilir.
        if not ot["acik_kutu"]:
            return {"tip": "kutu_yok", "ses": "uyari"}
        d = _kutu_kapat(c, ot, ts)
        if not d:
            # İşaret ve kilit temizlendi ama kabın kaydı okunamadı. Sessiz
            # kalmıyoruz: kullanıcı kaç adet saydığını bekliyordu.
            return {"tip": "kutu_kapandi", "kutu": ot["acik_kutu"], "kod": "",
                    "aciklama": "kap kaydı bulunamadı — içeriği boşaltılmış olabilir",
                    "sayilan": 0, "beklenen": None, "eksik": 0,
                    "kayit_yok": True, "ses": "uyari"}
        return dict(d, tip="kutu_kapandi",
                    ses="uyari" if d["eksik"] else "ok")

    if komut in ("yedek", "yedekkapat"):
        acik = 0 if komut == "yedekkapat" else (0 if ot["yedek_parca"] else 1)
        c.execute("UPDATE oturum SET yedek_parca=? WHERE id=?", (acik, oturum))
        return {"tip": "yedek_mod", "acik": bool(acik),
                "ses": "uyari" if acik else "tik"}

    if komut == "iptal":
        c.execute("DELETE FROM tampon WHERE oturum=?", (oturum,))
        # Bekleyen adet de grubun parçası: "o ürüne baştan başla" derken
        # 25 adet ayakta kalırsa sonraki ürüne sızar.
        c.execute("UPDATE oturum SET bekleyen_adet=0 WHERE id=?", (oturum,))
        return {"tip": "iptal", "ses": "uyari"}

    if komut == "gerial":
        return gerial(c, ot)

    if komut in ("fazla", "atla") and ot["yedek_parca"]:
        # Yedek parça modu açıkken bu iki komut ANLAMSIZ: "fazla mı eksik mi"
        # sorusu yok (kayıt zaten aranmıyor) ve kuyruğa atılacak bir belirsizlik
        # yok. Sessizce `fazla` / `kuyruk` yazmak modu delerdi — ekranda kırmızı
        # "YEDEK PARÇA MODU" bandı dururken kayıt Tiger sayım fazlası fişine
        # girerdi. Tampon KORUNUR, kullanıcı modu kapatıp tekrar basabilir.
        return {"tip": "yedek_modda_gecersiz", "komut": komut, "ses": "uyari"}

    if komut == "fazla":
        hs = [r["ham"] for r in c.execute(
            "SELECT ham FROM tampon WHERE oturum=? ORDER BY id", (oturum,))]
        # Boş tampon kontrolü.
        # Barkodu olmayan bir "fazla" kaydı oluşuyor, ne olduğu sorulamıyor
        # (sorulacak bir şey yok) ama `adsiz_fazlalar` onu adsız sayıp bitirme
        # kapısını kilitliyordu. Yanlışlıkla F3'e basmak yetiyordu.
        if not hs:
            return {"tip": "bos", "ses": "uyari"}
        c.execute("DELETE FROM tampon WHERE oturum=?", (oturum,))
        # Adet burada da grubun parçası: girilmişse fazla kaydının miktarı
        # olur ve TÜKENİR. Eskiden ikisi de olmuyordu — miktar sabit 1
        # yazılıyor, girilen 150 ise ayakta kalıp SONRAKİ ürüne sızıyordu.
        adet = int(ot["bekleyen_adet"] or 0)
        if adet:
            c.execute("UPDATE oturum SET bekleyen_adet=0 WHERE id=?", (oturum,))
        grup = _yeni_grup(c, oturum)
        # TEK GRUP = TEK ÜRÜN (CLAUDE.md 4.4). Tampondaki barkodların hepsi
        # aynı ürüne aittir; barkod başına satır yazmak o ürünü rapora N ayrı
        # fazla olarak koyardı — kuyruk_fazla ile aynı hata, aynı düzeltme.
        #
        # Oluşan satırın id'si geri veriliyor: arayüz hemen "bu ne?" diye
        # sorup ad yazdırıyor. Kodu olmayan isimsiz fazla kaydı raporda
        # kullanılamaz hâle geliyordu (DEMO_FEEDBACK.md 3).
        idler = [c.execute(
            "INSERT INTO okutma(oturum,ts,ham,seri,miktar,tip,raf,grup,not_,yeni_seri) "
            "VALUES(?,?,?,?,?,'fazla',?,?,'elle işaretlendi','')",
            (oturum, ts, " + ".join(hs), _fazla_seri(hs, None), adet or 1,
             ot["aktif_raf"], grup)).lastrowid]
        # Ad HENÜZ yok (arayüz hemen sonra soruyor), o yüzden burada yalnızca
        # etiket bağlanır ve kod biliniyorsa öğrenilir. Ad yazılınca
        # `okutma_guncelle` aynı yardımcıyı bir daha çağırır.
        yan = fazla_ogren(c, idler[0], ts)
        return dict({"tip": "fazla_elle", "barkodlar": hs, "okutma": idler,
                     "miktar": adet or 1, "ses": "uyari"}, **yan)

    if komut == "atla":
        hs = [r["ham"] for r in c.execute(
            "SELECT ham FROM tampon WHERE oturum=? ORDER BY id", (oturum,))]
        # BOŞ TAMPONDA HİÇBİR ŞEY TÜKETİLMEZ — `##SONRAKI##` ve `##FAZLA##` ile
        # aynı sözleşme. Eskiden bu dal kuyruğa hiçbir şey yazmadan `adet`i
        # sıfırlıyor ve ekrana "kuyruğa atıldı" diyordu: kullanıcının girdiği
        # 150 buharlaşıyor, `kuyruk_id` de None dönüyordu
        # (DENETIM_20260904.md Y4). 2026-08-27'de kapatılan "adet sessizce
        # kayboluyor" hatasının kalan tek dalı.
        if not hs:
            return {"tip": "bos", "ses": "uyari"}
        c.execute("DELETE FROM tampon WHERE oturum=?", (oturum,))
        adet = int(ot["bekleyen_adet"] or 0)
        if adet:
            c.execute("UPDATE oturum SET bekleyen_adet=0 WHERE id=?", (oturum,))
        onceki = _ayni_kuyruk(c, oturum, hs)
        kid = c.execute("INSERT INTO kuyruk(oturum,ts,barkodlar,raf,adet) "
                        "VALUES(?,?,?,?,?)",
                        (oturum, ts, json.dumps(hs, ensure_ascii=False),
                         ot["aktif_raf"], adet)).lastrowid
        return {"tip": "kuyruk", "kuyruk_id": kid, "barkodlar": hs,
                "miktar": adet or None, "kuyruk_tekrar": onceki, "ses": "kuyruk"}

    if komut == "bitir":
        # TAMPON ÖNCE KAPANIR, KAPILAR SONRA BAKAR.
        #
        # Sıra tersken kapılar boşa çalışıyordu: grup_coz tampondaki tanınmayan
        # grubu YENİ bir kuyruk kaydına yazıyor, hemen ardından oturum
        # kapanıyordu. Kullanıcı "bitti" sesini duyup depodan çıkıyor, elindeki
        # ürün kayıt dışı kalıyordu. Kapının varlık sebebi tam olarak buydu.
        grup_coz(c, ot)
        bekleyen = bekleyen_kuyruk(c, oturum)
        if bekleyen and not zorla:
            return {"tip": "bitir_engel", "kuyruk": bekleyen, "ses": "uyari"}
        # Adsız fazla raporda kullanılamaz: geriye seri numarası ve raf kalır,
        # ürünün ne olduğu bulunamaz.
        adsiz = adsiz_fazlalar(c, oturum)
        if adsiz and not zorla:
            return {"tip": "ad_engel", "adsiz": adsiz, "ses": "uyari"}
        # Fotoğrafsız fazla, sayımdan sonra kimsenin doğrulayamayacağı bir
        # satırdır: ürün rafa geri konur, geriye yalnızca kayıt kalır.
        fotosuz = fotosuz_fazlalar(c, oturum)
        if fotosuz and not zorla:
            return {"tip": "foto_engel", "fotosuz": fotosuz, "ses": "uyari"}
        # SON KAPI: ÇİFT OKUTMA + YUMUŞAK UYARILAR — tek yerde.
        #
        # İkisi ayrı kapı olsaydı ikinci ##BITIR## de uyarıya takılır, kullanıcı
        # hiç kapatamazdı. Aynı damga ikisini birden karşılıyor: ilk okutma ne
        # olduğunu SÖYLER, ikincisi kapatır.
        #
        # Çift okutma şart, çünkü ##BITIR## komut kartında basılı ve kazara
        # okutulan tek bir barkod günlerce süren bir sayımı kapatabiliyordu.
        # Damgayı araya giren herhangi bir okutma siler (yukarıda).
        #
        # Uyarılar ENGEL değil, çünkü sayımın kendisi doğru:
        #   * eksik adetli lot — 77 adetlik lotu bir kez okutmak onu bitirmez;
        #     depodan çıkmadan bir kez daha söylenmeli, geri dönmek pahalı
        #   * seçilmemiş seri no — kayıt sayıldı, yalnızca Tiger'a önerilen
        #     değer bir tahmin (rapor da dipnotla söylüyor)
        #
        # F10 ve `POST /bitir` kendi onaylarına sahip; onlar `zorla` ile geçer.
        if not zorla and not _bitir_onayli(ot):
            uyarilar = {}
            eksik_lot = eksik_lotlar(c, ot)
            if eksik_lot:
                uyarilar["eksik_lot"] = eksik_lot
            secilmemis = sn_secilmemisler(c, oturum)
            if secilmemis:
                uyarilar["sn_secilmemis"] = secilmemis
            c.execute("UPDATE oturum SET bitir_istegi=? WHERE id=?", (ts, oturum))
            return dict(uyarilar, saniye=BITIR_ONAY_SN, ses="uyari",
                        tip="bitir_uyari" if uyarilar else "bitir_onay")
        # Kapatma tek yerden: `oturumlar.bitir` açık kabı da kapatıyor.
        from . import oturumlar
        oturumlar.bitir(c, oturum)
        return {"tip": "bitti", "ses": "bitti"}

    if komut == "raf":
        eski = ot["aktif_raf"]
        if raf_adi != eski:
            # Raftan ayrılmadan önce o rafın kuyruğu çözülmeli: ürün hâlâ
            # önündeyken çözmek, gün sonunda 40 kaydı hatırlamaya çalışmaktan
            # kıyaslanamayacak kadar kolay.
            bekleyen = bekleyen_kuyruk(c, oturum, eski, bekletilen_haric=True)
            if bekleyen and not zorla:
                return {"tip": "raf_engel", "eski_raf": eski, "yeni_raf": raf_adi,
                        "kuyruk": bekleyen, "ses": "uyari"}
        c.execute("UPDATE oturum SET aktif_raf=? WHERE id=?", (raf_adi, oturum))
        return {"tip": "raf", "raf": raf_adi, "ses": "ok"}

    if not ham:
        return {"tip": "bos", "ses": "uyari"}

    c.execute("INSERT INTO tampon(oturum,ts,ham) VALUES(?,?,?)", (oturum, ts, ham))
    n = c.execute("SELECT COUNT(*) n FROM tampon WHERE oturum=?", (oturum,)).fetchone()["n"]
    r = coz(c, ham, yukleme, ambar, oturum)
    return {"tip": "tampon", "adet": n, "ham": ham, "coz": r["t"], "kod": r.get("kod"),
            "aciklama": r.get("aciklama"), "not": r.get("not"), "ses": "tik"}


BITIR_ONAY_SN = 60


def _bitir_onayli(ot):
    """İlk ##BITIR## damgası hâlâ taze mi? (komut kartı için çift okutma)"""
    ham = ot["bitir_istegi"]
    if not ham:
        return False
    try:
        t = datetime.datetime.fromisoformat(ham)
    except (TypeError, ValueError):
        return False
    return (datetime.datetime.now() - t).total_seconds() <= BITIR_ONAY_SN


def sn_secilmemisler(c, oturum):
    """Tiger'a önerilen seri numarası TAHMİN olan satırlar.

    `okutma.sn_adaylar` dolu = üründe birden çok tanınmayan alfanümerik barkod
    vardı ve hangisinin cihaza özel olduğu sorulmadı. Sayım doğru; belirsiz
    olan yalnızca Tiger Düzeltme sekmesine hangi değerin yazılacağı.
    """
    import json as _json
    cikti = []
    for r in c.execute("""SELECT o.id, o.kod, o.seri, o.yeni_seri, o.sn_adaylar, o.raf,
                                 b.aciklama
                          FROM okutma o LEFT JOIN beklenen b ON b.id=o.beklenen_id
                          WHERE o.oturum=? AND COALESCE(o.sn_adaylar,'')<>''
                          ORDER BY o.id""", (oturum,)):
        try:
            adaylar = _json.loads(r["sn_adaylar"])
        except (TypeError, ValueError):
            continue
        cikti.append({"id": r["id"], "kod": r["kod"], "seri": r["seri"],
                      "aciklama": r["aciklama"], "raf": r["raf"],
                      "secili": r["yeni_seri"], "adaylar": adaylar})
    return cikti


def gerial(c, ot, kapsam="okutma"):
    """Son okutmayı (önce tampon, sonra kayıtlı okutma) ya da son grubu geri alır."""
    oturum = ot["id"]
    if kapsam == "grup":
        g = c.execute("SELECT MAX(grup) g FROM okutma WHERE oturum=?",
                      (oturum,)).fetchone()["g"]
        if g:
            satirlar = c.execute(
                "SELECT * FROM okutma WHERE oturum=? AND grup=? ORDER BY id",
                (oturum, g)).fetchall()
            hs = [r["ham"] for r in satirlar]
            temiz = {}
            for r in satirlar:
                temiz.update(_yan_etkileri_geri_al(c, r))
            c.execute("DELETE FROM okutma WHERE oturum=? AND grup=?", (oturum, g))
            return {"tip": "gerial", "kapsam": "grup", "grup": g, "barkodlar": hs,
                    "unutulan": temiz.get("ogrenilen") or [],
                    "etiket_cozuldu": temiz.get("etiket"), "ses": "uyari"}
        return {"tip": "bos", "ses": "uyari"}

    l = c.execute("SELECT id,ham FROM tampon WHERE oturum=? ORDER BY id DESC LIMIT 1",
                  (oturum,)).fetchone()
    if l:
        c.execute("DELETE FROM tampon WHERE id=?", (l["id"],))
        return {"tip": "gerial", "kapsam": "tampon", "ham": l["ham"], "ses": "uyari"}
    x = c.execute("SELECT * FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                  (oturum,)).fetchone()
    if x:
        # Okutma satırını silmek yetmez: aynı işlemde `eslesme`'ye yazılan
        # öğrenme ve `etiket` bağlaması da geri alınmalı. Yoksa yanlış ürüne
        # okutulup Ctrl+Z ile geri alınan bir barkod kalıcı olarak o malzemeye
        # bağlı kalıyor ve Barkod Tablosu sekmesinden Tiger'a yazılmak üzere
        # listeleniyordu (ACIL_PLAN.md A5).
        #
        # SON SATIR DEĞİL SON GRUP siliniyor — `okutma_sil` bunu zaten böyle
        # yapıyordu (bir grup bir üründür, CLAUDE.md 4.4). `adet` dalı tek grubu
        # birden çok satıra yazabiliyor (`_adet_dagit`): ##ADET-5## çok lotlu bir
        # malzemede 5 satır açıyor ve satır bazlı geri alma bunun 4'ünü sayılmış
        # bırakıyordu. Kullanıcı geri aldığını sanıyor, 4 adet sayımda kalıyordu.
        # Üstelik `geri` (öğrenme/etiket) yalnızca İLK satırda durduğu için yan
        # etkiler de temizlenmiyordu.
        satirlar = (c.execute("SELECT * FROM okutma WHERE oturum=? AND grup=? "
                              "ORDER BY id", (oturum, x["grup"])).fetchall()
                    if x["grup"] is not None else [x])
        temiz = {}
        for r in satirlar:
            temiz.update(_yan_etkileri_geri_al(c, r))
        c.execute("DELETE FROM okutma WHERE id IN (%s)"
                  % ",".join("?" * len(satirlar)), [r["id"] for r in satirlar])
        return {"tip": "gerial", "kapsam": "okutma", "ham": x["ham"],
                "silinen": len(satirlar),
                "barkodlar": [r["ham"] for r in satirlar],
                "unutulan": temiz.get("ogrenilen") or [],
                "kuyruk_acildi": temiz.get("kuyruk"),
                "etiket_cozuldu": temiz.get("etiket"), "ses": "uyari"}
    return {"tip": "bos", "ses": "uyari"}


def okutma_sil(c, ot, okutma_id, kapsam="grup", kuyruga_geri=False):
    """Akış listesinden tek bir okutmayı (varsayılan: tüm grubunu) siler.

    `gerial`den farkı: o yalnızca SONUNCUYU alır, bu herhangi bir satırı.
    Sahadaki ihtiyaç bu — yanlış okutma bazen birkaç ürün sonra fark ediliyor.

    Varsayılan kapsam GRUP, çünkü bir grup bir üründür (CLAUDE.md 4.4) ve
    `adet` dalı tek grubu birden çok satıra yazabilir (`_adet_dagit`). O
    satırlarda `geri` yalnızca İLKİNDE durur; satır bazlı silmek öğrenmeyi
    ortada bırakır ya da miktarın bir kısmını geride bırakırdı.

    Yan etkiler `##GERIAL##` ile aynı yoldan geri alınır
    (`_yan_etkileri_geri_al`): öğrenilen barkod unutulur, etiket bağlaması
    çözülür. Ayrı bir temizleme kodu YOKTUR.

    TEK FARK KUYRUKTA. `kuyruga_geri` varsayılan olarak FALSE: Sil tuşu
    "bu satır hiç olmasın" demektir, "kararı geri al" değil. True'yken kayıt
    siliniyor ama doğduğu kuyruk satırı yeniden açılıyor ve ürün "Tiger'da
    kaydı yok" kuyruğunda tekrar beliriyordu — kullanıcı Sil tuşunun
    çalışmadığını sanıyordu (saha bildirimi 2026-08-28, S5). Kayıttan
    kurtulmanın hiçbir yolu yoktu: oturum, kuyruk boşalmadan kapanmıyor.

    Kararı gerçekten geri almak isteyen (yanlış çözdüm, yeniden çözeyim)
    `kuyruga_geri=True` gönderir; ##GERIAL## zaten varsayılan True ile çağırır.
    """
    x = c.execute("SELECT * FROM okutma WHERE id=? AND oturum=?",
                  (okutma_id, ot["id"])).fetchone()
    if not x:
        return {"hata": "okutma kaydı yok"}

    # grup NULL olabilir: `grup` sütunu sonradan eklendi (db.EK_SUTUNLAR),
    # eski satırlarda boş. O zaman satır bazına düşülür.
    if kapsam == "grup" and x["grup"] is not None:
        satirlar = c.execute(
            "SELECT * FROM okutma WHERE oturum=? AND grup=? ORDER BY id",
            (ot["id"], x["grup"])).fetchall()
    else:
        satirlar = [x]

    temiz = {}
    for r in satirlar:
        temiz.update(_yan_etkileri_geri_al(c, r, kuyruga_geri=kuyruga_geri))
    c.execute("DELETE FROM okutma WHERE id IN (%s)"
              % ",".join("?" * len(satirlar)), [r["id"] for r in satirlar])
    return {"tip": "silindi", "silinen": len(satirlar),
            "barkodlar": [r["ham"] for r in satirlar],
            "unutulan": (temiz.get("ogrenilen") or []) + (temiz.get("fazla_ad") or []),
            "etiket_cozuldu": temiz.get("etiket"),
            # Kuyruk kaydı ne oldu: yeniden açıldı mı, kapalı mı kaldı. Arayüz
            # bunu söylemek zorunda — "sildim" ile "kuyruğa geri gönderdim"
            # iki ayrı sonuçtur.
            "kuyruk_acildi": temiz.get("kuyruk") if kuyruga_geri else None,
            "kuyruk_kapali": temiz.get("kuyruk") if not kuyruga_geri else None,
            "ses": "uyari"}


# ---------------------------------------------------------------- durum / sayaçlar
# Bir beklenen satırı için "kaç adet sayıldı" — sayaç, eksik-lot ve aday arama
# sorguları aynı ifadeyi paylaşsın diye tek yerde. `BEKLENEN_ADET` ve
# `KAPASITE_VAR` dosyanın başında (bkz. oradaki not).
# Sayılan adet: okutulan miktar, beklenen adedi geçemez (fazlalık `reports`
# tarafında "adet fazlası" olarak ayrıca raporlanır). Seri ve lot için TEK
# ifade — ayrıştıkları anda ekranla rapor iki ayrı gerçek söylemeye başlıyor.
SAYILAN_ADET = """MIN(COALESCE((SELECT SUM(o.miktar) FROM okutma o
                                WHERE o.oturum=? AND o.beklenen_id=b.id), 0),
                      """ + BEKLENEN_ADET + ")"


def eksik_lotlar(c, ot):
    """YARIM KALMIŞ satırlar — bitirme uyarısı: dokunulmuş ama tamamlanmamış.

    77 adetlik bir lot bir kez okutulunca eskiden "okutulmuş" sayılıyor ve
    ekran "KALAN 0" diyordu; eksik 202 adet ancak Excel açılınca görülüyordu
    (gerçek veriyle üretildi, 2026-08-27).

    ÇOK ADETLİ SERİ SATIRLARI DA BURADA. "Seri satırında miktar hep 1"
    varsayımı gerçek veride yanlış: örnek Tiger çıktısında miktarı 2 ve 4 olan
    32 seri satırı var. O satırlar da yarım kalabilir ve kullanıcı depodan
    çıkmadan önce bunu duymalı. Ölçüt tek: `sayılan < beklenen_adet`.

    Hiç dokunulmamış satır burada YOK — o zaten sayaçtaki `kalan`'da görünüyor.
    Bu liste "başladın, bitirmedin" listesidir.
    """
    return [dict(r) for r in c.execute(
        """SELECT b.kod, b.seri, b.aciklama, b.izleme, """ + BEKLENEN_ADET + """ beklenen,
                  COALESCE((SELECT SUM(o.miktar) FROM okutma o
                            WHERE o.oturum=? AND o.beklenen_id=b.id), 0) sayilan
           FROM beklenen b
           WHERE b.yukleme=? AND b.ambar=? AND b.haric=0
             AND COALESCE((SELECT SUM(o.miktar) FROM okutma o
                           WHERE o.oturum=? AND o.beklenen_id=b.id), 0)
                 < """ + BEKLENEN_ADET + """
             AND EXISTS(SELECT 1 FROM okutma o WHERE o.oturum=? AND o.beklenen_id=b.id)
           ORDER BY b.id""",
        (ot["id"], ot["yukleme"], ot["ambar"], ot["id"], ot["id"]))]


def sayaclar(c, ot):
    """Ekranın üstündeki sayaçlar — ADET bazında.

    Eskiden satır bazındaydı (`COUNT(*)` / `COUNT(DISTINCT beklenen_id)`).
    Seri takipli satırda doğru sonuç veriyordu ama lot satırında yanlış: tek
    satır çok adet taşıdığı için bir okutma o satırı "bitmiş" sayıyordu. 870
    satırın hepsi birer kez okutulduğunda ekran "OKUTULAN 870 / KALAN 0"
    diyor, rapor ise 202 adet eksik gösteriyordu — ekranla rapor iki ayrı
    gerçek söylüyordu.

    Ölçüt `kapasite_kaldi()` ve `ara(sadece_acik=True)` ile aynı: sayılan
    adet, beklenen adedi geçemez (fazla sayım `reports` tarafında "adet
    fazlası" olarak ayrıca raporlanıyor, `kalan`'ı eksiye düşürmemeli).
    """
    oturum, yukleme, ambar = ot["id"], ot["yukleme"], ot["ambar"]
    r = c.execute("""SELECT COALESCE(SUM(%s),0) top, COALESCE(SUM(%s),0) ok
                     FROM beklenen b
                     WHERE b.yukleme=? AND b.ambar=? AND b.haric=0"""
                  % (BEKLENEN_ADET, SAYILAN_ADET),
                  (oturum, yukleme, ambar)).fetchone()
    top, ok = r["top"], r["ok"]
    fz = c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND tip='fazla'",
                   (oturum,)).fetchone()["n"]
    ky = c.execute("SELECT COUNT(*) n FROM kuyruk WHERE oturum=? AND cozuldu=0",
                   (oturum,)).fetchone()["n"]
    # Satır sayısı da lazım: "870 satırın 341'i" ekranda hâlâ anlamlı bir bilgi.
    sat = c.execute("SELECT COUNT(*) n FROM beklenen WHERE yukleme=? AND ambar=? "
                    "AND haric=0", (yukleme, ambar)).fetchone()["n"]
    return {"okutulan": int(ok), "kalan": int(top - ok), "fazla": fz, "kuyruk": ky,
            "toplam": int(top), "satir": sat}


def durum(c, ot, akis=40):
    """Sayım ekranının tek çağrıda ihtiyaç duyduğu her şey."""
    oturum, yukleme, ambar = ot["id"], ot["yukleme"], ot["ambar"]
    tampon = []
    for r in c.execute("SELECT ham FROM tampon WHERE oturum=? ORDER BY id", (oturum,)):
        t = coz(c, r["ham"], yukleme, ambar, oturum)
        tampon.append({"ham": r["ham"], "coz": t["t"], "kod": t.get("kod"),
                       "aciklama": t.get("aciklama"), "not": t.get("not")})
    # `id` ve `grup` şart: arayüzdeki satır bazlı silme (I1) olmadan akış
    # satırını adlandıramıyor, `##GERIAL##` ise yalnızca SONUNCUYU alıyordu.
    son = [dict(r) for r in c.execute(
        "SELECT id,ts,ham,kod,seri,tip,raf,grup,miktar,not_ FROM okutma "
        "WHERE oturum=? ORDER BY id DESC LIMIT ?", (oturum, akis))]
    return {"oturum": oturum, "yukleme": yukleme, "ambar": ambar,
            "aktif_raf": ot["aktif_raf"], "durum": ot["durum"],
            "bekleyen_adet": int(ot["bekleyen_adet"] or 0),
            # Kilit ve yedek parça modu ekranda GÖRÜNMEK zorunda: ikisi de
            # sessiz kalırsa bütün sayım yanlış malzemeye ya da yedek parçaya
            # yazılır ve bu ancak rapor açılınca fark edilir.
            "sabit_kod": ot["sabit_kod"],
            "sabit_aciklama": (c.execute(
                "SELECT aciklama FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                "LIMIT 1", (yukleme, ambar, ot["sabit_kod"])).fetchone() or
                {"aciklama": None})["aciklama"] if ot["sabit_kod"] else None,
            "yedek_parca": bool(ot["yedek_parca"]),
            # Açık kap da kilit ve yedek parça gibi KALICI bir kip: ekranda
            # görünmezse kullanıcı kabı kapattığını sanıp sonraki ürünleri
            # kilitli malzemeye yazar.
            "acik_kutu": kutu_sayaci(c, ot),
            "sayac": sayaclar(c, ot), "tampon": tampon, "akis": son}


def ara(c, yukleme, ambar, q="", limit=0, offset=0, oturum=None,
        sadece_acik=False, kirli=None, izleme=None, raf=None):
    """Malzeme arama / listeleme — kuyruk ve onay ekranlarının tek aracı.

    Aday önerisinin ("bu olabilir") yerini aldı: öneri sahada doğru sonuç
    vermiyordu, sıralama sezgisi kullanıcının bildiğini bilmiyordu
    (DEMO_FEEDBACK.md 4). Onun yerine kullanıcı kendi arıyor ve filtreliyor.

    q boşken de çalışır — filtrelerle düz liste gezilebilsin diye.

    limit=0 (VARSAYILAN) sınır yok demektir: eşleştirme listesi eksiksiz
    olmalı. Eskiden varsayılan 25'ti ve arayüzler 40/50 istiyordu; sayfalama
    da olmadığı için 869 satırlık bir kümenin yalnızca ilk sayfası
    görülebiliyordu. Kullanıcı listede olmayan ürünü elle tahmin edip aramak
    zorunda kalıyordu. Sınırı arayüz koymaz; hepsi gönderilir, süzme ve
    kademeli çizim istemcide yapılır.

    oturum verilirse her satır bu oturumda sayılıp sayılmadığını da taşır;
    kullanıcı aynı kaydı ikinci kez bağlamasın diye arayüz uyarır.

    sadece_acik: bu oturumda sayılmamış satırlar. Seri takiplide "hiç
      okutulmamış", lot/izlemesizde "sayılan < beklenen" demektir — bir lot
      kaleminin bir kez okutulmuş olması bitti anlamına gelmez.
    kirli:  True/False ile uydurma kayıtlı satırları süz
    izleme: 'seri' | 'lot' | 'yok'
    raf:    bu rafta aynı koddan sayılmış olanlar başa alınır (raf komşuluğu
            sahada en güçlü ipucu) — süzmez, sıralar.
    """
    kosul = ["b.yukleme=?", "b.ambar=?", "b.haric=0"]
    par = [yukleme, ambar]
    if q:
        # LIKE kaçışı: kullanıcının yazdığı `%` ve `_` joker davranıyordu.
        # `210-ACXU` aramak isteyen biri `%` yazınca tüm tabloyu çekiyordu.
        kosul.append("(b.kod LIKE ? ESCAPE '!' OR b.aciklama LIKE ? ESCAPE '!' "
                     "OR b.seri LIKE ? ESCAPE '!')")
        like = "%" + _like_kacir(q) + "%"
        par += [like, like, like]
    if kirli is not None:
        kosul.append("b.kirli=?")
        par.append(1 if kirli else 0)
    if izleme:
        kosul.append("b.izleme=?")
        par.append(izleme)
    if sadece_acik:
        # `kapasite_kaldi()` ile BİREBİR aynı ölçüt. Kopya SQL yazılmıyor:
        # ikisi ayrıştığı anda kullanıcı listede gördüğü kaydı bağlayamaz
        # (ya da göremediği kayda bağlayabilir).
        kosul.append("""COALESCE((SELECT SUM(o.miktar) FROM okutma o
                                  WHERE o.oturum=? AND o.beklenen_id=b.id), 0)
                        < """ + BEKLENEN_ADET)
        par += [oturum]
    nere = " AND ".join(kosul)

    toplam = c.execute("SELECT COUNT(*) n FROM beklenen b WHERE " + nere,
                       par).fetchone()["n"]
    rs = c.execute("""SELECT b.id, b.kod, b.aciklama, b.seri, b.kirli, b.izleme,
                      b.miktar, b.birim,
                      EXISTS(SELECT 1 FROM okutma o WHERE o.oturum=?
                             AND o.beklenen_id=b.id) sayildi,
                      (SELECT COUNT(*) FROM okutma o2 WHERE o2.oturum=?
                       AND o2.kod=b.kod AND COALESCE(o2.raf,'')=?) ayni_raf
                      FROM beklenen b WHERE """ + nere + """
                      ORDER BY ayni_raf DESC, sayildi, b.kirli DESC, b.id
                      """ + ("LIMIT ? OFFSET ?" if limit else ""),
                   [oturum, oturum, raf or ""] + par
                   + ([limit, offset] if limit else [])).fetchall()
    return {"satirlar": [dict(r) for r in rs], "toplam": toplam}


def fazla_bagla(c, okutma_id, beklenen_id):
    """Sayım sonu eşleştirmesi: fazla kaydını bir eksik kayda bağlar.

    Sahadaki gerçek: fazla çıkan ürün çoğu zaman eksik görünen kaydın ta
    kendisidir, sadece seri numarası tutmamıştır. Rapor üretilmeden önce
    kullanıcı ikisini yan yana görüp elle eşleştirir (DEMO_FEEDBACK.md 6).

    Barkodlar `kuyruk_coz` ile aynı kuralla öğrenilir; kirli bir slota
    bağlanırsa Tiger Düzeltme sekmesi kendiliğinden dolar.
    """
    x = c.execute("SELECT * FROM okutma WHERE id=?", (okutma_id,)).fetchone()
    if not x:
        return {"hata": "okutma kaydı yok"}
    if x["tip"] != "fazla":
        return {"hata": "yalnızca fazla kaydı bağlanabilir"}
    b = c.execute("SELECT * FROM beklenen WHERE id=?", (beklenen_id,)).fetchone()
    if not b:
        return {"hata": "malzeme yok"}
    if not kapasite_kaldi(c, x["oturum"], b):
        return {"hata": "bu kayıt bu oturumda zaten sayıldı"}
    # MİKTAR KAPASİTEYE SIĞMALI.
    #
    # Fazla kaydı 150 adet taşıyabiliyor (kaptan sayılmış olabilir) ama
    # bağlanacak satır tek cihazlık olabilir. Eskiden kontrol yoktu: 150'lik
    # kayıt seri takipli bir satıra bağlanınca sayaç 1 sayıyor, kalan 149
    # adet ne eksikte ne fazlada görünüyordu. Üstelik eşleştirme ekranı
    # miktarı GÖSTERMİYORDU bile, yani kullanıcı 150 olduğunu bilmiyordu.
    kalan = beklenen_adet(b) - c.execute(
        "SELECT COALESCE(SUM(miktar),0) n FROM okutma WHERE oturum=? AND beklenen_id=?",
        (x["oturum"], b["id"])).fetchone()["n"]
    if (x["miktar"] or 1) > kalan:
        return {"hata": "miktar_sigmiyor",
                "mesaj": "Bu fazla kaydı %g adet, seçilen kayda %g adet sığıyor. "
                         "Ya kaydın adedini düzeltin ya da daha büyük bir "
                         "kayda bağlayın." % (x["miktar"] or 1, kalan)}

    ts = _ts()
    hs = [p.strip() for p in str(x["ham"] or "").split(" + ") if p.strip()]
    # Seri etiketi öğrenilmez: tekil cihaza ait, malzeme seviyesine
    # yükseltilemez (kuyruk_coz ile aynı ayrım).
    for h in hs:
        if etiketler.ogrenilebilir(h):
            c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                      (norm(h), b["kod"], "", ts))
    # Fazla yolunda bağlanmış DS- etiketi ARTIK BİR KAYDA AİT: defterde de
    # öyle görünmeli, yoksa Etiketler sekmesi "hangi satıra yapıştı" sorusunu
    # cevaplayamaz ve Tiger Düzeltme satırıyla eşleşmez.
    for h in hs:
        if etiketler.etiket_turu(norm(h)) == "seri" and c.execute(
                "SELECT 1 FROM etiket WHERE kod=? AND beklenen_id IS NULL",
                (norm(h),)).fetchone():
            etiketler.bagla(c, h, b["kod"], b["id"], x["oturum"], ts, x["raf"])
            break
    malzeme_et = etiketler.malzeme_etiketi_isle(c, hs, b["kod"], x["oturum"], ts,
                                                x["raf"])
    # `yeni_seri` BURADA da yazılmalı: fazla satırının `beklenen_id`'si şimdi
    # doluyor, yani satır Tiger Düzeltme sorgusuna ilk kez giriyor. Boş
    # bırakılırsa (NULL) rapor eski kurala düşer ve `ham`'daki malzeme kodunu
    # önerebilir — `kuyruk_coz` ile aynı eleme uygulanıyor.
    yeni_es = _fazla_seri(hs, b["kod"])
    if norm(yeni_es) == norm(b["seri"] or ""):
        yeni_es = ""
    c.execute("""UPDATE okutma SET tip='eslesti', beklenen_id=?, kod=?, seri=?,
                 not_='sayım sonu eşleştirildi', yeni_seri=? WHERE id=?""",
              (b["id"], b["kod"], b["seri"], yeni_es, okutma_id))
    # `geri` EZİLMEZ, EKLENİR. Eskiden burada yeni bir JSON yazılıyor ve
    # kaydın önceki yan etkileri (kuyruk bağı, öğrenilmiş ad, bağlanmış
    # etiket) sessizce düşüyordu — kayıt sonradan silinince hiçbiri geri
    # alınamıyordu.
    _geri_ekle(c, okutma_id,
               ogrenilen=[h for h in hs if etiketler.ogrenilebilir(h)],
               malzeme_etiket=malzeme_et)
    return {"tip": "eslesti", "okutma": okutma_id, "kod": b["kod"],
            "aciklama": b["aciklama"], "seri": b["seri"]}


def elle_say(c, ot, beklenen_id, ham=None, adet=None):
    """Bir beklenen kaydı listeden seçerek "sayıldı" işaretler (I5).

    Barkodu olmayan ürünler için: cihazın üstünde yalnızca seri numarası ya da
    benzeri bir tanımlayıcı yazılı, okutulacak bir şey yok. Kullanıcı değeri
    telefondan yazar; tuttuysa `okut()` zaten eşleştirir. Tutmadıysa ürünü
    listeden bulup işaretler — bu yol o.

    `kuyruk_coz` ile aynı iki kural:
      * dolu kayda bağlanmaz (`kapasite_kaldi`) — yoksa iki fiziksel ürün tek
        kayda düşer
      * yazılan değer öğrenilir, DS- seri etiketi HARİÇ (tekil cihaza ait,
        malzeme seviyesine yükseltilemez)

    `adet` LOT / İZLEMESİZ KALEMDE UYGULANIR. Bu yol bir dönem SABİT 1
    yazıyordu ve elle saymanın asıl müşterisi tam da bu kalemlerdi (barkodsuz
    = dökme): 77 adetlik bir lotu listeden saymak 77 ayrı tıklama, 77 ayrı grup
    demekti (DENETIM_20260904.md O3). Seri takiplide adet uygulanmaz — her
    cihaz Tiger'da ayrı satır — ama sessizce yutulmaz, `adet_yersiz` ile
    bildirilir (`grup_coz` / `kuyruk_coz` ile aynı sözleşme).

    `adet` VERİLMEZSE `oturum.bekleyen_adet` KULLANILIR ve tüketilir —
    ##ADET-N## / telefondaki Adet paneli okutma akışında ne yapıyorsa burada da
    onu yapar. Ayrı bir adet kutusu açmak ikinci bir giriş yolu, dolayısıyla
    ikinci bir davranış demekti; sahadaki akış zaten "adedi gir, sonra ürünü
    seç".

    Kapasiteyi aşan adet REDDEDİLİR: `fazla_bagla`'daki `miktar_sigmiyor`
    kapısının aynısı — 77'lik lota 150 yazmak 73 adedi hiçbir yerde
    görünmeyecek şekilde yutardı. Reddedilen çağrıda adet TÜKENMEZ, kullanıcı
    düzeltip yeniden seçebilsin.
    """
    b = c.execute("SELECT * FROM beklenen WHERE id=?", (beklenen_id,)).fetchone()
    if not b:
        return {"hata": "malzeme yok"}
    if b["yukleme"] != ot["yukleme"] or str(b["ambar"]) != str(ot["ambar"]):
        return {"hata": "bu kayıt bu oturumun ambarında değil"}
    if b["haric"]:
        return {"hata": "bu kalem sayım dışı"}
    if not kapasite_kaldi(c, ot["id"], b):
        return {"hata": "bu kayıt bu oturumda zaten sayıldı"}

    seri_takipli = b["izleme"] == "seri"
    bekleyen = int(ot["bekleyen_adet"] or 0)
    istenen = float(adet) if adet is not None else float(bekleyen)
    adet_yersiz = istenen if (seri_takipli and istenen > 1) else None
    miktar = 1.0 if (seri_takipli or istenen <= 0) else istenen
    if miktar > 1:
        kalan = beklenen_adet(b) - c.execute(
            "SELECT COALESCE(SUM(miktar),0) n FROM okutma WHERE oturum=? "
            "AND beklenen_id=?", (ot["id"], b["id"])).fetchone()["n"]
        if miktar > kalan:
            # Adet TÜKENMEZ: kullanıcı düzeltip yeniden seçebilmeli.
            return {"hata": "miktar_sigmiyor",
                    "mesaj": "Bu kayda %g adet sığıyor, %g yazdınız."
                             % (kalan, miktar)}
    # Adet, okutma akışındaki gibi bu "grup"la birlikte tükenir — sonraki
    # ürüne sızmamalı (CLAUDE.md 4.5).
    if bekleyen and adet is None:
        c.execute("UPDATE oturum SET bekleyen_adet=0 WHERE id=?", (ot["id"],))

    ts = _ts()
    deger = (ham or "").strip()
    ogrenilen = []
    if deger and etiketler.ogrenilebilir(deger):
        c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                  (norm(deger), b["kod"], "", ts))
        ogrenilen.append(deger)
    # Havuzdaki boş DS- etiketi yazıldıysa BAĞLANIR (öğrenilmez — tekil cihaza
    # ait). `kuyruk_coz` bunu yapıyordu, burada eksikti: etiket defterde boş
    # kalıyor, Etiketler sekmesi "havuzda bekliyor" diyor ama etiket fiziksel
    # olarak ürünün üstünde duruyordu.
    etiket_bagli = None
    if deger and etiketler.etiket_mi(deger) and c.execute(
            "SELECT 1 FROM etiket WHERE kod=? AND tur='seri' AND beklenen_id IS NULL",
            (norm(deger),)).fetchone():
        etiketler.bagla(c, deger, b["kod"], b["id"], ot["id"], ts, ot["aktif_raf"])
        etiket_bagli = deger
    grup = _yeni_grup(c, ot["id"])
    yeni_es = "" if norm(deger) == norm(b["seri"] or "") else deger
    oid = c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,tip,
                       raf,grup,not_,geri,yeni_seri)
                       VALUES(?,?,?,?,?,?,?,'eslesti',?,?,?,?,?)""",
                    (ot["id"], ts, deger, b["kod"], b["seri"], miktar, b["id"],
                     ot["aktif_raf"], grup,
                     "elle işaretlendi" + ("" if miktar == 1 else " — %g adet" % miktar),
                     _geri_json(ogrenilen, etiket_bagli), yeni_es)).lastrowid
    # Satırın güncel toplamı: lot kaleminde "77'nin 40'ı" ekranda görünmeli,
    # yoksa kullanıcı kaç kez daha basacağını bilemez.
    top = c.execute("SELECT COALESCE(SUM(miktar),0) s FROM okutma WHERE oturum=? "
                    "AND beklenen_id=?", (ot["id"], b["id"])).fetchone()["s"]
    return {"tip": "eslesti", "okutma": oid, "kod": b["kod"],
            "aciklama": b["aciklama"], "seri": b["seri"],
            "ogrenilen": ogrenilen, "etiket": etiket_bagli,
            "miktar": miktar, "toplam": top, "beklenen": beklenen_adet(b),
            "adet_yersiz": adet_yersiz,
            "raf": ot["aktif_raf"], "ses": "ok"}


def fazla_coz_ayir(c, okutma_id):
    """Yanlış eşleştirmeyi geri alır — kayıt yeniden fazla olur."""
    x = c.execute("SELECT * FROM okutma WHERE id=?", (okutma_id,)).fetchone()
    if not x:
        return {"hata": "okutma kaydı yok"}
    if x["not_"] != "sayım sonu eşleştirildi":
        return {"hata": "yalnızca sayım sonu eşleştirmesi geri alınabilir"}
    # `yeni_seri` de temizlenir: bağ koptu, o öneri artık hiçbir kayda ait
    # değil. Bayat değer bırakmak, satır başka bir malzemeye bağlanırsa
    # (fazla_bagla yeniden hesaplar) yanıltıcı bir ara durum yaratır.
    c.execute("""UPDATE okutma SET tip='fazla', beklenen_id=NULL, kod=NULL,
                 yeni_seri='', not_='eşleştirme geri alındı' WHERE id=?""",
              (okutma_id,))
    return {"tip": "fazla", "okutma": okutma_id}


def esleme_verisi(c, ot):
    """Sayım sonu ekranı: solda fazlalar, sağda eksikler.

    Eksik listesi reports.eksik_kayitlar()'tan gelir — rapordaki Eksik
    sekmesiyle aynı satırlar görünsün.
    """
    from .reports import eksik_kayitlar
    eksik, _, _ = eksik_kayitlar(c, ot["id"])
    # `miktar` GÖRÜNMEK ZORUNDA: fazla kaydı 150 adet taşıyabiliyor (kaptan
    # sayılmış olabilir) ve tek cihazlık bir kayda bağlanırsa geri kalanı
    # buharlaşırdı. Sunucu artık reddediyor (`fazla_bagla` -> miktar_sigmiyor)
    # ama kullanıcı reddi anlamak için adedi görmeli.
    fazla = [{"id": r["id"], "ts": (r["ts"] or "")[:19].replace("T", " "),
              "ham": r["ham"], "kod": r["kod"], "seri": r["seri"], "ad": r["ad"],
              "miktar": r["miktar"], "raf": r["raf"], "not_": r["not_"] or "",
              "fotolar": [f["id"] for f in c.execute(
                  "SELECT id FROM kuyruk_foto WHERE okutma=? ORDER BY id", (r["id"],))]}
             for r in c.execute("SELECT * FROM okutma WHERE oturum=? AND tip='fazla' "
                                "ORDER BY id", (ot["id"],))]
    return {"fazla": fazla, "eksik": eksik}


def adsiz_fazlalar(c, oturum):
    """Ne olduğu yazılmamış fazla kayıtları — bitirme kapısı.

    Yalnızca malzeme kodu OLMAYANLAR sayılır: kodu bilinen kayıtta rapor
    açıklamayı `beklenen` tablosundan çekebiliyor. Kodu olmayanda ise geriye
    seri numarası ve raf kalır; gün sonunda o satırın hangi ürün olduğu
    bulunamaz. Sisteme ilk kez giren ürün (kendi bastığımız etiket dahil)
    tam olarak bu durumda.
    """
    return [{"id": r["id"], "ham": r["ham"], "raf": r["raf"], "seri": r["seri"],
             "ts": (r["ts"] or "")[:19].replace("T", " ")}
            for r in c.execute(
                """SELECT * FROM okutma WHERE oturum=? AND tip='fazla'
                   AND COALESCE(kod,'')='' AND COALESCE(ad,'')=''
                   ORDER BY id""", (oturum,))]


def fotosuz_fazlalar(c, oturum):
    """Fotoğrafı olmayan fazla kayıtları — bitirme kapısı için.

    Fazla, sayım bittikten sonra kimsenin doğrulayamayacağı tek çıktıdır:
    ürün rafa geri konur, geriye yalnızca bir satır kalır. Fotoğraf o satırı
    denetlenebilir yapar (DEMO_FEEDBACK.md 6).

    AMA fotoğraf tek denetlenebilirlik yolu değil: `kod` ya da `ad` yazılmışsa
    satırın ne olduğu zaten bellidir ve fotoğraf istenmez (`adsiz_fazlalar`
    ile aynı muafiyet). Eskiden bu ayrım yoktu; açıklamasını yazdığı ürün için
    de fotoğraf istenip oturum kapatılamıyordu.

    NOT: bu muafiyetten sonra kapı pratikte `ad_engel`in arkasında kalır —
    kodu ve adı olmayan kayıt zaten oradan geçemez. Kapı bilerek duruyor:
    kuralın iki ayrı yerde tekrar etmesi, `adsiz_fazlalar` ileride gevşerse
    fotoğrafsız-kimliksiz satırın sessizce rapora girmesini engelliyor.
    """
    return [{"id": r["id"], "ham": r["ham"], "kod": r["kod"], "ad": r["ad"],
             "raf": r["raf"]}
            for r in c.execute(
                """SELECT * FROM okutma o WHERE o.oturum=? AND o.tip='fazla'
                   AND COALESCE(o.kod,'')='' AND COALESCE(o.ad,'')=''
                   AND NOT EXISTS(SELECT 1 FROM kuyruk_foto f WHERE f.okutma=o.id)
                   ORDER BY o.id""", (oturum,))]


def _fazla_seri(hamlar, kod):
    """Fazla kaydına yazılacak seri numarası.

    grup_coz'daki `yeni_sn` kuralının aynısı: malzeme kodunun kendisi seri
    numarası değildir, yanında okutulan değerdir. Sıralamayı (üretici S/N önce,
    kendi etiketimiz son çare) reports._yeni_seri belirler — kural tek yerde
    dursun diye ona devrediliyor.
    """
    from .reports import _yeni_seri
    kn = norm(kod)
    kalan = [h for h in hamlar if norm(h) and norm(h) != kn]
    if not kalan:
        return ""
    return _yeni_seri(" + ".join(kalan))


def fazla_ogren(c, okutma_id, ts=None):
    """Fazla kaydının ÖĞRENMESİ ve ETİKET BAĞLAMASI — üç yol da buradan geçer.

    `kuyruk_coz` bunları hep yapıyordu, fazla yazan üç dal (`kuyruk_fazla`,
    `##FAZLA##` komutu, sonradan ad yazılması) HİÇBİRİNİ yapmıyordu. Sonuç
    2026-08-28 sayımında görüldü (saha bildirimi S2):

      * `DM-000001` etiketi 47 kez okutuldu, 47 kez fazla yazıldı ve 47 kez
        adı elle girildi — hiçbir zaman öğrenilmedi.
      * Fiziksel olarak 109 DS- etiketi ürünlere yapıştırıldı, defterde
        yalnızca 30'u bağlı göründü; aradaki 79'un hepsi bu yoldan geçmişti.
        Etiketler sekmesi onları "boşta" gösteriyordu.

    İki ayrı öğrenme var ve ayrımı malzeme kodunun bilinip bilinmemesi yapar:

      kod BİLİNİYOR   -> `eslesme`  (barkod -> Tiger malzeme kodu). Kayıt fazla
                         olsa bile ürün O malzemedir; yalnızca Tiger'ın seri
                         numaralarıyla eşleşmemiştir.
      kod BİLİNMİYOR  -> `fazla_ad` (barkod -> kullanıcının yazdığı ad). Tiger'da
                         karşılığı yok, yazılacak bir kod da yok. `eslesme`'ye
                         boş kodla satır atmak Barkod Tablosu'nu kirletirdi.

    SERİ ve KUTU etiketleri hiçbir zaman öğrenilmez (`etiketler.ogrenilebilir`):
    ikisi de tekil bir nesneye ait, malzeme seviyesine yükseltilemez.

    Öğrenilenler `okutma.geri`ye YAZILIR, yoksa ##GERIAL## / Sil onları geri
    alamaz ve yanlış ürüne bağlanmış bir ad gelecek yılın sayımına taşınırdı.
    """
    r = c.execute("SELECT * FROM okutma WHERE id=?", (okutma_id,)).fetchone()
    if not r or r["tip"] != "fazla":
        return {}
    ts = ts or r["ts"] or _ts()
    hamlar = [h.strip() for h in str(r["ham"] or "").split(" + ") if h.strip()]
    kod, ad = r["kod"], (r["ad"] or "").strip()

    ogrenildi, adlandi, etiket = [], [], None
    for h in hamlar:
        if not norm(h):
            continue
        if not etiketler.ogrenilebilir(h):
            continue                       # DS- / DK-: tekil nesneye ait
        if kod:
            c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                      (norm(h), kod, "", ts))
            ogrenildi.append(h)
        elif ad:
            c.execute("INSERT OR REPLACE INTO fazla_ad VALUES(?,?,?)",
                      (norm(h), ad, ts))
            adlandi.append(h)

    # Fiziksel olarak ürüne yapışan DS- etiketi deftere işlenir. Tiger kaydı
    # YOK, o yüzden `malzeme` ve `beklenen_id` boş kalır — ama oturum, raf ve
    # zaman yazılır, yani defter "bu etiket kullanıldı" der. Boş bırakılırsa
    # Etiketler sekmesi onu havuzda sanır ve aynı numara ikinci kez basılabilir.
    bos = [h for h in hamlar
           if etiketler.etiket_turu(norm(h)) == "seri"
           and c.execute("SELECT 1 FROM etiket WHERE kod=? AND beklenen_id IS NULL "
                         "AND oturum IS NULL", (norm(h),)).fetchone()]
    if bos:
        etiket = bos[0]
        etiketler.bagla(c, etiket, kod, None, r["oturum"], ts, r["raf"])

    # `geri`ye EKLENİR, üzerine yazılmaz: INSERT anında konmuş anahtarlar
    # (kuyruk) korunmalı, yoksa Sil tuşu kuyruk kaydını hiç göremezdi.
    _geri_ekle(c, okutma_id, ogrenilen=ogrenildi, fazla_ad=adlandi, etiket=etiket)
    return {"ogrenilen": ogrenildi, "fazla_ad": adlandi, "etiket": etiket}


def kuyruk_fazla(c, kuyruk_id, ad=None):
    """Kuyruktaki kaydı fazla olarak kapatır — karşılığı gerçekten yoksa.

    ad: ürünün ne olduğu, kullanıcının yazdığı serbest metin. Malzeme kodu
    BİLİNMİYORSA zorunludur; yoksa kayıt oluşturulmaz.

    Sebep: kodu olmayan fazla kaydının raporda açıklaması üretilemez —
    `beklenen` tablosunda karşılığı olmadığı için JOIN boş döner. Geriye seri
    numarası ve raf kalır, gün sonunda o satırın hangi ürün olduğu bulunamaz.
    Kendi bastığımız etiketle giren yepyeni ürünler tam olarak bu yoldan
    geçtiği için adı burada sormak şart.
    """
    q = c.execute("SELECT * FROM kuyruk WHERE id=?", (kuyruk_id,)).fetchone()
    if not q:
        return {"hata": "kuyruk kaydı yok"}
    # `kutu_coz`'da olan koruma buraya da: telefonda çift dokunuş (eldiven, yavaş
    # ağ, iki ekranın aynı kaydı göstermesi) tek üründen İKİ fazla satırı
    # üretiyordu — raporda iki satır, kullanıcıya iki kez ad sorusu.
    if q["cozuldu"]:
        return {"hata": "bu kayıt zaten çözüldü"}
    ad = (ad if ad is not None else q["ad"]) or ""
    ad = ad.strip()
    if not q["kod"] and not ad:
        return {"hata": "ad_gerekli",
                "mesaj": "Bu ürünün Tiger'da kaydı yok. Fazla olarak yazmadan "
                         "önce ne olduğunu yazın — yoksa raporda yalnızca seri "
                         "numarası ve raf kalır, ürün bulunamaz."}
    ts = _ts()
    hs = json.loads(q["barkodlar"])
    grup = _yeni_grup(c, q["oturum"])

    # TEK GRUP = TEK ÜRÜN, istisnasız.
    #
    # Grup mantığının tamamı buna dayanıyor (CLAUDE.md 4.4): kullanıcı bir
    # ürünün üstündeki BÜTÜN barkodları okutur (P/N, S/N, UPC, lot, kendi
    # etiketimiz) ve ##SONRAKI## der. O yüzden bir kuyruk kaydı da tek üründür.
    #
    # Eskiden yalnızca `fazla_onay` dalı böyle davranıyordu; normal kuyruk
    # kaydında `for h in hs` ile BARKOD BAŞINA bir fazla satırı yazılıyordu.
    # Sonuç: tek üründen okutulan iki barkod raporda iki ayrı fazla oluyor,
    # kullanıcıya adı iki kez soruluyor ve eşleştirme ekranı ikisini ayrı ayrı
    # eşleştirmesini bekliyordu (saha bildirimi 2026-08-23).
    #
    # Barkodlar `ham` içinde " + " ile saklanır (denetim izi); Tiger'a yazılacak
    # tek seri numarasını `_fazla_seri` seçer — `kuyruk_coz` ile aynı kural.
    not_ = ("onaylandı: karşılığı yok" if q["tur"] == "fazla_onay"
            else "kuyruktan fazla işaretlendi")
    # Miktar kuyruk satırından gelir, sabit 1 DEĞİL. Kullanıcı grup kapanırken
    # "150 tane" demişse fazla kaydı 150 olmalı — eskiden 1 yazılıyor ve 150
    # hiçbir yere düşmüyordu (saha bildirimi 2026-08-27).
    miktar = float(q["adet"] or 0) or 1
    idler = [c.execute(
        """INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,tip,raf,grup,not_,ad,geri,
           yeni_seri) VALUES(?,?,?,?,?,?,'fazla',?,?,?,?,?,'')""",
        (q["oturum"], ts, " + ".join(hs), q["kod"], _fazla_seri(hs, q["kod"]),
         miktar, q["raf"], grup, not_, ad or None,
         _geri_json(kuyruk=kuyruk_id))).lastrowid]

    # Kuyruktayken çekilen fotoğraf fazla kaydına da bağlanır: bitirme kapısı
    # fotoğrafı `okutma` üzerinden arıyor, kullanıcıdan aynı fotoğrafı ikinci
    # kez istemeyelim.
    if idler:
        c.execute("UPDATE kuyruk_foto SET okutma=? WHERE kuyruk=?",
                  (idler[0], kuyruk_id))
    c.execute("UPDATE kuyruk SET cozuldu=1 WHERE id=?", (kuyruk_id,))
    yan = fazla_ogren(c, idler[0], ts)
    return dict({"tip": "fazla", "okutma": idler, "kod": q["kod"], "miktar": miktar},
                **yan)


def kuyruk_coz(c, kuyruk_id, beklenen_id):
    """Kuyruktaki grubu bir malzemeye bağlar; barkodlar kalıcı olarak öğrenilir."""
    q = c.execute("SELECT * FROM kuyruk WHERE id=?", (kuyruk_id,)).fetchone()
    if not q:
        return {"hata": "kuyruk kaydı yok"}
    # Aynı kayıt iki kez çözülemez: ikinci çağrı lot satırında kapasite
    # kaldığı sürece İKİNCİ bir okutma yazıyor ve adet iki katına çıkıyordu.
    if q["cozuldu"]:
        return {"hata": "bu kayıt zaten çözüldü"}
    b = c.execute("SELECT * FROM beklenen WHERE id=?", (beklenen_id,)).fetchone()
    if not b:
        return {"hata": "malzeme yok"}
    # Çift bağlama koruması. `fazla_bagla`'da vardı, burada YOKTU: iki ayrı
    # kuyruk kaydı aynı beklenen satırına bağlanabiliyor ve iki fiziksel ürün
    # tek kayıtla kapatılmış görünüyordu. Arayüz de sayılmış kayıtları
    # listelediği için bu kolayca oluyordu.
    if not kapasite_kaldi(c, q["oturum"], b):
        return {"hata": "bu kayıt bu oturumda zaten sayıldı"}
    ts = _ts()
    hs = json.loads(q["barkodlar"])
    # Yalnızca SERİ etiketi öğrenilmez: tekil bir cihaza ait, malzeme
    # seviyesine yükseltilemez. Boş MALZEME etiketi ise tam tersine burada
    # öğrenilmelidir — kodu olmayan ürüne yapıştırılan etiket ancak böyle
    # kalıcı bir malzeme barkoduna dönüşür (CLAUDE.md 12).
    ogrenilecek = [h for h in hs if etiketler.ogrenilebilir(h)]
    bos_etiket = [h for h in hs if etiketler.etiket_mi(h)
                  and c.execute("SELECT 1 FROM etiket WHERE kod=? AND tur='seri' "
                                "AND beklenen_id IS NULL", (norm(h),)).fetchone()]
    for h in ogrenilecek:
        c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                  (norm(h), b["kod"], "", ts))
    if bos_etiket:
        etiketler.bagla(c, bos_etiket[0], b["kod"], b["id"], q["oturum"], ts, q["raf"])
    # BOŞ HAVUZ MALZEME ETİKETİ DEFTERE DE İŞLENİR.
    #
    # `eslesme`'ye yazmak yetmiyordu: `etiket.malzeme` boş kaldığı için defter
    # o numarayı "havuzda bekliyor" sayıyordu. İki sonucu var ve ikincisi
    # fiziksel — `etiketler.bas(kapsam="eksik")` "bu malzemenin etiketi var mı"
    # diye TAM BU ALANA bakıyor: aynı malzeme için İKİNCİ bir DM- numarası
    # basılıyor ve depoda tek ürünün üstünde iki farklı kod dolaşıyordu
    # (CLAUDE.md §12.1 bunun olmamasını şart koşuyor). Gerçek veride
    # doğrulandı: DM-000002 -> SR335 `eslesme`'de yazılı, defterde boştu;
    # yeniden basımda SR335'e DM-000174 veriliyordu.
    malzeme_et = etiketler.malzeme_etiketi_isle(c, hs, b["kod"], q["oturum"], ts,
                                                q["raf"])
    # Kuyruğa düşerken girilmiş adet burada karara bağlanır: MALZEME artık
    # belli, yani izleme yöntemi de belli. Lot / izlemesizde miktar olarak
    # uygulanır; seri takiplide uygulanamaz (her adet Tiger'da ayrı satır) ama
    # sessizce yutulmaz — `adet_yersiz` ile bildirilir, grup_coz ile aynı kural.
    adet = float(q["adet"] or 0)
    seri_takipli = b["izleme"] == "seri"
    miktar = 1 if (seri_takipli or not adet) else adet
    adet_yersiz = adet if (seri_takipli and adet > 1) else None
    grup = _yeni_grup(c, q["oturum"])
    # Tiger'a önerilecek seri numarası: `_fazla_seri` malzeme kodunu ELER,
    # sonra `reports._yeni_seri` sırasını uygular (üretici S/N önce, kendi
    # etiketimiz son çare). Kod elenmezse `fazla_onay` kuyruğundan gelen bir
    # grupta malzeme kodu seri no diye önerilebiliyordu — `##FAZLA##` bu
    # elemeyi hep yapıyordu, `kuyruk_coz` yapmıyordu.
    yeni_es = _fazla_seri(hs, b["kod"])
    if norm(yeni_es) == norm(b["seri"] or ""):
        yeni_es = ""
    c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,tip,raf,
                 grup,not_,geri,yeni_seri)
                 VALUES(?,?,?,?,?,?,?,'eslesti',?,?,'kuyruktan çözüldü',?,?)""",
              (q["oturum"], ts, " + ".join(hs), b["kod"], b["seri"], miktar, b["id"],
               q["raf"], grup,
               _geri_json(ogrenilecek, bos_etiket[0] if bos_etiket else None,
                          kuyruk=kuyruk_id, malzeme_etiket=malzeme_et), yeni_es))
    c.execute("UPDATE kuyruk SET cozuldu=1 WHERE id=?", (kuyruk_id,))
    return {"tip": "eslesti", "kod": b["kod"], "aciklama": b["aciklama"],
            "seri": b["seri"], "ogrenilen": ogrenilecek, "miktar": miktar,
            "adet_yersiz": adet_yersiz,
            "etiket": bos_etiket[0] if bos_etiket else None}


def kutu_coz(c, kuyruk_id, malzeme=None, adet=None):
    """Kuyruktaki KAP kaydını çözer: kabın içeriğini tanımlar, sayımı işler.

    İki soruyu birden kapatır ve ikisi de tek yerden cevaplanır:
      * "bu kapta ne var"  -> `kutu` tablosuna KALICI olarak yazılır, gelecek
        yıl aynı kap tek okutmayla malzemesini söyler
      * "kaç tane sayıldı" -> bu oturuma yazılır, kaba değil; kabın `adet`
        alanı yalnızca bir sonraki sayımın VARSAYILANI olarak tazelenir

    Seri takipli malzemede sayım YAPILMAZ: her adet Tiger'da ayrı satır, kap
    kodu bir cihaz değil. Kap tanımlanır, kullanıcı seri numaralarını okutur
    (KUTU_TASARIM.md 5, 10 — otomatik kilit I2 saha testinden sonra).
    """
    q = c.execute("SELECT * FROM kuyruk WHERE id=?", (kuyruk_id,)).fetchone()
    if not q:
        return {"hata": "kuyruk kaydı yok"}
    if (q["tur"] or "") != "kutu":
        return {"hata": "bu kayıt bir kap kaydı değil"}
    if q["cozuldu"]:
        return {"hata": "bu kayıt zaten çözüldü"}
    ot = c.execute("SELECT * FROM oturum WHERE id=?", (q["oturum"],)).fetchone()
    if not ot:
        return {"hata": "oturum yok"}
    hs = json.loads(q["barkodlar"])
    kutu_kod = next((h for h in hs if etiketler.etiket_turu(h) == "kutu"), None)
    if not kutu_kod:
        return {"hata": "kayıtta kap barkodu yok"}

    kod = (malzeme or q["kod"] or "").strip()
    if not kod:
        return {"hata": "kap_malzeme_gerekli"}
    b = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                  "ORDER BY id LIMIT 1", (ot["yukleme"], ot["ambar"], kod)).fetchone()
    if not b:
        # Ambar dışına çıkmıyoruz (CLAUDE.md 3.5). Kapta bu ambarda kayıtlı
        # olmayan bir şey varsa cevabı "fazla"dır, başka bir depodaki kayıt
        # değil.
        return {"hata": "bu malzeme bu ambarda kayıtlı değil: %s" % kod}
    if b["haric"]:
        return {"hata": "bu kalem sayım dışı: %s" % (b["haric_sebep"] or "")}

    ts = _ts()
    izleme = b["izleme"] or "yok"
    onceki = kutum.anlik(c, kutu_kod)
    miktar = float(adet) if adet is not None else float(q["adet"] or 0)
    if izleme != "seri" and miktar <= 0:
        # Sabit 1 yazılamaz: kapta bir tane olduğu bilgisi hiçbir yerden
        # gelmiyor ve yanlış sayı sessizce rapora girerdi.
        return {"hata": "kap_adet_gerekli"}

    # Kap kaydı her durumda yazılır — sayım yapılmasa bile. Asıl kazanç bu:
    # bir dahaki okutmada kap malzemesini kendisi söyleyecek.
    kutum.tanimla(c, kutu_kod, kod, miktar or None, izleme, raf=q["raf"],
                  oturum=q["oturum"], ts=ts)
    kutu_geri = {"kod": norm(kutu_kod), "onceki": onceki}

    # Kapla birlikte okutulmuş tanınmayan barkodlar malzemeye öğrenilir —
    # `kuyruk_coz` ile aynı kural. Kap kodunun kendisi `ogrenilebilir()`
    # tarafından elenir: kap bir malzeme değil, malzemenin durduğu yerdir.
    ogrenilen = [h for h in hs if etiketler.ogrenilebilir(h)]
    for h in ogrenilen:
        c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                  (norm(h), kod, "", ts))

    c.execute("UPDATE kuyruk SET cozuldu=1, kod=? WHERE id=?", (kod, kuyruk_id))
    if izleme == "seri":
        return {"tip": "kutu_seri", "kutu": kutu_kod, "kod": kod,
                "aciklama": b["aciklama"], "izleme": izleme, "adet": miktar or None,
                "ogrenilen": ogrenilen, "sayildi": False, "ses": "uyari"}

    grup = _yeni_grup(c, q["oturum"])
    sonuc = _adet_islemi(c, ot, kod, miktar, hs, q["raf"], grup, ts,
                         ek_not=" | kutu: %s" % kutu_kod,
                         geri=_geri_json(ogrenilen, kuyruk=kuyruk_id, kutu=kutu_geri),
                         aciklama=b["aciklama"], izleme=izleme)
    sonuc.update({"kutu": kutu_kod, "ogrenilen": ogrenilen, "sayildi": True,
                  "ses": "ok"})
    return sonuc
