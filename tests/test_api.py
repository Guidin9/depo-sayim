"""API uç noktaları — TestClient ile uçtan uca."""
import io
import json
import os

import pytest
from fastapi.testclient import TestClient

from app import db as dbm
from tests.conftest import VERI_DOSYA

SONRAKI = "##SONRAKI##"


@pytest.fixture
def istemci(tmp_path, monkeypatch):
    """Her test kendi veritabanıyla çalışır."""
    yol = str(tmp_path / "api.db")
    monkeypatch.setattr(dbm, "DB_YOLU", yol)
    monkeypatch.setattr(dbm, "VERI", str(tmp_path))
    from app import main
    with TestClient(main.app) as ist:
        yield ist


@pytest.fixture
def kurulu(istemci):
    """Rapor yüklenmiş, ambar 1 oturumu açılmış istemci."""
    with open(VERI_DOSYA, "rb") as f:
        r = istemci.post("/api/yukleme", files={"dosya": ("deneme.XLSX", f.read())})
    assert r.status_code == 200, r.text
    ozet = r.json()
    o = istemci.post("/api/oturum", json={"yukleme": ozet["yukleme"], "ambar": "1"})
    assert o.status_code == 200, o.text
    return istemci, ozet, o.json()


def okut(ist, oid, *barkodlar):
    son = None
    for b in barkodlar:
        r = ist.post("/api/oturum/%s/okut" % oid, json={"ham": b})
        assert r.status_code == 200, r.text
        son = r.json()
    return son


# ---------------------------------------------------------------- kurulum
def test_saglik(istemci):
    assert istemci.get("/api/saglik").json()["durum"] == "ok"


def test_yukleme_ve_ambarlar(kurulu):
    ist, ozet, _ = kurulu
    assert ozet["satir"] == 870 and ozet["kirli"] == 394
    assert any(k["desen"] == "LIC" for k in ozet["kurallar"])

    amb = ist.get("/api/yukleme/%s/ambarlar" % ozet["yukleme"]).json()
    assert amb == [{"ambar": "1", "satir": 870, "adet": 1072.0, "haric": 1,
                    "kirli": 394, "malzeme": 161}]


def test_bozuk_dosya_400(istemci):
    r = istemci.post("/api/yukleme",
                     files={"dosya": ("bos.json", io.BytesIO(b"[]"))})
    assert r.status_code == 400


def test_kural_guncelleme(kurulu):
    ist, ozet, _ = kurulu
    yid = ozet["yukleme"]
    lic = next(k for k in ozet["kurallar"] if k["desen"] == "LIC")
    r = ist.put("/api/yukleme/%s/kurallar" % yid,
                json={"yukleme": yid, "kurallar": [{"id": lic["id"], "aktif": False}]})
    assert r.status_code == 200
    assert not next(k for k in r.json() if k["id"] == lic["id"])["aktif"]

    r = ist.put("/api/yukleme/%s/kurallar" % yid,
                json={"yukleme": yid,
                      "kurallar": [{"tip": "tur", "desen": "TK", "aktif": True}]})
    yeni = next(k for k in r.json() if k["desen"] == "TK")
    assert yeni["satir"] == 10 and not yeni["varsayilan"]


def test_olmayan_ambar_400(kurulu):
    ist, ozet, o = kurulu
    ist.post("/api/oturum/%s/bitir" % o["id"])
    r = ist.post("/api/oturum", json={"yukleme": ozet["yukleme"], "ambar": "99"})
    assert r.status_code == 400


# ---------------------------------------------------------------- sayım
def test_senaryo_akisi(kurulu):
    ist, _, o = kurulu
    oid = o["id"]

    r = okut(ist, oid, "##RAF-A1##")
    assert r["tip"] == "raf" and r["durum"]["aktif_raf"] == "A1"

    r = okut(ist, oid, "210-ACXU-TİP2")
    assert r["coz"] == "kod" and len(r["durum"]["tampon"]) == 1

    r = okut(ist, oid, "5S47WC2", SONRAKI)
    assert r["tip"] == "eslesti" and r["seri"] == "5S47WC2"
    assert r["durum"]["sayac"]["okutulan"] == 1
    assert r["durum"]["akis"][0]["raf"] == "A1"

    r = okut(ist, oid, "0WGP72", "W3S2000G7745", SONRAKI)
    assert r["tip"] == "slot" and r["eski"] == "0WGP72SAYIM1"

    r = okut(ist, oid, "198701689928", "EDBP0153231475674", SONRAKI)
    assert r["tip"] == "kuyruk" and r["durum"]["sayac"]["kuyruk"] == 1


def test_oturum_devam_ettirme(kurulu):
    """Uygulama kapanıp açılsa bile açık oturum kaldığı yerden gelir."""
    ist, _, o = kurulu
    okut(ist, o["id"], "##RAF-B2##", "5S47WC2", SONRAKI, "210-BEJO")

    d = ist.get("/api/oturum/acik").json()
    assert d["oturum"] == o["id"]
    assert d["aktif_raf"] == "B2"
    assert [t["ham"] for t in d["tampon"]] == ["210-BEJO"]   # yarım grup korundu
    assert d["sayac"]["okutulan"] == 1


def test_gerial_uc_noktasi(kurulu):
    ist, _, o = kurulu
    okut(ist, o["id"], "5S47WC2", SONRAKI, "hj6g8x3", SONRAKI)
    r = ist.post("/api/oturum/%s/gerial" % o["id"], json={"kapsam": "grup"}).json()
    assert r["kapsam"] == "grup"
    assert r["durum"]["sayac"]["okutulan"] == 1


def test_kuyruk_cozme(kurulu):
    ist, _, o = kurulu
    oid = o["id"]
    okut(ist, oid, "198701689928", "EDBP0153231475674", SONRAKI)

    kuyruk = ist.get("/api/oturum/%s/kuyruk" % oid).json()
    assert len(kuyruk) == 1 and kuyruk[0]["barkodlar"][0] == "198701689928"

    bulunan = ist.get("/api/oturum/%s/ara" % oid,
                      params={"q": "0WGP72"}).json()["satirlar"]
    assert bulunan[0]["kirli"] == 1       # kirli kayıtlar üstte
    r = ist.post("/api/kuyruk/%s/coz" % kuyruk[0]["id"],
                 json={"beklenen_id": bulunan[0]["id"]})
    assert r.status_code == 200 and r.json()["kod"] == "0WGP72"
    assert ist.get("/api/oturum/%s/kuyruk" % oid).json() == []

    # öğrenme kalıcı: aynı UPC artık tanınıyor
    assert okut(ist, oid, "198701689928")["coz"] == "ogrenilmis"


def test_fazla_kaydina_ad_yazma(kurulu):
    """Elle fazla → PATCH /api/okutma/{id} ile ürün adı."""
    ist, _, o = kurulu
    r = okut(ist, o["id"], "KAYITSIZ-URUN-9911", "##FAZLA##")
    oid = r["okutma"][0]

    p = ist.patch("/api/okutma/%s" % oid, json={"ad": "Kırmızı HP güç kablosu"})
    assert p.status_code == 200 and p.json()["ad"] == "Kırmızı HP güç kablosu"

    # kısmi güncelleme: not yazmak adı silmemeli
    p = ist.patch("/api/okutma/%s" % oid, json={"not_": "üst raf"})
    assert p.json()["ad"] == "Kırmızı HP güç kablosu" and p.json()["not_"] == "üst raf"

    assert ist.patch("/api/okutma/999999", json={"ad": "x"}).status_code == 404


def test_onay_kuyrugu_okutma_aninda_fazla_yazmaz(kurulu):
    """DEMO_FEEDBACK 5: karşılığı bulunamayan ürün sorulmadan fazla olmaz."""
    ist, _, o = kurulu
    r = okut(ist, o["id"], "210-BEJO", "YENISERI12345", SONRAKI)
    assert r["tip"] == "onay"
    assert r["durum"]["sayac"]["fazla"] == 0

    k = ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]
    assert k["tur"] == "fazla_onay" and k["kod"] == "210-BEJO" and k["aciklama"]

    # kullanıcı "evet gerçekten fazla" der -> tek satır yazılır
    assert ist.delete("/api/kuyruk/%s" % k["id"]).json()["tip"] == "fazla"
    d = ist.get("/api/oturum/%s/durum" % o["id"]).json()
    assert d["sayac"]["fazla"] == 1 and d["sayac"]["kuyruk"] == 0


def test_sayim_sonu_esleme_uclari(kurulu):
    """Fazla + eksik yan yana, bağla, geri al, foto kapısı."""
    ist, _, o = kurulu
    oid = o["id"]
    r = okut(ist, oid, "210-BEJO", "YENISERI12345", SONRAKI)
    kid = r["kuyruk_id"]
    fid = ist.delete("/api/kuyruk/%s" % kid).json()["okutma"][0]

    e = ist.get("/api/oturum/%s/esleme" % oid).json()
    assert [f["id"] for f in e["fazla"]] == [fid]
    hedef = next(x for x in e["eksik"] if x["kod"] == "210-BEJO")

    # kodu bilinen fazla fotoğraf istemez (210-BEJO onaydan geldi)
    assert ist.get("/api/oturum/%s/esleme" % oid).json()["fazla"][0]["kod"] == "210-BEJO"

    b = ist.post("/api/okutma/%s/bagla" % fid, json={"beklenen_id": hedef["id"]})
    assert b.status_code == 200 and b.json()["kod"] == "210-BEJO"
    assert ist.get("/api/oturum/%s/esleme" % oid).json()["fazla"] == []

    assert ist.post("/api/okutma/%s/coz-ayir" % fid).json()["tip"] == "fazla"
    assert ist.post("/api/okutma/%s/coz-ayir" % fid).status_code == 400


def test_fazla_kaydina_fotograf(kurulu):
    ist, _, o = kurulu
    r = okut(ist, o["id"], "KAYITSIZ-URUN-9911", "##FAZLA##")
    fid = r["okutma"][0]

    y = ist.post("/api/okutma/%s/foto" % fid,
                 files={"dosya": ("f.jpg", io.BytesIO(b"jpeg"), "image/jpeg")})
    assert y.status_code == 200
    assert ist.get("/api/foto/%s" % y.json()["id"]).content == b"jpeg"

    # adı yazılmamış fazla bitirmeyi engeller
    y = ist.post("/api/oturum/%s/bitir" % o["id"])
    assert y.status_code == 409 and "adsiz" in y.json()["detail"]

    # adı ve fotoğrafı olan fazla engellemez
    ist.patch("/api/okutma/%s" % fid, json={"ad": "Kırmızı HP güç kablosu"})
    assert ist.post("/api/oturum/%s/bitir" % o["id"]).status_code == 200
    assert ist.post("/api/okutma/999999/foto",
                    files={"dosya": ("f.jpg", io.BytesIO(b"x"), "image/jpeg")}
                    ).status_code == 404


def test_kuyruk_fazla_isaretleme_ad_ister(kurulu):
    """Tanınmayan ürün adsız fazla yazılamaz.

    Kodu olmayan kaydın raporda açıklaması üretilemez; geriye seri numarası ve
    raf kalır ve gün sonunda o satırın hangi ürün olduğu bulunamaz. Sisteme
    ilk kez giren ürün (kendi bastığımız etiket dahil) tam bu yoldan geçer.
    """
    ist, _, o = kurulu
    okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)
    kid = ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]["id"]

    y = ist.request("DELETE", "/api/kuyruk/%s" % kid)
    assert y.status_code == 400 and y.json()["detail"]["hata"] == "ad_gerekli"
    # reddedildiyse kayıt hâlâ kuyrukta, fazla oluşmadı
    d = ist.get("/api/oturum/%s/durum" % o["id"]).json()
    assert d["sayac"]["fazla"] == 0 and d["sayac"]["kuyruk"] == 1

    y = ist.request("DELETE", "/api/kuyruk/%s" % kid,
                    json={"ad": "Siyah 2m güç kablosu"})
    assert y.status_code == 200 and y.json()["tip"] == "fazla"

    # TEK GRUP = TEK ÜRÜN: iki barkod okutuldu ama tek fazla kaydı oluşmalı.
    # Bu test eskiden fazla == 2 bekliyordu, yani hatayı kodluyordu: tek
    # üründen okutulan her barkod ayrı bir fazla satırı üretiyor, kullanıcıya
    # adı barkod sayısı kadar soruluyor ve eşleştirme ekranı aynı ürünü N kez
    # eşleştirmesini bekliyordu (saha bildirimi 2026-08-23).
    assert len(y.json()["okutma"]) == 1
    d = ist.get("/api/oturum/%s/durum" % o["id"]).json()
    assert d["sayac"]["fazla"] == 1 and d["sayac"]["kuyruk"] == 0

    from app import db as dbm
    c = dbm.baglan()
    try:
        r = c.execute("SELECT ham, ad, seri, miktar FROM okutma "
                      "WHERE oturum=? AND tip='fazla'", (o["id"],)).fetchall()
        assert len(r) == 1
        assert r[0]["ad"] == "Siyah 2m güç kablosu"
        assert r[0]["miktar"] == 1
        # Denetim izi: iki barkod da kayıtta duruyor
        assert r[0]["ham"] == "198701689928 + EDBP0153231475674"
        # Tiger'a yazılacak tek seri: UPC değil, gerçek S/N
        assert r[0]["seri"] == "EDBP0153231475674"
    finally:
        c.close()


def test_kuyrukta_yazilan_ad_fazlaya_tasinir(kurulu):
    """Ad ürün eldeyken (telefondan) yazılabilir; kapatırken tekrar sorulmaz."""
    ist, _, o = kurulu
    okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)
    kid = ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]["id"]

    p = ist.patch("/api/kuyruk/%s" % kid, json={"ad": "Mavi SFP modül"})
    assert p.status_code == 200 and p.json()["ad"] == "Mavi SFP modül"
    # not yazmak adı silmemeli
    assert ist.patch("/api/kuyruk/%s" % kid,
                     json={"not_": "üst raf"}).json()["ad"] == "Mavi SFP modül"

    assert ist.request("DELETE", "/api/kuyruk/%s" % kid).status_code == 200


def test_onay_kaydi_ad_istemez(kurulu):
    """Malzeme kodu biliniyorsa açıklama rapora zaten JOIN ile geliyor."""
    ist, _, o = kurulu
    okut(ist, o["id"], "210-BEJO", "YENISERI12345", SONRAKI)
    kid = ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]["id"]
    assert ist.request("DELETE", "/api/kuyruk/%s" % kid).status_code == 200


# ---------------------------------------------------------------- rapor
def test_rapor_onizleme_ve_indirme(kurulu):
    ist, _, o = kurulu
    oid = o["id"]
    okut(ist, oid, "##RAF-A1##", "0WGP72", "W3S2000G7745", SONRAKI)

    on = ist.get("/api/oturum/%s/rapor/onizleme" % oid, params={"limit": 5}).json()
    assert on["Tiger Düzeltme"]["satirlar"][0][2] == "0WGP72SAYIM1"
    assert on["Eksik"]["toplam"] > len(on["Eksik"]["satirlar"]) == 5
    assert on["_ozet"]["haric"] == 1

    r = ist.get("/api/oturum/%s/rapor.xlsx" % oid)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxml")
    assert r.content[:2] == b"PK"          # zip başlığı = geçerli xlsx


def test_oturum_bitirme_ve_gecmis(kurulu):
    ist, _, o = kurulu
    okut(ist, o["id"], "5S47WC2")          # tampondaki yarım grup
    assert ist.post("/api/oturum/%s/bitir" % o["id"]).json()["durum"] == "bitti"

    gecmis = ist.get("/api/oturumlar").json()
    assert gecmis[0]["id"] == o["id"] and gecmis[0]["okutulan"] == 1
    assert ist.get("/api/oturum/acik").json() is None
    # kapalı oturuma okutma kabul edilmez
    assert ist.post("/api/oturum/%s/okut" % o["id"],
                    json={"ham": "hj6g8x3"}).status_code == 409


def test_komut_karti(istemci):
    r = istemci.post("/api/komut-karti", json={"raflar": ["a1", "B2"]})
    assert r.status_code == 200
    assert "##SONRAKI##" in r.text and "RAF A1" in r.text and "RAF B2" in r.text
    assert "data:image/svg+xml;base64," in r.text
    assert "http://" not in r.text and "https://" not in r.text   # CDN yok


def test_kok_adres(istemci):
    """Arayüz derlenmişse SPA döner, derlenmemişse ne yapılacağını söyler."""
    derli = istemci.get("/api/saglik").json()["arayuz"]
    r = istemci.get("/")
    assert r.status_code == 200
    if derli:
        assert '<div id="kok">' in r.text
        assert "/assets/" in r.text
    else:
        assert "npm run build" in json.dumps(r.json(), ensure_ascii=False)


def test_yukleme_dosyasi_saklaniyor(kurulu, tmp_path):
    assert os.listdir(str(tmp_path / "yuklenen"))


# ---------------------------------------------------------------- kuyruk akışı
def test_raf_engeli_api(kurulu):
    ist, _, o = kurulu
    oid = o["id"]
    okut(ist, oid, "##RAF-A1##", "198701689928", "EDBP0153231475674", SONRAKI)

    r = okut(ist, oid, "##RAF-B2##")
    assert r["tip"] == "raf_engel"
    assert r["durum"]["aktif_raf"] == "A1"

    # bilinçli olarak aşmak: zorla
    r = ist.post("/api/oturum/%s/okut" % oid,
                 json={"ham": "##RAF-B2##", "zorla": True}).json()
    assert r["tip"] == "raf" and r["durum"]["aktif_raf"] == "B2"


def test_bitir_ucu_kuyrukta_409(kurulu):
    ist, _, o = kurulu
    okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)
    r = ist.post("/api/oturum/%s/bitir" % o["id"])
    assert r.status_code == 409
    assert "çözülmemiş" in r.json()["detail"]["mesaj"]
    assert ist.post("/api/oturum/%s/bitir?zorla=true" % o["id"]).json()["durum"] == "bitti"


def test_aday_onerisi_kaldirildi(kurulu):
    """DEMO_FEEDBACK 4: "bu olabilir" tamamen kaldırıldı."""
    ist, _, o = kurulu
    from app import matching
    r = okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)
    assert r["tip"] == "kuyruk" and "adaylar" not in r
    assert not hasattr(matching, "adaylar")
    # /adaylar ucu kalkınca SPA fallback'e düşer; JSON aday listesi dönmez
    y = ist.get("/api/oturum/%s/adaylar" % o["id"])
    assert "application/json" not in y.headers.get("content-type", "")


def test_arama_filtreleri_ve_sayfalama(kurulu):
    ist, _, o = kurulu
    oid = o["id"]

    r = ist.get("/api/oturum/%s/ara" % oid, params={"limit": 5}).json()
    assert len(r["satirlar"]) == 5 and r["toplam"] > 5

    ikinci = ist.get("/api/oturum/%s/ara" % oid,
                     params={"limit": 5, "offset": 5}).json()
    assert {s["id"] for s in r["satirlar"]} & {s["id"] for s in ikinci["satirlar"]} == set()

    kirli = ist.get("/api/oturum/%s/ara" % oid,
                    params={"limit": 20, "kirli": True}).json()
    assert kirli["satirlar"] and all(s["kirli"] == 1 for s in kirli["satirlar"])

    lot = ist.get("/api/oturum/%s/ara" % oid,
                  params={"limit": 20, "izleme": "lot"}).json()
    assert lot["satirlar"] and all(s["izleme"] == "lot" for s in lot["satirlar"])

    acik = ist.get("/api/oturum/%s/ara" % oid,
                   params={"limit": 20, "sadece_acik": True}).json()
    assert acik["satirlar"] and all(not s["sayildi"] for s in acik["satirlar"])


def test_kuyruk_notu(kurulu):
    ist, _, o = kurulu
    okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)
    kid = ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]["id"]
    r = ist.patch("/api/kuyruk/%s" % kid, json={"not_": "siyah kutu, üst raf"})
    assert r.json()["not_"] == "siyah kutu, üst raf"
    assert ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]["not_"] == "siyah kutu, üst raf"


def test_sonra_coz_isareti_raf_kapisini_acar(kurulu):
    """Telefonda fotograflanip ertelenen kayit raf degistirmeyi engellemez.

    Raf kapisinin amaci urun eldeyken karar verdirmek; fotografini cekip
    bilerek erteleyen kullanici o karari zaten vermistir. Ama oturum
    kapanirken kuyruk yine de bos olmali.
    """
    ist, _, o = kurulu
    ist.post("/api/oturum/%s/raf" % o["id"], json={"raf": "A1"})
    okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)
    k = ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]
    assert k["beklet"] is False

    engel = ist.post("/api/oturum/%s/raf" % o["id"], json={"raf": "B2"}).json()
    assert engel["tip"] == "raf_engel"

    isaret = ist.patch("/api/kuyruk/%s" % k["id"], json={"beklet": True}).json()
    assert isaret["beklet"] is True

    assert ist.post("/api/oturum/%s/raf" % o["id"], json={"raf": "B2"}).json()["tip"] == "raf"
    assert ist.post("/api/oturum/%s/bitir" % o["id"]).status_code == 409


def test_sonra_coz_isareti_geri_alinir_ve_notu_silmez(kurulu):
    ist, _, o = kurulu
    okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)
    kid = ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]["id"]

    ist.patch("/api/kuyruk/%s" % kid, json={"not_": "mavi kutu"})
    r = ist.patch("/api/kuyruk/%s" % kid, json={"beklet": True}).json()
    assert r["beklet"] is True and r["not_"] == "mavi kutu"   # kismi guncelleme

    r = ist.patch("/api/kuyruk/%s" % kid, json={"not_": "mavi kutu, ust raf"}).json()
    assert r["beklet"] is True                                # not yazmak isareti silmez

    r = ist.patch("/api/kuyruk/%s" % kid, json={"beklet": False}).json()
    assert r["beklet"] is False and r["not_"] == "mavi kutu, ust raf"


def test_kuyruk_fotografi(kurulu):
    """Telefondan çekilen fotoğraf kuyruk kaydına bağlanır."""
    ist, _, o = kurulu
    okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)
    kid = ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]["id"]

    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 500 + b"\xff\xd9"
    r = ist.post("/api/kuyruk/%s/foto" % kid,
                 files={"dosya": ("foto.jpg", jpeg, "image/jpeg")})
    assert r.status_code == 200
    fid = r.json()["id"]

    assert ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]["fotolar"] == [fid]
    g = ist.get("/api/foto/%s" % fid)
    assert g.status_code == 200 and g.content == jpeg
    assert g.headers["content-type"] == "image/jpeg"

    assert ist.delete("/api/foto/%s" % fid).status_code == 200
    assert ist.get("/api/foto/%s" % fid).status_code == 404


def test_foto_turu_ve_boyutu_denetlenir(kurulu):
    ist, _, o = kurulu
    okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)
    kid = ist.get("/api/oturum/%s/kuyruk" % o["id"]).json()[0]["id"]

    assert ist.post("/api/kuyruk/%s/foto" % kid,
                    files={"dosya": ("a.txt", b"merhaba", "text/plain")}).status_code == 400
    assert ist.post("/api/kuyruk/%s/foto" % kid,
                    files={"dosya": ("b.jpg", b"x" * (7 * 1024 * 1024),
                                     "image/jpeg")}).status_code == 413


def test_ag_adresleri(istemci):
    r = istemci.get("/api/ag").json()
    assert r["yerel"].startswith("http://127.0.0.1:")
    assert isinstance(r["adresler"], list)
    # her adresin telefon monitörü karşılığı da veriliyor
    assert all(a.endswith("/telefon") for a in r["telefon"])
    assert len(r["telefon"]) == len(r["adresler"])


def test_telefon_adresi_arayuzu_dondurur(istemci):
    """/telefon ayrı bir sayfa değil, aynı SPA — mod adresle seçiliyor."""
    if not istemci.get("/api/saglik").json()["arayuz"]:
        pytest.skip("arayüz derlenmemiş")
    r = istemci.get("/telefon")
    assert r.status_code == 200
    assert '<div id="kok">' in r.text


def test_index_onbellege_alinmiyor(istemci):
    """Telefon eski index.html'i tutarsa yeni arayüzü hiç görmez (CLAUDE.md 9)."""
    if not istemci.get("/api/saglik").json()["arayuz"]:
        pytest.skip("arayüz derlenmemiş")
    for yol in ("/", "/telefon"):
        assert istemci.get(yol).headers["cache-control"] == "no-store"


def test_telefon_qr_kodu(istemci):
    """PC ekranındaki QR: telefon IP yazmasın diye. segno yoksa 501 ve arayüz
    adresi yazıyla gösterir — uygulama kırılmaz."""
    r = istemci.get("/api/telefon-qr.svg?adres=http://10.0.0.5:8000/telefon")
    if r.status_code == 501:
        assert "segno" in r.json()["detail"]
        return
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.lstrip().startswith("<?xml")
    assert istemci.get("/api/telefon-qr.svg?adres=%s" % ("x" * 400)).status_code == 400


# ---------------------------------------------------------------- canlı ekran
def test_degisiklik_surumu_artar(kurulu):
    """Veriyi değiştiren istek, dinleyen ekranlara haber verecek sürümü artırır."""
    from app import olaylar
    ist, _, o = kurulu
    once = olaylar.surum()[0]

    ist.get("/api/oturum/%s/durum" % o["id"])          # okuma: sürüm değişmez
    assert olaylar.surum()[0] == once

    ist.post("/api/oturum/%s/okut" % o["id"], json={"ham": "5S47WC2"},
             headers={"X-Istemci": "telefon-1"})
    surum, kaynak = olaylar.surum()
    assert surum > once
    assert kaynak == "telefon-1"                        # kendi olayını ayırt et


def test_telefondan_raf_ayarlama(kurulu):
    ist, _, o = kurulu
    r = ist.post("/api/oturum/%s/raf" % o["id"], json={"raf": "c4"}).json()
    assert r["tip"] == "raf" and r["durum"]["aktif_raf"] == "C4"

    okut(ist, o["id"], "5S47WC2", SONRAKI)
    assert ist.get("/api/oturum/%s/raflar" % o["id"]).json() == ["C4"]


def test_telefondan_raf_degistirmek_de_kuyrukta_engellenir(kurulu):
    ist, _, o = kurulu
    ist.post("/api/oturum/%s/raf" % o["id"], json={"raf": "A1"})
    okut(ist, o["id"], "198701689928", "EDBP0153231475674", SONRAKI)

    r = ist.post("/api/oturum/%s/raf" % o["id"], json={"raf": "B2"}).json()
    assert r["tip"] == "raf_engel"
    r = ist.post("/api/oturum/%s/raf" % o["id"], json={"raf": "B2", "zorla": True}).json()
    assert r["tip"] == "raf"
