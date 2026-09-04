"""2026-08-28 gerçek sayımında sahadan bildirilen hatalar (S1, S2, S4).

Hepsi çalışan uygulamada, gerçek Tiger verisiyle yarım kalmış bir sayım
sırasında görüldü ve veritabanının kopyası üzerinde birebir üretildi.
S3 (temiz kayıtlı malzemede her adet için onay sorulması) bilinçli olarak
açık bırakıldı — CLAUDE.md §4.4'ün "sistem tahmin yürütmez" kuralı.

S5'in (Sil tuşu) testleri `test_silme.py`'de: sözleşme değiştiği için
oradaki test güncellendi.
"""
import json

import pytest

from app import etiketler, matching
from tests.conftest import AMBAR, haric_kur, oturum_taze

SONRAKI = "##SONRAKI##"
KILIT = "##KILIT##"
FAZLA = "##FAZLA##"


def _lot_malzeme(c):
    r = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                     AND izleme='lot' ORDER BY id LIMIT 1""", (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde lot malzemesi yok")
    return r["kod"]


def _kirli_malzeme(c):
    r = c.execute("""SELECT kod FROM beklenen WHERE yukleme=1 AND ambar=? AND haric=0
                     AND izleme='seri' AND kirli=1 GROUP BY kod ORDER BY COUNT(*) DESC
                     LIMIT 1""", (AMBAR,)).fetchone()
    if not r:
        pytest.skip("test verisinde kirli slotu olan malzeme yok")
    return r["kod"]


# --------------------------------------------------------------------- S1: kilit
def test_S1_taninmayan_urunde_kilit_onceki_urune_gecmez(c, ot, yaz):
    """##KILIT##, tamponda tanınmayan barkod varken ÖNCEKİ ürüne kilitlenmemeli.

    Sahada: Tiger'da olmayan bir ürünün DM- etiketi okutulup ##KILIT## denince
    bir önceki ürünün kodu kilitlendi — üstelik yeşil "ok" sesiyle. Ardından
    okutulan her seri numarası o yanlış malzemeye gider ve sayım sessizce
    bozulur; kullanıcı kilidin doğru kurulduğunu sanır.
    """
    onceki = _lot_malzeme(c)
    yaz(onceki, SONRAKI)                       # bir ürün sayıldı: son çarenin adayı
    assert c.execute("SELECT kod FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                     (ot["id"],)).fetchone()["kod"] == onceki

    etiketler.bas(c, "malzeme", adet=1, kapsam="bos")
    r = yaz("DM-000001")                       # Tiger'da karşılığı YOK
    assert r["coz"] in ("bilinmiyor", "upc")

    r = yaz(KILIT)
    assert r["tip"] == "kilit_yok", "tanınmayan üründe kilit KURULMAMALI"
    assert oturum_taze(c, ot)["sabit_kod"] is None
    assert "DM-000001" in (r.get("barkodlar") or []), "tampon korunmalı"


def test_S1_bos_tamponda_kilit_son_saydigim_urune_kurulur(c, ot, yaz):
    """Son çare dalı DURUYOR: boş tamponda ##KILIT## "az önce saydığıma kilitle"."""
    kod = _lot_malzeme(c)
    yaz(kod, SONRAKI)
    r = yaz(KILIT)
    assert r["tip"] == "kilit" and r["kod"] == kod
    assert oturum_taze(c, ot)["sabit_kod"] == kod


# ------------------------------------------------- S2: fazla yolunda öğrenme
def test_S2_tigerda_olmayan_urun_ikinci_okutmada_taninir(c, ot, yaz):
    """DM- etiketiyle giren ürün, adı bir kez yazıldıktan sonra tanınmalı.

    Sahada `DM-000001` 47 kez okutuldu, 47 kez fazla yazıldı ve adı 47 kez
    elle girildi: fazla yazan dalların hiçbiri öğrenmiyordu.
    """
    etiketler.bas(c, "malzeme", adet=1, kapsam="bos")
    yaz("DM-000001", FAZLA)
    oid = c.execute("SELECT id FROM okutma WHERE oturum=? AND tip='fazla'",
                    (ot["id"],)).fetchone()["id"]
    c.execute("UPDATE okutma SET ad=? WHERE id=?", ("DM-160 bas konuş", oid))
    matching.fazla_ogren(c, oid)
    assert c.execute("SELECT ad FROM fazla_ad WHERE barkod='DM000001'"
                     ).fetchone()["ad"] == "DM-160 bas konuş"

    # İkinci ürün: artık soru YOK, kuyruk YOK, ad hazır.
    r = yaz("DM-000001", SONRAKI)
    assert r["tip"] == "fazla_bilinen"
    assert r["ad"] == "DM-160 bas konuş"
    assert not matching.bekleyen_kuyruk(c, ot["id"]), "kuyruğa düşmemeli"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND tip='fazla'",
                     (ot["id"],)).fetchone()["n"] == 2


def test_S2_ogrenilen_ad_gerial_ile_unutulur(c, ot, yaz):
    """Yanlış ürüne bağlanan ad kalıcı olmamalı — ##GERIAL## onu da alır."""
    etiketler.bas(c, "malzeme", adet=1, kapsam="bos")
    yaz("DM-000001", FAZLA)
    oid = c.execute("SELECT id FROM okutma WHERE oturum=? AND tip='fazla'",
                    (ot["id"],)).fetchone()["id"]
    c.execute("UPDATE okutma SET ad='yanlış ürün' WHERE id=?", (oid,))
    matching.fazla_ogren(c, oid)
    assert c.execute("SELECT 1 FROM fazla_ad WHERE barkod='DM000001'").fetchone()

    matching.gerial(c, oturum_taze(c, ot))
    assert not c.execute("SELECT 1 FROM fazla_ad WHERE barkod='DM000001'").fetchone()


def test_S2_fazla_yolunda_seri_etiketi_deftere_islenir(c, ot, yaz):
    """Fiziksel olarak yapıştırılan DS- etiketi defterde "boşta" görünmemeli.

    Sahada 109 etiket yapıştırıldı, defterde 30'u bağlı göründü: aradaki 79'un
    hepsi fazla yolundan geçmişti ve Etiketler sekmesi onları havuzda sanıyordu.
    """
    etiketler.bas(c, "seri", adet=3)
    yaz("DS-000001", FAZLA)
    e = c.execute("SELECT * FROM etiket WHERE kod='DS000001'").fetchone()
    assert e["oturum"] == ot["id"], "etiket kullanıldı olarak işaretlenmeli"
    assert e["beklenen_id"] is None, "Tiger kaydı yok — bağlanacak satır da yok"


def test_S2_seri_etiketi_fazla_adina_OGRENILMEZ(c, ot, yaz):
    """DS- etiketi tekil cihaza aittir: ad havuzuna yazılamaz.

    Yazılsaydı o etiket sökülüp başka ürüne yapıştırıldığında yanlış ürün
    otomatik "fazla" yazılırdı.
    """
    etiketler.bas(c, "seri", adet=3)
    yaz("DS-000001", FAZLA)
    oid = c.execute("SELECT id FROM okutma WHERE oturum=? AND tip='fazla'",
                    (ot["id"],)).fetchone()["id"]
    c.execute("UPDATE okutma SET ad='deneme' WHERE id=?", (oid,))
    matching.fazla_ogren(c, oid)
    assert not c.execute("SELECT 1 FROM fazla_ad WHERE barkod='DS000001'").fetchone()


def test_S2_kod_biliniyorsa_eslesmeye_ogrenilir(c, ot):
    """Malzeme kodu bilinen fazla onayında barkod `eslesme`'ye gider.

    Fazla olması ürünün O MALZEME olmadığı anlamına gelmez; yalnızca Tiger'ın
    seri numaralarıyla eşleşmemiştir.
    """
    kod = _kirli_malzeme(c)
    kid = c.execute("""INSERT INTO kuyruk(oturum,ts,barkodlar,raf,tur,kod)
                       VALUES(?,?,?,?,'fazla_onay',?)""",
                    (ot["id"], "2026-09-02T00:00:00",
                     json.dumps(["ZZTESTBARKOD1"]), "A1", kod)).lastrowid
    matching.kuyruk_fazla(c, kid)
    e = c.execute("SELECT * FROM eslesme WHERE barkod='ZZTESTBARKOD1'").fetchone()
    assert e is not None and e["kod"] == kod


# ------------------------------------------------------------- S4: tampon
def test_S4_tekrar_donen_grup_tamponu_TUKETMEZ(c, ot, yaz):
    """Hiçbir satır yazılmadıysa tampon durmalı — ##FAZLA## hâlâ çalışmalı.

    Sahada: daha önce bağlanmış bir DS- etiketi okutulup ##SONRAKI## denince
    `tekrar` dönüyor, ardından Fazla'ya basmak hiçbir şey yapmıyordu (tampon
    boşalmıştı, ##FAZLA## `bos` dönüyordu). Kullanıcı etiketi söküp yenisini
    yapıştırınca çalışıyordu.
    """
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "seri", adet=3)
    yaz(kod, "DS-000001", SONRAKI)             # etiket bir slota bağlandı

    r = yaz("DS-000001", SONRAKI)              # aynı etiket ikinci kez
    assert r["tip"] == "tekrar"
    assert r.get("tampon_duruyor") is True
    assert c.execute("SELECT COUNT(*) n FROM tampon WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 1, "tampon korunmalı"

    r = yaz(FAZLA)                             # kullanıcı yine de karar verebilmeli
    assert r["tip"] == "fazla_elle"
    assert "DS-000001" in r["barkodlar"]


def test_S4_haric_kalem_de_tamponu_tuketmez(c, ot, yaz):
    """Sayım dışı kalemde de hiçbir satır yazılmıyor: tampon durur."""
    _, _, kod = haric_kur(c)   # (kural_id, satir_sayisi, ornek_kod)
    r = yaz(kod, SONRAKI)
    assert r["tip"] == "haric"
    assert c.execute("SELECT COUNT(*) n FROM tampon WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 1


def test_S4_adet_de_geri_gelir(c, ot, yaz):
    """Tamponla birlikte ##ADET-N## de korunur, sonraki ürüne sızmaz."""
    kod = _kirli_malzeme(c)
    etiketler.bas(c, "seri", adet=3)
    yaz(kod, "DS-000001", SONRAKI)
    yaz("##ADET-5##", "DS-000001")
    r = yaz(SONRAKI)
    assert r["tip"] == "tekrar"
    assert oturum_taze(c, ot)["bekleyen_adet"] == 5
