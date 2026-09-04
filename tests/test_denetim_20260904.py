"""2026-09-04 bağımsız denetimi — DENETIM_20260904.md.

478 test geçerken bulunan hatalar. Ortak tema: ÜÇ DÜZELTMENİN YARISI
UYGULANMIŞ — kural bir dalda kapatılmış, aynı kuralı kullanan öteki dallara
taşınmamış.

| Kapatılan hata | Düzeltme nereye kondu | Nereye konmadı |
|---|---|---|
| B2 (UPC seri no önerilir) | `matching._sn_karar` | `reports._yeni_seri` -> K1 |
| B4 (sayaç satır bazlı)    | `sayaclar`, `ara`     | `oturumlar.gecmis` -> Y2 |
| D1 (seri satırı miktar>1) | `kapasite_kaldi`      | `slot` sorgusu -> Y1 |

Dördüncüsü ters yönde: S2 düzeltmesi yeni bir sessiz çift sayım açtı (K2).

K1'in birim testleri `test_b1_barkod.py`'de (B2 ailesinin yanında) duruyor.
"""
import pytest

from app import db as dbm, etiketler, matching, oturumlar


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


def _fazla(c, ot):
    return c.execute("SELECT COUNT(*) n, COALESCE(SUM(miktar),0) m FROM okutma "
                     "WHERE oturum=? AND tip='fazla'", (ot["id"],)).fetchone()


def _adlandir(c, okutma_id, ad):
    """Arayüzün `PATCH /okutma/{id}` ile yaptığı: adı yaz, sonra öğren."""
    c.execute("UPDATE okutma SET ad=? WHERE id=?", (ad, okutma_id))
    matching.fazla_ogren(c, okutma_id)


# ------------------------------------------- K2: DS- etiketi ikinci kez okutma
def test_K2_ayni_seri_etiketi_ikinci_kez_ikinci_fazla_yazmaz():
    """DS- etiketi TEKİL cihaza aittir — ikinci okutma ikinci cihaz olamaz.

    Gerçek veride oldu (28.08 sayımı): DS-000054 iki fazla kaydında, okutma
    #23 ve #26, 36 saniye arayla.

    Kök sebep: `coz()` 1c yalnızca `etiket.beklenen_id`'ye bakıyordu. Fazla
    yolundan bağlanan etikette o alan NULL kalır (Tiger'da kaydı yok) ama
    `oturum` DOLAR — yani uygulama etiketin tükendiğini biliyor ve okumuyordu.
    """
    c, ot, _ = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0)])
    etiketler.bas(c, "seri", adet=3)
    r = _okut(c, ot, "DS-000001", "##FAZLA##")
    assert r["tip"] == "fazla_elle"
    _adlandir(c, r["okutma"][0], "KABLO 5M")

    r2 = _okut(c, ot, "DS-000001", "##SONRAKI##")
    assert r2["tip"] == "tekrar", "aynı etiket ikinci kez sayıldı"
    assert "DS-000001" in (r2.get("not") or "")
    n = _fazla(c, ot)
    assert (n["n"], n["m"]) == (1, 1)


def test_K2_ogrenilmis_ad_ile_birlikte_de_sessiz_kalmaz():
    """Asıl sessiz yol: etiket + ÖĞRENİLMİŞ barkod.

    `##FAZLA##` yolunda ikinci kayıt adsız kalıp `ad_engel`e takılıyordu
    (kullanıcı fark edebilirdi). Ad `fazla_ad`'a öğrenilmişse ikinci okutma
    `fazla_bilinen` dalından SORUSUZ geçiyor: yeşil akış, hiçbir kapı yok.
    """
    c, ot, _ = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0)])
    etiketler.bas(c, "seri", adet=3)
    r = _okut(c, ot, "DS-000001", "5901234123457", "##FAZLA##")
    _adlandir(c, r["okutma"][0], "SUNUCU RAY KİTİ")

    r2 = _okut(c, ot, "DS-000001", "5901234123457", "##SONRAKI##")
    assert r2["tip"] == "tekrar", "öğrenilmiş ad çift sayımı sessizce yazdı"
    n = _fazla(c, ot)
    assert (n["n"], n["m"]) == (1, 1)
    # Tampon DURUR: kullanıcı gerçekten ikinci bir cihaz tutuyorsa ##FAZLA##
    # ile kendi kararını verebilmeli — uygulama onun yerine karar vermiyor.
    assert r2.get("tampon_duruyor")


def test_K2_dm_etiketi_ve_upc_ikinci_kez_okutulabilir():
    """Kural YALNIZCA DS- etiketine ait.

    Malzeme etiketi ve perakende barkodu ürün TİPİNİ gösterir: aynı üründen
    iki adet olabilir, ikinci okutma doğru olabilir. Buraya `tekrar` koymak
    dökme kalemlerde sayımı durdururdu.
    """
    c, ot, _ = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0)])
    r = _okut(c, ot, "DM-999999", "##FAZLA##")
    _adlandir(c, r["okutma"][0], "SARF KABLO")
    r2 = _okut(c, ot, "DM-999999", "##SONRAKI##")
    assert r2["tip"] == "fazla_bilinen"
    assert _fazla(c, ot)["n"] == 2


def test_K2_gelecek_oturumda_etiket_yeniden_okutulabilir():
    """Ölçüt BU oturum: seneye etiket hâlâ ürünün üstünde ve sayılmalı."""
    c, ot, _ = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0)])
    etiketler.bas(c, "seri", adet=3)
    r = _okut(c, ot, "DS-000001", "##FAZLA##")
    _adlandir(c, r["okutma"][0], "KABLO 5M")
    oturumlar.bitir(c, ot["id"])

    ot2 = oturumlar.ac(c, ot["yukleme"], "1")
    assert ot2["id"] != ot["id"]
    assert matching.coz(c, "DS-000001", ot2["yukleme"], "1",
                        ot2["id"])["t"] == "etiket_bos"


# ------------------------------------- K3: kilit "Tiger'da yok" bilgisini ezmez
def test_K3_kilit_ogrenilmis_fazlayi_ezmez():
    """Kilit bir ORTAM KİPİ, `fazla_ad` kullanıcının AÇIK kararıdır.

    Kilidin dayanağı "grupta malzeme kodu yok, demek ki kilitli malzemenin bir
    cihazı". Grupta `fazla_ad`'a yazılmış bir barkod varsa o dayanak yanlıştır.

    Üretildi: adı "SARF KABLO" diye öğrenilmiş bir kablo, kilitli malzemenin
    kirli slotuna yazılıyor ve ekran YEŞİL yanıyordu.
    """
    c, ot, _ = _kur([("KOD1", "KOD1SAYIM1", "seri", 1, 1)])
    r = _okut(c, ot, "DM-999999", "##FAZLA##")
    _adlandir(c, r["okutma"][0], "SARF KABLO")

    assert _okut(c, ot, "KOD1", "##KILIT##")["tip"] == "kilit"
    assert _taze(c, ot)["sabit_kod"] == "KOD1"

    r2 = _okut(c, ot, "DM-999999", "##SONRAKI##")
    assert r2["tip"] == "fazla_bilinen", "kilit açık kararı ezdi"
    assert r2["ad"] == "SARF KABLO"
    # Kilitli malzemenin kirli slotu BOŞ kalmalı.
    assert not c.execute("SELECT 1 FROM okutma WHERE oturum=? AND kod='KOD1'",
                         (ot["id"],)).fetchone()


def test_K3_kilit_taninmayan_barkodda_calismaya_devam_eder():
    """Kilidin asıl işi bozulmamalı: bilinmeyen barkod hâlâ kilide yazılır.

    I2'nin tamamı buna dayanıyor — 21 cihazlı malzemede kodu bir kez okutup
    yalnız seri numaralarıyla devam etmek. Aşırı düzeltme burada görünürdü.
    """
    c, ot, _ = _kur([("KOD1", "KOD1SAYIM1", "seri", 1, 1)])
    _okut(c, ot, "KOD1", "##KILIT##")
    r = _okut(c, ot, "GERCEKSN0001", "##SONRAKI##")
    assert r["tip"] == "slot"
    assert r["kod"] == "KOD1"
    assert r["yeni"] == "GERCEKSN0001"


def test_K3_elle_okutulan_kod_ogrenilmis_fazlayi_da_yener():
    """Elle okutulan malzeme kodu her şeyi yener — kilit kuralının aynısı.

    Kullanıcı hem kodu hem daha önce fazla yazılmış bir barkodu okutuyorsa
    elindeki O malzemedir; barkod ona öğrenilir.
    """
    c, ot, _ = _kur([("KOD1", "KOD1SAYIM1", "seri", 1, 1)])
    r = _okut(c, ot, "DM-999999", "##FAZLA##")
    _adlandir(c, r["okutma"][0], "SARF KABLO")
    r2 = _okut(c, ot, "KOD1", "DM-999999", "##SONRAKI##")
    assert r2["tip"] == "slot"
    assert r2["kod"] == "KOD1"


# ------------------------------- Y1: aday arayan sorgular da kapasite ölçütünde
def test_Y1_cok_adetli_kirli_slot_ikinci_cihazi_da_alir():
    """`izleme='seri'` + `kirli=1` + `miktar=2`: iki cihaz da slotu doldurur.

    D1 ölçütü `beklenen_adet`e taşınırken `kapasite_kaldi`, `sayaclar`, `ara`,
    `eksik_lotlar` ve `reports.eksik_kayitlar` geçirilmiş, ADAY ARAYAN iki
    sorgu geçirilmemişti. `slot` sorgusu hâlâ "hiç okutulmamış" diyordu:
    ikinci cihaz kapasite dururken `fazla_onay` kuyruğuna düşüyor, satır hem
    1 adet eksik hem 1 adet onay bekler görünüyordu.
    """
    c, ot, (bid,) = _kur([("KOD1", "KOD1SAYIM1", "seri", 2, 1)])
    r1 = _okut(c, ot, "KOD1", "SNCIHAZ0001", "##SONRAKI##")
    assert r1["tip"] == "slot"
    r2 = _okut(c, ot, "KOD1", "SNCIHAZ0002", "##SONRAKI##")
    assert r2["tip"] == "slot", "ikinci cihaz onay kuyruğuna düştü"
    assert matching.sayaclar(c, _taze(c, ot))["okutulan"] == 2

    b = c.execute("SELECT * FROM beklenen WHERE id=?", (bid,)).fetchone()
    assert not matching.kapasite_kaldi(c, ot["id"], b)
    r3 = _okut(c, ot, "KOD1", "SNCIHAZ0003", "##SONRAKI##")
    assert r3["tip"] == "onay", "kapasite bittiğinde onaya düşmeli"


def test_Y1_tek_adetli_satirda_davranis_degismedi():
    """Ambar 1'in tamamı miktar=1: eski davranışla BİREBİR aynı kalmalı."""
    c, ot, _ = _kur([("KOD1", "KOD1SAYIM1", "seri", 1, 1)])
    assert _okut(c, ot, "KOD1", "SNCIHAZ0001", "##SONRAKI##")["tip"] == "slot"
    assert _okut(c, ot, "KOD1", "SNCIHAZ0002", "##SONRAKI##")["tip"] == "onay"


def test_Y1_gomulu_sn_cok_adetli_satirda_da_bulunur():
    """`coz()` 5. adımı da kapasite ölçütünde — aynı sorgu ailesi."""
    c, ot, _ = _kur([("KOD1", "KOD1 SAYIM X9Y0000Z", "seri", 2, 1)])
    assert matching.coz(c, "X9Y0000Z", ot["yukleme"], "1", ot["id"])["t"] == "seri"
    _okut(c, ot, "X9Y0000Z", "##SONRAKI##")
    # Kapasite duruyor: ikinci bir cihazın gömülü değeri hâlâ bulunabilmeli.
    # (Aynı değerin ikinci okutması 3b adımından `tekrar` döner, buraya gelmez.)
    b = c.execute("SELECT * FROM beklenen WHERE kod='KOD1'").fetchone()
    assert matching.kapasite_kaldi(c, ot["id"], b)


# --------------------------------------------- Y4 / Y5: adet buharlaşmaları
def test_Y4_bos_tamponda_atla_adedi_yakmaz():
    """`##ATLA##` boş tamponda hiçbir şey tüketmez.

    Eskiden kuyruğa hiçbir şey yazmadan `bekleyen_adet`i sıfırlıyor ve ekrana
    "kuyruğa atıldı" diyordu (`kuyruk_id` None). `##SONRAKI##` ve `##FAZLA##`
    bu kontrolü yapıyordu, `##ATLA##` yapmıyordu.
    """
    c, ot, _ = _kur([("KOD1", "L1", "lot", 77, 0)])
    _okut(c, ot, "##ADET-150##")
    assert _taze(c, ot)["bekleyen_adet"] == 150

    for komut in ("##SONRAKI##", "##FAZLA##", "##ATLA##"):
        r = _okut(c, ot, komut)
        assert r["tip"] == "bos", "%s boş tamponda %s döndü" % (komut, r["tip"])
        assert _taze(c, ot)["bekleyen_adet"] == 150, "%s adedi yaktı" % komut


def test_Y4_dolu_tamponda_atla_adedi_kuyruga_tasir():
    """Asıl davranış bozulmamalı: adet kuyruk satırına geçer ve tükenir."""
    c, ot, _ = _kur([("KOD1", "L1", "lot", 77, 0)])
    _okut(c, ot, "##ADET-150##")
    r = _okut(c, ot, "TANINMAYANBARKOD1", "##ATLA##")
    assert r["tip"] == "kuyruk" and r["kuyruk_id"]
    assert r["miktar"] == 150
    assert _taze(c, ot)["bekleyen_adet"] == 0
    assert c.execute("SELECT adet FROM kuyruk WHERE id=?",
                     (r["kuyruk_id"],)).fetchone()["adet"] == 150


def test_Y5_celiskili_grupta_adet_sessizce_yanmaz():
    """Çelişkili grup da `adet_yersiz` bildirir.

    Her satır bir cihazdır, yani ##ADET-25## uygulanamaz — ama `eslesti` ve
    `slot` dalları bunu söylerken bu dal söylemiyordu ve 25 sessizce yanıyordu.
    """
    c, ot, _ = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0),
                     ("KOD2", "TEMIZSN2", "seri", 1, 0)])
    r = _okut(c, ot, "##ADET-25##", "TEMIZSN1", "TEMIZSN2", "##SONRAKI##")
    assert r["tip"] == "coklu" and r["sayi"] == 2
    assert r["adet_yersiz"] == 25, "girilen adet sessizce yandı"
    assert _taze(c, ot)["bekleyen_adet"] == 0


# ---------------------------------------------- O5: kuyrukta aynı kayıt tekrarı
def test_O5_ayni_barkod_kumesi_kuyruga_ikinci_kez_dusunce_uyarir():
    """UYARIR, engellemez ve BİRLEŞTİRMEZ.

    Canlı sayımda oldu: `kuyruk#125` ve `#126` birebir aynı
    (`MIC-75GF10-00A1 + KMAA700581`), 16:05 ve 16:07.

    Birleştirmek aynı barkodlu İKİ fiziksel ürünün birini kaybettirirdi;
    engellemek kullanıcıya ikinciyi hiç kaydettirmezdi. Kayıt yazılır, karar
    kullanıcınındır.
    """
    c, ot, _ = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0)])
    r1 = _okut(c, ot, "MIC-75GF10-00A1", "KMAA700581", "##SONRAKI##")
    assert r1["tip"] == "kuyruk" and not r1["kuyruk_tekrar"]

    r2 = _okut(c, ot, "MIC-75GF10-00A1", "KMAA700581", "##SONRAKI##")
    assert r2["tip"] == "kuyruk"
    assert r2["kuyruk_tekrar"] and r2["kuyruk_tekrar"]["id"] == r1["kuyruk_id"]
    # Kayıt YİNE yazıldı — sayım kaybolmadı.
    assert r2["kuyruk_id"] != r1["kuyruk_id"]
    assert len(matching.bekleyen_kuyruk(c, ot["id"])) == 2


def test_O5_okutma_sirasi_urunu_degistirmez():
    """Ölçüt normalize edilmiş KÜME, sıra değil."""
    c, ot, _ = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0)])
    _okut(c, ot, "AAA111BBB", "CCC222DDD", "##SONRAKI##")
    r = _okut(c, ot, "ccc-222-ddd", "aaa-111-bbb", "##SONRAKI##")
    assert r["kuyruk_tekrar"], "sıra/biçim farkı tekrarı gizledi"


def test_O5_cozulmus_kayit_tekrar_saymaz():
    """Çözülmüş kuyruk kaydı uyarı üretmez — o iş bitti."""
    c, ot, idler = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0)])
    r1 = _okut(c, ot, "TANINMAYAN0001", "##SONRAKI##")
    matching.kuyruk_coz(c, r1["kuyruk_id"], idler[0])
    r2 = _okut(c, ot, "TANINMAYAN0001", "##SONRAKI##")
    assert r2["tip"] != "kuyruk" or not r2.get("kuyruk_tekrar")


# ------------------------------------------ Y2: Geçmiş ekranı da adet bazında
def test_Y2_gecmis_sayaci_sayim_ekraniyla_ayni_sayiyi_soyler():
    """İki ekran aynı oturum için aynı sayıyı söylemeli.

    B4 düzeltmesi `sayaclar`, `ara` ve `eksik_lotlar`'a uygulanmış,
    `oturumlar.gecmis`'e uygulanmamıştı: canlı oturum #2 için Sayım ekranı 171,
    Geçmiş ekranı 107 gösteriyordu. Lot satırı tek satırda çok adet taşıdığı
    için satır saymak 77 adetlik bir lotu bir okutmayla "bitmiş" gösteriyor.
    """
    c, ot, _ = _kur([("LOT1", "LOT1A", "lot", 77, 0),
                     ("KOD1", "TEMIZSN1", "seri", 1, 0)])
    _okut(c, ot, "##ADET-10##", "LOT1A", "##SONRAKI##")
    _okut(c, ot, "TEMIZSN1", "##SONRAKI##")

    sayac = matching.sayaclar(c, _taze(c, ot))
    satir = next(r for r in oturumlar.gecmis(c) if r["id"] == ot["id"])
    assert satir["okutulan"] == sayac["okutulan"] == 11
    assert satir["toplam"] == sayac["toplam"] == 78
    # Satır bazlı eski ölçüt burada 2 derdi — lotun 67 eksik adedini gizleyerek.
    assert satir["okutulan"] != 2


def test_Y2_gecmis_haric_kalemleri_saymaz():
    """`haric=0` süzgeci de `sayaclar` ile aynı olmalı."""
    c, ot, _ = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0),
                     ("KOD2", "TEMIZSN2", "seri", 1, 0)])
    c.execute("UPDATE beklenen SET haric=1, haric_sebep='test' WHERE kod='KOD2'")
    satir = next(r for r in oturumlar.gecmis(c) if r["id"] == ot["id"])
    assert satir["toplam"] == matching.sayaclar(c, _taze(c, ot))["toplam"] == 1


# ============================================================== uç nokta kapıları
# Bu bölüm TestClient kullanıyor: `kurulu` fixture'ı `tests/test_api.py`'de.
import pytest  # noqa: E402  (bölüm sınırı — yukarısı saf motor testleri)

from tests.test_api import istemci, kurulu, okut  # noqa: E402,F401


def _acik_fazla(ist, oid):
    """Adı yazılmış bir fazla kaydı üretir (kapılara takılmasın)."""
    okut(ist, oid, "TANIMSIZBARKOD001", "##FAZLA##")
    fid = ist.get("/api/oturum/%s/durum" % oid).json()["akis"][0]["id"]
    ist.patch("/api/okutma/%s" % fid, json={"ad": "TEST ÜRÜNÜ"})
    return fid


# ------------------------------------- O1: hata mesajı arayüze ULAŞMALI
def test_O1_miktar_sigmiyor_mesaji_arayuze_ulasir(kurulu):
    """`matching` yazdığı açıklamayı router atmamalı.

    Eskiden `HTTPException(400, sonuc["hata"])` yalnızca slug'ı gönderiyordu ve
    Eşleştirme ekranı kırmızı kutuya `miktar_sigmiyor` yazıyordu — Türkçe bir
    arayüzde makine etiketi. `routers/kuyruk.py` aynı durumu zaten doğru
    yapıyordu; iki router aynı sözleşmede değildi.
    """
    ist, _, ot = kurulu
    oid = ot["id"]
    okut(ist, oid, "##ADET-150##", "TANIMSIZBARKOD001", "##FAZLA##")
    fid = ist.get("/api/oturum/%s/durum" % oid).json()["akis"][0]["id"]
    ist.patch("/api/okutma/%s" % fid, json={"ad": "150 LİK KUTU"})

    b = ist.get("/api/oturum/%s/ara?sadece_acik=true&izleme=seri" % oid).json()
    hedef = b["satirlar"][0]["id"]
    r = ist.post("/api/okutma/%s/bagla" % fid, json={"beklenen_id": hedef})
    assert r.status_code == 400
    d = r.json()["detail"]
    assert isinstance(d, dict), "detail hâlâ düz slug"
    assert d["hata"] == "miktar_sigmiyor"
    assert "adet" in d["mesaj"] and "sığıyor" in d["mesaj"]


# ------------------------------- O2: kapalı oturumda kayıt değiştirilemez
def test_O2_kapali_oturumda_okutma_silinemez(kurulu):
    """Kapalı oturumun raporu üretilmiş, çoğu zaman Tiger'a da girilmiştir.

    Kapı `POST /okut` ve mod uçlarında hep vardı; SİLME / GERİ ALMA /
    DÜZELTME uçlarında yoktu ve kapanmış oturumdan okutma silmek 200 dönüyordu.
    """
    ist, _, ot = kurulu
    oid = ot["id"]
    b = ist.get("/api/oturum/%s/ara?sadece_acik=true&izleme=seri" % oid).json()
    seri = next(s["seri"] for s in b["satirlar"] if s["seri"] and not s["kirli"])
    okut(ist, oid, seri, "##SONRAKI##")
    okutma = ist.get("/api/oturum/%s/durum" % oid).json()["akis"][0]["id"]
    assert ist.post("/api/oturum/%s/bitir?zorla=true" % oid).status_code == 200

    assert ist.request("DELETE", "/api/okutma/%s" % okutma).status_code == 409
    assert ist.patch("/api/okutma/%s" % okutma,
                     json={"not_": "kapalıyken"}).status_code == 409
    assert ist.post("/api/oturum/%s/gerial" % oid,
                    json={"kapsam": "okutma"}).status_code == 409
    assert ist.post("/api/okutma/%s/seri-sec" % okutma,
                    json={"seri": ""}).status_code == 409
    # Kayıt DURUYOR.
    assert ist.get("/api/oturum/%s/durum" % oid).json()["akis"][0]["id"] == okutma


def test_O2_yeniden_acinca_yine_duzeltilebilir(kurulu):
    """Kapı çıkış yolunu söylüyor: Geçmiş > Yeniden aç."""
    ist, _, ot = kurulu
    oid = ot["id"]
    b = ist.get("/api/oturum/%s/ara?sadece_acik=true&izleme=seri" % oid).json()
    seri = next(s["seri"] for s in b["satirlar"] if s["seri"] and not s["kirli"])
    okut(ist, oid, seri, "##SONRAKI##")
    okutma = ist.get("/api/oturum/%s/durum" % oid).json()["akis"][0]["id"]
    ist.post("/api/oturum/%s/bitir?zorla=true" % oid)
    assert ist.post("/api/oturum/%s/yeniden-ac" % oid).status_code == 200
    assert ist.request("DELETE", "/api/okutma/%s" % okutma).status_code == 200


def test_O2_esleme_uclari_kapali_oturumda_da_calisir(kurulu):
    """Eşleştirme sayım SONU adımıdır — kapı oraya konmamalı.

    Aşırı düzeltme burada görünürdü: rapor öncesi eşleştirme, oturum
    kapandıktan sonra da yapılabilmeli.
    """
    ist, _, ot = kurulu
    oid = ot["id"]
    fid = _acik_fazla(ist, oid)
    ist.post("/api/oturum/%s/bitir?zorla=true" % oid)
    assert ist.get("/api/oturum/%s/esleme" % oid).status_code == 200
    b = ist.get("/api/oturum/%s/ara?sadece_acik=true&izleme=seri" % oid).json()
    r = ist.post("/api/okutma/%s/bagla" % fid,
                 json={"beklenen_id": b["satirlar"][0]["id"]})
    assert r.status_code == 200


# --------------------------------- O3: elle sayma lot kaleminde adet alabilmeli
def test_O3_elle_say_lot_kaleminde_adet_uygular():
    """Elle saymanın asıl müşterisi barkodsuz = dökme kalemler.

    Bu yol SABİT 1 yazıyordu: 77 adetlik bir lotu listeden saymak 77 ayrı
    tıklama, 77 ayrı grup demekti.
    """
    c, ot, (bid,) = _kur([("LOT1", "LOT1A", "lot", 77, 0)])
    r = matching.elle_say(c, _taze(c, ot), bid, adet=40)
    assert r["tip"] == "eslesti" and r["miktar"] == 40
    assert r["toplam"] == 40 and r["beklenen"] == 77
    assert matching.sayaclar(c, _taze(c, ot))["okutulan"] == 40


def test_O3_elle_say_bekleyen_adedi_kullanir_ve_tuketir():
    """##ADET-N## / Adet paneli okutma akışında ne yapıyorsa burada da onu yapar.

    Ayrı bir adet kutusu ikinci bir giriş yolu, dolayısıyla ikinci bir davranış
    demekti; sahadaki akış zaten "adedi gir, sonra ürünü seç".
    """
    c, ot, (bid,) = _kur([("LOT1", "LOT1A", "lot", 77, 0)])
    _okut(c, ot, "##ADET-25##")
    r = matching.elle_say(c, _taze(c, ot), bid)
    assert r["miktar"] == 25
    assert _taze(c, ot)["bekleyen_adet"] == 0, "adet sonraki ürüne sızdı"


def test_O3_elle_say_kapasiteyi_asan_adedi_reddeder():
    """77'lik lota 150 yazmak 73 adedi hiçbir yerde görünmeden yutardı."""
    c, ot, (bid,) = _kur([("LOT1", "LOT1A", "lot", 77, 0)])
    _okut(c, ot, "##ADET-150##")
    r = matching.elle_say(c, _taze(c, ot), bid)
    assert r["hata"] == "miktar_sigmiyor" and "77" in r["mesaj"]
    # Reddedilen çağrıda adet TÜKENMEZ — kullanıcı düzeltip yeniden seçebilsin.
    assert _taze(c, ot)["bekleyen_adet"] == 150
    assert matching.sayaclar(c, _taze(c, ot))["okutulan"] == 0


def test_O3_elle_say_seri_takiplide_adedi_bildirir():
    """Seri takiplide adet uygulanmaz ama sessizce yutulmaz."""
    c, ot, (bid,) = _kur([("KOD1", "TEMIZSN1", "seri", 1, 0)])
    r = matching.elle_say(c, _taze(c, ot), bid, adet=25)
    assert r["miktar"] == 1 and r["adet_yersiz"] == 25


def test_O3_elle_say_varsayilan_hala_bir_adet():
    """Adet girilmemişse davranış eskisiyle aynı."""
    c, ot, (bid,) = _kur([("LOT1", "LOT1A", "lot", 77, 0)])
    assert matching.elle_say(c, _taze(c, ot), bid)["miktar"] == 1
