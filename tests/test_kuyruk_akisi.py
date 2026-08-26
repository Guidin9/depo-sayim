"""Kuyruk birikmesini önleyen davranışlar.

Sahadaki sorun: gün sonunda kuyrukta onlarca kayıt oluyor ve hangi ürünün
hangi rafta okutulduğu hatırlanamıyor. Çözüm sırası:
  1. raftan ayrılmadan çözmeye zorla (raf_engel / bitir_engel)
  2. ürünü bulmak için arama / filtreleme (aday önerisi kaldırıldı)
  3. not ve fotoğraf (isteğe bağlı hatırlatıcılar)
"""
from app import matching
from tests.conftest import haric_kur, oturum_taze

SONRAKI = "##SONRAKI##"
BILINMEYEN = ("198701689928", "EDBP0153231475674")


def _kuyruga_at(yaz, raf=None):
    if raf:
        yaz("##RAF-%s##" % raf)
    return yaz(*BILINMEYEN, SONRAKI)


# ---------------------------------------------------------------- 1. raf kapısı
def test_raf_degistirmek_cozulmemis_kuyrukta_engellenir(c, ot, yaz):
    r = _kuyruga_at(yaz, "A1")
    assert r["tip"] == "kuyruk"

    engel = yaz("##RAF-B2##")
    assert engel["tip"] == "raf_engel"
    assert engel["eski_raf"] == "A1" and engel["yeni_raf"] == "B2"
    assert engel["kuyruk"][0]["barkodlar"] == list(BILINMEYEN)
    assert engel["ses"] == "uyari"
    # raf değişmedi — hâlâ A1'desin
    assert oturum_taze(c, ot)["aktif_raf"] == "A1"


def test_kuyruk_cozulunce_raf_degisir(c, ot, yaz):
    _kuyruga_at(yaz, "A1")
    kid = c.execute("SELECT id FROM kuyruk WHERE oturum=?", (ot["id"],)).fetchone()["id"]
    hedef = c.execute("SELECT id FROM beklenen WHERE seri='0WGP72SAYIM1'").fetchone()["id"]
    matching.kuyruk_coz(c, kid, hedef)

    assert yaz("##RAF-B2##")["tip"] == "raf"
    assert oturum_taze(c, ot)["aktif_raf"] == "B2"


def test_baska_rafin_kuyrugu_engellemez(c, ot, yaz):
    """A1'de takılan kayıt, B2'den C3'e geçmeyi engellememeli."""
    _kuyruga_at(yaz, "A1")
    matching.okut(c, oturum_taze(c, ot), "##RAF-B2##", zorla=True)
    assert yaz("##RAF-C3##")["tip"] == "raf"
    assert oturum_taze(c, ot)["aktif_raf"] == "C3"


def test_zorla_ile_gecilebilir(c, ot, yaz):
    _kuyruga_at(yaz, "A1")
    r = matching.okut(c, oturum_taze(c, ot), "##RAF-B2##", zorla=True)
    assert r["tip"] == "raf"
    assert oturum_taze(c, ot)["aktif_raf"] == "B2"


def test_ayni_rafi_tekrar_okutmak_engellenmez(c, ot, yaz):
    """A1'deyken yine A1 okutmak raf değişimi değildir."""
    _kuyruga_at(yaz, "A1")
    assert yaz("##RAF-A1##")["tip"] == "raf"


def test_bitirmek_cozulmemis_kuyrukta_engellenir(c, ot, yaz):
    _kuyruga_at(yaz, "A1")
    engel = yaz("##BITIR##")
    assert engel["tip"] == "bitir_engel"
    assert len(engel["kuyruk"]) == 1
    assert oturum_taze(c, ot)["durum"] == "acik"

    r = matching.okut(c, oturum_taze(c, ot), "##BITIR##", zorla=True)
    assert r["tip"] == "bitti"
    assert oturum_taze(c, ot)["durum"] == "bitti"


def test_rafsiz_sayimda_kapi_calisir(c, ot, yaz):
    """Raf hiç kullanılmıyorsa da bitirirken kuyruk uyarısı gelmeli."""
    yaz(*BILINMEYEN, SONRAKI)
    assert yaz("##BITIR##")["tip"] == "bitir_engel"


def test_bitir_kapanmamis_grubu_da_gorur(c, ot, yaz):
    """Regresyon (ACIL_PLAN.md A2): kapı kendi deliğini açıyordu.

    Kullanıcı tanınmayan bir ürünü okutup SONRAKI demeden ##BITIR## derse:
    kapılar önce boş kuyruğa bakıyor, SONRA `grup_coz` tampondaki grubu YENİ
    bir kuyruk kaydına yazıyor ve oturum kapanıyordu. Kullanıcı "bitti" sesini
    duyup depodan çıkıyor, elindeki ürün kayıt dışı kalıyordu.

    Doğrusu: tampon önce kapanır, kapılar sonra bakar.
    """
    yaz(*BILINMEYEN)                       # SONRAKI YOK — grup hâlâ tamponda
    r = yaz("##BITIR##")
    assert r["tip"] == "bitir_engel"
    assert len(r["kuyruk"]) == 1
    assert oturum_taze(c, ot)["durum"] == "acik"
    assert len(matching.bekleyen_kuyruk(c, ot["id"])) == 1


def test_bitir_kapanmamis_eslesen_grubu_kaybetmez(c, ot, yaz):
    """Tanınan bir grup da kaybolmamalı: yazılır ve oturum normal kapanır."""
    b = c.execute("""SELECT seri FROM beklenen WHERE yukleme=1 AND ambar='1'
                     AND haric=0 AND izleme='seri' AND kirli=0 AND seri<>''
                     ORDER BY id LIMIT 1""").fetchone()
    yaz(b["seri"])                         # SONRAKI YOK
    assert yaz("##BITIR##")["tip"] == "bitti"
    assert oturum_taze(c, ot)["durum"] == "bitti"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND tip='eslesti'",
                     (ot["id"],)).fetchone()["n"] == 1


# ---------------------------------------------------------------- 2. arama / listeleme
#
# "Bu olabilir" aday önerisi kaldırıldı: sahada doğru sonuç vermiyordu
# (DEMO_FEEDBACK.md 4). Yerine kullanıcının kendi aradığı, filtrelediği liste.
def test_arama_kod_aciklama_ve_seri_ile_bulur(c, ot):
    for q in ("0WGP72", "SSD", "0WGP72SAYIM1"):
        r = matching.ara(c, ot["yukleme"], ot["ambar"], q, oturum=ot["id"])
        assert r["satirlar"], "%s bulunamadı" % q


def test_arama_bos_sorguda_listeler(c, ot):
    """q boşken de çalışır — filtrelerle düz liste gezilebilsin."""
    r = matching.ara(c, ot["yukleme"], ot["ambar"], "", limit=10, oturum=ot["id"])
    assert len(r["satirlar"]) == 10 and r["toplam"] > 10


def test_arama_varsayilan_hepsini_dondurur(c, ot):
    """Regresyon: eşleştirme listesi eksiksiz olmalı.

    Varsayılan limit 25'ti ve arayüzler 40/50 istiyordu; sayfalama da
    olmadığı için 800+ satırlık bir kümenin yalnızca ilk sayfası
    görülebiliyordu. Kullanıcı listede olmayan ürünü tahmin edip aramak
    zorunda kalıyordu (saha bildirimi 2026-08-23).
    """
    r = matching.ara(c, ot["yukleme"], ot["ambar"], "", oturum=ot["id"])
    assert len(r["satirlar"]) == r["toplam"] > 100

    # limit hâlâ açıkça istenebilir (test ve sayfalama için)
    az = matching.ara(c, ot["yukleme"], ot["ambar"], "", limit=5, oturum=ot["id"])
    assert len(az["satirlar"]) == 5 and az["toplam"] == r["toplam"]


def test_arama_sayfalar(c, ot):
    ilk = matching.ara(c, ot["yukleme"], ot["ambar"], "", limit=5, oturum=ot["id"])
    ikinci = matching.ara(c, ot["yukleme"], ot["ambar"], "", limit=5, offset=5,
                          oturum=ot["id"])
    assert ilk["toplam"] == ikinci["toplam"]
    assert {s["id"] for s in ilk["satirlar"]} & {s["id"] for s in ikinci["satirlar"]} == set()


def test_arama_sadece_acik_sayilani_eler(c, ot, yaz):
    """Seri takipli satır sayılınca 'sayılmamış' filtresinden düşer."""
    b = c.execute("""SELECT kod, seri FROM beklenen WHERE izleme='seri' AND ambar='1'
                     AND kirli=0 GROUP BY kod HAVING COUNT(*)=1 LIMIT 1""").fetchone()
    ot2 = oturum_taze(c, ot)
    once = matching.ara(c, ot["yukleme"], ot["ambar"], b["kod"], oturum=ot["id"],
                        sadece_acik=True)
    assert any(s["kod"] == b["kod"] for s in once["satirlar"])

    yaz(b["seri"], SONRAKI)
    sonra = matching.ara(c, ot["yukleme"], ot["ambar"], b["kod"], oturum=ot2["id"],
                         sadece_acik=True)
    assert all(s["kod"] != b["kod"] for s in sonra["satirlar"])


def test_arama_lot_yarim_sayilinca_acik_kalir(c, ot, yaz):
    """77 beklenen lottan 1 okutulduysa kalem hâlâ 'sayılmamış' sayılır."""
    yaz("0C5RNH", SONRAKI)
    r = matching.ara(c, ot["yukleme"], ot["ambar"], "0C5RNH",
                     oturum=oturum_taze(c, ot)["id"], sadece_acik=True)
    assert any(s["kod"] == "0C5RNH" for s in r["satirlar"])


def test_arama_kirli_ve_izleme_filtreleri(c, ot):
    kirli = matching.ara(c, ot["yukleme"], ot["ambar"], "", limit=50, oturum=ot["id"],
                         kirli=True)
    assert kirli["satirlar"] and all(s["kirli"] == 1 for s in kirli["satirlar"])

    lot = matching.ara(c, ot["yukleme"], ot["ambar"], "", limit=50, oturum=ot["id"],
                       izleme="lot")
    assert lot["satirlar"] and all(s["izleme"] == "lot" for s in lot["satirlar"])


def test_arama_ayni_raftakini_one_alir(c, ot, yaz):
    yaz("##RAF-A1##", "0C5RNH", SONRAKI)
    r = matching.ara(c, ot["yukleme"], ot["ambar"], "", limit=5,
                     oturum=ot["id"], raf="A1")
    assert r["satirlar"][0]["kod"] == "0C5RNH" and r["satirlar"][0]["ayni_raf"] == 1


def test_arama_haric_kalemi_gostermez(c, ot):
    """Lisans / hizmet kalemi fiziksel nesne değil, bağlanacak hedef de değil."""
    _, _, kod = haric_kur(c)
    r = matching.ara(c, ot["yukleme"], ot["ambar"], kod, limit=50,
                     oturum=ot["id"])
    assert r["satirlar"] == []


def test_aramadan_secince_kuyruk_kapanir(c, ot, yaz):
    r = _kuyruga_at(yaz, "A1")
    hedef = matching.ara(c, ot["yukleme"], ot["ambar"], "0WGP72",
                         oturum=ot["id"])["satirlar"][0]
    matching.kuyruk_coz(c, r["kuyruk_id"], hedef["id"])
    assert matching.bekleyen_kuyruk(c, ot["id"]) == []
    assert matching.sayaclar(c, ot)["kuyruk"] == 0


# ---------------------------------------------------------------- 3. not
def test_kuyruga_not_yazilir(c, ot, yaz):
    _kuyruga_at(yaz, "A1")
    kid = matching.bekleyen_kuyruk(c, ot["id"])[0]["id"]
    c.execute("UPDATE kuyruk SET not_=? WHERE id=?", ("siyah kutu, üst raf", kid))
    assert matching.bekleyen_kuyruk(c, ot["id"])[0]["not_"] == "siyah kutu, üst raf"


# ---------------------------------------------------------------- 4. sayım sonu eşleştirme
#
# Fazla çıkan ürün çoğu zaman eksik görünen kaydın ta kendisidir, sadece seri
# numarası tutmamıştır. Rapor üretilmeden önce ikisi yan yana konur
# (DEMO_FEEDBACK.md 6).
def _fazla_yap(c, ot, yaz):
    """Onaydan geçirilmiş bir fazla kaydı üretir; okutma id'sini döner."""
    r = yaz("210-BEJO", "YENISERI12345", SONRAKI)
    assert r["tip"] == "onay"
    return matching.kuyruk_fazla(c, r["kuyruk_id"])["okutma"][0]


def test_esleme_verisi_fazla_ve_eksigi_yanyana_verir(c, ot, yaz):
    oid = _fazla_yap(c, ot, yaz)
    v = matching.esleme_verisi(c, oturum_taze(c, ot))
    assert [f["id"] for f in v["fazla"]] == [oid]
    assert any(e["kod"] == "210-BEJO" for e in v["eksik"])


def test_esleme_rapordaki_eksikle_ayni_listedir(c, ot, yaz):
    """Tek gerçek kuralı: ekran ile rapor aynı satırları göstermeli."""
    from app import reports
    yaz("5S47WC2", SONRAKI)
    v = matching.esleme_verisi(c, oturum_taze(c, ot))
    rapor = reports.rapor_verisi(c, ot["id"])["Eksik"]
    assert len(v["eksik"]) == len(rapor["satirlar"])


def test_fazla_baglayinca_eslesir_ve_ogrenir(c, ot, yaz):
    oid = _fazla_yap(c, ot, yaz)
    hedef = c.execute("""SELECT id FROM beklenen WHERE kod='210-BEJO'
                         AND seri<>'' ORDER BY id LIMIT 1""").fetchone()["id"]
    s = matching.fazla_bagla(c, oid, hedef)
    assert s["tip"] == "eslesti" and s["kod"] == "210-BEJO"

    x = c.execute("SELECT * FROM okutma WHERE id=?", (oid,)).fetchone()
    assert x["tip"] == "eslesti" and x["beklenen_id"] == hedef
    # barkod kalıcı öğrenildi
    assert c.execute("SELECT kod FROM eslesme WHERE barkod='YENISERI12345'"
                     ).fetchone()["kod"] == "210-BEJO"


def test_ayni_kayda_ikinci_kez_baglanmaz(c, ot, yaz):
    """Zaten sayılmış satır ikinci bir fazlaya bağlanamaz — çift sayım olurdu."""
    oid = _fazla_yap(c, ot, yaz)
    hedef = c.execute("SELECT id FROM beklenen WHERE seri='5S47WC2'").fetchone()["id"]
    yaz("5S47WC2", SONRAKI)                       # hedef artık sayıldı
    assert "hata" in matching.fazla_bagla(c, oid, hedef)


def test_esleme_geri_alinabilir(c, ot, yaz):
    oid = _fazla_yap(c, ot, yaz)
    hedef = c.execute("""SELECT id FROM beklenen WHERE kod='210-BEJO'
                         AND seri<>'' ORDER BY id LIMIT 1""").fetchone()["id"]
    matching.fazla_bagla(c, oid, hedef)
    assert matching.fazla_coz_ayir(c, oid)["tip"] == "fazla"
    x = c.execute("SELECT * FROM okutma WHERE id=?", (oid,)).fetchone()
    assert x["tip"] == "fazla" and x["beklenen_id"] is None
    # eşleştirilmemiş bir kayıt geri alınamaz
    assert "hata" in matching.fazla_coz_ayir(c, oid)


def test_fazla_komutu_grubu_tek_urun_sayar(c, ot, yaz):
    """##FAZLA## tamponun tamamını TEK fazla kaydı yapar.

    Grup mantığının çekirdeği (CLAUDE.md 4.4): bir ürünün üstündeki bütün
    barkodlar aynı gruba okutulur. Barkod başına satır yazmak o ürünü rapora
    N ayrı fazla olarak koyar ve eşleştirmede N kez sorar.
    """
    r = yaz(*BILINMEYEN, "##FAZLA##")
    assert r["tip"] == "fazla_elle"
    assert len(r["okutma"]) == 1, "iki barkod tek ürün, tek kayıt olmalı"

    x = c.execute("SELECT ham, seri, miktar FROM okutma WHERE id=?",
                  (r["okutma"][0],)).fetchone()
    assert x["ham"] == " + ".join(BILINMEYEN)   # denetim izi: ikisi de duruyor
    assert x["seri"] == BILINMEYEN[1]           # UPC değil, gerçek S/N
    assert x["miktar"] == 1
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND tip='fazla'",
                     (ot["id"],)).fetchone()["n"] == 1


def test_kodu_bilinen_fazla_foto_istemez(c, ot, yaz):
    """Kimliği olan fazla kaydı fotoğrafsız da bitirilebilir.

    Regresyon: eskiden HER fazla kaydı fotoğraf istiyordu. Kullanıcı ürünün
    ne olduğunu yazdığı hâlde fotoğraf soruluyor ve oturum kapatılamıyordu
    (saha bildirimi 2026-08-23). Fotoğraf denetlenebilirliğin tek yolu değil:
    `kod` ya da `ad` varsa satırın ne olduğu zaten bellidir.
    """
    _fazla_yap(c, ot, yaz)                     # 210-BEJO -> kod biliniyor
    assert matching.fotosuz_fazlalar(c, ot["id"]) == []
    assert yaz("##BITIR##")["tip"] == "bitti"


def test_adi_yazilan_kodsuz_fazla_foto_istemez(c, ot, yaz):
    """Kodu olmayan ürün: önce ad sorulur, ad yazılınca fotoğraf istenmez."""
    r = yaz("KAYITSIZ-URUN-9911", "##FAZLA##")
    oid = r["okutma"][0]
    assert yaz("##BITIR##")["tip"] == "ad_engel"

    c.execute("UPDATE okutma SET ad=? WHERE id=?", ("Kırmızı HP güç kablosu", oid))
    assert matching.adsiz_fazlalar(c, ot["id"]) == []
    assert matching.fotosuz_fazlalar(c, ot["id"]) == []
    assert yaz("##BITIR##")["tip"] == "bitti"


def test_kimliksiz_fazla_hala_foto_ister(c, ot, yaz):
    """Ne kodu ne adı olan kayıt fotoğrafsız kalmaz.

    Pratikte `ad_engel` önce devreye girer; bu test kuralın kendisini
    doğruluyor, kapı sırasını değil.
    """
    r = yaz("KAYITSIZ-URUN-9911", "##FAZLA##")
    oid = r["okutma"][0]
    assert [f["id"] for f in matching.fotosuz_fazlalar(c, ot["id"])] == [oid]

    c.execute("INSERT INTO kuyruk_foto(okutma,ts,tur,boyut,veri) "
              "VALUES(?,'','image/jpeg',3,?)", (oid, b"jpg"))
    assert matching.fotosuz_fazlalar(c, ot["id"]) == []


def test_ayni_kayda_iki_kuyruk_baglanamaz(c, ot, yaz):
    """Çift bağlama koruması — iki fiziksel ürün tek kayıtla kapatılmasın.

    `fazla_bagla`'da bu koruma vardı, `kuyruk_coz`'da YOKTU. Arayüz sayılmış
    kayıtları da listelediği için sahada kolayca oluşuyordu.
    """
    k1 = _kuyruga_at(yaz, "A1")["kuyruk_id"]
    hedef = c.execute("SELECT id FROM beklenen WHERE seri='0WGP72SAYIM1'").fetchone()["id"]
    assert matching.kuyruk_coz(c, k1, hedef)["tip"] == "eslesti"

    k2 = yaz("BASKA-BARKOD-7788", SONRAKI)["kuyruk_id"]
    assert matching.kuyruk_coz(c, k2, hedef) == {"hata": "bu kayıt bu oturumda zaten sayıldı"}


def test_kuyrukta_cekilen_foto_fazla_kaydina_tasinir(c, ot, yaz):
    """Aynı fotoğraf ikinci kez istenmesin: kuyrukta çekildiyse yeter."""
    r = yaz("210-BEJO", "YENISERI12345", SONRAKI)
    c.execute("INSERT INTO kuyruk_foto(kuyruk,ts,tur,boyut,veri) "
              "VALUES(?,'','image/jpeg',3,?)", (r["kuyruk_id"], b"jpg"))
    matching.kuyruk_fazla(c, r["kuyruk_id"])
    assert matching.fotosuz_fazlalar(c, ot["id"]) == []
