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

from .norm import komut_coz, norm, sifirsiz, upc_mi

SAYILMADI = ("AND NOT EXISTS(SELECT 1 FROM okutma o WHERE o.oturum=? "
             "AND o.beklenen_id=b.id)")


def _ts():
    return datetime.datetime.now().isoformat()


def _sayildi(c, oturum, bid):
    return bool(c.execute("SELECT 1 FROM okutma WHERE oturum=? AND beklenen_id=? LIMIT 1",
                          (oturum, bid)).fetchone())


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
        d = {"t": "tekrar" if _sayildi(c, oturum, r["id"]) else "seri", "id": r["id"],
             "kod": r["kod"], "aciklama": r["aciklama"], "seri": r["seri"],
             "izleme": r["izleme"], "birim": r["birim"]}
        if notu:
            d["not"] = notu
        return d

    # 2) Birebir malzeme kodu
    r = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod_n=? "
                  "ORDER BY id LIMIT 1", (yukleme, ambar, n)).fetchone()
    if r:
        return {"t": "kod", "kod": r["kod"], "aciklama": r["aciklama"],
                "izleme": r["izleme"], "birim": r["birim"]}

    # 3) Kod öneki: ARK-1250L-S5A1 -> ARK1250LS5A1ATR8641924 (her iki taraf >= 8)
    if len(n) >= 8:
        r = c.execute("""SELECT * FROM beklenen WHERE yukleme=? AND ambar=?
                         AND LENGTH(kod_n)>=8
                         AND (kod_n LIKE ?||'%' OR ? LIKE kod_n||'%')
                         ORDER BY id LIMIT 1""",
                      (yukleme, ambar, n, n)).fetchone()
        if r:
            return {"t": "kod", "kod": r["kod"], "aciklama": r["aciklama"],
                    "izleme": r["izleme"], "birim": r["birim"], "not": "önek eşleşmesi"}

    # 4) Öğrenilmiş eşleşme
    e = c.execute("SELECT * FROM eslesme WHERE barkod=?", (n,)).fetchone()
    if e:
        r = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                      "ORDER BY id LIMIT 1", (yukleme, ambar, e["kod"])).fetchone()
        if r:
            return {"t": "ogrenilmis", "kod": r["kod"], "aciklama": r["aciklama"],
                    "izleme": r["izleme"], "birim": r["birim"]}

    # 5) İçerme: gerçek S/N kirli kaydın içine gömülmüş olabilir
    if len(n) >= 6:
        r = c.execute("""SELECT * FROM beklenen b WHERE yukleme=? AND ambar=?
                         AND izleme='seri' AND kirli=1 AND INSTR(seri_n, ?)>0
                         AND kod_n<>? """ + SAYILMADI + " ORDER BY id LIMIT 1",
                      (yukleme, ambar, n, n, oturum)).fetchone()
        if r:
            return {"t": "seri", "id": r["id"], "kod": r["kod"],
                    "aciklama": r["aciklama"], "seri": r["seri"],
                    "izleme": r["izleme"], "birim": r["birim"], "not": "gömülü S/N"}

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

    grup = _yeni_grup(c, oturum)
    coz_list = [(h, coz(c, h, yukleme, ambar, oturum)) for h in hamlar]

    seri_h = next((x for x in coz_list if x[1]["t"] == "seri"), None)
    kod_h = next((x for x in coz_list if x[1]["t"] in ("kod", "ogrenilmis")), None)
    tekrar = next((x for x in coz_list if x[1]["t"] == "tekrar"), None)
    bilinmeyen = [h for h, r in coz_list if r["t"] in ("bilinmiyor", "upc")]

    if tekrar and not seri_h:
        return {"tip": "tekrar", "kod": tekrar[1]["kod"], "seri": tekrar[1]["seri"],
                "ses": "uyari"}

    kaynak = seri_h or kod_h
    if not kaynak:
        kid = c.execute("INSERT INTO kuyruk(oturum,ts,barkodlar,raf) VALUES(?,?,?,?)",
                        (oturum, ts, json.dumps(hamlar, ensure_ascii=False),
                         raf)).lastrowid
        return {"tip": "kuyruk", "kuyruk_id": kid, "barkodlar": hamlar, "raf": raf,
                "ses": "kuyruk"}

    kod = kaynak[1]["kod"]
    aciklama = kaynak[1]["aciklama"]

    # bilinmeyen barkodları bu malzemeye öğret
    ogrenilen = []
    for h in bilinmeyen:
        c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)", (norm(h), kod, "", ts))
        ogrenilen.append(h)

    if seri_h:
        r = seri_h[1]
        notu = (r.get("not") or "")
        if ogrenilen:
            notu += " | öğrenildi: " + ",".join(ogrenilen)
        c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,tip,
                     raf,grup,not_) VALUES(?,?,?,?,?,1,?,'eslesti',?,?,?)""",
                  (oturum, ts, seri_h[0], kod, r["seri"], r["id"], raf, grup, notu))
        return {"tip": "eslesti", "kod": kod, "aciklama": aciklama, "seri": r["seri"],
                "ogrenilen": ogrenilen, "raf": raf, "not": notu.strip(" |"), "ses": "ok"}

    # Malzeme belli ama seri eşleşmedi
    izleme = kaynak[1].get("izleme", "yok")
    if izleme == "seri":
        slot = c.execute("""SELECT * FROM beklenen b WHERE yukleme=? AND ambar=? AND kod=?
                            AND kirli=1 """ + SAYILMADI + " ORDER BY id LIMIT 1",
                         (yukleme, ambar, kod, oturum)).fetchone()
        yeni_sn = max(bilinmeyen, key=len) if bilinmeyen else ""
        if slot:
            c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,
                         tip,raf,grup,not_)
                         VALUES(?,?,?,?,?,1,?,'eslesti',?,?,'slot dolduruldu')""",
                      (oturum, ts, yeni_sn or kod, kod, slot["seri"], slot["id"],
                       raf, grup))
            return {"tip": "slot", "kod": kod, "aciklama": aciklama, "eski": slot["seri"],
                    "yeni": yeni_sn, "raf": raf, "ses": "ok"}
        c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,tip,raf,grup,not_)
                     VALUES(?,?,?,?,?,1,'fazla',?,?,'seri takipli, karşılığı yok')""",
                  (oturum, ts, yeni_sn or kod, kod, yeni_sn, raf, grup))
        return {"tip": "fazla", "kod": kod, "aciklama": aciklama, "yeni": yeni_sn,
                "raf": raf, "ses": "uyari"}

    b = c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? AND kod=? "
                  "ORDER BY id LIMIT 1", (yukleme, ambar, kod)).fetchone()
    c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,tip,raf,
                 grup,not_) VALUES(?,?,?,?,?,1,?,'kod',?,?,'adet +1')""",
              (oturum, ts, kaynak[0], kod, b["seri"] if b else "",
               b["id"] if b else None, raf, grup))
    top = c.execute("SELECT SUM(miktar) s FROM okutma WHERE oturum=? AND kod=?",
                    (oturum, kod)).fetchone()["s"]
    return {"tip": "adet", "kod": kod, "aciklama": aciklama, "toplam": top,
            "beklenen": b["miktar"] if b else 0, "ogrenilen": ogrenilen, "raf": raf,
            "ses": "ok"}


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
             "beklet": bool(r["beklet"])}
            for r in c.execute(sql + " ORDER BY id", par)]


def adaylar(c, ot, limit=5):
    """Tanınmayan grup için olası malzemeler.

    Sıralama sahadaki gerçeğe göre: (1) bu rafta aynı koddan zaten sayılmış
    olanlar — raf komşuluğu en güçlü ipucu, (2) açık kirli slotu olanlar —
    uydurma kayıt zaten gerçek S/N'in yerini tutuyor, (3) açık satırı çok olan.
    Sadece öneridir, hiçbir eşleştirme kararını değiştirmez.
    """
    raf = ot["aktif_raf"] or ""
    rs = c.execute("""
        SELECT b.kod, b.aciklama, b.izleme, b.birim, MIN(b.id) id,
               SUM(b.kirli) acik_kirli, COUNT(*) acik_satir, SUM(b.miktar) acik_adet,
               (SELECT COUNT(*) FROM okutma o2 WHERE o2.oturum=? AND o2.kod=b.kod
                AND COALESCE(o2.raf,'')=?) ayni_raf
        FROM beklenen b
        WHERE b.yukleme=? AND b.ambar=? AND b.haric=0
          AND CASE WHEN b.izleme='seri'
                   THEN NOT EXISTS(SELECT 1 FROM okutma o
                                   WHERE o.oturum=? AND o.beklenen_id=b.id)
                   -- lot / izlemesiz: bir kez okutulmuş olması bitti demek değil
                   ELSE COALESCE((SELECT SUM(o.miktar) FROM okutma o
                                  WHERE o.oturum=? AND o.beklenen_id=b.id), 0)
                        < COALESCE(b.miktar, 0)
              END
        GROUP BY b.kod
        ORDER BY ayni_raf DESC, acik_kirli DESC, acik_satir DESC, id
        LIMIT ?""",
        (ot["id"], raf, ot["yukleme"], ot["ambar"], ot["id"], ot["id"],
         limit)).fetchall()
    return [dict(r) for r in rs]


def _adayli(c, ot, sonuc):
    """Kuyruğa düşen gruba olası malzemeleri iliştirir (yalnızca öneri)."""
    if sonuc.get("tip") == "kuyruk" and sonuc.get("kuyruk_id"):
        sonuc["adaylar"] = adaylar(c, ot)
    return sonuc


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
    komut, raf_adi = komut_coz(ham)

    if komut == "sonraki":
        return _adayli(c, ot, grup_coz(c, ot))

    if komut == "iptal":
        c.execute("DELETE FROM tampon WHERE oturum=?", (oturum,))
        return {"tip": "iptal", "ses": "uyari"}

    if komut == "gerial":
        return gerial(c, ot)

    if komut == "fazla":
        hs = [r["ham"] for r in c.execute(
            "SELECT ham FROM tampon WHERE oturum=? ORDER BY id", (oturum,))]
        c.execute("DELETE FROM tampon WHERE oturum=?", (oturum,))
        grup = _yeni_grup(c, oturum)
        for h in hs or [""]:
            c.execute("INSERT INTO okutma(oturum,ts,ham,miktar,tip,raf,grup,not_) "
                      "VALUES(?,?,?,1,'fazla',?,?,'elle işaretlendi')",
                      (oturum, ts, h, ot["aktif_raf"], grup))
        return {"tip": "fazla_elle", "barkodlar": hs, "ses": "uyari"}

    if komut == "atla":
        hs = [r["ham"] for r in c.execute(
            "SELECT ham FROM tampon WHERE oturum=? ORDER BY id", (oturum,))]
        c.execute("DELETE FROM tampon WHERE oturum=?", (oturum,))
        kid = None
        if hs:
            kid = c.execute("INSERT INTO kuyruk(oturum,ts,barkodlar,raf) "
                            "VALUES(?,?,?,?)",
                            (oturum, ts, json.dumps(hs, ensure_ascii=False),
                             ot["aktif_raf"])).lastrowid
        return _adayli(c, ot, {"tip": "kuyruk", "kuyruk_id": kid, "barkodlar": hs,
                               "ses": "kuyruk"})

    if komut == "bitir":
        bekleyen = bekleyen_kuyruk(c, oturum)
        if bekleyen and not zorla:
            return {"tip": "bitir_engel", "kuyruk": bekleyen, "ses": "uyari"}
        grup_coz(c, ot)
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
            hs = [r["ham"] for r in c.execute(
                "SELECT ham FROM okutma WHERE oturum=? AND grup=? ORDER BY id",
                (oturum, g))]
            c.execute("DELETE FROM okutma WHERE oturum=? AND grup=?", (oturum, g))
            return {"tip": "gerial", "kapsam": "grup", "grup": g, "barkodlar": hs,
                    "ses": "uyari"}
        return {"tip": "bos", "ses": "uyari"}

    l = c.execute("SELECT id,ham FROM tampon WHERE oturum=? ORDER BY id DESC LIMIT 1",
                  (oturum,)).fetchone()
    if l:
        c.execute("DELETE FROM tampon WHERE id=?", (l["id"],))
        return {"tip": "gerial", "kapsam": "tampon", "ham": l["ham"], "ses": "uyari"}
    x = c.execute("SELECT id,ham FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                  (oturum,)).fetchone()
    if x:
        c.execute("DELETE FROM okutma WHERE id=?", (x["id"],))
        return {"tip": "gerial", "kapsam": "okutma", "ham": x["ham"], "ses": "uyari"}
    return {"tip": "bos", "ses": "uyari"}


# ---------------------------------------------------------------- durum / sayaçlar
def sayaclar(c, ot):
    oturum, yukleme, ambar = ot["id"], ot["yukleme"], ot["ambar"]
    top = c.execute("SELECT COUNT(*) n FROM beklenen WHERE yukleme=? AND ambar=? "
                    "AND haric=0", (yukleme, ambar)).fetchone()["n"]
    ok = c.execute("""SELECT COUNT(DISTINCT o.beklenen_id) n FROM okutma o
                      JOIN beklenen b ON b.id=o.beklenen_id
                      WHERE o.oturum=? AND b.haric=0""", (oturum,)).fetchone()["n"]
    fz = c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND tip IN "
                   "('fazla','bilinmiyor')", (oturum,)).fetchone()["n"]
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
    son = [dict(r) for r in c.execute(
        "SELECT ts,ham,kod,seri,tip,raf,not_ FROM okutma WHERE oturum=? "
        "ORDER BY id DESC LIMIT ?", (oturum, akis))]
    return {"oturum": oturum, "yukleme": yukleme, "ambar": ambar,
            "aktif_raf": ot["aktif_raf"], "durum": ot["durum"],
            "sayac": sayaclar(c, ot), "tampon": tampon, "akis": son}


def ara(c, yukleme, ambar, q, limit=25, oturum=None):
    """Kuyruk ekranı için malzeme arama — kirli kayıtlılar üstte.

    oturum verilirse her satır bu oturumda sayılıp sayılmadığını da taşır;
    kullanıcı aynı kaydı ikinci kez bağlamasın diye arayüz uyarır.
    """
    like = "%" + (q or "") + "%"
    rs = c.execute("""SELECT b.id, b.kod, b.aciklama, b.seri, b.kirli, b.izleme,
                      b.miktar, b.birim,
                      EXISTS(SELECT 1 FROM okutma o WHERE o.oturum=?
                             AND o.beklenen_id=b.id) sayildi
                      FROM beklenen b WHERE b.yukleme=? AND b.ambar=?
                      AND (b.kod LIKE ? OR b.aciklama LIKE ?)
                      ORDER BY sayildi, b.kirli DESC, b.id LIMIT ?""",
                   (oturum, yukleme, ambar, like, like, limit)).fetchall()
    return [dict(r) for r in rs]


def kuyruk_coz(c, kuyruk_id, beklenen_id):
    """Kuyruktaki grubu bir malzemeye bağlar; barkodlar kalıcı olarak öğrenilir."""
    q = c.execute("SELECT * FROM kuyruk WHERE id=?", (kuyruk_id,)).fetchone()
    if not q:
        return {"hata": "kuyruk kaydı yok"}
    b = c.execute("SELECT * FROM beklenen WHERE id=?", (beklenen_id,)).fetchone()
    if not b:
        return {"hata": "malzeme yok"}
    ts = _ts()
    hs = json.loads(q["barkodlar"])
    for h in hs:
        c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                  (norm(h), b["kod"], "", ts))
    grup = _yeni_grup(c, q["oturum"])
    c.execute("""INSERT INTO okutma(oturum,ts,ham,kod,seri,miktar,beklenen_id,tip,raf,
                 grup,not_) VALUES(?,?,?,?,?,1,?,'eslesti',?,?,'kuyruktan çözüldü')""",
              (q["oturum"], ts, " + ".join(hs), b["kod"], b["seri"], b["id"],
               q["raf"], grup))
    c.execute("UPDATE kuyruk SET cozuldu=1 WHERE id=?", (kuyruk_id,))
    return {"tip": "eslesti", "kod": b["kod"], "aciklama": b["aciklama"],
            "seri": b["seri"], "ogrenilen": hs}
