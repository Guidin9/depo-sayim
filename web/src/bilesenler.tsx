/** Paylaşılan arayüz parçaları.
 *
 * Kural: renk tek başına bilgi taşımaz — her durum ikon + metinle de anlatılır
 * (depo aydınlatması kötü, ekrana uzaktan bakılıyor).
 *
 * Design.md uyarlaması buradan yayılıyor: Kurulum, Kuyruk, Rapor, Geçmiş ve
 * Ayarlar ekranlarının görünümünün çoğu Dugme / Panel / Baslik üzerinden
 * geliyor, o ekranlarda ayrıca iş yapmak gerekmiyor.
 */
import type { ReactNode } from "react";
import type { CozTipi } from "./api";
import * as Ik from "./ikonlar";
import type { BaglantiHali } from "./olaylar";

export function Dugme({
  cocuk,
  tikla,
  tur = "sade",
  kisayol,
  genis,
  pasif,
  baslik,
}: {
  cocuk: ReactNode;
  tikla?: () => void;
  tur?: "sade" | "ana" | "tehlike";
  kisayol?: string;
  genis?: boolean;
  pasif?: boolean;
  baslik?: string;
}) {
  /* Yalnızca "sade" cam yüzeye geçti, o da bulanıklık yapmayan varyantına.
     Birincil ve tehlikeli eylemler opak kalıyor: depoda uzaktan bakınca
     hangisinin ana düğme olduğu bir bakışta seçilmeli, cam bunu zayıflatıyor. */
  const stil =
    tur === "ana"
      ? "bg-vurgu text-white hover:brightness-110"
      : tur === "tehlike"
        ? "bg-hata/15 text-hata border border-hata/40 hover:bg-hata/25"
        : "cam-hafif text-yazi hover:bg-cizgi";
  return (
    <button
      type="button"
      onClick={tikla}
      disabled={pasif}
      title={baslik}
      className={`${stil} ${genis ? "w-full" : ""} inline-flex items-center justify-center gap-2
        rounded-full px-5 text-[15px] font-semibold transition duration-200 ease-kolay
        disabled:cursor-not-allowed disabled:opacity-40`}
    >
      {cocuk}
      {kisayol && (
        <kbd className="rounded-full border border-current/30 px-2 py-0.5 text-[11px] font-normal opacity-70">
          {kisayol}
        </kbd>
      )}
    </button>
  );
}

/** Şirket logosu + isim.
 *
 * Bukalemun app.ico'dan geliyor ve public/ altından kökle servis ediliyor;
 * sekmedeki favicon ile aynı dosya, arayüzle sekme aynı şeyi gösteriyor. */
export function Marka({ boy = 28, yazi = true }: { boy?: number; yazi?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <img
        src="/logo.png"
        alt=""
        width={boy}
        height={boy}
        style={{ width: boy, height: boy }}
        className="shrink-0 object-contain"
      />
      {yazi && <span className="font-serif text-2xl tracking-tight">Depo Sayım</span>}
    </span>
  );
}

/** Ekran başlığı — Design.md'nin dev serif hero'sunun ekran ölçeğine inmiş hâli. */
export function Baslik({ cocuk, alt }: { cocuk: ReactNode; alt?: ReactNode }) {
  return (
    <header>
      <h1 className="font-serif text-4xl leading-[0.95] font-normal tracking-tight sm:text-5xl">
        {cocuk}
      </h1>
      {alt && <p className="mt-2 max-w-2xl text-[15px] text-solgun">{alt}</p>}
    </header>
  );
}

/** Cam kabuk + opak gövde.
 *
 * Bölümün kendisi cam: kenarlarından ızgara zemin geçiyor ve Design.md'nin
 * gradyan saç teli kenarlığı buraya uygulanıyor. Gövde opak bg-panel kalıyor —
 * içindeki veri satırlarının kontrastı düşmemeli. */
export function Panel({
  baslik,
  sag,
  cocuk,
  sinif = "",
}: {
  baslik?: ReactNode;
  sag?: ReactNode;
  cocuk: ReactNode;
  sinif?: string;
}) {
  return (
    <section className={`cam rounded-2xl ${sinif}`}>
      {(baslik || sag) && (
        <header className="flex items-center justify-between gap-3 border-b border-cizgi px-5 py-3">
          <h2 className="text-[13px] font-bold tracking-wider text-solgun uppercase">{baslik}</h2>
          {sag}
        </header>
      )}
      <div className="bg-panel p-4">{cocuk}</div>
    </section>
  );
}

/* İkon + metin çifti bilerek korunuyor: renk tek başına bilgi taşımaz.
   Değişen yalnızca ikonun emoji/glif yerine çizgi SVG olması. */
const ROZET: Record<CozTipi, { ad: string; Ikon: typeof Ik.Onay; sinif: string }> = {
  seri: { ad: "S/N tanındı", Ikon: Ik.Onay, sinif: "bg-ok/15 text-ok border-ok/40" },
  kod: { ad: "malzeme kodu", Ikon: Ik.Etiket, sinif: "bg-bilgi/15 text-bilgi border-bilgi/40" },
  ogrenilmis: { ad: "öğrenilmiş", Ikon: Ik.Yildiz, sinif: "bg-vurgu/20 text-vurgu border-vurgu/50" },
  upc: { ad: "UPC barkodu", Ikon: Ik.Barkod, sinif: "bg-uyari/15 text-uyari border-uyari/40" },
  bilinmiyor: { ad: "tanınmadı", Ikon: Ik.Soru, sinif: "bg-hata/15 text-hata border-hata/40" },
  tekrar: { ad: "zaten okutuldu", Ikon: Ik.Tekrar, sinif: "bg-uyari/15 text-uyari border-uyari/40" },
  // Bizim bastığımız, henüz hiçbir ürüne bağlanmamış seri etiketi
  etiket_bos: { ad: "boş etiket", Ikon: Ik.Etiket, sinif: "bg-vurgu/15 text-vurgu border-vurgu/40" },
  bos: { ad: "boş", Ikon: Ik.Bos, sinif: "bg-panel2 text-solgun border-cizgi" },
};

export function Rozet({ tip }: { tip: CozTipi }) {
  const r = ROZET[tip] ?? ROZET.bos;
  return (
    <span
      className={`${r.sinif} inline-flex shrink-0 items-center gap-1.5 rounded-full border
        px-2.5 py-1 text-[12px] font-bold whitespace-nowrap`}
    >
      <r.Ikon boy={14} />
      {r.ad}
    </span>
  );
}

export function SayacKutu({
  etiket,
  deger,
  vurgu,
  buyuk,
}: {
  etiket: string;
  deger: number | string;
  vurgu?: "ok" | "uyari" | "hata" | "solgun";
  buyuk?: boolean;
}) {
  const renk =
    vurgu === "ok"
      ? "text-ok"
      : vurgu === "uyari"
        ? "text-uyari"
        : vurgu === "hata"
          ? "text-hata"
          : "text-yazi";
  /* Sayaçlar Inter + tabular-nums olarak kalıyor, serif'e geçmiyor: Instrument
     Serif'te sabit genişlikli rakam garantisi yok, sayaçlar her okutmada
     zıplardı. Design.md'nin "dev tipografi" karakteri boyutla veriliyor. */
  return (
    <div className="min-w-[82px] text-center">
      <div
        className={`rakam font-bold tracking-tight ${renk} ${buyuk ? "text-5xl" : "text-3xl"}
          leading-none`}
      >
        {deger}
      </div>
      <div className="mt-1.5 text-[11px] font-semibold tracking-wider text-solgun uppercase">
        {etiket}
      </div>
    </div>
  );
}

/** Canlı bağlantı göstergesi — Design.md'nin yeşil CTA noktası.
 *
 * Emoji yerine gerçek nokta, canlıyken yayılan halkasıyla. Yanındaki metin
 * bilerek duruyor: renk tek başına bilgi taşımaz. */
export function Nokta({ hal, metin = true }: { hal: BaglantiHali; metin?: boolean }) {
  const h = {
    canli: { renk: "bg-ok", yazi: "text-ok", ad: "canlı" },
    baglaniyor: { renk: "bg-uyari", yazi: "text-uyari", ad: "bağlanıyor" },
    kopuk: { renk: "bg-hata", yazi: "text-hata", ad: "kopuk" },
  }[hal];
  return (
    <span className="inline-flex items-center gap-2 text-[13px] font-semibold">
      <span className="relative inline-flex h-2 w-2 shrink-0">
        {hal === "canli" && (
          <span className={`halka absolute inset-0 rounded-full ${h.renk}`} aria-hidden />
        )}
        <span
          className={`relative h-2 w-2 rounded-full ${h.renk} ${
            hal === "baglaniyor" ? "nabiz" : ""
          }`}
          aria-hidden
        />
      </span>
      {metin && <span className={h.yazi}>{h.ad}</span>}
    </span>
  );
}

export function Uyari({ tur = "hata", cocuk }: { tur?: "hata" | "uyari" | "bilgi"; cocuk: ReactNode }) {
  const stil = {
    hata: "border-hata/50 bg-hata/10 text-hata",
    uyari: "border-uyari/50 bg-uyari/10 text-uyari",
    bilgi: "border-bilgi/50 bg-bilgi/10 text-bilgi",
  }[tur];
  return (
    <div className={`${stil} rounded-xl border px-4 py-3 text-[14px] font-semibold`}>{cocuk}</div>
  );
}

/** Boş durum — serif italik. Veri değil, anlatı; tipografi de öyle desin. */
export function Bos({ cocuk }: { cocuk: ReactNode }) {
  return <p className="py-10 text-center font-serif text-xl text-solgun italic">{cocuk}</p>;
}

export function Kod({ cocuk }: { cocuk: ReactNode }) {
  return <span className="font-mono text-[14px] break-all">{cocuk}</span>;
}
