"""Komut barkodu kartı üretici (komut_karti.py'nin fonksiyon hali).

Code128 ile basılır, laminatlanıp sahada taşınır (CLAUDE.md 4.5). Raf listesi
kullanıcıdan gelir.
"""
import base64
import io

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
]
RENKLER = ["#1b5e20", "#b71c1c", "#e65100", "#4a148c", "#01579b", "#263238"]


def _svg(kod):
    import barcode
    from barcode.writer import SVGWriter
    b = barcode.get("code128", kod, writer=SVGWriter())
    f = io.BytesIO()
    b.write(f, options={"module_height": 11.0, "module_width": 0.30,
                        "font_size": 0, "text_distance": 0, "quiet_zone": 3.0})
    return base64.b64encode(f.getvalue()).decode()


def _kart(kod, ad, ac, renk):
    return ("<div class=k style=\"--r:%s\"><div class=ad>%s</div>"
            "<img src=\"data:image/svg+xml;base64,%s\"><div class=kod>%s</div>"
            "<div class=ac>%s</div></div>" % (renk, ad, _svg(kod), kod, ac))


def kart_html(raflar=None):
    """Yazdırılabilir A4 komut kartı HTML'i döner."""
    raflar = [str(r).strip().upper() for r in (raflar or []) if str(r).strip()]
    parcalar = [_kart(k, a, c, RENKLER[i % len(RENKLER)])
                for i, (k, a, c) in enumerate(KOMUTLAR)]
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
