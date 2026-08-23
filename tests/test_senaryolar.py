"""CLAUDE.md 8 — sahada doğrulanmış yedi senaryo. Hepsi geçmek zorunda."""
from app import matching
from tests.conftest import oturum_taze

SONRAKI = "##SONRAKI##"


def test_1_kod_ve_seri_birlikte(c, ot, yaz):
    """210-ACXU-TİP2 + 5S47WC2 + SONRAKI -> eşleşti, Dell R730."""
    r = yaz("210-ACXU-TİP2", "5S47WC2", SONRAKI)
    assert r["tip"] == "eslesti"
    assert r["kod"] == "210-ACXU-TİP2"
    assert r["seri"] == "5S47WC2"
    assert "R730" in r["aciklama"]


def test_2_kucuk_harf_seri(c, ot, yaz):
    """hj6g8x3 + SONRAKI -> eşleşti, Dell monitör (küçük harf toleransı)."""
    r = yaz("hj6g8x3", SONRAKI)
    assert r["tip"] == "eslesti"
    assert r["kod"] == "210-BEJO"
    assert r["seri"] == "HJ6G8X3"


def test_3_onek_eslesmesi(c, ot, yaz):
    """ARK-1250L-S5A1 + KSA7658744 + SONRAKI -> eşleşti, önek eşleşmesi."""
    onek = matching.coz(c, "ARK-1250L-S5A1", ot["yukleme"], ot["ambar"], ot["id"])
    assert onek["t"] == "kod"
    assert onek["not"] == "önek eşleşmesi"
    assert onek["kod"] == "ARK-1250LS5A1ATR/8641924"

    r = yaz("ARK-1250L-S5A1", "KSA7658744", SONRAKI)
    assert r["tip"] == "eslesti"
    assert r["kod"] == "ARK-1250LS5A1ATR/8641924"
    assert r["seri"] == "KSA7658744"


def test_4_ikisi_de_taninmiyor_kuyruga(c, ot, yaz):
    """198701689928 (UPC) + EDBP0153231475674 (S/N) + SONRAKI -> kuyruk."""
    r = yaz("198701689928", "EDBP0153231475674", SONRAKI)
    assert r["tip"] == "kuyruk"
    assert r["barkodlar"] == ["198701689928", "EDBP0153231475674"]
    assert c.execute("SELECT COUNT(*) n FROM kuyruk WHERE oturum=? AND cozuldu=0",
                     (ot["id"],)).fetchone()["n"] == 1


def test_5_kirli_slot_doldurma(c, ot, yaz):
    """0WGP72 + yeni S/N + SONRAKI -> slot dolduruldu, 0WGP72SAYIM1 düzeltilecek."""
    r = yaz("0WGP72", "W3S2000G7745", SONRAKI)
    assert r["tip"] == "slot"
    assert r["kod"] == "0WGP72"
    assert r["eski"] == "0WGP72SAYIM1"
    assert r["yeni"] == "W3S2000G7745"
    # okutulan gerçek S/N kalıcı olarak öğrenildi
    assert c.execute("SELECT kod FROM eslesme WHERE barkod=?",
                     ("W3S2000G7745",)).fetchone()["kod"] == "0WGP72"


def test_6_tekrar_uyarisi(c, ot, yaz):
    """5S47WC2 ikinci kez -> tekrar uyarısı."""
    assert yaz("5S47WC2", SONRAKI)["tip"] == "eslesti"

    tampon = yaz("5S47WC2")
    assert tampon["tip"] == "tampon" and tampon["coz"] == "tekrar"

    r = yaz(SONRAKI)
    assert r["tip"] == "tekrar"
    assert r["seri"] == "5S47WC2"
    # tek okutma kaydı kaldı, mükerrer yazılmadı
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND seri='5S47WC2'",
                     (ot["id"],)).fetchone()["n"] == 1


def test_7_ogrenme_kalici(c, ot, yaz):
    """Kuyruk çözüldükten sonra aynı UPC tanınır."""
    UPC = "198701689928"
    assert yaz(UPC, "EDBP0153231475674", SONRAKI)["tip"] == "kuyruk"

    kid = c.execute("SELECT id FROM kuyruk WHERE oturum=? AND cozuldu=0",
                    (ot["id"],)).fetchone()["id"]
    hedef = c.execute("SELECT id FROM beklenen WHERE seri='0WGP72SAYIM1'").fetchone()["id"]
    assert matching.kuyruk_coz(c, kid, hedef)["kod"] == "0WGP72"

    tampon = yaz(UPC)
    assert tampon["coz"] == "ogrenilmis"
    assert tampon["kod"] == "0WGP72"

    r = yaz(SONRAKI)
    assert r["tip"] == "slot"          # sıradaki uydurma kayıt düzeltiliyor
    assert r["eski"] == "0WGP72SAYIM2"


# ---------------------------------------------------------------- ek davranışlar
def test_lot_adet_sayimi(c, ot, yaz):
    """Lot izlemeli malzeme okutulunca adet +1, beklenen 77 (CLAUDE.md 2.4)."""
    r = yaz("0C5RNH", SONRAKI)
    assert r["tip"] == "adet"
    assert r["kod"] == "0C5RNH"
    assert r["toplam"] == 1
    assert r["beklenen"] == 77
    r2 = yaz("0C5RNH", SONRAKI)
    assert r2["toplam"] == 2


def test_gomulu_seri_no(c, ot):
    """Kirli kaydın içine gömülü gerçek S/N okutulunca aday olarak eşleşir."""
    kirli = c.execute("SELECT * FROM beklenen WHERE seri LIKE '%ASELSANBOTPROJESI%' "
                      "LIMIT 1").fetchone()
    if kirli is None:
        import pytest
        pytest.skip("bu veride gömülü S/N örneği yok")
    gomulu = kirli["seri_n"][-10:]
    r = matching.coz(c, gomulu, ot["yukleme"], ot["ambar"], ot["id"])
    assert r["t"] == "seri"
    assert r["not"] == "gömülü S/N"
    assert r["id"] == kirli["id"]


def test_bastaki_sifir_varyanti(c, ot):
    """Tiger'da 00008682122630086, okuyucu 8682122630086 yazar (CLAUDE.md 4.1)."""
    from app.norm import norm, sifirsiz
    sn = "00008682122630086"
    c.execute("""INSERT INTO beklenen(yukleme,kod,kod_n,aciklama,tur,ambar,izleme,seri,
                 seri_n,seri_n0,miktar,birim,kirli,kirli_sebep,haric,haric_sebep,kaynak)
                 VALUES(?,?,?,?,?,?,'seri',?,?,?,1,'AD',0,'',0,'','seri_lot')""",
              (ot["yukleme"], "TEST-SIFIR", "TESTSIFIR", "SIFIR TESTI", "TM",
               ot["ambar"], sn, norm(sn), sifirsiz(norm(sn))))
    c.commit()

    r = matching.coz(c, "8682122630086", ot["yukleme"], ot["ambar"], ot["id"])
    assert r["t"] == "seri"
    assert r["not"] == "baştaki sıfır varyantı"
    assert r["seri"] == sn
    # ters yön: fazladan sıfırla okutulsa da tutar
    assert matching.coz(c, "008682122630086", ot["yukleme"], ot["ambar"],
                        ot["id"])["t"] == "seri"


def test_alfanumerik_sifir_varyanti_tutmaz(c, ot):
    """Sıfır varyantı sadece rakam değerlerde çalışır — kod eşleşmesini bozmaz."""
    r = matching.coz(c, "0WGP72", ot["yukleme"], ot["ambar"], ot["id"])
    assert r["t"] == "kod" and r["kod"] == "0WGP72"


def test_raf_takibi(c, ot, yaz):
    """##RAF-A1## sonrası okutmalar o rafa yazılır."""
    r = yaz("##RAF-A1##")
    assert r["tip"] == "raf" and r["raf"] == "A1"
    assert oturum_taze(c, ot)["aktif_raf"] == "A1"

    yaz("5S47WC2", SONRAKI)
    assert c.execute("SELECT raf FROM okutma WHERE oturum=? ORDER BY id DESC LIMIT 1",
                     (ot["id"],)).fetchone()["raf"] == "A1"

    yaz("##RAF-B3##", "198701689928", "##ATLA##")
    assert c.execute("SELECT raf FROM kuyruk WHERE oturum=? ORDER BY id DESC LIMIT 1",
                     (ot["id"],)).fetchone()["raf"] == "B3"


def test_gerial_ve_iptal(c, ot, yaz):
    """##GERIAL## önce tamponu, tampon boşsa son okutmayı geri alır."""
    yaz("210-ACXU-TİP2", "5S47WC2")
    assert yaz("##GERIAL##")["ham"] == "5S47WC2"
    assert c.execute("SELECT COUNT(*) n FROM tampon WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 1

    assert yaz("##IPTAL##")["tip"] == "iptal"
    assert c.execute("SELECT COUNT(*) n FROM tampon WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0

    yaz("5S47WC2", SONRAKI)
    assert yaz("##GERIAL##")["kapsam"] == "okutma"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=?",
                     (ot["id"],)).fetchone()["n"] == 0


def test_grup_gerial(c, ot, yaz):
    """Son grup tek hamlede geri alınır."""
    yaz("5S47WC2", SONRAKI)
    yaz("hj6g8x3", SONRAKI)
    r = matching.gerial(c, oturum_taze(c, ot), kapsam="grup")
    assert r["kapsam"] == "grup"
    kalan = c.execute("SELECT seri FROM okutma WHERE oturum=?", (ot["id"],)).fetchall()
    assert [x["seri"] for x in kalan] == ["5S47WC2"]


def test_fazla_elle(c, ot, yaz):
    """##FAZLA## tampondaki barkodları fazla olarak yazar."""
    r = yaz("BILINMEYEN-URUN-123", "##FAZLA##")
    assert r["tip"] == "fazla_elle"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND tip='fazla'",
                     (ot["id"],)).fetchone()["n"] == 1


def test_seri_takipli_karsiligi_yok_onaya_dusler(c, ot, yaz):
    """Açık kirli slot yoksa sonuç FAZLA DEĞİL, onay kuyruğudur.

    DEMO_FEEDBACK.md 5: eski davranış sessizce fazla yazıyordu. Bu dala düşmek
    "stokta yok" demek değil, "Tiger'daki seri numaralarıyla eşleşmedi"
    demektir — kararı kullanıcı verir.
    """
    r = yaz("210-BEJO", "YENISERI12345", SONRAKI)
    assert r["tip"] == "onay"
    assert r["kod"] == "210-BEJO"
    # onaylanmadan hiçbir fazla kaydı oluşmaz
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND tip='fazla'",
                     (ot["id"],)).fetchone()["n"] == 0
    q = c.execute("SELECT * FROM kuyruk WHERE id=?", (r["kuyruk_id"],)).fetchone()
    assert q["tur"] == "fazla_onay" and q["kod"] == "210-BEJO"


def test_onay_kaydi_sayilmamis_temiz_satira_baglanabilir(c, ot, yaz):
    """Asıl kazanç: malzemenin sayılmamış TEMİZ satırı dururken fazla yazılmıyor.

    Kullanıcı onay kartından o satırı seçince kayıt eşleşmiş sayılır.
    """
    r = yaz("210-BEJO", "YENISERI12345", SONRAKI)
    acik = c.execute("""SELECT b.id FROM beklenen b WHERE b.kod='210-BEJO'
                        AND b.kirli=0 AND NOT EXISTS(SELECT 1 FROM okutma o
                        WHERE o.oturum=? AND o.beklenen_id=b.id)
                        ORDER BY b.id LIMIT 1""", (ot["id"],)).fetchone()
    assert acik, "temiz ve sayılmamış satır bulunmalı — senaryonun ön koşulu"
    s = matching.kuyruk_coz(c, r["kuyruk_id"], acik["id"])
    assert s["tip"] == "eslesti" and s["kod"] == "210-BEJO"
    assert c.execute("SELECT COUNT(*) n FROM okutma WHERE oturum=? AND tip='fazla'",
                     (ot["id"],)).fetchone()["n"] == 0


def test_onay_gercekten_fazlaysa_tek_satir_yazar(c, ot, yaz):
    """Onay kaydı iki barkod taşısa da tek üründür: raporda tek fazla satırı."""
    r = yaz("210-BEJO", "YENISERI12345", SONRAKI)
    s = matching.kuyruk_fazla(c, r["kuyruk_id"])
    assert s["tip"] == "fazla" and len(s["okutma"]) == 1
    satir = c.execute("SELECT * FROM okutma WHERE oturum=? AND tip='fazla'",
                      (ot["id"],)).fetchone()
    assert satir["kod"] == "210-BEJO"          # malzeme kodu kaybolmuyor
    assert satir["seri"] == "YENISERI12345"    # kodun kendisi değil, S/N yazılır


def test_onay_kaydi_bitir_kapisini_tetikler(c, ot, yaz):
    """Onaylanmamış fazla dururken oturum kapanmamalı."""
    yaz("210-BEJO", "YENISERI12345", SONRAKI)
    r = yaz("##BITIR##")
    assert r["tip"] == "bitir_engel"
    assert r["kuyruk"][0]["tur"] == "fazla_onay"


def test_sayaclar(c, ot, yaz):
    onceki = matching.sayaclar(c, ot)
    yaz("5S47WC2", SONRAKI)
    sonra = matching.sayaclar(c, oturum_taze(c, ot))
    assert sonra["okutulan"] == onceki["okutulan"] + 1
    assert sonra["kalan"] == onceki["kalan"] - 1
    assert sonra["toplam"] == onceki["toplam"]


def test_bitir_oturumu_kapatir(c, ot, yaz):
    r = yaz("##BITIR##")
    assert r["tip"] == "bitti"
    assert oturum_taze(c, ot)["durum"] == "bitti"
