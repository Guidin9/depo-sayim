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
  | "bos";

export type TamponSatiri = {
  ham: string;
  coz: CozTipi;
  kod: string | null;
  aciklama: string | null;
  not: string | null;
};

export type AkisSatiri = {
  ts: string;
  ham: string;
  kod: string | null;
  seri: string | null;
  tip: string;
  raf: string | null;
  not_: string | null;
};

export type Durum = {
  oturum: number;
  yukleme: number;
  ambar: string;
  aktif_raf: string | null;
  durum: string;
  sayac: Sayac;
  tampon: TamponSatiri[];
  akis: AkisSatiri[];
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
  barkodlar?: string[];
  ogrenilen?: string[];
  raf?: string;
  adet?: number;
  ham?: string;
  coz?: CozTipi;
  not?: string | null;
  kapsam?: string;
  durum?: Durum;
  kuyruk_id?: number;
  adaylar?: Aday[];
  eski_raf?: string | null;
  yeni_raf?: string;
  kuyruk?: KuyrukSatiri[];
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
};

export type Aday = {
  id: number;
  kod: string;
  aciklama: string;
  izleme: string;
  birim: string;
  acik_kirli: number;
  acik_satir: number;
  acik_adet: number;
  ayni_raf: number;
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
};

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

export type EtiketSatiri = {
  kod: string;
  gosterim: string;
  tur: "malzeme" | "seri";
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
  tur: "malzeme" | "seri";
  adet?: number;      // kaç etiket (malzeme: atlanırsa hepsi)
  kopya?: number;     // malzeme: her koddan kaç kopya
  kapsam?: "eksik" | "hepsi" | "bos";
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
      if (g?.detail) mesaj = typeof g.detail === "string" ? g.detail : JSON.stringify(g.detail);
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
  adaylar: (id: number, limit = 5) =>
    istek<Aday[]>(`/api/oturum/${id}/adaylar?limit=${limit}`),
  gerial: (id: number, kapsam: "okutma" | "grup") =>
    gonder<OkutmaSonucu>(`/api/oturum/${id}/gerial`, { kapsam }),
  bitir: (id: number, zorla = false) =>
    gonder<{ id: number; durum: string }>(`/api/oturum/${id}/bitir?zorla=${zorla}`, {}),
  oturumlar: () => istek<OturumOzeti[]>("/api/oturumlar"),
  ara: (id: number, q: string) =>
    istek<AramaSonucu[]>(`/api/oturum/${id}/ara?q=${encodeURIComponent(q)}`),

  kuyruk: (id: number) => istek<KuyrukSatiri[]>(`/api/oturum/${id}/kuyruk`),
  kuyrukCoz: (kid: number, beklenen_id: number) =>
    gonder<OkutmaSonucu>(`/api/kuyruk/${kid}/coz`, { beklenen_id }),
  kuyrukFazla: (kid: number) => istek<{ tip: string }>(`/api/kuyruk/${kid}`, { method: "DELETE" }),
  kuyrukNot: (kid: number, not_: string) =>
    gonder<KuyrukSatiri>(`/api/kuyruk/${kid}`, { not_ }, "PATCH"),
  kuyrukBeklet: (kid: number, beklet: boolean) =>
    gonder<KuyrukSatiri>(`/api/kuyruk/${kid}`, { beklet }, "PATCH"),
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
  raflar: (id: number) => istek<string[]>(`/api/oturum/${id}/raflar`),

  onizleme: (id: number) => istek<RaporOnizleme>(`/api/oturum/${id}/rapor/onizleme`),
  raporUrl: (id: number) => `/api/oturum/${id}/rapor.xlsx`,

  etiketIhtiyac: (yukleme: number, ambar: string) =>
    istek<EtiketIhtiyaci>(
      `/api/etiket/ihtiyac?yukleme=${yukleme}&ambar=${encodeURIComponent(ambar)}`,
    ),
  etiketler: (tur?: "malzeme" | "seri", q?: string) => {
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
        if (g?.detail) mesaj = typeof g.detail === "string" ? g.detail : JSON.stringify(g.detail);
      } catch {
        /* gövde JSON değilse durum metni kalsın */
      }
      throw new ApiHatasi(mesaj);
    }
    return y.text();
  },

  komutKarti: async (raflar: string[]) => {
    const y = await fetch("/api/komut-karti", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raflar }),
    });
    if (!y.ok) throw new ApiHatasi("Komut kartı üretilemedi");
    return y.text();
  },
};
