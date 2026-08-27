"""Oturum yaşam döngüsü.

Oturum bir yüklemeye ve bir ambara bağlıdır. Aynı anda tek açık oturum olur;
uygulama kapanıp açılsa bile arayüz acik() ile kaldığı yerden devam eder.
"""
import datetime


def ac(c, yukleme, ambar):
    ts = datetime.datetime.now().isoformat()
    var = acik(c)
    if var:
        return var
    oid = c.execute("INSERT INTO oturum(yukleme,ambar,basla,durum) VALUES(?,?,?,'acik')",
                    (yukleme, str(ambar), ts)).lastrowid
    c.commit()
    return getir(c, oid)


def acik(c):
    return c.execute("SELECT * FROM oturum WHERE bitir IS NULL ORDER BY id DESC "
                     "LIMIT 1").fetchone()


def getir(c, oturum_id):
    return c.execute("SELECT * FROM oturum WHERE id=?", (oturum_id,)).fetchone()


def bitir(c, oturum_id):
    """Oturumu kapatır. Açık kap varsa ÖNCE o kapanır.

    İki `##BITIR##` yolu (komut barkodu ve /bitir ucu) burada birleşiyor;
    kapatmayı ikisine ayrı ayrı yazmak, birinde unutulması demekti. Açık kap
    kapanmadan oturum biterse kabın son bilinen adedi bu sayımla tazelenmez ve
    gelecek yıl kap eski sayıyı önerir.
    """
    from . import matching
    ot = getir(c, oturum_id)
    if ot and ot["acik_kutu"]:
        matching._kutu_kapat(c, ot)
    ts = datetime.datetime.now().isoformat()
    c.execute("UPDATE oturum SET bitir=?, durum='bitti' WHERE id=? AND bitir IS NULL",
              (ts, oturum_id))
    c.commit()
    return getir(c, oturum_id)


def gecmis(c):
    rs = c.execute("""SELECT o.*, y.dosya_adi,
                      (SELECT COUNT(DISTINCT beklenen_id) FROM okutma
                       WHERE oturum=o.id AND beklenen_id IS NOT NULL) okutulan,
                      (SELECT COUNT(*) FROM okutma
                       WHERE oturum=o.id AND tip='fazla') fazla,
                      (SELECT COUNT(*) FROM kuyruk WHERE oturum=o.id AND cozuldu=0) kuyruk
                      FROM oturum o LEFT JOIN yukleme y ON y.id=o.yukleme
                      ORDER BY o.id DESC""").fetchall()
    return [dict(r) for r in rs]
