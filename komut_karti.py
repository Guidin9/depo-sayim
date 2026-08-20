#!/usr/bin/env python3
"""Sayim komut barkodu karti uretir -> komut_karti.html (yazdirilabilir)
Kullanim:  python komut_karti.py [raf1 raf2 ...]
Gereksinim: pip install python-barcode
"""
import sys, io, base64
import barcode
from barcode.writer import SVGWriter

KOMUTLAR = [
    ("##SONRAKI##", "SIRADAKİ ÜRÜN", "Bir ürünün tüm barkodlarını okuttuktan sonra bunu okut. "
     "Gruplama böyle kapanır."),
    ("##IPTAL##", "GRUBU İPTAL", "Az önce okuttuklarını sil, o ürüne baştan başla."),
    ("##GERIAL##", "SON OKUTMAYI SİL", "Yanlış okuttuğun tek barkodu geri alır."),
    ("##FAZLA##", "FAZLA OLARAK İŞARETLE", "Bu ürün Tiger kaydında yok, fazla olarak yaz."),
    ("##ATLA##", "ATLA / SONRA ÇÖZ", "Karar veremedin. Kuyruğa atar, sayım sonunda çözersin."),
    ("##BITIR##", "SAYIMI BİTİR", "Oturumu kapatır, rapor hazırlanır."),
]

def svg(kod):
    b = barcode.get("code128", kod, writer=SVGWriter())
    f = io.BytesIO()
    b.write(f, options={"module_height": 11.0, "module_width": 0.30,
                        "font_size": 0, "text_distance": 0, "quiet_zone": 3.0})
    return base64.b64encode(f.getvalue()).decode()

def kart(kod, ad, ac, renk):
    return f"""<div class=k style="--r:{renk}">
      <div class=ad>{ad}</div>
      <img src="data:image/svg+xml;base64,{svg(kod)}">
      <div class=kod>{kod}</div>
      <div class=ac>{ac}</div></div>"""

def main():
    raflar = sys.argv[1:]
    renkler = ["#1b5e20", "#b71c1c", "#e65100", "#4a148c", "#01579b", "#263238"]
    p = [kart(k, a, c, renkler[i % 6]) for i, (k, a, c) in enumerate(KOMUTLAR)]
    for r in raflar:
        p.append(kart(f"##RAF-{r.upper()}##", f"RAF {r.upper()}",
                      "Bu rafta saymaya başlarken okut.", "#37474f"))
    html = """<!doctype html><html lang=tr><meta charset=utf-8><title>Sayım Komut Kartı</title>
<style>
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
<div class=grid>""" + "".join(p) + """</div>
<p style="margin-top:14px;font-size:11px;color:#666">
<b>Akış:</b> Ürünün üstündeki barkodları sırayla okut (P/N, S/N, UPC — hangisi varsa),
sonra <b>SIRADAKİ ÜRÜN</b> okut. Uygulama o gruptaki barkodların aynı ürüne ait olduğunu anlar,
tanımadıklarını tanıdıklarına bağlayarak öğrenir.</p></html>"""
    with open("komut_karti.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("komut_karti.html olusturuldu ->  tarayicida ac, Ctrl+P ile yazdir")

if __name__ == "__main__":
    main()
