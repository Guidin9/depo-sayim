"""Komut satırı — sunucuyu ayağa kaldırmadan yükleme ve rapor doğrulaması.

    python -m app.cli yukle deneme.XLSX [--yukleme 1]
    python -m app.cli ozet [yukleme_id]
    python -m app.cli kurallar [yukleme_id]
    python -m app.cli oturumlar
    python -m app.cli rapor <oturum_id> [cikti.xlsx]
"""
import sys

from . import db as dbm
from . import importer, oturumlar, reports


def _ozet_yaz(o):
    print("Yüklendi: %s satır  (%s)  -> yükleme #%s"
          % (o["satir"], o["kaynak"], o["yukleme"]))
    for r in o["izleme"]:
        print("   %-5s satır=%-5s malzeme=%-5s adet=%-7g kirli=%s"
              % (r["izleme"], r["satir"], r["malzeme"], r["adet"] or 0, r["kirli"] or 0))
    if o["kirli_sebep"]:
        print("   kirli sebepleri: " +
              ", ".join("%s=%s" % (r["sebep"], r["satir"]) for r in o["kirli_sebep"]))
    print("   ambarlar: " +
          ", ".join("%s (%s satır)" % (r["ambar"], r["satir"]) for r in o["ambarlar"]))
    print("   sayım dışı: %s satır / %g adet" % (o["haric"]["satir"], o["haric"]["adet"]))


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv:
        print(__doc__)
        return 1
    komut, argv = argv[0], argv[1:]
    c = dbm.baglan()

    if komut == "yukle":
        if not argv:
            print("Kullanım: python -m app.cli yukle <rapor.xlsx|rapor.json>")
            return 1
        yid = None
        if "--yukleme" in argv:
            i = argv.index("--yukleme")
            yid = int(argv[i + 1])
            del argv[i:i + 2]
        try:
            _ozet_yaz(importer.yukle(c, argv[0], yukleme_id=yid))
        except importer.YuklemeHatasi as e:
            print("HATA: %s" % e)
            return 2
        kurallar = [k for k in importer.kural_ozeti(c, 1) if k["satir"]]
        if kurallar:
            print("\nSayım dışı kurallarını Kurulum ekranında gözden geçirin:")
            for k in kurallar:
                print("   [%s] %-14s %-16s %s satır"
                      % ("x" if k["aktif"] else " ", k["tip"], k["desen"], k["satir"]))
        return 0

    if komut == "ozet":
        yid = int(argv[0]) if argv else _son_yukleme(c)
        _ozet_yaz(importer.ozetle(c, yid))
        return 0

    if komut == "kurallar":
        yid = int(argv[0]) if argv else _son_yukleme(c)
        for k in importer.kural_ozeti(c, yid):
            print("#%-3s [%s] %-9s %-16s satır=%-4s adet=%g"
                  % (k["id"], "x" if k["aktif"] else " ", k["tip"], k["desen"],
                     k["satir"], k["adet"]))
        return 0

    if komut == "oturumlar":
        for o in oturumlar.gecmis(c):
            print("#%-3s ambar=%-4s %s  okutulan=%-5s fazla=%-4s kuyruk=%-3s %s"
                  % (o["id"], o["ambar"], (o["basla"] or "")[:19], o["okutulan"],
                     o["fazla"], o["kuyruk"], o["durum"]))
        return 0

    if komut == "rapor":
        if not argv:
            print("Kullanım: python -m app.cli rapor <oturum_id> [cikti.xlsx]")
            return 1
        oid = int(argv[0])
        yol = argv[1] if len(argv) > 1 else reports.rapor_yolu(oid)
        ozet = reports.excel_yaz(c, oid, yol)
        print("Rapor yazıldı: %s" % yol)
        print("   " + "  ".join("%s=%s" % (k, v) for k, v in ozet["sayilar"].items()))
        if ozet["haric"]:
            print("   sayım dışı: %s kalem" % ozet["haric"])
        return 0

    print("Bilinmeyen komut: %s\n%s" % (komut, __doc__))
    return 1


def _son_yukleme(c):
    r = c.execute("SELECT id FROM yukleme ORDER BY id DESC LIMIT 1").fetchone()
    if not r:
        raise SystemExit("Önce bir rapor yükleyin.")
    return r["id"]


if __name__ == "__main__":
    raise SystemExit(main())
