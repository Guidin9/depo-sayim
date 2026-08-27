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
from .norm import ADET_TAVAN, komut_coz, norm, sifirsiz, upc_mi

SAYILMADI = ("AND NOT EXISTS(SELECT 1 FROM okutma o WHERE o.oturum=? "
             "AND o.beklenen_id=b.id)")


def _ts():
    return datetime.datetime.now().isoformat()


def _sayildi(c, oturum, bid):
    return bool(c.execute("SELECT 1 FROM okutma WHERE oturum=? AND beklenen_id=? LIMIT 1",
                          (oturum, bid)).fetchone())


def kapasite_kaldi(c, oturum, b):
    """Bu beklenen kayda bu oturumda HÂLÂ bağlanabilir mi?

    Elle eşleştirmenin tek doğruluk ölçütü. `_sayildi` tek başına yetmez:

    - `izleme='seri'`: her satır bir tekil cihaz, bir kez okutulur. Sayıldıysa
      kapasite bitmiştir.
    - `lot` / `yok`: tek satır çok adet taşır. 77 adetlik bir lotun bir kez
      okutulmuş olması bittiği anlamına GELMEZ; sayılan < beklenen olduğu
      sürece bağlanabilir.

    Bu ayrım `ara(sadece_acik=True)` içindeki SQL ile birebir aynı olmalı —
    arayüzün gösterdiği liste ile sunucunun kabul ettiği bağlama aynı kuralı
    kullanmazsa kullanıcı listede gördüğü kaydı bağlayamaz.
    """
    if b["izleme"] == "seri":
        return not _sayildi(c, oturum, b["id"])
    sayilan = c.execute("SELECT COALESCE(SUM(miktar),0) n FROM okutma "
                        "WHERE oturum=? AND beklenen_id=?",
                        (oturum, b["id"])).fetchone()["n"]
    return sayilan < (b["miktar"] or 0)


def _geri_json(ogrenilen=None, etiket=None, kuyruk=None):
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
    if etiket:
        d["etiket"] = etiket
    if kuyruk:
        d["kuyruk"] = kuyruk
    return json.dumps(d, ensure_ascii=False) if d else None


def _yan_etkileri_geri_al(c, satir):
    """`okutma.geri` içindeki yan etkileri temizler. Ne temizlendiğini döner."""
    try:
        d = json.loads(satir["geri"] or "") or {}
    except (TypeError, ValueError):
        return {}
    for h in d.get("ogrenilen") or []:
        c.execute("DELETE FROM eslesme WHERE barkod=?", (norm(h),))
    if d.get("etiket"):
        etiketler.coz_bagla(c, d["etiket"])
    if d.get("kuyruk"):
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
        return {"t": "etiket_bos", "ham": ham, "etiket": e["gosterim"]}

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

    # 4) Öğrenilmiş eşleşme
    e = c.execute("SELECT * FROM eslesme WHERE barkod=?", (n,)).fetchone()
    if e:
        r = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                      "ORDER BY id LIMIT 1", (yukleme, ambar, e["kod"])).fetchone()
        if r:
            return {"t": "ogrenilmis", "kod": r["kod"], "aciklama": r["aciklama"],
                    "izleme": r["izleme"], "birim": r["birim"],
                    "haric": r["haric"], "haric_sebep": r["haric_sebep"]}

    # 5) İçerme: gerçek S/N kirli kaydın içine gömülmüş olabilir
    if len(n) >= 6:
        r = c.execute("""SELECT * FROM beklenen b WHERE yukleme=? AND ambar=?
                         AND izleme='seri' AND kirli=1 AND INSTR(seri_n, ?)>0
                         AND kod_n<>? """ + SAYILMADI + " ORDER BY id LIMIT 1",
                      (yukleme, ambar, n, n, oturum)).fetchone()
        if r:
            return {"t": "seri", "id": r["id"], "kod": r["kod"],
                    "aciklama": r["aciklama"], "seri": r["seri"],
                    "izleme": r["izleme"], "birim": r["birim"],
                    "haric": r["haric"], "haric_sebep": r["haric_sebep"],
                    "not": "gömülü S/N"}

    # 6/7) UPC ya da bilinmiyor
    return {"t": "upc" if upc_mi(ham) else "bilinmiyor", "ham": ham}


# ---------------------------------------------------------------- grup çözümleme
def _yeni_grup(c, oturum):
    r = c.execute("SELECT COALESCE(MAX(grup),0)+1 g FROM okutma WHERE oturum=?",
                  (oturum,)).fetchone()
    return r["g"]


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
    sabit = None
    if not kod_h and ot["sabit_kod"]:
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

    if tekrar and not seri_h:
        return {"tip": "tekrar", "kod": tekrar[1]["kod"], "seri": tekrar[1]["seri"],
                "ses": "uyari"}

    kaynak = seri_h or kod_h
    if not kaynak:
        # Girilen adet kuyruk satırına TAŞINIR, burada harcanmaz.
        #
        # Malzeme bilinmiyor, yani seri takipli mi lot mu bilinmiyor; adedin
        # anlamlı olup olmadığına ancak kayıt çözülünce karar verilebilir.
        # Eskiden `bekleyen_adet` grup kapanırken sıfırlanıyor ve buraya hiç
        # yazılmıyordu: kullanıcı "150 tane var" diyor, ürün tanınmıyor,
        # 150 hiçbir yere düşmeden kayboluyordu (saha bildirimi 2026-08-27).
        kid = c.execute("INSERT INTO kuyruk(oturum,ts,barkodlar,raf,not_,adet) "
                        "VALUES(?,?,?,?,?,?)",
                        (oturum, ts, json.dumps(hamlar, ensure_ascii=False), raf,
                         "boş etiket okutuldu, malzeme belirtilmedi"
                         if bos_etiket else None, bekleyen_adet)).lastrowid
        # `miktar`, `adet` DEĞİL: yanıttaki `adet` tampondaki BARKOD sayısını
        # söylüyor (satır ~741), buradaki ise kaç ÜRÜN olduğunu.
        return {"tip": "kuyruk", "kuyruk_id": kid, "barkodlar": hamlar, "raf": raf,
                "bos_etiket": bos_etiket, "miktar": bekleyen_adet or None,
                "ses": "kuyruk"}

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
        return {"tip": "haric", "kod": kaynak[1]["kod"],
                "aciklama": kaynak[1]["aciklama"],
                "sebep": kaynak[1].get("haric_sebep") or "",
                "barkodlar": hamlar, "raf": raf, "ses": "uyari"}

    kod = kaynak[1]["kod"]
    aciklama = kaynak[1]["aciklama"]
    # ##ADET-N## seri takipli kalemde anlamsız: her adet ayrı bir cihaz, Tiger'da
    # ayrı bir satır. Sessizce yok saymak yerine söylenir — kullanıcı yanlış
    # barkod okutmuş olabilir ve 25 adedin uçtuğunu bilmeli.
    adet_yersiz = (bekleyen_adet if bekleyen_adet > 1
                   and kaynak[1].get("izleme") == "seri" else None)

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
                "sabit_kod": sabit, "ses": "ok"}

    # Malzeme belli ama seri eşleşmedi
    izleme = kaynak[1].get("izleme", "yok")
    if izleme == "seri":
        slot = c.execute("""SELECT * FROM beklenen b WHERE yukleme=? AND ambar=? AND kod=?
                            AND kirli=1 """ + SAYILMADI + " ORDER BY id LIMIT 1",
                         (yukleme, ambar, kod, oturum)).fetchone()
        # Tiger'a yazılacak seri numarası seçimi. Üretici S/N okutulduysa ya da
        # elle yazıldıysa O kazanır; havuz etiketi son çaredir. Cihazın gerçek
        # seri numarası garanti/RMA izidir, uydurma numarayla değiştirilmez.
        yeni_sn = (max(bilinmeyen, key=len) if bilinmeyen
                   else (bos_etiket[0] if bos_etiket else ""))
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
            c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,
                         tip,raf,grup,not_,geri,yeni_seri)
                         VALUES(?,?,?,?,?,1,?,'eslesti',?,?,?,?,?)""",
                      (oturum, ts, " + ".join(hamlar), kod, slot["seri"],
                       slot["id"], raf, grup,
                       ("slot dolduruldu" if yeni_sn
                        else "sayıldı — seri numarası verilmedi, Tiger düzeltmesi yok")
                       + (" | etiket: " + bos_etiket[0] if bos_etiket else "")
                       + (" | sabit kod: " + sabit if sabit else ""),
                       _geri_json(ogrenilen,
                                  bos_etiket[0] if bos_etiket else None),
                       yeni_sn))
            return {"tip": "slot", "kod": kod, "aciklama": aciklama, "eski": slot["seri"],
                    "yeni": yeni_sn, "sn_yok": not yeni_sn,
                    "etiket": bos_etiket[0] if bos_etiket else None,
                    "raf": raf, "adet_yersiz": adet_yersiz, "sabit_kod": sabit,
                    "ses": "ok" if yeni_sn else "uyari"}
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
                         kod, "seri takipli, karşılığı bulunamadı",
                         bekleyen_adet)).lastrowid
        return {"tip": "onay", "kuyruk_id": kid, "kod": kod, "aciklama": aciklama,
                "yeni": yeni_sn, "barkodlar": hamlar,
                "etiket": bos_etiket[0] if bos_etiket else None,
                "raf": raf, "adet_yersiz": adet_yersiz, "sabit_kod": sabit,
                "ses": "uyari"}

    # Lot / izlemesiz: Tiger'da adet başına seri saklanmıyor, boş etiketi
    # bağlayacak kayıt yok. Sayımı yine de işleriz — malzeme doğru tanındı —
    # ama etiket bağlanmaz ve kullanıcı uyarılır, yoksa etiket havuzu sessizce
    # tükenir.
    adet = bekleyen_adet or 1
    etiket_notu = ((" | etiket bağlanmadı: izleme=%s" % izleme) if bos_etiket else "")         + (" | sabit kod: " + sabit if sabit else "")

    # Hangi satır(lar)a yazılacağı önemli.
    #
    # Lot numarası okutulduysa miktarın TAMAMI o satıra yazılır — başka lota
    # taşınmaz. Tiger'da 77 yazan lotta 80 sayıldıysa bu gerçek bir bulgudur;
    # rapor onu adet fazlası olarak gösterir, biz örtmeyiz.
    #
    # Yalnızca malzeme kodu biliniyorsa miktar açık satırlara dağıtılır
    # (`_adet_dagit`): 57 lotluk malzemede ##ADET-5## beş ayrı satıra gider.
    if seri_h:
        b = c.execute("SELECT * FROM beklenen WHERE id=?",
                      (seri_h[1]["id"],)).fetchone()
        pay = [(b, adet)] if b else []
    else:
        pay = _adet_dagit(c, oturum, yukleme, ambar, kod, adet)

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
                   "adet +%g" % m + etiket_notu,
                   _geri_json(ogrenilen) if i == 0 else None))

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
            "satir": len(pay), "ogrenilen": ogrenilen, "raf": raf, "sabit_kod": sabit,
            "etiket_yersiz": bos_etiket[0] if bos_etiket else None,
            "ses": "uyari" if bos_etiket else "ok"}


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
            aday, kaynak = None, None
            for r in c.execute("SELECT ham FROM tampon WHERE oturum=? ORDER BY id",
                               (oturum,)):
                t = coz(c, r["ham"], yukleme, ambar, oturum)
                if t["t"] in ("kod", "ogrenilmis"):
                    aday, kaynak = r["ham"], t
                    break
            if not aday:
                # Son çare: kilitten önce zaten bir ürün sayılmışsa onun kodu.
                x = c.execute("SELECT kod FROM okutma WHERE oturum=? AND kod<>'' "
                              "AND kod IS NOT NULL ORDER BY id DESC LIMIT 1",
                              (oturum,)).fetchone()
                if x:
                    aday, kaynak = x["kod"], coz(c, x["kod"], yukleme, ambar, oturum)
        if not kaynak or not kaynak.get("kod"):
            # Sessizce kilitlememek şart: kullanıcı kilitlendiğini sanıp
            # onlarca seri numarası okutur ve hepsi kuyruğa düşerdi.
            return {"tip": "kilit_yok", "ses": "uyari"}
        kod = kaynak["kod"]
        c.execute("UPDATE oturum SET sabit_kod=? WHERE id=?", (kod, oturum))
        # Kilitlenen kod tampondan düşer: kilit onu zaten temsil ediyor, grupta
        # ikinci kez durursa her ürüne malzeme kodu okutulmuş gibi görünürdü.
        if aday is not None:
            c.execute("DELETE FROM tampon WHERE oturum=? AND ham=?", (oturum, aday))
        return {"tip": "kilit", "kod": kod, "aciklama": kaynak.get("aciklama"),
                "izleme": kaynak.get("izleme"), "ses": "ok"}

    if komut == "kilitac":
        c.execute("UPDATE oturum SET sabit_kod=NULL WHERE id=?", (oturum,))
        return {"tip": "kilitac", "ses": "tik"}

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
        # Boş tampon kontrolü — `##ATLA##` bunu yapıyordu, `##FAZLA##` yapmıyordu.
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
        return {"tip": "fazla_elle", "barkodlar": hs, "okutma": idler,
                "miktar": adet or 1, "ses": "uyari"}

    if komut == "atla":
        hs = [r["ham"] for r in c.execute(
            "SELECT ham FROM tampon WHERE oturum=? ORDER BY id", (oturum,))]
        c.execute("DELETE FROM tampon WHERE oturum=?", (oturum,))
        adet = int(ot["bekleyen_adet"] or 0)
        if adet:
            c.execute("UPDATE oturum SET bekleyen_adet=0 WHERE id=?", (oturum,))
        kid = None
        if hs:
            kid = c.execute("INSERT INTO kuyruk(oturum,ts,barkodlar,raf,adet) "
                            "VALUES(?,?,?,?,?)",
                            (oturum, ts, json.dumps(hs, ensure_ascii=False),
                             ot["aktif_raf"], adet)).lastrowid
        return {"tip": "kuyruk", "kuyruk_id": kid, "barkodlar": hs,
                "miktar": adet or None, "ses": "kuyruk"}

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
        c.execute("UPDATE oturum SET bitir=?, durum='bitti' WHERE id=?", (ts, oturum))
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
        temiz = _yan_etkileri_geri_al(c, x)
        c.execute("DELETE FROM okutma WHERE id=?", (x["id"],))
        return {"tip": "gerial", "kapsam": "okutma", "ham": x["ham"],
                "unutulan": temiz.get("ogrenilen") or [],
                "etiket_cozuldu": temiz.get("etiket"), "ses": "uyari"}
    return {"tip": "bos", "ses": "uyari"}


def okutma_sil(c, ot, okutma_id, kapsam="grup"):
    """Akış listesinden tek bir okutmayı (varsayılan: tüm grubunu) siler.

    `gerial`den farkı: o yalnızca SONUNCUYU alır, bu herhangi bir satırı.
    Sahadaki ihtiyaç bu — yanlış okutma bazen birkaç ürün sonra fark ediliyor.

    Varsayılan kapsam GRUP, çünkü bir grup bir üründür (CLAUDE.md 4.4) ve
    `adet` dalı tek grubu birden çok satıra yazabilir (`_adet_dagit`). O
    satırlarda `geri` yalnızca İLKİNDE durur; satır bazlı silmek öğrenmeyi
    ortada bırakır ya da miktarın bir kısmını geride bırakırdı.

    Yan etkiler `##GERIAL##` ile aynı yoldan geri alınır
    (`_yan_etkileri_geri_al`): öğrenilen barkod unutulur, etiket bağlaması
    çözülür, kuyruk kaydı yeniden açılır. Ayrı bir temizleme kodu YOKTUR.
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
        temiz.update(_yan_etkileri_geri_al(c, r))
    c.execute("DELETE FROM okutma WHERE id IN (%s)"
              % ",".join("?" * len(satirlar)), [r["id"] for r in satirlar])
    return {"tip": "silindi", "silinen": len(satirlar),
            "barkodlar": [r["ham"] for r in satirlar],
            "unutulan": temiz.get("ogrenilen") or [],
            "etiket_cozuldu": temiz.get("etiket"),
            "kuyruk_acildi": temiz.get("kuyruk"), "ses": "uyari"}


# ---------------------------------------------------------------- durum / sayaçlar
def sayaclar(c, ot):
    oturum, yukleme, ambar = ot["id"], ot["yukleme"], ot["ambar"]
    top = c.execute("SELECT COUNT(*) n FROM beklenen WHERE yukleme=? AND ambar=? "
                    "AND haric=0", (yukleme, ambar)).fetchone()["n"]
    ok = c.execute("""SELECT COUNT(DISTINCT o.beklenen_id) n FROM okutma o
                      JOIN beklenen b ON b.id=o.beklenen_id
                      WHERE o.oturum=? AND b.haric=0""", (oturum,)).fetchone()["n"]
    fz = c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND tip='fazla'",
                   (oturum,)).fetchone()["n"]
    ky = c.execute("SELECT COUNT(*) n FROM kuyruk WHERE oturum=? AND cozuldu=0",
                   (oturum,)).fetchone()["n"]
    return {"okutulan": ok, "kalan": top - ok, "fazla": fz, "kuyruk": ky, "toplam": top}


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
        kosul.append("""CASE WHEN b.izleme='seri'
                             THEN NOT EXISTS(SELECT 1 FROM okutma o
                                             WHERE o.oturum=? AND o.beklenen_id=b.id)
                             ELSE COALESCE((SELECT SUM(o.miktar) FROM okutma o
                                            WHERE o.oturum=? AND o.beklenen_id=b.id), 0)
                                  < COALESCE(b.miktar, 0)
                        END""")
        par += [oturum, oturum]
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

    ts = _ts()
    hs = [p.strip() for p in str(x["ham"] or "").split(" + ") if p.strip()]
    # Seri etiketi öğrenilmez: tekil cihaza ait, malzeme seviyesine
    # yükseltilemez (kuyruk_coz ile aynı ayrım).
    for h in hs:
        if etiketler.etiket_turu(h) != "seri":
            c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                      (norm(h), b["kod"], "", ts))
    # `yeni_seri` BURADA da yazılmalı: fazla satırının `beklenen_id`'si şimdi
    # doluyor, yani satır Tiger Düzeltme sorgusuna ilk kez giriyor. Boş
    # bırakılırsa (NULL) rapor eski kurala düşer ve `ham`'daki malzeme kodunu
    # önerebilir — `kuyruk_coz` ile aynı eleme uygulanıyor.
    yeni_es = _fazla_seri(hs, b["kod"])
    if norm(yeni_es) == norm(b["seri"] or ""):
        yeni_es = ""
    c.execute("""UPDATE okutma SET tip='eslesti', beklenen_id=?, kod=?, seri=?,
                 not_='sayım sonu eşleştirildi', geri=?, yeni_seri=? WHERE id=?""",
              (b["id"], b["kod"], b["seri"],
               _geri_json([h for h in hs if etiketler.etiket_turu(h) != "seri"]),
               yeni_es, okutma_id))
    return {"tip": "eslesti", "okutma": okutma_id, "kod": b["kod"],
            "aciklama": b["aciklama"], "seri": b["seri"]}


def elle_say(c, ot, beklenen_id, ham=None):
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

    ts = _ts()
    deger = (ham or "").strip()
    ogrenilen = []
    if deger and etiketler.etiket_turu(deger) != "seri":
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
                       VALUES(?,?,?,?,?,1,?,'eslesti',?,?,'elle işaretlendi',?,?)""",
                    (ot["id"], ts, deger, b["kod"], b["seri"], b["id"],
                     ot["aktif_raf"], grup,
                     _geri_json(ogrenilen, etiket_bagli), yeni_es)).lastrowid
    return {"tip": "eslesti", "okutma": oid, "kod": b["kod"],
            "aciklama": b["aciklama"], "seri": b["seri"],
            "ogrenilen": ogrenilen, "etiket": etiket_bagli,
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
    fazla = [{"id": r["id"], "ts": (r["ts"] or "")[:19].replace("T", " "),
              "ham": r["ham"], "kod": r["kod"], "seri": r["seri"], "ad": r["ad"],
              "raf": r["raf"], "not_": r["not_"] or "",
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
    return {"tip": "fazla", "okutma": idler, "kod": q["kod"], "miktar": miktar}


def kuyruk_coz(c, kuyruk_id, beklenen_id):
    """Kuyruktaki grubu bir malzemeye bağlar; barkodlar kalıcı olarak öğrenilir."""
    q = c.execute("SELECT * FROM kuyruk WHERE id=?", (kuyruk_id,)).fetchone()
    if not q:
        return {"hata": "kuyruk kaydı yok"}
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
    ogrenilecek = [h for h in hs if etiketler.etiket_turu(h) != "seri"]
    bos_etiket = [h for h in hs if etiketler.etiket_mi(h)
                  and c.execute("SELECT 1 FROM etiket WHERE kod=? AND tur='seri' "
                                "AND beklenen_id IS NULL", (norm(h),)).fetchone()]
    for h in ogrenilecek:
        c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                  (norm(h), b["kod"], "", ts))
    if bos_etiket:
        etiketler.bagla(c, bos_etiket[0], b["kod"], b["id"], q["oturum"], ts, q["raf"])
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
                          kuyruk=kuyruk_id), yeni_es))
    c.execute("UPDATE kuyruk SET cozuldu=1 WHERE id=?", (kuyruk_id,))
    return {"tip": "eslesti", "kod": b["kod"], "aciklama": b["aciklama"],
            "seri": b["seri"], "ogrenilen": ogrenilecek, "miktar": miktar,
            "adet_yersiz": adet_yersiz,
            "etiket": bos_etiket[0] if bos_etiket else None}
