"""Komut barkodu kartı ve etiket sayfası üreticisi.

Komut kartı komut_karti.py'nin fonksiyon hâli: Code128 ile basılır,
laminatlanıp sahada taşınır (CLAUDE.md 4.5). Raf listesi kullanıcıdan gelir.

etiket_html() ise kendi bastığımız raf/birim etiketlerini kâğıda dizer
(CLAUDE.md 12). İki düzen: A4 lazer etiket sayfası ve termal rulo.
"""
import base64
import html
import io

from .norm import raf_adi

KOMUTLAR = [
    ("##SONRAKI##", "SIRADAKİ ÜRÜN",
     "Bir ürünün tüm barkodlarını okuttuktan sonra bunu okut. Gruplama böyle kapanır."),
    ("##IPTAL##", "GRUBU İPTAL",
     "Az önce okuttuklarını sil, o ürüne baştan başla."),
    ("##GERIAL##", "SON OKUTMAYI SİL",
     "Yanlış okuttuğun tek barkodu geri alır."),
    ("##FAZLA##", "FAZLA OLARAK İŞARETLE",
     "Bu ürün Tiger kaydında yok, fazla olarak yaz."),
    ("##ATLA##", "ATLA / SONRA ÇÖZ",
     "Karar veremedin. Kuyruğa atar, sayım sonunda çözersin."),
    ("##BITIR##", "SAYIMI BİTİR",
     "Oturumu kapatır, rapor hazırlanır."),
    # I2 — kilit PARAMETRESİZ basılır: malzeme kodlarının bir kısmı boşluk ya
    # da Türkçe karakter taşıyor ve Code128'e girmiyor (CLAUDE.md 2.1).
    ("##KILIT##", "BU MALZEMEYE OKUT",
     "Önce malzeme kodunu okut, sonra bunu. Artık yalnız seri numaralarını "
     "okutman yeter — her cihazda kodu tekrar okutma."),
    ("##KILITAC##", "KİLİDİ AÇ",
     "Malzeme kilidini kaldırır, normal sayıma döner."),
    # KUTU_TASARIM.md 5 — kap kapatma. Kap AÇMAK için komut yok: kabın kendi
    # etiketi (DK-) zaten o işi yapıyor, malzemeyi kilitleyip sayacı başlatıyor.
    ("##KUTUKAPAT##", "KABI KAPAT",
     "Seri takipli kapta işin bittiğinde okut. Kilit açılır, kaç adet "
     "okuttuğunu söyler; kapta yazan sayıdan azsa uyarır."),
    # I4
    ("##YEDEK##", "YEDEK PARÇA MODU",
     "Açar/kapatır. Açıkken okutulan hiçbir şey Tiger kayıtlarında ARANMAZ, "
     "doğrudan yedek parça olarak yazılır."),
]
RENKLER = ["#1b5e20", "#b71c1c", "#e65100", "#4a148c", "#01579b", "#263238",
           "#004d40", "#33691e", "#880e4f"]


def _svg(kod):
    import barcode
    from barcode.writer import SVGWriter
    b = barcode.get("code128", kod, writer=SVGWriter())
    f = io.BytesIO()
    b.write(f, options={"module_height": 11.0, "module_width": 0.30,
                        "font_size": 0, "text_distance": 0, "quiet_zone": 3.0})
    return base64.b64encode(f.getvalue()).decode()


def _kart(kod, ad, ac, renk):
    # html.escape: raf adı kullanıcıdan geliyor. `_etiket()` kaçıyordu, burası
    # kaçmıyordu — tutarsızdı.
    return ("<div class=k style=\"--r:%s\"><div class=ad>%s</div>"
            "<img src=\"data:image/svg+xml;base64,%s\"><div class=kod>%s</div>"
            "<div class=ac>%s</div></div>"
            % (renk, html.escape(str(ad)), _svg(kod), html.escape(str(kod)),
               html.escape(str(ac))))


ADET_VARSAYILAN = (1, 5, 10, 25, 50, 100)


def kart_html(raflar=None, adetler=None):
    """Yazdırılabilir A4 komut kartı HTML'i döner.

    `adetler`: lot / izlemesiz kalemlerde miktar girmek için basılacak
    `##ADET-N##` barkodları (CLAUDE.md 2.4). Değerler BİRİKİR — 25 iki kez
    okutulunca 50 olur — o yüzden her sayıyı basmaya gerek yok.
    """
    # raf_adi(): Code128 ASCII dışını basamaz ve basılan değerle sonradan elle
    # yazılan değer aynı olmalı — normalizasyon `komut_coz` ile TEK kaynaktan.
    raflar = [a for a in (raf_adi(r) for r in (raflar or [])) if a]
    adetler = ADET_VARSAYILAN if adetler is None else adetler
    adetler = sorted({int(a) for a in adetler if 0 < int(a) <= 9999})
    parcalar = [_kart(k, a, c, RENKLER[i % len(RENKLER)])
                for i, (k, a, c) in enumerate(KOMUTLAR)]
    for a in adetler:
        parcalar.append(_kart(
            "##ADET-%d##" % a, "%d ADET" % a,
            "Lot/dökme kalemde miktar. Üst üste okutulursa toplanır.", "#00695c"))
    if adetler:
        parcalar.append(_kart("##ADET-0##", "ADEDİ SIFIRLA",
                              "Yanlış adet okuttuysan bunu okut.", "#00695c"))
    for r in raflar:
        parcalar.append(_kart("##RAF-%s##" % r, "RAF %s" % r,
                              "Bu rafta saymaya başlarken okut.", "#37474f"))
    return """<!doctype html><html lang=tr><meta charset=utf-8>
<title>Sayım Komut Kartı</title><style>
@page{size:A4;margin:10mm}
body{font:13px/1.35 Arial,sans-serif;margin:0;color:#111}
h1{font-size:19px;margin:0 0 2px}
p.alt{margin:0 0 14px;color:#555;font-size:12px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.k{border:2px solid var(--r);border-radius:7px;padding:9px 11px;break-inside:avoid}
.ad{font-weight:700;font-size:14px;color:var(--r);letter-spacing:.3px}
.k img{width:100%;height:52px;object-fit:contain;object-position:left;margin:3px 0}
.kod{font-family:ui-monospace,Consolas,monospace;font-size:10px;color:#888}
.ac{font-size:11px;color:#444;margin-top:3px}
</style>
<h1>Sayım Komut Kartı</h1>
<p class=alt>Yazdır, kes, laminatla. Klavyeye dokunmadan okuyucuyla komut ver.</p>
<div class=grid>""" + "".join(parcalar) + """</div>
<p style="margin-top:14px;font-size:11px;color:#666">
<b>Akış:</b> Ürünün üstündeki barkodları sırayla okut (P/N, S/N, UPC — hangisi varsa),
sonra <b>SIRADAKİ ÜRÜN</b> okut. Uygulama o gruptaki barkodların aynı ürüne ait
olduğunu anlar, tanımadıklarını tanıdıklarına bağlayarak öğrenir.</p></html>"""


# ---------------------------------------------------------------- etiketler
# A4 lazer etiket sayfası: 3 sütun x 8 satır = 24 etiket, 70x37,125 mm (piyasadaki
# en yaygın 24'lük kesim). Bu format TAM SAYFA doldurur: 3x70=210 mm (A4 eni) ve
# 8x37,125=297 mm (A4 boyu) — kenar boşluğu ve etiketler arası boşluk YOKTUR.
# Bu yüzden `kenar` 0'dır: sıfırdan farklı bir kenar, ızgarayı fiziksel kesim
# konumlarından kaydırır ve alt satır kendi etiketinin dışına taşar. Hücre içi
# 1.5 mm dolgu barkodu kenardan uzak tutar; yazıcının basamadığı ince kenar
# barkoda değmez. Termal rulo: etiket başına bir sayfa.
A4 = {"sutun": 3, "satir": 8, "en": 70.0, "boy": 37.125, "kenar": 0.0}
RULO = {"en": 50.0, "boy": 25.0, "kenar": 1.0}

# Çubuk genişliği etiketin okunabilirliğini belirleyen tek şey: depo aydınlatması
# kötü, okuyucu açılı tutuluyor. 9 karakterlik Code128 ~135 modül eder; 0.45 mm
# modülle ~60 mm genişliğe çıkıyor, yani 70 mm'lik hücrenin neredeyse tamamına.
# Daha ince çubuk sayfaya daha çok etiket sığdırmaz — hücre sayısı sabit — sadece
# okumayı zorlaştırır.
ETIKET_SVG = {"module_height": 11.0, "module_width": 0.45, "font_size": 0,
              "text_distance": 0, "quiet_zone": 2.0}


def _etiket_svg(kod):
    import barcode
    from barcode.writer import SVGWriter
    b = barcode.get("code128", kod, writer=SVGWriter())
    f = io.BytesIO()
    b.write(f, options=ETIKET_SVG)
    return base64.b64encode(f.getvalue()).decode()


def _kisalt(s, n=34):
    s = str(s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def raf_satirlari(raflar, kopya=1):
    """Raf konum barkodlarını (##RAF-A1##) etiket_html satırlarına çevirir.

    Raf etiketi defter kalemi DEĞİL: DS/DM numarası tüketmez, `etiket`
    tablosuna yazılmaz, `eslesme`'ye dokunmaz — tıpkı komut kartındaki gibi
    yalnızca bir konum işaretidir (CLAUDE.md 12.1). Aynı raf birden çok yüze
    yapıştırılacaksa `kopya` ile çoğaltılır.
    """
    raflar = [a for a in (raf_adi(r) for r in (raflar or [])) if a]
    kopya = max(1, int(kopya or 1))
    satirlar = []
    for r in raflar:
        satirlar += [{"gosterim": "##RAF-%s##" % r, "tur": "raf", "ad": r}] * kopya
    return satirlar


def _etiket(s):
    """Tek etiket hücresi. Malzeme etiketinde kod ve açıklama da basılır."""
    g = s["gosterim"]
    if s.get("tur") == "raf":
        # Raf etiketinde önemli olan uzaktan okunan konum adı: onu büyük ve
        # üste alıyoruz, barkod altında kalıyor.
        return ('<div class="k rafk"><div class=raf>%s</div>'
                '<img src="data:image/svg+xml;base64,%s">'
                '<div class=kod>%s</div></div>'
                % (html.escape(str(s.get("ad") or "")), _etiket_svg(g),
                   html.escape(g)))
    if s.get("tur") == "kutu":
        # Kap etiketi kabın ÜSTÜNDE durur ve uzaktan okunur: içerik büyük
        # yazılır, barkod altında kalır (raf etiketiyle aynı mantık).
        #
        # ADET BASILMAZ. İlk taslakta "150 AD" satırı vardı; içerik ayda bir
        # değişiyor (KUTU_TASARIM.md 9.3) ve depoda yazıcı yok — ayda bir
        # yeniden basım imkânsız. Yanlış basılmış bir sayı, hiç sayı
        # olmamasından çok daha kötüdür: kapta 150 yazar, içinde 130 vardır ve
        # sayan kişi elindeki gerçeğe değil etikete inanır.
        ad = _kisalt(s.get("aciklama") or s.get("malzeme") or "KAP", 28)
        return ('<div class="k rafk"><div class=kutuad>%s</div>'
                '<img src="data:image/svg+xml;base64,%s">'
                '<div class=kod>%s</div>%s</div>'
                % (html.escape(str(ad)), _etiket_svg(g), html.escape(g),
                   ("<div class=m>%s</div>" % html.escape(str(s.get("malzeme"))))
                   if s.get("malzeme") else ""))
    alt = ""
    if s.get("tur") == "malzeme":
        alt = ("<div class=m>%s</div><div class=a>%s</div>"
               % (html.escape(str(s.get("malzeme") or "")),
                  html.escape(_kisalt(s.get("aciklama")))))
    else:
        alt = "<div class=a>SAYIM ETİKETİ</div>"
    return ('<div class=k><img src="data:image/svg+xml;base64,%s">'
            '<div class=kod>%s</div>%s</div>'
            % (_etiket_svg(g), html.escape(g), alt))


def etiket_html(satirlar, duzen="a4", atla=0, olcu=None):
    """Basılabilir etiket sayfası HTML'i döner.

    atla: yarım kalmış etiket sayfasını israf etmemek için ilk N hücre boş
    bırakılır — kullanıcı sayfayı yazıcıya kaldığı yerden koyar.
    """
    if duzen not in ("a4", "rulo"):
        raise ValueError("bilinmeyen düzen: %s" % duzen)
    o = dict(RULO if duzen == "rulo" else A4)
    o.update(olcu or {})
    hucreler = ['<div class="k bos"></div>'] * max(0, int(atla or 0)) if duzen == "a4" else []
    hucreler += [_etiket(s) for s in satirlar]

    if duzen == "rulo":
        sayfa = "@page{size:%gmm %gmm;margin:%gmm}" % (o["en"], o["boy"], o["kenar"])
        yerlesim = (".grid{display:block}"
                    ".k{width:100%%;height:%gmm;break-after:page}"
                    ".k:last-child{break-after:auto}"
                    # Ekranda da gerçek etiket oranı görünsün: yazdırmada @page
                    # zaten sınırlıyor ama önizleme yanıltıcı olmasın.
                    "@media screen{.grid{width:%gmm}}"
                    % (o["boy"] - 2 * o["kenar"], o["en"] - 2 * o["kenar"]))
    else:
        sayfa = "@page{size:A4;margin:%gmm}" % o["kenar"]
        yerlesim = (".grid{display:grid;grid-template-columns:repeat(%d,%gmm);"
                    "grid-auto-rows:%gmm}" % (o["sutun"], o["en"], o["boy"]))

    return """<!doctype html><html lang=tr><meta charset=utf-8>
<title>Sayım Etiketleri</title><style>
%s
body{font:11px/1.25 Arial,sans-serif;margin:0;color:#000;background:#fff}
%s
.k{display:flex;flex-direction:column;justify-content:center;align-items:center;
   padding:1.5mm;box-sizing:border-box;break-inside:avoid;overflow:hidden;text-align:center}
.k.bos{visibility:hidden}
.k img{width:96%%;height:11mm;object-fit:contain}
.kod{font-family:ui-monospace,Consolas,monospace;font-size:12px;font-weight:700;
     letter-spacing:.5px;margin-top:.6mm}
.m{font-weight:700;font-size:10px;margin-top:.6mm}
.a{font-size:8px;color:#444}
.raf{font-weight:800;font-size:18px;letter-spacing:1px;margin-bottom:.8mm}
.kutuad{font-weight:800;font-size:14px;line-height:1.15;margin-bottom:.8mm}
@media screen{body{padding:10px;background:#eee}
  .k{outline:1px dashed #bbb;background:#fff}}
</style><div class=grid>%s</div></html>""" % (sayfa, yerlesim, "".join(hucreler))
