"""6 sekmeli sayım raporu (CLAUDE.md 5, 12).

depo_sayim.py:307-375 taşındı. Sekme adları ve sütun düzeni korundu, üstüne:
  * Fazla / Eşleşen / Tiger Düzeltme sekmelerine Raf sütunu
  * Eksik sekmesi sayım dışı kalemleri listelemez, sayıyı dipnot olarak yazar
  * Lot ve izlemesiz kalemlerde adet farkı hesaplanır (seri takipli kalemlerde
    prototipteki davranış aynen korunur: okutulmayan satır eksiktir)
  * Etiketler sekmesi: kendi bastığımız etiketlerin defteri (CLAUDE.md 12)

rapor_verisi() hem Excel yazıcısını hem arayüzdeki sekme önizlemesini besler ki
iki yerde iki ayrı gerçek olmasın.
"""
import os

SEKME = ("Eksik", "Fazla", "Eşleşen", "Tiger Düzeltme", "Barkod Tablosu",
         "Etiketler")

BASLIKLAR = {
    "Eksik": ["Malzeme Kodu", "Açıklama", "Beklenen Seri/Lot", "İzleme", "Miktar",
              "Birim", "Not"],
    # Ürün Adı: Tiger'da kaydı olmayan ürünlerde açıklama JOIN'den gelemez,
    # kullanıcı elle yazar (CLAUDE.md 5, DEMO_FEEDBACK.md 3).
    "Fazla": ["Zaman", "Raf", "Okutulan", "Malzeme Kodu", "Açıklama", "Seri",
              "Miktar", "Not", "Ürün Adı"],
    "Eşleşen": ["Zaman", "Raf", "Malzeme Kodu", "Açıklama", "Seri/Lot", "Miktar",
                "Tip", "Not"],
    "Tiger Düzeltme": ["Malzeme Kodu", "Açıklama", "MEVCUT (hatalı) Seri No",
                       "YENİ (gerçek) Seri No", "Raf", "Zaman"],
    "Barkod Tablosu": ["Okutulan Barkod", "Malzeme Kodu", "Açıklama",
                       "Öğrenildiği An"],
    "Etiketler": ["Etiket", "Tür", "Malzeme Kodu", "Açıklama",
                  "Bağlandığı Kayıt", "Raf", "Basıldığı An", "Bağlandığı An"],
}

DIPNOT = {
    "Tiger Düzeltme": ["Bu sayfadaki kayıtlar Tiger'da seri numarası düzeltmesi "
                       "gerektirir.", "Ambar Sayımı ekranından fiş oluştururken "
                       "kullanın."],
    "Barkod Tablosu": ["Bu barkodları Tiger'da malzeme kartı > Birimler > Barkod "
                       "alanına yazın.", "Yazdıktan sonra bu ürünler sorusuz eşleşir.",
                       "Liste bu raporun ambarındaki malzemelerle sınırlıdır; "
                       "önceki oturumlarda öğrenilenler de burada — Tiger'a "
                       "girilmemiş olabilirler."],
    "Etiketler": ["Kendi bastığımız etiketlerin defteri: hangi numara neye yapıştı.",
                  "Tiger'a yazılacak değerler Tiger Düzeltme ve Barkod Tablosu "
                  "sekmelerinde; bu sayfa fiziksel etiketi bulmak içindir.",
                  "Malzemesi boş satırlar henüz kullanılmamış, havuzda bekleyen "
                  "etiketlerdir."],
}


def _kisa(ts):
    return (ts or "")[:19].replace("T", " ")


def _yeni_seri(ham):
    """Tiger'a yazılacak gerçek seri numarasını seçer.

    Kuyruktan çözülen grupta okutma 'A + B' biçiminde saklanır (denetim izi).
    Tiger Düzeltme sekmesine tek bir değer yazılmalı: perakende barkodu olmayan
    en uzun parça — grup çözümlemesindeki kuralın aynısı (matching.grup_coz).

    Kendi bastığımız etiketler son sıraya düşer. 'DM-000123 + DS-000045'
    grubunda iki parça da aynı uzunlukta olduğu için max() ilkini — yani MALZEME
    etiketini — seçerdi; malzeme etiketi seri numarası değildir. Seri etiketi
    ancak başka aday yoksa kullanılır (grup_coz'daki yeni_sn sırasının aynısı).
    """
    from .etiketler import etiket_turu
    from .norm import upc_mi
    parcalar = [p.strip() for p in str(ham or "").split(" + ") if p.strip()]
    if len(parcalar) <= 1:
        return ham
    adaylar = [p for p in parcalar if not upc_mi(p)] or parcalar
    for sinif in (None, "seri"):            # önce gerçek S/N, sonra seri etiketi
        havuz = [p for p in adaylar if etiket_turu(p) == sinif]
        if havuz:
            return max(havuz, key=len)
    return max(adaylar, key=len)


def eksik_kayitlar(c, oturum_id):
    """Sayımda karşılığı bulunamayan beklenen satırlar.

    Rapordaki Eksik sekmesi ve sayım sonu eşleştirme ekranı aynı listeyi
    kullanır — iki yerde iki ayrı gerçek olmasın (DEMO_FEEDBACK.md 6).

    (eksik, adet_fazlasi, haric_sayisi) döner; ilk ikisi sözlük listesidir.
    """
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
        ortak = {"id": r["id"], "kod": r["kod"], "aciklama": r["aciklama"],
                 "seri": r["seri"], "izleme": r["izleme"], "birim": r["birim"],
                 "kirli": r["kirli"]}
        if r["izleme"] == "seri":
            if not okunan:
                eksik.append(dict(ortak, miktar=r["miktar"], not_=(
                    "KIRLI KAYIT — " + r["kirli_sebep"] if r["kirli"] else "")))
            continue
        # lot / izlemesiz: adet karşılaştırması
        fark = (r["miktar"] or 0) - okunan
        if fark > 0:
            eksik.append(dict(ortak, miktar=fark,
                              not_="adet farkı — sayılan %g / beklenen %g"
                                   % (okunan, r["miktar"] or 0)))
        elif fark < 0:
            adet_fazlasi.append(dict(ortak, miktar=-fark,
                                     not_="adet fazlası — sayılan %g / beklenen %g"
                                          % (okunan, r["miktar"] or 0)))
    return eksik, adet_fazlasi, haric_sayisi


def rapor_verisi(c, oturum_id):
    """Sekme adı -> {basliklar, satirlar, dipnot} sözlüğü."""
    o = c.execute("SELECT * FROM oturum WHERE id=?", (oturum_id,)).fetchone()
    if not o:
        raise ValueError("Oturum #%s bulunamadı" % oturum_id)
    yukleme, ambar = o["yukleme"], o["ambar"]

    ham_eksik, ham_adet_fazlasi, haric_sayisi = eksik_kayitlar(c, oturum_id)
    eksik = [[e["kod"], e["aciklama"], e["seri"], e["izleme"], e["miktar"],
              e["birim"], e["not_"]] for e in ham_eksik]
    adet_fazlasi = [["", "", e["kod"], e["kod"], e["aciklama"], e["seri"],
                     e["miktar"], e["not_"], ""] for e in ham_adet_fazlasi]

    # Açıklama boşsa elle yazılan ad devreye girer: kodu olmayan kayıtta
    # sütunun boş kalması raporu okunamaz yapıyordu.
    fazla = [[_kisa(r["ts"]), r["raf"] or "", r["ham"], r["kod"] or "?",
              r["aciklama"] or r["ad"] or "", r["seri"] or "", r["miktar"],
              r["not_"] or "", r["ad"] or ""]
             for r in c.execute("""SELECT o.*, b.aciklama FROM okutma o
                                   LEFT JOIN beklenen b ON b.kod=o.kod
                                        AND b.yukleme=? AND b.ambar=?
                                   WHERE o.oturum=? AND o.tip='fazla' 
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

    # Yalnızca BU raporun ambarındaki malzemelere ait barkodlar.
    #
    # Eskiden `eslesme` tablosunun tamamı dökülüyordu: başka ambarların
    # malzemeleri, önceki sayımlardan öğrenilen her şey ve basılmış her `DM-`
    # etiketi her raporda yeniden çıkıyor, liste sonsuza kadar büyüyordu.
    # Sekmenin işi "Tiger'da HANGİ malzeme kartına ne yazacağım" — o kart bu
    # ambarın dışındaysa bu raporun işi değil.
    barkodlar = [[r["barkod"], r["kod"], r["aciklama"] or "", _kisa(r["ts"])]
                 for r in c.execute("""SELECT e.barkod, e.kod, e.ts,
                        (SELECT aciklama FROM beklenen WHERE kod=e.kod
                         AND yukleme=? AND ambar=? LIMIT 1) aciklama
                        FROM eslesme e
                        WHERE EXISTS(SELECT 1 FROM beklenen b WHERE b.kod=e.kod
                                     AND b.yukleme=? AND b.ambar=? AND b.haric=0)
                        ORDER BY e.kod, e.barkod""",
                                    (yukleme, ambar, yukleme, ambar))]

    etiket_satir = [[r["gosterim"], "Malzeme" if r["tur"] == "malzeme" else "Seri",
                     r["malzeme"] or "", r["aciklama"] or "", r["slot"] or "",
                     r["raf"] or "", _kisa(r["ts"]), _kisa(r["ts_bagla"])]
                    for r in c.execute("""SELECT e.*,
                          (SELECT aciklama FROM beklenen WHERE kod=e.malzeme
                           ORDER BY yukleme DESC LIMIT 1) aciklama,
                          (SELECT seri FROM beklenen WHERE id=e.beklenen_id) slot
                          FROM etiket e ORDER BY e.tur, e.kod""")]

    veri = {}
    for ad, satirlar in (("Eksik", eksik), ("Fazla", fazla), ("Eşleşen", eslesen),
                         ("Tiger Düzeltme", duzeltme), ("Barkod Tablosu", barkodlar),
                         ("Etiketler", etiket_satir)):
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
