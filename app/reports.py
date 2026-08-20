"""5 sekmeli sayım raporu (CLAUDE.md 5).

depo_sayim.py:307-375 taşındı. Sekme adları ve sütun düzeni korundu, üstüne:
  * Fazla / Eşleşen / Tiger Düzeltme sekmelerine Raf sütunu
  * Eksik sekmesi sayım dışı kalemleri listelemez, sayıyı dipnot olarak yazar
  * Lot ve izlemesiz kalemlerde adet farkı hesaplanır (seri takipli kalemlerde
    prototipteki davranış aynen korunur: okutulmayan satır eksiktir)

rapor_verisi() hem Excel yazıcısını hem arayüzdeki sekme önizlemesini besler ki
iki yerde iki ayrı gerçek olmasın.
"""
import os

SEKME = ("Eksik", "Fazla", "Eşleşen", "Tiger Düzeltme", "Barkod Tablosu")

BASLIKLAR = {
    "Eksik": ["Malzeme Kodu", "Açıklama", "Beklenen Seri/Lot", "İzleme", "Miktar",
              "Birim", "Not"],
    "Fazla": ["Zaman", "Raf", "Okutulan", "Malzeme Kodu", "Açıklama", "Seri",
              "Miktar", "Not"],
    "Eşleşen": ["Zaman", "Raf", "Malzeme Kodu", "Açıklama", "Seri/Lot", "Miktar",
                "Tip", "Not"],
    "Tiger Düzeltme": ["Malzeme Kodu", "Açıklama", "MEVCUT (hatalı) Seri No",
                       "YENİ (gerçek) Seri No", "Raf", "Zaman"],
    "Barkod Tablosu": ["Okutulan Barkod", "Malzeme Kodu", "Açıklama",
                       "Öğrenildiği An"],
}

DIPNOT = {
    "Tiger Düzeltme": ["Bu sayfadaki kayıtlar Tiger'da seri numarası düzeltmesi "
                       "gerektirir.", "Ambar Sayımı ekranından fiş oluştururken "
                       "kullanın."],
    "Barkod Tablosu": ["Bu barkodları Tiger'da malzeme kartı > Birimler > Barkod "
                       "alanına yazın.", "Yazdıktan sonra bu ürünler sorusuz eşleşir."],
}


def _kisa(ts):
    return (ts or "")[:19].replace("T", " ")


def _yeni_seri(ham):
    """Tiger'a yazılacak gerçek seri numarasını seçer.

    Kuyruktan çözülen grupta okutma 'A + B' biçiminde saklanır (denetim izi).
    Tiger Düzeltme sekmesine tek bir değer yazılmalı: perakende barkodu olmayan
    en uzun parça — grup çözümlemesindeki kuralın aynısı (matching.grup_coz).
    """
    from .norm import upc_mi
    parcalar = [p.strip() for p in str(ham or "").split(" + ") if p.strip()]
    if len(parcalar) <= 1:
        return ham
    adaylar = [p for p in parcalar if not upc_mi(p)] or parcalar
    return max(adaylar, key=len)


def rapor_verisi(c, oturum_id):
    """Sekme adı -> {basliklar, satirlar, dipnot} sözlüğü."""
    o = c.execute("SELECT * FROM oturum WHERE id=?", (oturum_id,)).fetchone()
    if not o:
        raise ValueError("Oturum #%s bulunamadı" % oturum_id)
    yukleme, ambar = o["yukleme"], o["ambar"]

    sayilan = {r["beklenen_id"]: r["adet"] for r in c.execute(
        "SELECT beklenen_id, SUM(miktar) adet FROM okutma WHERE oturum=? "
        "AND beklenen_id IS NOT NULL GROUP BY beklenen_id", (oturum_id,))}

    eksik, adet_fazlasi = [], []
    haric_sayisi = 0
    for r in c.execute("SELECT * FROM beklenen WHERE yukleme=? AND ambar=? ORDER BY id",
                       (yukleme, ambar)):
        if r["haric"]:
            haric_sayisi += 1
            continue
        okunan = sayilan.get(r["id"], 0)
        if r["izleme"] == "seri":
            if not okunan:
                eksik.append([r["kod"], r["aciklama"], r["seri"], r["izleme"],
                              r["miktar"], r["birim"],
                              "KIRLI KAYIT — " + r["kirli_sebep"] if r["kirli"] else ""])
            continue
        # lot / izlemesiz: adet karşılaştırması
        fark = (r["miktar"] or 0) - okunan
        if fark > 0:
            eksik.append([r["kod"], r["aciklama"], r["seri"], r["izleme"], fark,
                          r["birim"], "adet farkı — sayılan %g / beklenen %g"
                          % (okunan, r["miktar"] or 0)])
        elif fark < 0:
            adet_fazlasi.append(["", "", r["kod"], r["kod"], r["aciklama"], r["seri"],
                                 -fark, "adet fazlası — sayılan %g / beklenen %g"
                                 % (okunan, r["miktar"] or 0)])

    fazla = [[_kisa(r["ts"]), r["raf"] or "", r["ham"], r["kod"] or "?",
              r["aciklama"] or "", r["seri"] or "", r["miktar"], r["not_"] or ""]
             for r in c.execute("""SELECT o.*, b.aciklama FROM okutma o
                                   LEFT JOIN beklenen b ON b.kod=o.kod
                                        AND b.yukleme=? AND b.ambar=?
                                   WHERE o.oturum=? AND o.tip IN ('fazla','bilinmiyor')
                                   GROUP BY o.id ORDER BY o.id""",
                                (yukleme, ambar, oturum_id))]
    for satir in adet_fazlasi:
        satir[0] = _kisa(o["bitir"] or o["basla"])
        fazla.append(satir)

    eslesen = [[_kisa(r["ts"]), r["raf"] or "", r["kod"], r["aciklama"] or "",
                r["seri"], r["miktar"], r["tip"], r["not_"] or ""]
               for r in c.execute("""SELECT o.*, b.aciklama FROM okutma o
                                     LEFT JOIN beklenen b ON b.id=o.beklenen_id
                                     WHERE o.oturum=? AND o.tip IN ('eslesti','kod')
                                     ORDER BY o.id""", (oturum_id,))]

    duzeltme = [[r["kod"], r["aciklama"], r["seri"], _yeni_seri(r["ham"]),
                 r["raf"] or "", _kisa(r["ts"])]
                for r in c.execute("""SELECT o.ham, o.ts, o.raf, b.kod, b.aciklama,
                                      b.seri FROM okutma o
                                      JOIN beklenen b ON b.id=o.beklenen_id
                                      WHERE o.oturum=? AND b.kirli=1 AND o.ham<>''
                                      ORDER BY o.id""", (oturum_id,))]

    barkodlar = [[r["barkod"], r["kod"], r["aciklama"] or "", _kisa(r["ts"])]
                 for r in c.execute("""SELECT e.*, (SELECT aciklama FROM beklenen
                                       WHERE kod=e.kod ORDER BY yukleme DESC LIMIT 1)
                                       aciklama FROM eslesme e ORDER BY e.kod""")]

    veri = {}
    for ad, satirlar in (("Eksik", eksik), ("Fazla", fazla), ("Eşleşen", eslesen),
                         ("Tiger Düzeltme", duzeltme), ("Barkod Tablosu", barkodlar)):
        veri[ad] = {"basliklar": BASLIKLAR[ad], "satirlar": satirlar,
                    "dipnot": list(DIPNOT.get(ad, []))}
    if haric_sayisi:
        veri["Eksik"]["dipnot"].append(
            "%d kalem sayım dışı filtresiyle çıkarıldı (lisans / hizmet / nakliye "
            "vb.) — eksik sayılmadılar." % haric_sayisi)
    veri["_ozet"] = {
        "oturum": oturum_id, "ambar": ambar, "yukleme": yukleme,
        "basla": _kisa(o["basla"]), "bitir": _kisa(o["bitir"]), "durum": o["durum"],
        "haric": haric_sayisi,
        "sayilar": {ad: len(veri[ad]["satirlar"]) for ad in SEKME},
    }
    return veri


def excel_yaz(c, oturum_id, yol):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    veri = rapor_verisi(c, oturum_id)
    wb = Workbook()
    wb.remove(wb.active)
    kalin = Font(name="Arial", bold=True, color="FFFFFF")
    dolgu = PatternFill("solid", fgColor="2A3140")
    not_yazi = Font(name="Arial", italic=True, color="666666")

    for ad in SEKME:
        s = veri[ad]
        ws = wb.create_sheet(ad)
        ws.append(s["basliklar"])
        for h in ws[1]:
            h.font = kalin
            h.fill = dolgu
            h.alignment = Alignment(vertical="center")
        for satir in s["satirlar"]:
            ws.append(list(satir))
        for i, b in enumerate(s["basliklar"], 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = \
                max(12, min(45, len(b) + 18))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        if s["dipnot"]:
            ws.append([])
            for d in s["dipnot"]:
                ws.append([d])
                ws.cell(ws.max_row, 1).font = not_yazi

    if os.path.dirname(yol):
        os.makedirs(os.path.dirname(os.path.abspath(yol)), exist_ok=True)
    wb.save(yol)
    return veri["_ozet"]


def rapor_yolu(oturum_id, klasor=None):
    from .db import VERI
    klasor = klasor or os.path.join(VERI, "rapor")
    return os.path.join(klasor, "sayim_%s.xlsx" % oturum_id)
