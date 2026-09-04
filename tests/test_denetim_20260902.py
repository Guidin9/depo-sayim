"""2026-09-02 bağımsız denetimi — dokümanlara güvenmeden yapılan kod taraması.

462 test geçerken bulunan dört hata. Üçü SESSİZ YANLIŞ SAYIM üretiyordu:
ekranda doğru sonuç, hata yalnızca Excel'de ya da hiç.

Ortak ders: hepsi bir VARSAYIMDAN doğdu, koddan değil.
"D1" varsayımı CLAUDE.md §2.4'te yazılıydı ve gerçek Tiger verisinde YANLIŞTI —
"seri satırında miktar hep 1" diyordu, oysa örnek çıktıda miktarı 2 ve 4 olan
32 seri satırı var.
"""
import pytest

from app import db as dbm, etiketler, matching, oturumlar, reports


def _kur(satirlar):
    """Verilen beklenen satırlarıyla bellekte bir sayım kurar."""
    c = dbm.baglan(":memory:")
    y = c.execute("INSERT INTO yukleme(ts,dosya_adi,kaynak,satir) "
                  "VALUES('t','t','seri_lot',0)").lastrowid
    idler = []
    for kod, seri, izleme, miktar, kirli in satirlar:
        idler.append(c.execute(
            """INSERT INTO beklenen(yukleme,kod,kod_n,aciklama,tur,ambar,izleme,
               seri,seri_n,seri_n0,seri_aciklama,miktar,birim,kirli,kirli_sebep,
               haric,haric_sebep,kaynak)
               VALUES(?,?,?,?,'TM','1',?,?,?,NULL,'',?,'AD',?,'',0,'','seri_lot')""",
            (y, kod, kod, kod + " açıklama", izleme, seri, seri, miktar,
             kirli)).lastrowid)
    ot = oturumlar.ac(c, y, "1")
    return c, ot, idler


def _taze(c, ot):
    return c.execute("SELECT * FROM oturum WHERE id=?", (ot["id"],)).fetchone()


def _okut(c, ot, *hamlar):
    r = None
    for h in hamlar:
        r = matching.okut(c, _taze(c, ot), h)
    return r


# --------------------------------------------------------- D1: çok adetli seri
def test_D1_seri_satirinda_miktar_2_ise_iki_cihaz_sayilir():
    """`izleme='seri'` + `miktar=2`: iki cihaz da sayılabilmeli.

    Eskiden `kapasite_kaldi` seri takiplide `miktar`a HİÇ bakmıyordu ("bir kez
    okutulur"). Tek okutma satırı kapatıyor, ikinci cihaz `tekrar` deyip
    sayılmıyordu — ve hiçbir yere de düşmüyordu.
    """
    c, ot, (bid,) = _kur([("MIK2", "SNAAA111", "seri", 2, 0)])
    assert matching.sayaclar(c, _taze(c, ot))["toplam"] == 2, "Tiger 2 adet diyor"

    _okut(c, ot, "SNAAA111", "##SONRAKI##")
    assert matching.sayaclar(c, _taze(c, ot))["okutulan"] == 1
    assert matching.sayaclar(c, _taze(c, ot))["kalan"] == 1

    r = _okut(c, ot, "SNAAA111", "##SONRAKI##")
    assert r["tip"] == "eslesti", "ikinci cihaz da sayılmalı"
    s = matching.sayaclar(c, _taze(c, ot))
    assert (s["okutulan"], s["kalan"]) == (2, 0)

    r = _okut(c, ot, "SNAAA111", "##SONRAKI##")
    assert r["tip"] == "tekrar", "üçüncüsü artık sığmaz"


def test_D1_yarim_kalan_seri_satiri_RAPORDA_eksik_cikar():
    """Bir adedi okutulmuş 2 adetlik seri satırı: kalan 1 adet Eksik'te olmalı.

    Eskiden rapor `if not okunan` diyordu — bir okutma satırı "tam" sayıyor ve
    eksik adet hiçbir yerde görünmüyordu.
    """
    c, ot, (bid,) = _kur([("MIK2", "SNAAA111", "seri", 2, 0)])
    _okut(c, ot, "SNAAA111", "##SONRAKI##")
    eksik, adet_fazlasi, _ = reports.eksik_kayitlar(c, ot["id"])
    assert len(eksik) == 1 and eksik[0]["miktar"] == 1
    assert "sayılan 1 / beklenen 2" in eksik[0]["not_"]
    assert not adet_fazlasi


def test_D1_yarim_kalan_seri_satiri_BITIRME_kapisinda_uyarir():
    """`##BITIR##` yarım kalan çok adetli seri satırını da söylemeli."""
    c, ot, _ = _kur([("MIK2", "SNAAA111", "seri", 2, 0)])
    _okut(c, ot, "SNAAA111", "##SONRAKI##")
    uyari = matching.eksik_lotlar(c, _taze(c, ot))
    assert [u["kod"] for u in uyari] == ["MIK2"]
    assert (uyari[0]["beklenen"], uyari[0]["sayilan"]) == (2, 1)


def test_D1_normal_seri_satiri_DEGISMEDI():
    """miktar=1 olan sıradan seri satırında davranış birebir aynı kalmalı."""
    c, ot, _ = _kur([("TEK", "SNBBB222", "seri", 1, 0)])
    assert _okut(c, ot, "SNBBB222", "##SONRAKI##")["tip"] == "eslesti"
    assert _okut(c, ot, "SNBBB222", "##SONRAKI##")["tip"] == "tekrar"
    assert matching.sayaclar(c, _taze(c, ot))["kalan"] == 0


def test_D1_miktar_sifir_olan_seri_satiri_yine_sayilabilir():
    """Tiger'dan 0 miktarla gelen seri satırı sayılamaz hâle GELMEMELİ."""
    c, ot, _ = _kur([("SIFIR", "SNCCC333", "seri", 0, 0)])
    assert _okut(c, ot, "SNCCC333", "##SONRAKI##")["tip"] == "eslesti"


# ------------------------------------------------- D2: fazla_bagla `geri`yi ezmesin
def test_D2_fazla_bagla_onceki_yan_etkileri_DUSURMEZ():
    """Bağlama, kaydın önceki yan etkilerini `geri`den silmemeli.

    Eskiden `geri` yepyeni bir JSON'la değiştiriliyordu: kuyruk bağı,
    öğrenilmiş ad ve bağlanmış etiket sessizce düşüyordu. Kayıt sonradan
    silinince hiçbiri geri alınamıyor, yanlış ürün adı gelecek okutmalarda
    yaşamaya devam ediyordu.
    """
    c, ot, (bid,) = _kur([("KOD1", "KOD1SAYIM1", "seri", 1, 1)])
    etiketler.bas(c, "seri", adet=3)
    etiketler.bas(c, "malzeme", adet=2, kapsam="bos")

    _okut(c, ot, "DM-000001", "DS-000001", "##ATLA##")
    kid = c.execute("SELECT id FROM kuyruk WHERE oturum=?", (ot["id"],)).fetchone()["id"]
    oid = matching.kuyruk_fazla(c, kid, ad="test ürünü")["okutma"][0]
    assert c.execute("SELECT 1 FROM fazla_ad WHERE barkod='DM000001'").fetchone()

    matching.fazla_bagla(c, oid, bid)
    import json
    d = json.loads(c.execute("SELECT geri FROM okutma WHERE id=?", (oid,)).fetchone()["geri"])
    assert d.get("kuyruk") == kid
    assert "DM-000001" in (d.get("fazla_ad") or [])
    assert d.get("etiket") == "DS-000001"

    # ve silmek hepsini gerçekten geri alır
    matching.okutma_sil(c, _taze(c, ot), oid)
    assert not c.execute("SELECT 1 FROM fazla_ad WHERE barkod='DM000001'").fetchone()
    assert c.execute("SELECT oturum FROM etiket WHERE kod='DS000001'").fetchone()["oturum"] is None


def test_D2_fazla_bagla_seri_etiketini_KAYDA_baglar():
    """Bağlanan kaydın DS- etiketi defterde o satırı göstermeli."""
    c, ot, (bid,) = _kur([("KOD1", "KOD1SAYIM1", "seri", 1, 1)])
    etiketler.bas(c, "seri", adet=3)
    _okut(c, ot, "DS-000001", "##FAZLA##")
    oid = c.execute("SELECT id FROM okutma WHERE tip='fazla'").fetchone()["id"]
    c.execute("UPDATE okutma SET ad='x' WHERE id=?", (oid,))
    matching.fazla_bagla(c, oid, bid)
    e = c.execute("SELECT * FROM etiket WHERE kod='DS000001'").fetchone()
    assert e["beklenen_id"] == bid and e["malzeme"] == "KOD1"


# ------------------------------------------- D3: boş havuz malzeme etiketi defteri
def test_D3_bos_havuz_malzeme_etiketi_deftere_islenir():
    """DM- etiketi çözülünce `etiket.malzeme` DOLMALI, yalnızca `eslesme` değil."""
    c, ot, (bid,) = _kur([("KOD1", "SNAAA111", "seri", 1, 0)])
    etiketler.bas(c, "malzeme", adet=2, kapsam="bos")
    _okut(c, ot, "DM-000001", "##ATLA##")
    kid = c.execute("SELECT id FROM kuyruk WHERE oturum=?", (ot["id"],)).fetchone()["id"]
    matching.kuyruk_coz(c, kid, bid)
    assert c.execute("SELECT kod FROM eslesme WHERE barkod='DM000001'").fetchone()["kod"] == "KOD1"
    assert c.execute("SELECT malzeme FROM etiket WHERE kod='DM000001'"
                     ).fetchone()["malzeme"] == "KOD1", "defter de bilmeli"


def test_D3_ayni_malzemeye_IKINCI_etiket_basilmaz():
    """Asıl sonuç fiziksel: aynı ürünün üstünde iki farklı DM- kodu dolaşmamalı.

    `bas(kapsam="eksik")` "bu malzemenin etiketi var mı" diye `etiket.malzeme`
    alanına bakıyor. Defter boş kaldığı için aynı malzemeye ikinci bir numara
    basılıyordu — gerçek veriyle doğrulandı (DM-000002 -> SR335 eşleşmede
    yazılı, defterde boş; yeniden basımda SR335'e DM-000174 veriliyordu).
    """
    c, ot, (bid,) = _kur([("KOD1", "SNAAA111", "seri", 1, 0)])
    etiketler.bas(c, "malzeme", adet=2, kapsam="bos")
    _okut(c, ot, "DM-000001", "##ATLA##")
    kid = c.execute("SELECT id FROM kuyruk WHERE oturum=?", (ot["id"],)).fetchone()["id"]
    matching.kuyruk_coz(c, kid, bid)

    _, satirlar = etiketler.bas(c, "malzeme", kapsam="eksik", yukleme=ot["yukleme"],
                               ambar="1")
    assert not [s for s in satirlar if s["malzeme"] == "KOD1"], \
        "KOD1'in etiketi zaten var (DM-000001) — ikincisi basılmamalı"


def test_D3_gerial_malzeme_etiketini_havuza_dondurur():
    c, ot, (bid,) = _kur([("KOD1", "SNAAA111", "seri", 1, 0)])
    etiketler.bas(c, "malzeme", adet=2, kapsam="bos")
    _okut(c, ot, "DM-000001", "##ATLA##")
    kid = c.execute("SELECT id FROM kuyruk WHERE oturum=?", (ot["id"],)).fetchone()["id"]
    matching.kuyruk_coz(c, kid, bid)
    matching.gerial(c, _taze(c, ot))
    assert c.execute("SELECT malzeme FROM etiket WHERE kod='DM000001'"
                     ).fetchone()["malzeme"] is None


def test_D3_goc_mevcut_defteri_onarir():
    """Açılışta `eslesme`'de bağlı olan eski DM- etiketleri deftere yazılır."""
    c = dbm.baglan(":memory:")
    c.execute("INSERT INTO etiket(kod,gosterim,tur,ts) VALUES('DM000002','DM-000002','malzeme','t')")
    c.execute("INSERT INTO eslesme VALUES('DM000002','SR335','','t')")
    dbm.malzeme_etiket_defterini_onar(c)
    assert c.execute("SELECT malzeme FROM etiket WHERE kod='DM000002'"
                     ).fetchone()["malzeme"] == "SR335"
    # idempotent + bağlı etiketin malzemesi değişmez
    c.execute("UPDATE eslesme SET kod='BASKA' WHERE barkod='DM000002'")
    dbm.malzeme_etiket_defterini_onar(c)
    assert c.execute("SELECT malzeme FROM etiket WHERE kod='DM000002'"
                     ).fetchone()["malzeme"] == "SR335"


# ------------------------------------------------- D4: miktar kapasiteye sığmalı
def test_D4_buyuk_miktarli_fazla_tek_cihazlik_kayda_BAGLANAMAZ():
    """150 adetlik fazla, 1 adetlik seri satırına bağlanırsa 149 adet uçardı."""
    c, ot, (bid,) = _kur([("KOD1", "KOD1SAYIM1", "seri", 1, 1)])
    _okut(c, ot, "##ADET-150##", "BILINMEYEN-URUN", "##FAZLA##")
    oid = c.execute("SELECT id FROM okutma WHERE tip='fazla'").fetchone()["id"]
    assert c.execute("SELECT miktar FROM okutma WHERE id=?", (oid,)).fetchone()["miktar"] == 150

    r = matching.fazla_bagla(c, oid, bid)
    assert r.get("hata") == "miktar_sigmiyor"
    assert c.execute("SELECT tip FROM okutma WHERE id=?", (oid,)).fetchone()["tip"] == "fazla"


def test_D4_sigan_miktar_baglanir():
    """200 adetlik lota 150 adetlik fazla sığar."""
    c, ot, (bid,) = _kur([("LOT1", "LOT1-A", "lot", 200, 0)])
    _okut(c, ot, "##ADET-150##", "BILINMEYEN-URUN", "##FAZLA##")
    oid = c.execute("SELECT id FROM okutma WHERE tip='fazla'").fetchone()["id"]
    assert matching.fazla_bagla(c, oid, bid)["tip"] == "eslesti"
    assert matching.sayaclar(c, _taze(c, ot))["okutulan"] == 150


def test_D4_eslestirme_ekrani_miktari_GOSTERIR():
    """Kullanıcı reddi anlamak için adedi görmek zorunda."""
    c, ot, _ = _kur([("KOD1", "KOD1SAYIM1", "seri", 1, 1)])
    _okut(c, ot, "##ADET-150##", "BILINMEYEN-URUN", "##FAZLA##")
    v = matching.esleme_verisi(c, _taze(c, ot))
    assert v["fazla"][0]["miktar"] == 150


# ------------------------------- D5: bellek veritabanı gerçek deftere yazmasın
def test_D5_bellek_veritabani_gercek_etiket_defterine_DOKUNMAZ():
    """`:memory:` bağlantısı proje `data/etiket` klasörünü ne okur ne yazar.

    `klasor()` eskiden dosya yolu olmayan bağlantıda `data/etiket`e düşüyordu
    — docstring'inde yazan amacın tam tersi. Sonuç 2026-09-02'de gerçekleşti:
    `baglan(":memory:")` ile çalışan bir denetim betiği önce gerçek defteri
    OKUDU (240 seri + 24 malzeme etiketi belleğe geldi), sonra kendi iki
    satırlık deneme basımıyla `basim-1.csv` ve `basim-2.csv` dosyalarını EZDİ.
    Yedekten geri alındı.

    Basılmış fiziksel etiket veritabanından uzun ömürlüdür (CLAUDE.md §12.7);
    kalıcı olmayan bir veritabanının o deftere dokunacak hiçbir işi yok.
    """
    c = dbm.baglan(":memory:")
    assert etiketler.klasor(c) is None
    # basım CSV yazmaya çalışmaz, patlamaz da
    assert etiketler.csv_yaz(c, 1, [{"kod": "DM000001", "gosterim": "DM-000001",
                                     "tur": "malzeme", "malzeme": None}]) is None
    # gerçek defterden okumaz: bellek veritabanı BOŞ açılır
    assert not c.execute("SELECT 1 FROM etiket LIMIT 1").fetchone()
    assert etiketler.csv_geri_yukle(c) == 0
    # kap defteri de aynı kapıdan geçer
    from app import kutu as kutum
    assert kutum.csv_yaz(c) is None
    assert kutum.csv_geri_yukle(c) == 0


def test_D5_dosya_tabanli_veritabani_KENDI_klasorune_yazar(tmp_path):
    """Gerçek dosyada defter çalışmaya devam eder — yanındaki klasöre."""
    yol = str(tmp_path / "sayim.db")
    c = dbm.baglan(yol)
    etiketler.bas(c, "seri", adet=2)
    assert etiketler.klasor(c) == str(tmp_path / "etiket")
    assert (tmp_path / "etiket" / "basim-1.csv").is_file()
