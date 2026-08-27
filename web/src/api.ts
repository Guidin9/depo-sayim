/** Backend sarmalayıcı ve paylaşılan tipler. */
import { ISTEMCI } from "./olaylar";

export type Kural = {
  id: number;
  tip: "tur" | "aciklama";
  desen: string;
  aktif: boolean;
  varsayilan: boolean;
  satir: number;
  adet: number;
};

export type Ozet = {
  yukleme: number;
  dosya: string;
  ts: string;
  kaynak: string;
  satir: number;
  izleme: { izleme: string; satir: number; adet: number; malzeme: number; kirli: number }[];
  ambarlar: { ambar: string; satir: number; adet: number }[];
  kirli_sebep: { sebep: string; satir: number }[];
  kirli: number;
  haric: { satir: number; adet: number };
  /** Raporda gerçekten geçen malzeme türleri — `tur` kuralları yazmak için. */
  turler: { tur: string; satir: number }[];
  kurallar?: Kural[];
  eklenen?: number;
  atlanan?: number;
};

export type Ambar = {
  ambar: string;
  satir: number;
  adet: number;
  haric: number;
  kirli: number;
  malzeme: number;
};

export type Sayac = {
  okutulan: number;
  kalan: number;
  fazla: number;
  kuyruk: number;
  toplam: number;
};

export type CozTipi =
  | "seri"
  | "kod"
  | "ogrenilmis"
  | "upc"
  | "bilinmiyor"
  | "tekrar"
  | "etiket_bos"
  /* Kap etiketi (KUTU_TASARIM.md): tanımlı / tanımsız / malzemesi bu ambarda
     olmayan. Kap kodu hiçbir zaman "bilinmiyor" dönmez — öğrenilmez de. */
  | "kutu"
  | "kutu_bos"
  | "kutu_yabanci"
  | "bos";

export type TamponSatiri = {
  ham: string;
  coz: CozTipi;
  kod: string | null;
  aciklama: string | null;
  not: string | null;
};

export type AkisSatiri = {
  /** Satır bazlı silme (I1) için şart — `##GERIAL##` yalnızca sonuncuyu alır. */
  id: number;
  ts: string;
  ham: string;
  kod: string | null;
  seri: string | null;
  tip: string;
  raf: string | null;
  /** Bir grup bir üründür; silme varsayılan olarak grubun tamamını alır. */
  grup: number | null;
  miktar: number;
  not_: string | null;
};

export type Durum = {
  oturum: number;
  yukleme: number;
  ambar: string;
  aktif_raf: string | null;
  /** Sıradaki grubun adedi — ##ADET-N## / telefon tuş takımı. 0 = verilmedi. */
  bekleyen_adet: number;
  /** Kilitli malzeme kodu (I2). Yalnız seri numaraları okutuluyor demek. */
  sabit_kod: string | null;
  sabit_aciklama: string | null;
  /** Yedek parça modu (I4): okutulan hiçbir şey Tiger'da ARANMAZ. */
  yedek_parca: boolean;
  /** Açık seri takipli kap (KUTU_TASARIM.md 5). Kilit gibi KALICI bir kip:
   *  ekranda görünmezse kullanıcı kabı kapattığını sanıp sonraki ürünleri
   *  kilitli malzemeye yazar. `beklenen` kabın SON BİLİNEN adedi — gerçek
   *  değil, karşılaştırma için. */
  acik_kutu: KutuSayaci | null;
  durum: string;
  sayac: Sayac;
  tampon: TamponSatiri[];
  akis: AkisSatiri[];
};

export type KutuSayaci = {
  kutu: string;
  kod: string;
  aciklama: string | null;
  sayilan: number;
  beklenen: number | null;
  taze: boolean;
  /** beklenen - sayilan (yalnızca eksikse). Uyarır, ENGELLEMEZ. */
  eksik: number;
};

export type Ses = "tik" | "ok" | "uyari" | "kuyruk" | "bitti";

export type OkutmaSonucu = {
  tip: string;
  ses?: Ses;
  kod?: string;
  /* Kendi bastığımız etiketler (CLAUDE.md 12) */
  etiket?: string | null;
  etiket_yersiz?: string | null;
  bos_etiket?: string[];
  aciklama?: string;
  seri?: string;
  eski?: string;
  yeni?: string;
  toplam?: number;
  beklenen?: number;
  /** Adet dalında hangi lot satırına yazıldığı — çok lotlu malzemede şart. */
  izleme?: "seri" | "lot" | "yok";
  /** Bu grupta işlenen MİKTAR (kaç ürün) ve kaç beklenen satırına dağıtıldığı.
      `adet` ile karıştırmayın: o, tamponda kaç BARKOD olduğunu söylüyor. */
  miktar?: number;
  satir?: number;
  /** Seri takipli kalemde girilen adet uygulanamadı — sessizce yutmuyoruz. */
  adet_yersiz?: number | null;
  /** Adet tavanı aşıldığında dönen sınır. */
  tavan?: number;
  /** tip="haric": kalemi sayım dışı bırakan kural (`tur:TK`, `aciklama:LİSANS`). */
  sebep?: string;
  /** tip="slot": sayıldı ama Tiger'a yazılacak seri numarası verilmedi. */
  sn_yok?: boolean;
  /** Kilitli malzeme koduyla sayıldıysa hangi kodla (I2). */
  sabit_kod?: string | null;
  /** tip="yedek_mod": mod açık mı. */
  acik?: boolean;
  /** ##GERIAL## ve okutma silme, geri alınan yan etkileri bildirir. */
  unutulan?: string[];
  etiket_cozuldu?: string | null;
  /** tip="silindi": kaç okutma satırı gitti, kuyruk kaydı yeniden açıldı mı. */
  silinen?: number;
  kuyruk_acildi?: number | null;
  barkodlar?: string[];
  ogrenilen?: string[];
  raf?: string;
  /** tip="tampon": tampondaki BARKOD sayısı — ürün adedi değil.
   *  Ürün adedi her zaman `miktar`. */
  adet?: number;
  ham?: string;
  coz?: CozTipi;
  not?: string | null;
  kapsam?: string;
  durum?: Durum;
  kuyruk_id?: number;
  /** Elle fazlada oluşan okutma satırlarının id'leri — arayüz ad sorabilsin. */
  okutma?: number[];
  eski_raf?: string | null;
  yeni_raf?: string;
  kuyruk?: KuyrukSatiri[];
  /** Fotoğrafsız fazla kayıtları — bitirme kapısı (DEMO_FEEDBACK.md 6). */
  fotosuz?: { id: number; ham: string; kod: string | null; raf: string | null }[];
  /** Ne olduğu yazılmamış fazla kayıtları — bitirme kapısı. */
  adsiz?: { id: number; ham: string; raf: string | null; seri: string | null }[];
  /** Kap okutmasında kabın gösterim kodu (DK-000007). */
  kutu?: string | null;
  /** tip="kutu_yabanci": kayıtta duran ama bu ambarda olmayan malzeme. */
  eski_kod?: string | null;
  /** tip="kutu_sor" / "kutu_seri": kabın SON BİLİNEN adedi ve tazeliği.
   *  `oneri_adet` yalnızca kayıt tazeyken dolu — bayat kayıtta alan boş açılır,
   *  çünkü içerik ayda bir değişiyor (KUTU_TASARIM.md 3, 6). */
  taze?: boolean;
  oneri_adet?: number | null;
  /** tip="kutu_kapandi": kapanış özeti. */
  sayilan?: number;
  eksik?: number;
  /** tip="kutu_acildi": bu kap açılırken kapanan önceki kap (varsa). */
  onceki_kutu?: KutuSayaci | null;
  /** tip="kilitac": kilit kabın kilidiyse kap da kapanır, özeti burada. */
  kutu_kapandi?: KutuSayaci | null;
  /** tip="kutu_acildi": kap zaten açıktı (sayaç sıfırlanmadı). */
  zaten_acik?: boolean;
  /** tip="kutu_kapandi": kabın kaydı okunamadı — boşaltılmış olabilir. */
  kayit_yok?: boolean;
};

/** Karar bekleyen kaydın türü.
 *
 * bilinmiyor: ne seri ne kod tanındı — "bu hangi malzeme?"
 * fazla_onay: malzeme tanındı, karşılığı bulunamadı — "gerçekten fazla mı?"
 */
export type KuyrukTuru = "bilinmiyor" | "fazla_onay" | "kutu";

/** Kap kaydı — "bu kapta ne var" (KUTU_TASARIM.md).
 *
 * Kalıcı olan MALZEME BAĞIDIR, adet değil: içerik ayda bir değişiyor, sayım
 * yılda bir yapılıyor. `oneri_adet` bu yüzden yalnızca taze kayıtta dolu;
 * bayatta null döner ve arayüz adet alanını BOŞ açar. `adet` son bilinen
 * değerdir ve yalnızca gri ipucu olarak gösterilir. */
export type KutuBilgi = {
  kod: string;
  gosterim: string;
  malzeme: string | null;
  aciklama: string | null;
  adet: number | null;
  izleme: "seri" | "lot" | "yok" | null;
  raf: string | null;
  yas_gun: number | null;
  taze: boolean;
  tazelik_gun: number;
  oneri_adet: number | null;
  /** Kayıtlı malzeme bu ambarda var mı (CLAUDE.md 3.5 — dışına çıkmıyoruz). */
  bu_ambarda: boolean | null;
  ts: string | null;
  ts_guncelle: string | null;
};

export type KuyrukSatiri = {
  id: number;
  barkodlar: string[];
  raf: string | null;
  ts: string;
  cozuldu: boolean;
  not_: string;
  /** Telefonda "sonra çözerim" işaretlendi: fotoğrafı var, çözümü PC'de. */
  beklet: boolean;
  fotolar: number[];
  tur: KuyrukTuru;
  /** fazla_onay'da tanınan malzeme kodu; bilinmiyor'da null. */
  kod: string | null;
  ad: string | null;
  /** Grup kapanırken girilmiş adet. 0 = girilmedi ("1 tane" ile aynı şey değil). */
  adet: number;
  aciklama: string;
  /** tur="kutu" kayıtlarında kabın durumu; ötekilerde null. */
  kutu: KutuBilgi | null;
};

/** Kap defteri satırı — `GET /api/kutu` ne dönüyorsa o.
 *
 * `KutuBilgi` ile karıştırmayın: orası TEK kap için tazelik kararını da verir
 * (`oneri_adet`, `tazelik_gun`, `bu_ambarda`), liste ucu vermez. İkisini tek
 * tip saymak, listede olmayan alanları varmış gibi okumak demekti. */
export type KutuSatiri = {
  kod: string;
  gosterim: string;
  malzeme: string | null;
  adet: number | null;
  izleme: "seri" | "lot" | "yok" | null;
  raf: string | null;
  ts: string | null;
  ts_guncelle: string | null;
  oturum: number | null;
  aciklama: string | null;
  yas_gun: number | null;
  taze: boolean;
};

export type AramaSonucu = {
  id: number;
  kod: string;
  aciklama: string;
  seri: string;
  kirli: number;
  izleme: string;
  miktar: number;
  birim: string;
  sayildi: number;
  /** Bu rafta aynı koddan kaç satır sayıldı — raf komşuluğu en güçlü ipucu. */
  ayni_raf: number;
};

/** Arama / listeleme filtreleri. Hepsi isteğe bağlı; q boşken de çalışır. */
export type AramaFiltre = {
  q?: string;
  limit?: number;
  offset?: number;
  /** Bu oturumda sayılmamış satırlar (lot'ta sayılan < beklenen). */
  sadece_acik?: boolean;
  /** Yalnızca uydurma kayıtlı (ya da yalnızca temiz) satırlar. */
  kirli?: boolean;
  izleme?: "seri" | "lot" | "yok";
};

export type AramaYaniti = { satirlar: AramaSonucu[]; toplam: number };

/** Sayım sonu eşleştirme ekranı (DEMO_FEEDBACK.md 6). */
export type FazlaKaydi = {
  id: number;
  ts: string;
  ham: string;
  kod: string | null;
  seri: string | null;
  ad: string | null;
  raf: string | null;
  not_: string;
  fotolar: number[];
};

export type EksikKaydi = {
  id: number;
  kod: string;
  aciklama: string;
  seri: string;
  izleme: string;
  birim: string;
  kirli: number;
  miktar: number;
  not_: string;
};

export type EslemeVerisi = { fazla: FazlaKaydi[]; eksik: EksikKaydi[] };

export type Sekme = {
  basliklar: string[];
  satirlar: (string | number | null)[][];
  dipnot: string[];
  toplam: number;
};

export type RaporOnizleme = Record<string, Sekme> & {
  _ozet: {
    oturum: number;
    ambar: string;
    yukleme: number;
    basla: string;
    bitir: string;
    durum: string;
    haric: number;
    sayilar: Record<string, number>;
  };
};

export type OturumOzeti = {
  id: number;
  yukleme: number;
  ambar: string;
  basla: string;
  bitir: string | null;
  durum: string;
  dosya_adi: string | null;
  okutulan: number;
  fazla: number;
  kuyruk: number;
};

/* Kesin sayı değil, ÜST SINIR: kutuların çoğunda üretici kodu/serisi zaten
   basılı olabilir (Tiger'a girilmemiş olsa da), onlara etiket gerekmez. */
export type EtiketIhtiyaci = {
  malzeme: { tekil: number; basili: number; eksik: number; barkodsuz: number };
  seri: { kirli_kayit: number; havuzda: number; ust_sinir: number };
};

export type EtiketTuru = "malzeme" | "seri" | "kutu";

export type EtiketSatiri = {
  kod: string;
  gosterim: string;
  tur: EtiketTuru;
  basim: number | null;
  ts: string | null;
  malzeme: string | null;
  aciklama: string | null;
  slot: string | null;
  beklenen_id: number | null;
  raf: string | null;
  ts_bagla: string | null;
};

export type BasimOzeti = {
  id: number;
  ts: string;
  tur: string;
  adet: number;
  ilk: string;
  son: string;
  duzen: string;
};

export type BasimIstegi = {
  tur: EtiketTuru;
  adet?: number;      // kaç etiket (malzeme: atlanırsa hepsi)
  kopya?: number;     // malzeme: her koddan kaç kopya
  /** kutu: "tanimli" = içeriği belli kapları YENİDEN bas (yeni numara
   *  tüketmez — kap etiketi değişse de kod aynı kalmalı). */
  kapsam?: "eksik" | "hepsi" | "bos" | "tanimli";
  yukleme?: number;
  ambar?: string;
  duzen: "a4" | "rulo";
  atla?: number;
};

export class ApiHatasi extends Error {}

async function istek<T>(yol: string, secenek?: RequestInit): Promise<T> {
  // Her istek kendi kimliğini taşır ki canlı yayın kendi olayımızı ayırt etsin.
  const y = await fetch(yol, {
    ...secenek,
    headers: { ...(secenek?.headers ?? {}), "X-Istemci": ISTEMCI },
  });
  if (!y.ok) {
    let mesaj = `${y.status} ${y.statusText}`;
    try {
      const g = await y.json();
      // Kapı yanıtlarında detail bir sözlük ve içinde okunabilir `mesaj` var
      // (kuyruk / fotoğraf kapıları). Kullanıcıya JSON göstermeyelim.
      if (g?.detail)
        mesaj =
          typeof g.detail === "string"
            ? g.detail
            : (g.detail.mesaj ?? JSON.stringify(g.detail));
    } catch {
      /* gövde JSON değilse durum metni kalsın */
    }
    throw new ApiHatasi(mesaj);
  }
  return (await y.json()) as T;
}

const gonder = <T,>(yol: string, govde: unknown, yontem = "POST") =>
  istek<T>(yol, {
    method: yontem,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(govde),
  });

export const api = {
  saglik: () => istek<{ durum: string; yukleme: number; beklenen: number }>("/api/saglik"),

  yukle: (dosya: File, yukleme?: number) => {
    const veri = new FormData();
    veri.append("dosya", dosya);
    if (yukleme) veri.append("yukleme", String(yukleme));
    return istek<Ozet>("/api/yukleme", { method: "POST", body: veri });
  },
  yuklemeler: () => istek<{ id: number; dosya_adi: string; ts: string; satir: number }[]>("/api/yukleme"),
  yuklemeOzeti: (id: number) => istek<Ozet>(`/api/yukleme/${id}/ozet`),
  ambarlar: (id: number) => istek<Ambar[]>(`/api/yukleme/${id}/ambarlar`),
  kurallar: (id: number) => istek<Kural[]>(`/api/yukleme/${id}/kurallar`),
  kurallariGuncelle: (
    id: number,
    kurallar: Partial<Kural>[],
    silinecek: number[] = [],
  ) => gonder<Kural[]>(`/api/yukleme/${id}/kurallar`, { yukleme: id, kurallar, silinecek }, "PUT"),

  oturumAc: (yukleme: number, ambar: string) =>
    gonder<{ id: number }>("/api/oturum", { yukleme, ambar }),
  acikOturum: () => istek<Durum | null>("/api/oturum/acik"),
  durum: (id: number) => istek<Durum>(`/api/oturum/${id}/durum`),
  okut: (id: number, ham: string, zorla = false) =>
    gonder<OkutmaSonucu>(`/api/oturum/${id}/okut`, { ham, zorla }),
  gerial: (id: number, kapsam: "okutma" | "grup") =>
    gonder<OkutmaSonucu>(`/api/oturum/${id}/gerial`, { kapsam }),
  bitir: (id: number, zorla = false) =>
    gonder<{ id: number; durum: string }>(`/api/oturum/${id}/bitir?zorla=${zorla}`, {}),
  oturumlar: () => istek<OturumOzeti[]>("/api/oturumlar"),
  ara: (id: number, f: AramaFiltre = {}) => {
    const p = new URLSearchParams();
    if (f.q) p.set("q", f.q);
    if (f.limit != null) p.set("limit", String(f.limit));
    if (f.offset) p.set("offset", String(f.offset));
    if (f.sadece_acik) p.set("sadece_acik", "true");
    if (f.kirli != null) p.set("kirli", String(f.kirli));
    if (f.izleme) p.set("izleme", f.izleme);
    return istek<AramaYaniti>(`/api/oturum/${id}/ara?${p}`);
  },

  /** Fazla kaydına elle ürün adı (Tiger'da karşılığı olmayan ürünler için). */
  okutmaAd: (okutmaId: number, ad: string) =>
    gonder<{ id: number; ad: string }>(`/api/okutma/${okutmaId}`, { ad }, "PATCH"),
  /** Akıştaki bir okutmayı sil. Varsayılan kapsam: grubun tamamı. */
  okutmaSil: (okutmaId: number, kapsam: "grup" | "satir" = "grup") =>
    gonder<OkutmaSonucu>(`/api/okutma/${okutmaId}`, { kapsam }, "DELETE"),

  esleme: (id: number) => istek<EslemeVerisi>(`/api/oturum/${id}/esleme`),
  fazlaBagla: (okutmaId: number, beklenen_id: number) =>
    gonder<{ tip: string; kod: string }>(`/api/okutma/${okutmaId}/bagla`, { beklenen_id }),
  fazlaCozAyir: (okutmaId: number) =>
    istek<{ tip: string }>(`/api/okutma/${okutmaId}/coz-ayir`, { method: "POST" }),
  okutmaFotosu: (okutmaId: number, dosya: Blob, ad = "foto.jpg") => {
    const veri = new FormData();
    veri.append("dosya", dosya, ad);
    return istek<{ id: number; boyut: number }>(`/api/okutma/${okutmaId}/foto`, {
      method: "POST",
      body: veri,
    });
  },

  kuyruk: (id: number) => istek<KuyrukSatiri[]>(`/api/oturum/${id}/kuyruk`),
  /** Kap kaydını çöz: içeriği tanımla ve (serisizse) sayımı işle.
   *  Seri takipli malzemede adet gönderilmez — sayım seri numaralarıyla olur. */
  kutuCoz: (kid: number, malzeme: string, adet?: number | null) =>
    gonder<OkutmaSonucu & { sayildi?: boolean }>(`/api/kuyruk/${kid}/kutu`, {
      malzeme,
      adet: adet ?? null,
    }),
  kuyrukCoz: (kid: number, beklenen_id: number) =>
    gonder<OkutmaSonucu>(`/api/kuyruk/${kid}/coz`, { beklenen_id }),
  /** Kuyruk kaydını fazla olarak kapatır.
   *  Malzeme kodu bilinmiyorsa `ad` ZORUNLU — sunucu adsız kaydı reddeder. */
  kuyrukFazla: (kid: number, ad?: string) =>
    istek<{ tip: string; okutma: number[] }>(`/api/kuyruk/${kid}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ad: ad ?? null }),
    }),
  kuyrukAd: (kid: number, ad: string) =>
    gonder<KuyrukSatiri>(`/api/kuyruk/${kid}`, { ad }, "PATCH"),
  kuyrukNot: (kid: number, not_: string) =>
    gonder<KuyrukSatiri>(`/api/kuyruk/${kid}`, { not_ }, "PATCH"),
  kuyrukBeklet: (kid: number, beklet: boolean) =>
    gonder<KuyrukSatiri>(`/api/kuyruk/${kid}`, { beklet }, "PATCH"),
  /** Kuyruk kaydının adedini düzelt (kutuda 150 sanıp 130 çıkabilir). */
  kuyrukAdet: (kid: number, adet: number) =>
    gonder<KuyrukSatiri>(`/api/kuyruk/${kid}`, { adet }, "PATCH"),
  fotoYukle: (kid: number, dosya: Blob, ad = "foto.jpg") => {
    const veri = new FormData();
    veri.append("dosya", dosya, ad);
    return istek<{ id: number; boyut: number }>(`/api/kuyruk/${kid}/foto`, {
      method: "POST",
      body: veri,
    });
  },
  fotoSil: (fid: number) => istek<{ silindi: number }>(`/api/foto/${fid}`, { method: "DELETE" }),
  fotoUrl: (fid: number) => `/api/foto/${fid}`,
  ag: () =>
    istek<{ adresler: string[]; telefon: string[]; port: number; yerel: string }>("/api/ag"),
  rafAyarla: (id: number, raf: string, zorla = false) =>
    gonder<OkutmaSonucu>(`/api/oturum/${id}/raf`, { raf, zorla }),
  /** Sıradaki grubun adedi. 0 sıfırlar, öteki değerler mevcuda EKLENİR —
      ##ADET-N## komut barkoduyla birebir aynı yol. */
  adetAyarla: (id: number, adet: number) =>
    gonder<OkutmaSonucu>(`/api/oturum/${id}/adet`, { adet }),
  /** Barkodu olmayan ürünü listeden seçerek sayıldı işaretle (I5). */
  elleSay: (id: number, beklenen_id: number, ham?: string) =>
    gonder<OkutmaSonucu>(`/api/oturum/${id}/say`, { beklenen_id, ham: ham ?? null }),
  /** Malzeme kodunu kilitle; kod boş/null ise kilidi açar (I2). */
  sabitKod: (id: number, kod: string | null) =>
    gonder<OkutmaSonucu>(`/api/oturum/${id}/sabit-kod`, { kod }),
  /** Yedek parça modunu aç/kapat (I4). */
  yedekParca: (id: number, acik: boolean) =>
    gonder<OkutmaSonucu>(`/api/oturum/${id}/yedek-parca`, { acik }),
  /** Açık seri takipli kabı kapat — `##KUTUKAPAT##` ile aynı yol. */
  kutuKapat: (id: number) =>
    gonder<OkutmaSonucu>(`/api/oturum/${id}/kutu-kapat`, {}),

  raflar: (id: number) => istek<string[]>(`/api/oturum/${id}/raflar`),

  /* --- kap defteri (KUTU_TASARIM.md). Oturuma bağlı DEĞİL: kabın içeriği
     fiziksel bir gerçek, sayım oturumu değil. */
  kutular: (q?: string, sadece_tanimli = false) => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (sadece_tanimli) p.set("sadece_tanimli", "true");
    return istek<KutuSatiri[]>(`/api/kutu?${p}`);
  },
  kutu: (kod: string, yukleme?: number, ambar?: string) => {
    const p = new URLSearchParams();
    if (yukleme != null) p.set("yukleme", String(yukleme));
    if (ambar != null) p.set("ambar", ambar);
    return istek<KutuBilgi>(`/api/kutu/${encodeURIComponent(kod)}?${p}`);
  },
  kutuTanimla: (
    kod: string,
    v: { malzeme: string; adet?: number | null; yukleme: number; ambar: string;
         raf?: string | null; oturum?: number | null },
  ) => gonder<KutuBilgi>(`/api/kutu/${encodeURIComponent(kod)}`, v),
  /** Kap boşaldı / başka işe ayrıldı: içerik bağı silinir, NUMARA KALIR. */
  kutuBosalt: (kod: string) =>
    istek<KutuBilgi>(`/api/kutu/${encodeURIComponent(kod)}`, { method: "DELETE" }),

  onizleme: (id: number) => istek<RaporOnizleme>(`/api/oturum/${id}/rapor/onizleme`),
  raporUrl: (id: number) => `/api/oturum/${id}/rapor.xlsx`,

  etiketIhtiyac: (yukleme: number, ambar: string) =>
    istek<EtiketIhtiyaci>(
      `/api/etiket/ihtiyac?yukleme=${yukleme}&ambar=${encodeURIComponent(ambar)}`,
    ),
  etiketler: (tur?: EtiketTuru, q?: string) => {
    const p = new URLSearchParams();
    if (tur) p.set("tur", tur);
    if (q) p.set("q", q);
    return istek<EtiketSatiri[]>(`/api/etiket?${p}`);
  },
  basimlar: () => istek<BasimOzeti[]>("/api/etiket/basimlar"),

  // Komut kartı gibi: JSON değil yazdırılabilir HTML döner.
  etiketBas: async (istek_: BasimIstegi) => {
    const y = await fetch("/api/etiket/basim", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Istemci": ISTEMCI },
      body: JSON.stringify(istek_),
    });
    if (!y.ok) {
      let mesaj = `${y.status} ${y.statusText}`;
      try {
        const g = await y.json();
        // Kapı yanıtlarında detail bir sözlük ve içinde okunabilir `mesaj` var
      // (kuyruk / fotoğraf kapıları). Kullanıcıya JSON göstermeyelim.
      if (g?.detail)
        mesaj =
          typeof g.detail === "string"
            ? g.detail
            : (g.detail.mesaj ?? JSON.stringify(g.detail));
      } catch {
        /* gövde JSON değilse durum metni kalsın */
      }
      throw new ApiHatasi(mesaj);
    }
    return y.text();
  },

  komutKarti: async (raflar: string[], adetler?: number[]) => {
    const y = await fetch("/api/komut-karti", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raflar, adetler: adetler ?? null }),
    });
    if (!y.ok) throw new ApiHatasi("Komut kartı üretilemedi");
    return y.text();
  },

  // Raf barkodları yapışkanlı 24'lük etiket sayfası olarak (komut kartından
  // farklı: rafa doğrudan yapıştırılır, laminatlanmaz).
  rafEtiketi: async (raflar: string[], kopya: number, atla: number) => {
    const y = await fetch("/api/raf-etiketi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raflar, kopya, atla }),
    });
    if (!y.ok) {
      let mesaj = "Raf etiketi üretilemedi";
      try {
        const g = await y.json();
        if (g?.detail) mesaj = typeof g.detail === "string" ? g.detail : mesaj;
      } catch {
        /* gövde JSON değilse varsayılan mesaj kalsın */
      }
      throw new ApiHatasi(mesaj);
    }
    return y.text();
  },
};
