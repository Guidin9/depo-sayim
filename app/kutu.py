"""Kap defteri — "bu kapta ne var" (KUTU_TASARIM.md).

Dördüncü soru. `##RAF-A1##` "nerede duruyorum", `DM-` "ne bu", `DS-` "hangisi
bu", `DK-` ise "bu kapta ne var" der (CLAUDE.md 12.1 + KUTU_TASARIM.md 2).

İki şey ayrı tutulur ve bu ayrım tasarımın tamamıdır:

  MALZEME BAĞI kalıcıdır.  Kap ayda bir boşalıp dolabilir ama M.2 SSD
      kutusuna ertesi ay switch konmaz. Kazanç burada: kutu okutulunca malzeme,
      izleme yöntemi ve raf anında gelir — kullanıcı 150 kalemlik listede
      malzeme aramaz.
  ADET kalıcı DEĞİLDİR.  Saha cevabı (2026-08-27): içerik ayda bir civarında
      değişiyor, sayım ise yılda bir yapılıyor. Sayım anında `adet` alanının
      doğru olma ihtimali pratikte sıfırdır. Bu yüzden `adet` bir gerçek değil,
      girdi alanının VARSAYILANIDIR ve tazelik kuralına tabidir (`taze_mi`).

Kutuya körü körüne güvenmek, uygulamanın kendi bayat verisini sayım sonucu
diye onaylaması olurdu — Tiger'ın Ambar Sayımı ekranındaki "Sayım Miktarı
fiili stokla dolu gelir" tuzağının (CLAUDE.md 6) bizim tarafımızdaki hâli.
"""
import csv
import datetime
import os

from .norm import norm

# Bir kutu kaydının adedi kaç gün "taze" sayılır. Bunun üstünde adet alanı
# EKRANA BOŞ gelir; son bilinen değer yalnızca gri bir ipucu olarak durur.
# Yıllık sayımda pratikte hep bu dal işler; taze dal aynı kabın kısa aralıkla
# iki kez sayıldığı durum içindir (raf tekrarı, kısmi sayım).
TAZELIK_GUN = 30

BASLIK = ["kod", "gosterim", "malzeme", "adet", "izleme", "raf", "ts",
          "ts_guncelle"]


def _ts():
    return datetime.datetime.now().isoformat()


def getir(c, kod):
    return c.execute("SELECT * FROM kutu WHERE kod=?", (norm(kod),)).fetchone()


def yas_gun(satir):
    """Adet en son kaç gün önce doğrulandı? Bilinmiyorsa None."""
    ham = (satir["ts_guncelle"] or satir["ts"]) if satir else None
    if not ham:
        return None
    try:
        t = datetime.datetime.fromisoformat(ham)
    except ValueError:
        return None
    return max(0.0, (datetime.datetime.now() - t).total_seconds() / 86400.0)


def taze_mi(satir, gun=TAZELIK_GUN):
    y = yas_gun(satir)
    return y is not None and y <= gun


def tanimla(c, kod, malzeme, adet, izleme, raf=None, oturum=None, ts=None):
    """Kabın içeriğini yazar ya da günceller. `ts_guncelle` her yazmada tazelenir.

    `kod` basılmış ama `etiket` defterinde yoksa oraya da yazılır: defter
    sıfırlanmış bir makinede kap tanımlanabilmeli, ama sayaç o numarayı ikinci
    kez vermemeli (CLAUDE.md 12.7).
    """
    n, ts = norm(kod), ts or _ts()
    g = str(kod).strip().upper()
    var = getir(c, n)
    c.execute("INSERT OR IGNORE INTO etiket(kod,gosterim,tur,ts) VALUES(?,?,'kutu',?)",
              (n, var["gosterim"] if var else g, ts))
    if var:
        c.execute("""UPDATE kutu SET malzeme=?, adet=?, izleme=?, raf=COALESCE(?,raf),
                     ts_guncelle=? WHERE kod=?""",
                  (malzeme, adet, izleme, raf, ts, n))
    else:
        c.execute("""INSERT INTO kutu(kod,gosterim,malzeme,adet,izleme,raf,ts,
                     ts_guncelle,oturum) VALUES(?,?,?,?,?,?,?,?,?)""",
                  (n, g, malzeme, adet, izleme, raf, ts, ts, oturum))
    csv_yaz(c)
    return getir(c, n)


def bosalt(c, kod):
    """Kabın içerik bağını siler — kap boşaldı ya da başka bir işe ayrıldı.

    Kayıt SİLİNMEZ, malzemesi boşaltılır: kabın kendisi hâlâ depoda ve numarası
    tüketilmiş durumda. Bir sonraki okutmada "tanımsız kap" olarak sorulur.
    """
    n = norm(kod)
    if not getir(c, n):
        return None
    c.execute("UPDATE kutu SET malzeme=NULL, adet=NULL, izleme=NULL, ts_guncelle=? "
              "WHERE kod=?", (_ts(), n))
    csv_yaz(c)
    return getir(c, n)


ANLIK_ALAN = ("malzeme", "adet", "izleme", "raf", "ts", "ts_guncelle")


def anlik(c, kod):
    """Kap kaydının şu anki fotoğrafı — `##GERIAL##` için.

    Kayıt yoksa None döner ve geri alma onu SİLER. Olmadan: yanlış okutulup
    geri alınan bir kap, kaydında yeni adet ve taze `ts_guncelle` ile kalırdı;
    bir sonraki okutmada kullanıcının az önce reddettiği sayı önerilirdi.
    """
    r = getir(c, kod)
    return {a: r[a] for a in ANLIK_ALAN} if r else None


def geri_al(c, kod, onceki):
    """Kap kaydını `anlik()` ile alınmış hâline döndürür."""
    n = norm(kod)
    if onceki is None:
        c.execute("DELETE FROM kutu WHERE kod=?", (n,))
    else:
        c.execute("""UPDATE kutu SET malzeme=?, adet=?, izleme=?, raf=?, ts=?,
                     ts_guncelle=? WHERE kod=?""",
                  tuple(onceki.get(a) for a in ANLIK_ALAN) + (n,))
    csv_yaz(c)


def gorunum(c, satir, yukleme=None, ambar=None):
    """Ekranın kap hakkında bilmesi gereken her şey — tazelik kararı dahil.

    `oneri_adet` yalnızca kayıt tazeyse doludur. Bayat kayıtta None döner ve
    arayüz adet alanını BOŞ açar; son bilinen değer `adet` alanında ipucu
    olarak durmaya devam eder.
    """
    if not satir:
        return None
    y = yas_gun(satir)
    taze = taze_mi(satir)
    aciklama = None
    bulundu = None
    if satir["malzeme"] and yukleme is not None and ambar is not None:
        r = c.execute("SELECT aciklama, izleme FROM beklenen WHERE yukleme=? AND "
                      "ambar=? AND kod=? LIMIT 1",
                      (yukleme, ambar, satir["malzeme"])).fetchone()
        bulundu = bool(r)
        if r:
            aciklama = r["aciklama"]
    return {"kod": satir["kod"], "gosterim": satir["gosterim"],
            "malzeme": satir["malzeme"], "aciklama": aciklama,
            "adet": satir["adet"], "izleme": satir["izleme"], "raf": satir["raf"],
            "yas_gun": None if y is None else round(y, 1), "taze": taze,
            "tazelik_gun": TAZELIK_GUN,
            "oneri_adet": satir["adet"] if taze else None,
            "bu_ambarda": bulundu,
            "ts": satir["ts"], "ts_guncelle": satir["ts_guncelle"]}


def liste(c, q=None, sadece_tanimli=False, limit=500):
    """Kap defteri: BASILMIŞ her kap, içeriği varsa içeriğiyle.

    Kaynak `etiket` tablosu, `kutu` değil. Sebep: kap etiketi basıldığında
    anonimdir (`kutu` satırı ilk tanımlamada doğar). Yalnızca `kutu`ya
    bakılsaydı 24 kap etiketi basan kullanıcı "kap defteri boş" görürdü —
    oysa kaplar elinde duruyor, yalnızca içerikleri henüz sorulmadı.
    """
    sql = ["""SELECT e.kod, e.gosterim, k.malzeme, k.adet, k.izleme,
                     COALESCE(k.raf, e.raf) raf, COALESCE(k.ts, e.ts) ts,
                     k.ts_guncelle, k.oturum,
                     (SELECT aciklama FROM beklenen WHERE kod=k.malzeme
                      ORDER BY yukleme DESC LIMIT 1) aciklama
              FROM etiket e LEFT JOIN kutu k ON k.kod=e.kod
              WHERE e.tur='kutu'"""]
    par = []
    if q:
        sql.append("AND (e.gosterim LIKE ? OR k.malzeme LIKE ?)")
        par += ["%" + q + "%"] * 2
    if sadece_tanimli:
        sql.append("AND COALESCE(k.malzeme,'')<>''")
    sql.append("ORDER BY e.kod LIMIT ?")
    par.append(limit)
    cikti = []
    for r in c.execute(" ".join(sql), par):
        d = dict(r)
        # Tazelik yalnızca İÇERİĞİ olan kap için anlamlı: boş kapta `ts`
        # basım tarihidir, "adet ne zaman doğrulandı" değil.
        y = yas_gun(r) if r["malzeme"] else None
        d["yas_gun"] = None if y is None else round(y, 1)
        d["taze"] = bool(r["malzeme"]) and taze_mi(r)
        cikti.append(d)
    return cikti


# ------------------------------------------------------- sıfırlamaya dayanma
def _yol(c):
    from .etiketler import klasor
    return os.path.join(klasor(c), "kutu.csv")


def csv_yaz(c):
    """Kap defterini veritabanı dışına da yazar.

    `etiketler.csv_yaz` ile aynı gerekçe, bir adım ötesi: sifirla.bat
    `data\\*.db` dosyalarını yedeğe taşıyor ama `data/etiket` klasörüne
    dokunmuyor. Yalnızca etiket numaraları geri gelseydi depodaki 100 kabın
    hepsi yeniden "tanımsız" olurdu ve kalıcı kutu kaydının tek kazancı
    (malzemeyi tek okutmada bilmek) sıfırlanırdı.

    Defter küçük (kap sayısı kadar satır), o yüzden her değişiklikte tamamı
    yeniden yazılıyor — artımlı yazmanın tutarsız kalma riski yok.
    """
    satirlar = c.execute("SELECT * FROM kutu ORDER BY kod").fetchall()
    yol = _yol(c)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", newline="", encoding="utf-8") as f:
        y = csv.DictWriter(f, BASLIK, extrasaction="ignore")
        y.writeheader()
        for s in satirlar:
            y.writerow({a: s[a] for a in BASLIK})
    return yol


def csv_geri_yukle(c):
    """Kap defteri boşsa CSV'den geri okur. Dolu defterde hiçbir şey yapmaz."""
    yol = _yol(c)
    if not os.path.isfile(yol):
        return 0
    if c.execute("SELECT 1 FROM kutu LIMIT 1").fetchone():
        return 0
    n = 0
    with open(yol, newline="", encoding="utf-8") as f:
        for s in csv.DictReader(f):
            if not s.get("kod"):
                continue
            c.execute("""INSERT OR IGNORE INTO kutu(kod,gosterim,malzeme,adet,izleme,
                         raf,ts,ts_guncelle) VALUES(?,?,?,?,?,?,?,?)""",
                      (s["kod"], s.get("gosterim"), s.get("malzeme") or None,
                       float(s["adet"]) if s.get("adet") else None,
                       s.get("izleme") or None, s.get("raf") or None,
                       s.get("ts"), s.get("ts_guncelle")))
            # Etiket defteri de sıfırlanmış olabilir: kap numarası basılmış
            # sayılmalı, yoksa sayaç aynı numarayı ikinci kez verir.
            c.execute("INSERT OR IGNORE INTO etiket(kod,gosterim,tur,ts) "
                      "VALUES(?,?,'kutu',?)",
                      (s["kod"], s.get("gosterim"), s.get("ts")))
            n += 1
    return n
