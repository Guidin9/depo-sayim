"""Kendi bastığımız etiketlerin defteri (CLAUDE.md 12).

Depodaki kalemlerin bir kısmında ne üretici parça numarası ne de okunabilir bir
seri numarası var. Etiketi kendimiz basıyoruz, ama depoda yazıcı yok: toplu
basılıp elde götürülüyor. Bu yüzden üç ayrı etiket sınıfı var.

  malzeme (DM-000123)  Malzeme kodunun taranabilir hâli. Malzeme kodu başına
                       BİR kod; raf gözüne / kutuya yapışır. Aynı malzeme iki
                       rafta duruyorsa aynı kod iki kez basılır. Kaç FARKLI kod
                       gerektiği rapordan tam bilinir (tekil malzeme sayısı).
  seri    (DS-000045)  Basıldığında HİÇBİR ŞEYE ait değildir, sadece sıralı
                       numaradır; okutulduğunda o tekil cihazın Tiger'daki seri
                       numarası olur. Bu yüzden "hangi üründen kaç etiket
                       basayım" sorusu hiç sorulmaz; fazla basılan israf değil,
                       sonraki sayıma kalır.
  kutu    (DK-000007)  Kabın kimliği: "bu kapta ne var" (KUTU_TASARIM.md).
                       Basıldığında o da anonimdir; içeriği okutma anında
                       `kutu` tablosuna yazılır ve KALICIDIR — gelecek yıl aynı
                       kap tek okutmayla malzemesini söyler. Kalıcı olan
                       malzeme bağıdır, ADET DEĞİL: içerik ayda bir değişiyor,
                       o yüzden adet her sayımda yeniden sorulur ve etikete
                       basılmaz.

Bunların hiçbiri `##RAF-A1##` konum barkodu değildir (CLAUDE.md 4.5): o "nerede
duruyorum"u, buradakiler "ne" ve "hangisi"ni söyler.

Malzeme ve seri sınıfı mevcut Tiger'a-geri-yazma yollarına düşer, yeni rapor
mantığı gerektirmez: malzeme etiketi `eslesme` üzerinden Barkod Tablosu
sekmesine, seri etiketi kirli slot doldurma üzerinden Tiger Düzeltme sekmesine.

Kutu sınıfı Tiger'a HİÇ yazılmaz ve `eslesme`'ye de girmez: kap bir malzeme
değil, malzemenin bulunduğu yerdir. Kutu kodunu malzeme barkodu diye Tiger'ın
malzeme kartına yazmak, kap ertesi ay başka bir ürünle dolduğunda kalıcı bir
yanlış eşleşme bırakırdı (aynı gerekçe seri etiketinde de var — CLAUDE.md
12.6). Kutunun içeriği yalnızca `kutu` tablosunda durur.
"""
import csv
import os
import re

from .norm import norm

ONEK = {"malzeme": "DM", "seri": "DS", "kutu": "DK"}
HANE = 6

# Sabit genişlik şart: değişken uzunlukta bir etiket kodu diğerinin öneki
# olabilirdi ve matching.coz() 3. adımı >=8 karakterde önek eşleşmesi yapıyor.
DESEN = re.compile(r"^(%s)\d{%d}$" % ("|".join(ONEK.values()), HANE))

DUZENLER = ("a4", "rulo")

# Code128'e olduğu gibi basılamayacak malzeme kodu: ASCII dışı karakter (Türkçe
# harfler) ya da boşluk. 666 tekil koddan 57'si böyle (CLAUDE.md 2.1).
BARKODSUZ = re.compile(r"[^\x20-\x7E]|\s")


def kod_barkodlanabilir(kod):
    """Malzeme kodu olduğu gibi barkoda çevrilebilir mi?

    Çevrilemiyorsa o malzemenin kutusunda taranabilir bir kod bulunma ihtimali
    de yoktur — etiket kesin gerekir. Bu yüzden basım sırasında öne alınırlar.
    """
    k = str(kod or "").strip()
    return bool(k) and not BARKODSUZ.search(k)


def bicimle(tur, no):
    """(tur, 45) -> 'DS-000045' — insan okur hâli."""
    return "%s-%0*d" % (ONEK[tur], HANE, no)


def etiket_turu(deger):
    """Değer bizim bastığımız bir etiket mi? ONEK anahtarı ya da None döner.

    Yalnızca desene bakar, veritabanına değil: rapor ve eşleştirme yolları
    etiket defteri sıfırlanmış olsa da doğru davranmalı.

    TERS ARAMA, ikili if/else DEĞİL. Eskiden "DM değilse seri" yazıyordu ve
    üçüncü sınıf eklendiği anda sessizce yanlış cevap veriyordu:
    `etiket_turu("DK-000007")` -> "seri". Sonuçları (KUTU_TASARIM.md 4):
      * `kuyruk_coz` / `fazla_bagla` kutu kodunu "öğrenilmeyecek seri etiketi"
        sanardı — doğru sonuç, yanlış sebep; kural değişirse sessizce bozulur.
      * `reports._yeni_seri` kutu numarasını gerçek bir seri numarası adayı
        sayardı ve Tiger'a "bu cihazın S/N'i DK-000007" diye yazdırırdı.
    """
    n = norm(deger)
    if not DESEN.match(n):
        return None
    for tur, onek in ONEK.items():
        if n.startswith(onek):
            return tur
    return None


def etiket_mi(deger):
    """Normalize edilmiş değer bizim bastığımız etiket desenine uyuyor mu?"""
    return etiket_turu(deger) is not None


# `eslesme` tablosuna (yani Tiger'ın malzeme kartındaki Barkod alanına) YAZILMAZ.
# İkisi de tekil bir nesneye ait: seri etiketi bir cihaza, kutu etiketi bir kaba.
# Malzeme seviyesine yükseltilirlerse o malzemenin HER ürünü o barkodu taşıyor
# sayılır — ve kap ertesi ay başka bir ürünle dolduğunda yanlış eşleşme kalıcı
# olur (CLAUDE.md 12.6 ikinci madde, KUTU_TASARIM.md 4).
OGRENILMEZ = ("seri", "kutu")


def ogrenilebilir(deger):
    """Bu barkod bir malzemeye kalıcı olarak bağlanabilir mi?

    Kural tek yerde dursun diye: `matching` üç ayrı yerde (`kuyruk_coz`,
    `fazla_bagla`, `elle_say`) aynı ayrımı yapıyor ve biri güncellenmeden
    kalırsa fark ancak gelecek yılın raporunda görülür.
    """
    return etiket_turu(deger) not in OGRENILMEZ


def sonraki_no(c, tur):
    r = c.execute("SELECT MAX(CAST(SUBSTR(kod,3) AS INTEGER)) n FROM etiket "
                  "WHERE tur=?", (tur,)).fetchone()
    return (r["n"] or 0) + 1


# ------------------------------------------------------------------- ihtiyaç
def ihtiyac(c, yukleme, ambar):
    """Kaç etiket gerekebileceğinin ÜST SINIRI — hedef değil, öneri girdisi.

    Kesin bir sayı veremeyiz ve vermeye çalışmak yanıltıcı olur: depodaki
    ürünlerin birçoğunun kutusunda üretici parça numarası ya da seri numarası
    zaten basılı, Tiger'a girilmemiş olsa bile. Onlar okutulduğunda hiç etiket
    gerekmez. Gerçek ihtiyaç ancak bir raf sayıldıktan sonra ortaya çıkar.

    Bu yüzden burada yalnızca "en fazla bu kadar" hesaplanır; kaç adet
    basılacağına kullanıcı karar verir.
    """
    tekil = c.execute("SELECT COUNT(DISTINCT kod) n FROM beklenen "
                      "WHERE yukleme=? AND ambar=? AND haric=0",
                      (yukleme, ambar)).fetchone()["n"]
    basili = c.execute("""SELECT COUNT(DISTINCT e.malzeme) n FROM etiket e
                          WHERE e.tur='malzeme' AND e.malzeme IN
                          (SELECT kod FROM beklenen WHERE yukleme=? AND ambar=?
                           AND haric=0)""", (yukleme, ambar)).fetchone()["n"]
    kirli = c.execute("SELECT COUNT(*) n FROM beklenen WHERE yukleme=? AND ambar=? "
                      "AND haric=0 AND izleme='seri' AND kirli=1",
                      (yukleme, ambar)).fetchone()["n"]
    havuz = c.execute("SELECT COUNT(*) n FROM etiket WHERE tur='seri' "
                      "AND beklenen_id IS NULL").fetchone()["n"]
    # Kodu hiç barkod olamayanlar: etiket bunlarda kesin gerekli.
    barkodsuz = sum(
        0 if kod_barkodlanabilir(r["kod"]) else 1
        for r in c.execute("SELECT DISTINCT kod FROM beklenen WHERE yukleme=? "
                           "AND ambar=? AND haric=0", (yukleme, ambar)))
    return {
        "malzeme": {"tekil": tekil, "basili": basili, "eksik": tekil - basili,
                    "barkodsuz": barkodsuz},
        "seri": {"kirli_kayit": kirli, "havuzda": havuz,
                 "ust_sinir": max(0, kirli - havuz)},
    }


# -------------------------------------------------------------------- basım
def bas(c, tur, adet=None, kopya=1, kapsam="eksik", yukleme=None, ambar=None,
        duzen="a4", not_=None):
    """Yeni basım partisi açar ve basılacak satırları döner.

    kutu:    `adet` kadar yeni anonim kap numarası. Seri etiketiyle aynı
             mantık — basılırken hiçbir şeye ait değildir, içeriği ilk
             okutmada tanımlanır (KUTU_TASARIM.md 3).
    malzeme: `adet` kaç FARKLI malzemenin etiketleneceğidir (None = hepsi).
             160 malzemenin hepsine etiket gerekmez: çoğunun kutusunda üretici
             kodu zaten basılıdır. Az basıp devam edilir, sonraki basım kaldığı
             yerden sürer.
             Sıralama rastgele değil: kodu hiç barkod olamayanlar (boşluk ya da
             Türkçe karakter içerenler) başa alınır — onların kutusunda
             taranabilir kod bulunma ihtimali yoktur, etiket kesin gerekir.
             `kapsam` hangi havuzdan seçileceğini belirler: "eksik" henüz
             etiketi olmayanlar, "hepsi" tümü. `kopya` her koddan kaç KOPYA
             basılacağıdır (aynı malzeme iki rafta duruyorsa 2).
    seri:    `adet` kadar yeni anonim numara.

    Kopyalar veritabanına bir kez yazılır, kâğıda `kopya` kez basılır.
    """
    if tur not in ONEK:
        raise ValueError("bilinmeyen etiket türü: %s" % tur)
    if duzen not in DUZENLER:
        raise ValueError("bilinmeyen düzen: %s" % duzen)
    # `kopya or 1` yazılamaz: 0 sessizce 1'e dönerdi ve kullanıcı istemediği
    # bir sayfayı basardı. Eksik gelen değer 1, açıkça verilen 0 hatadır.
    kopya = 1 if kopya is None else int(kopya)
    if kopya < 1:
        raise ValueError("kopya en az 1 olmalı")

    from .matching import _ts
    ts = _ts()
    benzersiz = []
    no = sonraki_no(c, tur)

    if tur == "malzeme" and kapsam == "bos":
        # Tiger'da hiç malzeme kodu OLMAYAN ürünler için boş havuz: 5 m kablo
        # gibi kalemlerin kodu yok, uyduramayız da. Etiketi yapıştırıp okutulur,
        # grup kuyruğa düşer, bir kez çözülünce `eslesme`'ye yazılır ve o koddan
        # sonraki her üründe sorusuz tanınır.
        adet = int(adet or 0)
        if adet < 1:
            raise ValueError("adet en az 1 olmalı")
        for _ in range(adet):
            g = bicimle("malzeme", no)
            no += 1
            benzersiz.append({"kod": norm(g), "gosterim": g, "tur": "malzeme",
                              "malzeme": None, "aciklama": None, "yeni": True})
    elif tur == "malzeme":
        if not yukleme or ambar is None:
            raise ValueError("malzeme etiketi için yükleme ve ambar gerekli")
        if kapsam not in ("eksik", "hepsi"):
            raise ValueError("bilinmeyen kapsam: %s" % kapsam)
        malzemeler = c.execute(
            """SELECT kod, MIN(aciklama) aciklama FROM beklenen
               WHERE yukleme=? AND ambar=? AND haric=0
               GROUP BY kod""", (yukleme, ambar)).fetchall()
        # Barkod olamayan kodlar başa. False (0) önce sıralanır.
        malzemeler = sorted(
            malzemeler, key=lambda m: (kod_barkodlanabilir(m["kod"]), m["kod"]))
        sinir = None if adet is None else max(0, int(adet))
        for m in malzemeler:
            if sinir is not None and len(benzersiz) >= sinir:
                break
            var = c.execute("SELECT * FROM etiket WHERE tur='malzeme' AND malzeme=?",
                            (m["kod"],)).fetchone()
            if var:
                if kapsam == "eksik":
                    continue
                benzersiz.append({"kod": var["kod"], "gosterim": var["gosterim"],
                                  "tur": "malzeme", "malzeme": m["kod"],
                                  "aciklama": m["aciklama"], "yeni": False})
                continue
            g = bicimle("malzeme", no)
            no += 1
            benzersiz.append({"kod": norm(g), "gosterim": g, "tur": "malzeme",
                              "malzeme": m["kod"], "aciklama": m["aciklama"],
                              "yeni": True})
    elif tur == "kutu" and kapsam == "tanimli":
        # YENİDEN BASIM: içeriği belli kapların etiketi. Yeni numara
        # TÜKETİLMEZ — kap etiketi değişince kod aynı kalmalı, yoksa depoda
        # aynı kap için iki numara dolaşır (CLAUDE.md 12.7 ile aynı gerekçe).
        # İçerik değiştiğinde (kap başka ürüne ayrıldığında) bu yol kullanılır.
        sinir = None if adet is None else max(0, int(adet))
        for k in c.execute("""SELECT k.kod, k.gosterim, k.malzeme,
                                (SELECT aciklama FROM beklenen WHERE kod=k.malzeme
                                 ORDER BY yukleme DESC LIMIT 1) aciklama
                              FROM kutu k WHERE COALESCE(k.malzeme,'')<>''
                              ORDER BY k.kod"""):
            if sinir is not None and len(benzersiz) >= sinir:
                break
            benzersiz.append({"kod": k["kod"], "gosterim": k["gosterim"],
                              "tur": "kutu", "malzeme": k["malzeme"],
                              "aciklama": k["aciklama"], "yeni": False})
    else:
        # seri ve kutu: ikisi de anonim havuz. Fark yalnızca ne sorduklarında
        # ("hangisi bu" / "bu kapta ne var") ve etiketin basılış biçiminde.
        adet = int(adet or 0)
        if adet < 1:
            raise ValueError("adet en az 1 olmalı")
        for _ in range(adet):
            g = bicimle(tur, no)
            no += 1
            benzersiz.append({"kod": norm(g), "gosterim": g, "tur": tur,
                              "malzeme": None, "aciklama": None, "yeni": True})

    # Kâğıda çıkacak satırlar: her benzersiz kod `kopya` kez.
    satirlar = [x for x in benzersiz for _ in range(kopya)]

    yeniler = [x for x in benzersiz if x["yeni"]]
    basim_id = c.execute(
        "INSERT INTO basim(ts,tur,adet,ilk,son,duzen,not_) VALUES(?,?,?,?,?,?,?)",
        (ts, tur, len(satirlar),
         benzersiz[0]["gosterim"] if benzersiz else "",
         benzersiz[-1]["gosterim"] if benzersiz else "",
         duzen,
         not_ or (("%d kopya" % kopya) if kopya > 1 else None))).lastrowid

    for x in yeniler:
        c.execute("INSERT INTO etiket(kod,gosterim,tur,basim,ts,malzeme) "
                  "VALUES(?,?,?,?,?,?)",
                  (x["kod"], x["gosterim"], x["tur"], basim_id, ts, x["malzeme"]))
        # Malzeme etiketi öğrenilmiş barkod olarak da yazılır: motorun 4. adımı
        # onu sorusuz tanır ve rapordaki Barkod Tablosu sekmesi Tiger'ın malzeme
        # kartına yazılmak üzere listeler.
        # Boş havuz etiketinin bağlanacağı malzeme henüz yok; o kuyruktan
        # çözülünce öğrenilecek.
        if x["tur"] == "malzeme" and x["malzeme"]:
            c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                      (x["kod"], x["malzeme"], "", ts))

    if yeniler:
        csv_yaz(c, basim_id, yeniler, ts)
    return basim_id, satirlar


def defter(c, tur=None, basim=None, q=None, limit=500):
    """Etiket defteri — fiziksel etiketle dijital kaydı eşleyen tek kayıt."""
    # Kap etiketinde malzeme `etiket` tablosunda DEĞİL `kutu` defterinde durur:
    # kabın içeriği değişebilir, etiket numarası değişmez. COALESCE olmadan
    # ekrandaki defter kap satırlarını malzemesiz gösteriyor, rapordaki
    # Etiketler sekmesi ise doğru gösteriyordu — iki yerde iki ayrı gerçek.
    # `e.*` zaten bir `malzeme` sütunu getiriyor; ikinci kez aynı adla
    # seçilemez (sqlite3.Row ilk eşleşmeyi döner, yani hep NULL gelirdi).
    # Kap malzemesi ayrı adla çekilip aşağıda birleştiriliyor.
    sql = ["""SELECT e.*,
                     (SELECT malzeme FROM kutu WHERE kod=e.kod) kutu_malzeme,
                     (SELECT aciklama FROM beklenen
                      WHERE kod=COALESCE(e.malzeme,
                                (SELECT malzeme FROM kutu WHERE kod=e.kod))
                      ORDER BY yukleme DESC LIMIT 1) aciklama,
                     (SELECT seri FROM beklenen WHERE id=e.beklenen_id) slot
              FROM etiket e WHERE 1=1"""]
    par = []
    if tur:
        sql.append("AND e.tur=?")
        par.append(tur)
    if basim:
        sql.append("AND e.basim=?")
        par.append(basim)
    if q:
        sql.append("AND (e.gosterim LIKE ? OR e.malzeme LIKE ? OR EXISTS("
                   "SELECT 1 FROM kutu k WHERE k.kod=e.kod AND k.malzeme LIKE ?))")
        par += ["%" + q + "%"] * 3
    sql.append("ORDER BY e.tur, e.kod LIMIT ?")
    par.append(limit)
    cikti = []
    for r in c.execute(" ".join(sql), par):
        d = dict(r)
        d["malzeme"] = d["malzeme"] or d.pop("kutu_malzeme")
        d.pop("kutu_malzeme", None)
        cikti.append(d)
    return cikti


def basimlar(c, limit=50):
    return [dict(r) for r in c.execute(
        "SELECT * FROM basim ORDER BY id DESC LIMIT ?", (limit,))]


def bagla(c, etiket_kod, malzeme, beklenen_id, oturum, ts, raf):
    """Boş seri etiketini okutma anında bir kayda bağlar."""
    c.execute("""UPDATE etiket SET malzeme=?, beklenen_id=?, oturum=?,
                 ts_bagla=?, raf=? WHERE kod=?""",
              (malzeme, beklenen_id, oturum, ts, raf, norm(etiket_kod)))


def malzeme_etiketi_isle(c, barkodlar, malzeme, oturum=None, ts=None, raf=None):
    """Boş havuzdan basılmış DM- etiketini bir malzemeye bağlar (defter kaydı).

    Boş havuz etiketi (`bas(kapsam="bos")`) basılırken hiçbir şeye ait değildir;
    hangi malzemeye yapıştığı ancak okutma çözülünce belli olur. O an
    `eslesme`'ye yazmak motorun tanıması için yeterli, ama DEFTER için değil:
    `bas(kapsam="eksik")` "bu malzemenin etiketi var mı" diye `etiket.malzeme`
    alanına bakıyor. Boş kalırsa aynı malzemeye İKİNCİ bir numara basılır ve
    depoda tek ürünün üstünde iki farklı kod dolaşır.

    Bağlanmış bir etiketin malzemesi DEĞİŞTİRİLMEZ: numara bir kez bir
    malzemeye ait olur (CLAUDE.md §12.1). Bağlanan etiketi döner.
    """
    for h in barkodlar or ():
        n = norm(h)
        if etiket_turu(n) != "malzeme":
            continue
        r = c.execute("SELECT malzeme FROM etiket WHERE kod=?", (n,)).fetchone()
        if not r or r["malzeme"]:
            continue                      # defterde yok ya da zaten bağlı
        c.execute("""UPDATE etiket SET malzeme=?, oturum=COALESCE(oturum,?),
                     ts_bagla=COALESCE(ts_bagla,?), raf=COALESCE(raf,?)
                     WHERE kod=?""", (malzeme, oturum, ts, raf, n))
        return h
    return None


def coz_bagla(c, etiket_kod):
    """Bağlamayı çözer — etiket havuza geri döner. `##GERIAL##` kullanır.

    Etiket numarası TÜKETİLMEZ: `basim` kaydı ve CSV defteri yerinde kalır,
    yalnızca "neye yapıştı" bilgisi silinir. Fiziksel etiket hâlâ elde ya da
    ürünün üstünde; bir sonraki okutmada yeniden bağlanır.
    """
    c.execute("""UPDATE etiket SET malzeme=NULL, beklenen_id=NULL, oturum=NULL,
                 ts_bagla=NULL, raf=NULL WHERE kod=?""", (norm(etiket_kod),))


# ------------------------------------------------------- sıfırlamaya dayanma
def klasor(c):
    """Basım CSV'lerinin klasörü — bağlantının veritabanı dosyasının yanında.

    Sabit bir yol yerine bağlantıdan türetiliyor ki testler ve geçici
    veritabanları proje `data/` klasörüne yazmasın.

    BELLEK VERİTABANI (`:memory:`) İÇİN KLASÖR YOKTUR — None döner ve yazma
    yolları sessizce atlanır.

    Eski hâli bu durumda `data/etiket`e düşüyordu, yani amacının tam tersini
    yapıyordu: `baglan(":memory:")` ile açılan HER bağlantı gerçek etiket
    defterini okuyor ve üstüne yazıyordu. Bir denetim betiği 2026-09-02'de
    `basim-1.csv` (240 seri etiketi) ve `basim-2.csv` (24 malzeme etiketi)
    dosyalarını iki satırlık deneme verisiyle EZDİ; yedekten geri alındı.

    Defterin tek işi basılmış fiziksel numarayı korumak (CLAUDE.md §12.7) —
    kalıcı olmayan bir veritabanının ona dokunacak hiçbir işi yok.
    """
    yol = None
    for r in c.execute("PRAGMA database_list"):
        if r[1] == "main":
            yol = r[2]
            break
    if not yol:
        return None
    return os.path.join(os.path.dirname(os.path.abspath(yol)), "etiket")


BASLIK = ["kod", "gosterim", "tur", "malzeme", "ts"]


def csv_yaz(c, basim_id, satirlar, ts=None):
    """Basım partisini veritabanı dışına da yazar.

    sifirla.bat data klasöründeki .db dosyalarını yedeğe taşıyor; basılmış
    fiziksel etiket ise veritabanından uzun ömürlü. data/etiket klasörüne
    dokunulmadığı için defter burada hayatta kalır ve sayaç basılmış bir
    numarayı asla yeniden vermez.
    """
    kl = klasor(c)
    if not kl:                     # bellek veritabanı: kalıcı defter yok
        return None
    os.makedirs(kl, exist_ok=True)
    yol = os.path.join(kl, "basim-%s.csv" % basim_id)
    with open(yol, "w", newline="", encoding="utf-8") as f:
        # restval yerine açıkça ts veriyoruz: satır sözlüklerinde ts alanı yok,
        # DictWriter onu sessizce boş bırakırdı ve geri yüklemede basım tarihi
        # kaybolurdu.
        y = csv.DictWriter(f, BASLIK, extrasaction="ignore")
        y.writeheader()
        for s in satirlar:
            y.writerow(dict(s, ts=s.get("ts") or ts or ""))
    return yol


def csv_geri_yukle(c):
    """Defter boş ama basım CSV'leri duruyorsa etiketleri geri okur.

    Bağlama bilgisi geri gelmez, gerekmez de: rapor Tiger'a işlendikten sonra
    her iki etiket türü de Tiger'ın kendi alanlarında (Barkod / Seri No)
    yaşıyor. Buradaki amaç yalnızca sayacın basılı numarayı tekrar vermemesi.
    """
    kl = klasor(c)
    if not kl or not os.path.isdir(kl):
        return 0
    if c.execute("SELECT 1 FROM etiket LIMIT 1").fetchone():
        return 0
    n = 0
    for ad in sorted(os.listdir(kl)):
        if not ad.startswith("basim-") or not ad.endswith(".csv"):
            continue
        with open(os.path.join(kl, ad), newline="", encoding="utf-8") as f:
            for s in csv.DictReader(f):
                if not s.get("kod"):
                    continue
                c.execute("INSERT OR IGNORE INTO etiket(kod,gosterim,tur,ts,malzeme) "
                          "VALUES(?,?,?,?,?)",
                          (s["kod"], s["gosterim"], s["tur"], s.get("ts"),
                           s.get("malzeme") or None))
                if s["tur"] == "malzeme" and s.get("malzeme"):
                    c.execute("INSERT OR REPLACE INTO eslesme VALUES(?,?,?,?)",
                              (s["kod"], s["malzeme"], "", s.get("ts")))
                n += 1
    return n
