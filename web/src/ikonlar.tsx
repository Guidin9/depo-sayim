/** Çizgi ikon seti.
 *
 * Emoji kullanmıyoruz. Emoji her işletim sisteminde başka çiziliyor, kendi
 * rengini dayatıyor (arayüzün geri kalanıyla uyuşmuyor), yazı tipi ölçeğine
 * uymuyor ve depo aydınlatmasında uzaktan bakınca bulanık bir renk lekesine
 * dönüşüyor. Bunlar currentColor ile çiziliyor: bulunduğu düğmenin rengini
 * alıyorlar, hep aynı kalınlıkta ve her ekranda aynı.
 *
 * Ölçü 24'lük ızgarada, 1.75 kalınlık. Varsayılan boy 18px — 15px'lik düğme
 * metninin yanında optik olarak denk duruyor.
 */
import type { SVGProps } from "react";

type Props = { boy?: number } & Omit<SVGProps<SVGSVGElement>, "width" | "height">;

function Ikon({ boy = 18, children, ...kalan }: Props & { children: React.ReactNode }) {
  return (
    <svg
      width={boy}
      height={boy}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className="shrink-0"
      {...kalan}
    >
      {children}
    </svg>
  );
}

/* ------------------------------------------------------------- cihazlar */

export const Telefon = (p: Props) => (
  <Ikon {...p}>
    <rect x="6" y="2" width="12" height="20" rx="2.5" />
    <path d="M10.5 18.5h3" />
  </Ikon>
);

export const Ekran = (p: Props) => (
  <Ikon {...p}>
    <rect x="3" y="4" width="18" height="12" rx="2" />
    <path d="M2 20h20" />
  </Ikon>
);

export const Okuyucu = (p: Props) => (
  <Ikon {...p}>
    <path d="M4 7V5.5A1.5 1.5 0 0 1 5.5 4H7M17 4h1.5A1.5 1.5 0 0 1 20 5.5V7M20 17v1.5a1.5 1.5 0 0 1-1.5 1.5H17M7 20H5.5A1.5 1.5 0 0 1 4 18.5V17" />
    <path d="M8 8.5v7M11 8.5v7M14 8.5v7M16.5 8.5v7" />
  </Ikon>
);

export const Klavye = (p: Props) => (
  <Ikon {...p}>
    <rect x="2" y="6" width="20" height="12" rx="2" />
    <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M8 14h8" />
  </Ikon>
);

/* ---------------------------------------------------------------- ses */

export const SesAcik = (p: Props) => (
  <Ikon {...p}>
    <path d="M11 5 6.5 9H3v6h3.5L11 19z" />
    <path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13" />
  </Ikon>
);

export const SesKapali = (p: Props) => (
  <Ikon {...p}>
    <path d="M11 5 6.5 9H3v6h3.5L11 19z" />
    <path d="m16 9.5 5 5M21 9.5l-5 5" />
  </Ikon>
);

/* ------------------------------------------------------------- eylemler */

export const Kamera = (p: Props) => (
  <Ikon {...p}>
    <path d="M3 8.5A1.5 1.5 0 0 1 4.5 7h2.2l1.2-2h8.2l1.2 2h2.2A1.5 1.5 0 0 1 21 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z" />
    <circle cx="12" cy="13" r="3.2" />
  </Ikon>
);

export const Duraklat = (p: Props) => (
  <Ikon {...p}>
    <path d="M9.5 5v14M14.5 5v14" />
  </Ikon>
);

export const Not = (p: Props) => (
  <Ikon {...p}>
    <path d="M4 20h4l10-10a2.5 2.5 0 0 0-3.5-3.5L4.5 16.5z" />
    <path d="M13.5 7.5 16.5 10.5" />
  </Ikon>
);

export const Ara = (p: Props) => (
  <Ikon {...p}>
    <circle cx="10.5" cy="10.5" r="6.5" />
    <path d="m15.5 15.5 4.5 4.5" />
  </Ikon>
);

export const Indir = (p: Props) => (
  <Ikon {...p}>
    <path d="M12 3v11M7.5 10 12 14.5 16.5 10" />
    <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
  </Ikon>
);

export const Yukle = (p: Props) => (
  <Ikon {...p}>
    <path d="M12 16V5M7.5 9.5 12 5l4.5 4.5" />
    <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
  </Ikon>
);

export const Yazdir = (p: Props) => (
  <Ikon {...p}>
    <path d="M7 9V3h10v6" />
    <path d="M7 18H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2" />
    <rect x="7" y="15" width="10" height="6" rx="1" />
  </Ikon>
);

export const Kapat = (p: Props) => (
  <Ikon {...p}>
    <path d="m6 6 12 12M18 6 6 18" />
  </Ikon>
);

export const Cop = (p: Props) => (
  <Ikon {...p}>
    <path d="M4 7h16" />
    <path d="M9 7V4h6v3" />
    <path d="M6 7l1 13h10l1-13" />
    <path d="M10 11v6M14 11v6" />
  </Ikon>
);

export const Kilit = (p: Props) => (
  <Ikon {...p}>
    <rect x="4" y="10" width="16" height="10" rx="2" />
    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
  </Ikon>
);

export const KilitAcik = (p: Props) => (
  <Ikon {...p}>
    <rect x="4" y="10" width="16" height="10" rx="2" />
    <path d="M8 10V7a4 4 0 0 1 7.5-2" />
  </Ikon>
);

export const Vida = (p: Props) => (
  <Ikon {...p}>
    <path d="M14.7 6.3a4 4 0 0 1-5.2 5.2L4 17v3h3l5.5-5.5a4 4 0 0 1 5.2-5.2l-2.6 2.6-2.1-2.1z" />
  </Ikon>
);

export const Geri = (p: Props) => (
  <Ikon {...p}>
    <path d="M9 14 4 9l5-5" />
    <path d="M4 9h11a5 5 0 0 1 0 10h-4" />
  </Ikon>
);

export const OkSag = (p: Props) => (
  <Ikon {...p}>
    <path d="M4 12h15M13 6l6 6-6 6" />
  </Ikon>
);

export const Tekrar = (p: Props) => (
  <Ikon {...p}>
    <path d="M20 12a8 8 0 1 1-2.6-5.9" />
    <path d="M20 3v5h-5" />
  </Ikon>
);

/* -------------------------------------------------------------- durumlar */

export const Onay = (p: Props) => (
  <Ikon {...p}>
    <path d="m4.5 12.5 5 5 10-11" />
  </Ikon>
);

export const Uyari = (p: Props) => (
  <Ikon {...p}>
    <path d="M12 3.5 22 20H2z" />
    <path d="M12 9.5v5M12 17.5h.01" />
  </Ikon>
);

export const Engel = (p: Props) => (
  <Ikon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m6 6 12 12" />
  </Ikon>
);

export const Soru = (p: Props) => (
  <Ikon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 1 1 3.2 2.4c-.5.2-.7.6-.7 1.1v.5" />
    <path d="M12 17h.01" />
  </Ikon>
);

export const Bitti = (p: Props) => (
  <Ikon {...p}>
    <rect x="5" y="5" width="14" height="14" rx="2" />
  </Ikon>
);

export const Yildiz = (p: Props) => (
  <Ikon {...p}>
    <path d="m12 3.5 2.7 5.6 6 .9-4.35 4.3 1.03 6.1L12 17.5l-5.38 2.9 1.03-6.1L3.3 10l6-.9z" />
  </Ikon>
);

export const Barkod = (p: Props) => (
  <Ikon {...p}>
    <path d="M4 5v14M7.5 5v14M11 5v10M14.5 5v14M18 5v10M20.5 5v14" />
  </Ikon>
);

export const Etiket = (p: Props) => (
  <Ikon {...p}>
    <path d="M4 10h16M4 14h16M10 4 8 20M16 4l-2 16" />
  </Ikon>
);

/* Raf — depoda rafı gösteren işaret. ▣ karakterinin yerini alıyor. */
export const Raf = (p: Props) => (
  <Ikon {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M3 9.5h18M3 15h18" />
  </Ikon>
);

export const Pano = (p: Props) => (
  <Ikon {...p}>
    <path d="M9 4H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2" />
    <rect x="9" y="2.5" width="6" height="4" rx="1.2" />
  </Ikon>
);

/* Adet / miktar: üst üste konmuş katmanlar. Lot ve dökme kalemlerde "tek satır
   çok adet" fikrini anlatan tek şekil — kutu ikonu tekil ürün çağrıştırıyordu. */
export const Katman = (p: Props) => (
  <Ikon {...p}>
    <path d="M12 3 3 7.5l9 4.5 9-4.5L12 3Z" />
    <path d="M3 12.5 12 17l9-4.5" />
    <path d="M3 17 12 21.5 21 17" />
  </Ikon>
);

export const Bos = (p: Props) => (
  <Ikon {...p}>
    <circle cx="12" cy="12" r="2" />
  </Ikon>
);

/* Kuyruk kartlarının aç/kapa oku. */
export const Cevron = ({ acik, ...p }: Props & { acik?: boolean }) => (
  <Ikon {...p}>{acik ? <path d="m6 9 6 6 6-6" /> : <path d="m9 6 6 6-6 6" />}</Ikon>
);
