"""Normalizasyon ve sınıflandırma kuralları.

Bu modül depo_sayim.py:15-50'den BİREBİR taşındı. Kurallar sahada gerçek
veriyle doğrulandı — davranışı değiştirmeyin (CLAUDE.md 4.1, 4.3).
"""
import re

TR = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigguussoocc")


def norm(s):
    """Büyük harf, Türkçe katla, harf-rakam dışını at."""
    if s is None:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(s).translate(TR).upper())


def sifirsiz(n):
    """Baştaki sıfırlar atılmış varyant. Sadece tamamı rakam olan değerler için.

    Tiger'da 00008682122630086 durabilir ama okuyucu 8682122630086 yazar
    (CLAUDE.md 4.1). Rakam olmayan değerler için None döner ki alfanümerik
    kodlarda yanlış eşleşme olmasın.
    """
    if not n or not n.isdigit():
        return None
    k = n.lstrip("0")
    return k or None


KOMUT = {"##SONRAKI##": "sonraki", "##IPTAL##": "iptal", "##GERIAL##": "gerial",
         "##FAZLA##": "fazla", "##ATLA##": "atla", "##BITIR##": "bitir",
         # Sabit malzeme kodu (I2): kod bir kez okutulur, ardından yalnız seri
         # numaraları okutulur. Kartta basılı hâli parametresizdir — malzeme
         # kodlarının 57'si boşluk / Türkçe karakter taşıyor ve Code128'e
         # girmiyor (CLAUDE.md 2.1), o yüzden kilit TAMPONDAN okunur.
         "##KILIT##": "kilit", "##KILITAC##": "kilitac",
         # Yedek parça modu (I4): açıkken okutulan hiçbir şey veritabanında
         # ARANMAZ, doğrudan yedek parça olarak yazılır.
         "##YEDEK##": "yedek", "##YEDEKKAPAT##": "yedekkapat"}

RAF_ONEK = "##RAF-"
ADET_ONEK = "##ADET-"
# Parametreli kilit YALNIZCA arayüz üretir (telefon / PC düğmesi), kart basmaz:
# kod ASCII dışı olabilir. Tek kod yolu kalsın diye uç de bu komuttan geçer.
KILIT_ONEK = "##KILIT-"

# Adet barkodunun üst sınırı. Dört hane, çünkü beş haneli bir değer okuma
# hatasıdır: en büyük Tiger kalemi 460 adet.
ADET_TAVAN = 9999


def raf_adi(ham):
    """Raf adını hem BASILABİLİR hem OKUTULABİLİR hâle getirir.

    Code128 yalnızca ASCII taşır: `ÜST-1` basılamaz, python-barcode
    `IllegalCharacterError` atar ve komut kartı ucu 500 verirdi. Türkçe bir
    depoda `ÜST`, `ÖN`, `ÇIKIŞ` yazmak en doğal şey.

    Asıl tuzak 500 değil, ondan derini: basılan değerle sonradan ELLE yazılan
    değerin aynı olması gerekiyor. Kart `UST-1` basıp telefondaki kutuya
    `ÜST-1` yazılırsa uygulama bunları İKİ AYRI RAF sayardı. Bu yüzden
    normalizasyon tek yerde — `komut_coz()` — ve barkod üretimi de aynı
    işlevi kullanıyor.

    Türkçe harfler katlanır (Ü→U), sonra yalnızca `A-Z 0-9 boşluk . _ -`
    bırakılır. Beyaz liste kara listeden güvenli: `#` komut sınırlayıcısını
    (`##RAF-A#1##`), Code128'in basamadığı her şeyi ve HTML'e sızabilecek
    karakterleri tek kuralla eler. Raf adı bir konum etiketidir — `A1`,
    `B2-ALT`, `UST 3` — bu küme yeter.
    """
    s = str(ham or "").strip().translate(TR).upper()
    s = re.sub(r"[^A-Z0-9 ._-]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def komut_coz(ham):
    """Okutulan değer komut barkodu mu? (komut_adi, deger) döner.

    `deger` rafta raf adı (metin), adette miktar (tam sayı), ötekilerde None.
    """
    u = str(ham).strip().upper()
    if u in KOMUT:
        return KOMUT[u], None
    if u.startswith(RAF_ONEK) and u.endswith("##") and len(u) > len(RAF_ONEK) + 2:
        ad = raf_adi(u[len(RAF_ONEK):-2])
        # Temizlikten sonra hiçbir şey kalmadıysa bu bir raf komutu değildir
        # (`##RAF-ÇÇ##` gibi). Sessizce boş rafa geçmektense tampona düşsün.
        if ad:
            return "raf", ad
    # ##ADET-25## — lot / izlemesiz kalemde "bu üründen 25 tane var" (CLAUDE.md 2.4).
    # Tanınmayan bir ##ADET-...## komut değil sayılır ve tampona düşer; sessizce
    # 0 adet saymaktansa kullanıcının gördüğü bir "bilinmiyor" daha iyidir.
    if u.startswith(ADET_ONEK) and u.endswith("##"):
        s = u[len(ADET_ONEK):-2]
        if s.isdigit() and int(s) <= ADET_TAVAN:
            return "adet", int(s)
    # ##KILIT-<kod>## — arayüzden gelen açık kod. `ham` büyütülmüş hâliyle
    # dönülür; malzeme kodu zaten `coz()` içinde norm()'dan geçiyor.
    if u.startswith(KILIT_ONEK) and u.endswith("##") and len(u) > len(KILIT_ONEK) + 2:
        kod = str(ham).strip()[len(KILIT_ONEK):-2].strip()
        if kod:
            return "kilit", kod
    return None, None


def upc_mi(s):
    """12-13 haneli, kontrol hanesi tutan perakende barkodu mu?"""
    s = re.sub(r"\D", "", str(s))
    if len(s) not in (12, 13):
        return False
    d = [int(c) for c in s]
    t = sum(d[i] * (3 if (len(s) - 2 - i) % 2 == 0 else 1) for i in range(len(s) - 1))
    return (10 - t % 10) % 10 == d[-1]


KIRLI_KELIME = re.compile(r"SAYIM|SAYIN|STOK|CIKAN|DENEME|FAZLA|TEST|PROJE|DEPO|BAKIM")


def kirli_mi(seri, kod):
    """Seri numarası gerçek mi, yoksa stok tutturmak için uydurulmuş mu?"""
    n, k = norm(seri), norm(kod)
    if not n:
        return 1, "bos"
    if re.search(r"[ ]", str(seri)):
        return 1, "bosluk"
    if KIRLI_KELIME.search(n):
        return 1, "placeholder"
    if k and len(k) > 3 and n.startswith(k):
        return 1, "kod+sayac"
    if len(n) > 25:
        return 1, "asiri uzun"
    return 0, ""


def izleme_coz(deger):
    """Tiger'ın 'İzleme Yöntemi' metnini seri / lot / yok değerine indirger."""
    s = str(deger or "")
    if "Seri" in s or "SERI" in s.upper():
        return "seri"
    if "Lot" in s or "LOT" in s.upper():
        return "lot"
    return "yok"
