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
