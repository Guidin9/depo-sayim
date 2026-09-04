/** Paylaşılan arayüz parçaları.
 *
 * Kural: renk tek başına bilgi taşımaz — her durum ikon + metinle de anlatılır
 * (depo aydınlatması kötü, ekrana uzaktan bakılıyor).
 *
 * Görsel dil: Flat + Swiss. Gölge yok, gradyan yok, cam yok, hap yok.
 * Yarıçap her yerde 2px (`rounded-sm`); tek istisna Nokta'nın bağlantı
 * noktası ve halkası — onlar gerçekten daire.
 *
 * Bu dosya değiştiğinde Kurulum, Kuyruk, Rapor, Geçmiş, Ayarlar, Etiket ve
 * Eşleme ekranlarının görünümünün çoğu kendiliğinden gelir. Sayim ve Telefon
 * kendi işaretlemesini çizdiği için onlar ayrıca geçirilir.
 *
 * Durum rengi + tint eşleşmesi TEK yerde durur (DURUM_STILI): rozet, uyarı ve
 * durum şeridi aynı tablodan besleniyor, yoksa üç ayrı yerde ayrışıyorlar.
 */
import type { InputHTMLAttributes, ReactNode, Ref } from "react";
import { useEffect } from "react";
import type { CozTipi } from "./api";
import * as Ik from "./ikonlar";
import type { BaglantiHali } from "./olaylar";

/** Durum ailesi → mürekkep + tint + kenarlık.
 *
 * Opaklık çarpanı (bg-ok/15 gibi) BİLEREK kullanılmıyor. Açık zeminde /15 ve
 * üstü kontrastı 4.5:1'in altına düşürüyor, amber ise hiçbir opaklıkta
 * geçmiyor (%10'da bile 4.39). Sabit tint jetonlarının oranı ölçüldü. */
const DURUM_STILI = {
  ok: "bg-ok-tint text-ok border-ok",
  uyari: "bg-uyari-tint text-uyari border-uyari",
  hata: "bg-hata-tint text-hata border-hata",
  bilgi: "bg-bilgi-tint text-bilgi border-bilgi",
  vurgu: "bg-vurgu-tint text-vurgu border-vurgu",
  notr: "bg-panel2 text-solgun border-cizgi",
} as const;

export type DurumTuru = keyof typeof DURUM_STILI;

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
  /* Üç seviye, üçü de opak: depoda uzaktan bakınca hangisinin ana düğme
     olduğu bir bakışta seçilmeli. */
  const stil =
    tur === "ana"
      ? "bg-vurgu text-white hover:brightness-115"
      : tur === "tehlike"
        ? "bg-hata-tint text-hata border border-hata hover:bg-hata hover:text-white"
        : "bg-panel text-yazi border border-cizgi-kuvvetli hover:bg-panel2";
  return (
    <button
      type="button"
      onClick={tikla}
      disabled={pasif}
      title={baslik}
      className={`${stil} ${genis ? "w-full" : ""} inline-flex items-center justify-center gap-2
        rounded-sm px-5 text-govde font-semibold transition-colors duration-150 ease-kolay
        disabled:cursor-not-allowed disabled:border-cizgi disabled:bg-panel2
        disabled:text-solgun-hafif disabled:hover:bg-panel2`}
    >
      {cocuk}
      {/* opacity-70 kullanılmıyor: %70 opak koyu metin beyaz üzerinde
          okunabilirliği düşürüyor, koyu temada tam tersiydi. */}
      {kisayol && (
        <kbd className="rounded-sm border border-current px-2 py-0.5 text-mikro font-normal">
          {kisayol}
        </kbd>
      )}
    </button>
  );
}

/** Düğme gibi görünen İNDİRME BAĞLANTISI.
 *
 * `<a download><Dugme/></a>` DEĞİL: etkileşimli içeriğin içine etkileşimli
 * içerik koymak geçersiz HTML ve klavye davranışı tarayıcının olay yayılımına
 * kalıyor — odaklanan `<button>`ın kendi `onClick`'i yok, Enter'ın indirmeyi
 * başlatması tesadüfe bağlı (DENETIM_20260904.md Dx4).
 *
 * Yükseklik `min-height` kuralından değil, açıkça geliyor: `a` `stil.css`'teki
 * 48 px kuralının kapsamında değil (kural `button, select, input,
 * [role=button]`), oysa bu da eldivenle basılan bir hedef.
 */
export function IndirBaglantisi({
  yol,
  cocuk,
  tur = "sade",
}: {
  yol: string;
  cocuk: ReactNode;
  tur?: "sade" | "ana";
}) {
  const stil =
    tur === "ana"
      ? "bg-vurgu text-white hover:brightness-115"
      : "bg-panel text-yazi border border-cizgi-kuvvetli hover:bg-panel2";
  return (
    <a
      href={yol}
      download
      className={`${stil} inline-flex min-h-12 items-center justify-center gap-2
        rounded-sm px-5 text-govde font-semibold no-underline transition-colors
        duration-150 ease-kolay`}
    >
      {cocuk}
    </a>
  );
}

/** Şirket logosu + isim.
 *
 * Bukalemun app.ico'dan geliyor ve public/ altından kökle servis ediliyor;
 * sekmedeki favicon ile aynı dosya, arayüzle sekme aynı şeyi gösteriyor.
 * Logo yeni tasarımda da korunur — şirket kimliği, tasarım tercihi değil
 * (CLAUDE.md §10.2): yeniden renklendirilmez, yeniden çizilmez. */
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
      {yazi && <span className="text-2xl font-bold tracking-tight">Depo Sayım</span>}
    </span>
  );
}

/** Ekran başlığı. Hiyerarşi yazı tipiyle değil kalınlıkla kurulur. */
export function Baslik({ cocuk, alt }: { cocuk: ReactNode; alt?: ReactNode }) {
  return (
    <header>
      <h1 className="text-4xl leading-[1.05] font-extrabold tracking-tight sm:text-5xl">
        {cocuk}
      </h1>
      {alt && <p className="mt-2 max-w-2xl text-govde text-solgun">{alt}</p>}
    </header>
  );
}

/** Geri düğmesi + başlık — altı ekranda birebir tekrar eden kalıp. */
export function EkranBasligi({
  cocuk,
  alt,
  geri,
  sag,
}: {
  cocuk: ReactNode;
  alt?: ReactNode;
  geri?: () => void;
  sag?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex items-end gap-4">
        {geri && (
          <Dugme cocuk={<><Ik.Geri boy={18} /> Geri</>} tikla={geri} />
        )}
        <Baslik cocuk={cocuk} alt={alt} />
      </div>
      {sag}
    </div>
  );
}

/** Bölüm kartı: başlık şeridi + gövde. */
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
    <section className={`overflow-hidden rounded-sm border border-cizgi bg-panel ${sinif}`}>
      {(baslik || sag) && (
        <header className="flex items-center justify-between gap-3 border-b border-cizgi bg-panel2 px-5 py-3">
          <h2 className="text-mikro font-bold tracking-etiket text-solgun uppercase">{baslik}</h2>
          {sag}
        </header>
      )}
      <div className="p-4">{cocuk}</div>
    </section>
  );
}

/* İkon + metin çifti bilerek korunuyor: renk tek başına bilgi taşımaz. */
const ROZET: Record<CozTipi, { ad: string; Ikon: typeof Ik.Onay; tur: DurumTuru }> = {
  seri: { ad: "S/N tanındı", Ikon: Ik.Onay, tur: "ok" },
  kod: { ad: "malzeme kodu", Ikon: Ik.Etiket, tur: "bilgi" },
  ogrenilmis: { ad: "öğrenilmiş", Ikon: Ik.Yildiz, tur: "vurgu" },
  upc: { ad: "UPC barkodu", Ikon: Ik.Barkod, tur: "uyari" },
  bilinmiyor: { ad: "tanınmadı", Ikon: Ik.Soru, tur: "hata" },
  tekrar: { ad: "zaten okutuldu", Ikon: Ik.Tekrar, tur: "uyari" },
  // Bizim bastığımız, henüz hiçbir ürüne bağlanmamış seri etiketi
  etiket_bos: { ad: "boş etiket", Ikon: Ik.Etiket, tur: "vurgu" },
  // Kap etiketi (DK-): "bu kapta ne var". Tanımlıysa malzemeyi getirir,
  // tanımsızsa bir kez sorulur (KUTU_TASARIM.md).
  kutu: { ad: "kap", Ikon: Ik.Katman, tur: "bilgi" },
  kutu_bos: { ad: "tanımsız kap", Ikon: Ik.Soru, tur: "uyari" },
  kutu_yabanci: { ad: "kap içeriği değişmiş", Ikon: Ik.Soru, tur: "uyari" },
  bos: { ad: "boş", Ikon: Ik.Bos, tur: "notr" },
};

export function Rozet({ tip }: { tip: CozTipi }) {
  const r = ROZET[tip] ?? ROZET.bos;
  return (
    <span
      className={`${DURUM_STILI[r.tur]} inline-flex shrink-0 items-center gap-1.5 rounded-sm
        border px-2.5 py-1 text-mikro font-bold whitespace-nowrap`}
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
  /* .rakam (tabular-nums) şart: orantılı rakamda sayaç her okutmada zıplar. */
  return (
    <div className="min-w-[82px] text-center">
      <div
        className={`rakam font-bold tracking-tight ${renk} ${buyuk ? "text-5xl" : "text-3xl"}
          leading-none`}
      >
        {deger}
      </div>
      <div className="mt-1.5 text-mikro font-semibold tracking-etiket text-solgun uppercase">
        {etiket}
      </div>
    </div>
  );
}

/** Canlı bağlantı göstergesi.
 *
 * Yanındaki metin bilerek duruyor: renk tek başına bilgi taşımaz. Nokta ve
 * halkası, arayüzdeki tek `rounded-full` — gerçekten daire olmalılar. */
export function Nokta({ hal, metin = true }: { hal: BaglantiHali; metin?: boolean }) {
  const h = {
    canli: { renk: "bg-ok", yazi: "text-ok", ad: "canlı" },
    baglaniyor: { renk: "bg-uyari", yazi: "text-uyari", ad: "bağlanıyor" },
    kopuk: { renk: "bg-hata", yazi: "text-hata", ad: "kopuk" },
  }[hal];
  return (
    <span className="inline-flex items-center gap-2 text-kucuk font-semibold">
      <span className="relative inline-flex h-2.5 w-2.5 shrink-0">
        {hal === "canli" && (
          <span className={`halka absolute inset-0 rounded-full ${h.renk}`} aria-hidden />
        )}
        <span
          className={`relative h-2.5 w-2.5 rounded-full ${h.renk} ${
            hal === "baglaniyor" ? "nabiz" : ""
          }`}
          aria-hidden
        />
      </span>
      {metin && <span className={h.yazi}>{h.ad}</span>}
    </span>
  );
}

export function Uyari({
  tur = "hata",
  cocuk,
}: {
  tur?: "hata" | "uyari" | "bilgi";
  cocuk: ReactNode;
}) {
  return (
    <div
      className={`${DURUM_STILI[tur]} rounded-sm border border-l-[3px] px-4 py-3
        text-kucuk font-semibold`}
    >
      {cocuk}
    </div>
  );
}

/** Durum şeridi: tint dolgu + 3px sol kural + ikon + metin.
 *
 * Okutma sonucu şeritleri (Sayım ve Telefon) ile bölüm uyarıları buradan
 * çıkar. Ikon zorunlu değil ama güçlü tavsiye: renk tek başına bilgi taşımaz. */
export function Durum({
  tur,
  Ikon,
  ana,
  alt,
  sag,
}: {
  tur: DurumTuru;
  Ikon?: typeof Ik.Onay;
  ana: ReactNode;
  alt?: ReactNode;
  sag?: ReactNode;
}) {
  return (
    <div
      className={`${DURUM_STILI[tur]} flex items-center gap-3 rounded-sm border
        border-l-[3px] px-4 py-3`}
    >
      {Ikon && <Ikon boy={20} />}
      <div className="min-w-0 flex-1">
        <div className="text-govde font-bold">{ana}</div>
        {alt && <div className="mt-0.5 text-kucuk font-medium">{alt}</div>}
      </div>
      {sag}
    </div>
  );
}

/** Metin girdisi.
 *
 * ~15 elle yazılmış kopyanın yerini alıyor. İki şeyi merkezîleştiriyor:
 *
 * 1. GÖRÜNÜRLÜK. Açık temada girdi dolgusu (zemin) beyaz kartın içinde
 *    1.10:1 — kutunun sınırını gösteren tek şey kenarlık. Bu yüzden ayraç
 *    rengi (cizgi) değil cizgi-kuvvetli kullanılıyor: 4.55:1, metin dışı
 *    3:1 eşiğini geçen tek değer.
 * 2. DOKUNMA HEDEFİ. Global kural artık input'u da kapsıyor (48px), ama
 *    py değerinin de tutarlı olması gerekiyor.
 *
 * Kontrolsüz (uncontrolled) kullanımı DESTEKLER: Sayım ve Telefon'daki barkod
 * alanları e.currentTarget.value okuyup alanı temizliyor. `deger` verilmezse
 * React kontrolü ele almaz. */
export function Girdi({
  deger,
  degisti,
  boyut = "orta",
  mono,
  ref,
  ...kalan
}: {
  deger?: string;
  degisti?: (v: string) => void;
  boyut?: "orta" | "okutma";
  mono?: boolean;
  ref?: Ref<HTMLInputElement>;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "size" | "ref">) {
  const olcek =
    boyut === "okutma"
      ? "border-2 border-vurgu px-5 py-5 text-2xl sm:text-3xl"
      : "border border-cizgi-kuvvetli px-4 py-3 text-govde";
  return (
    <input
      ref={ref}
      value={deger}
      onChange={degisti ? (e) => degisti(e.target.value) : undefined}
      className={`w-full rounded-sm bg-zemin text-yazi placeholder:text-solgun-hafif
        focus:border-vurgu ${olcek} ${mono ? "font-mono" : ""}`}
      {...kalan}
    />
  );
}

/** Alan etiketi + girdi sarmalayıcı. */
export function Alan({
  etiket,
  ipucu,
  cocuk,
}: {
  etiket: ReactNode;
  ipucu?: ReactNode;
  cocuk: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-mikro font-bold tracking-etiket text-solgun uppercase">
        {etiket}
      </span>
      {cocuk}
      {ipucu && <span className="mt-1.5 block text-mikro text-solgun">{ipucu}</span>}
    </label>
  );
}

/** Modal örtüsü.
 *
 * Yedi elle yazılmış kopyanın yerini alıyor. Perde `bg-black/70` DEĞİL:
 * açık bir uygulamanın üstünde %70 siyah her modal açılışında sert bir
 * karartma yapıyor ve arıza gibi hissettiriyor. Fotoğraf büyütmede koyu
 * perde korunuyor — fotoğrafın kendisi onu gerektiriyor.
 *
 * Escape ile kapanma ve perdeye tıklayınca kapanma burada tek yerde:
 * kopyaların bir kısmında vardı, bir kısmında yoktu. */
export function Ortu({
  baslik,
  cocuk,
  altlik,
  kapat,
  genislik = "orta",
  tur = "kutu",
}: {
  baslik?: ReactNode;
  cocuk: ReactNode;
  altlik?: ReactNode;
  kapat?: () => void;
  genislik?: "dar" | "orta" | "genis";
  tur?: "kutu" | "foto";
}) {
  useEffect(() => {
    if (!kapat) return;
    const f = (e: KeyboardEvent) => e.key === "Escape" && kapat();
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, [kapat]);

  const en = { dar: "max-w-md", orta: "max-w-2xl", genis: "max-w-5xl" }[genislik];
  const perde = tur === "foto" ? "bg-yazi/85" : "bg-yazi/45";

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center ${perde} p-4`}
      onClick={(e) => kapat && e.target === e.currentTarget && kapat()}
      role="dialog"
      aria-modal="true"
    >
      {tur === "foto" ? (
        <div className="flex flex-col items-center gap-4">{cocuk}</div>
      ) : (
        <div
          className={`flex max-h-full w-full ${en} flex-col overflow-hidden rounded-sm
            border border-cizgi bg-panel`}
        >
          {(baslik || kapat) && (
            <header className="flex items-center justify-between gap-3 border-b border-cizgi bg-panel2 px-5 py-3">
              <h2 className="text-mikro font-bold tracking-etiket text-solgun uppercase">
                {baslik}
              </h2>
              {kapat && (
                <button
                  type="button"
                  onClick={kapat}
                  aria-label="Kapat"
                  className="rounded-sm p-2 text-solgun hover:bg-cizgi hover:text-yazi"
                >
                  <Ik.Kapat boy={20} />
                </button>
              )}
            </header>
          )}
          <div className="min-h-0 flex-1 overflow-y-auto p-4">{cocuk}</div>
          {altlik && (
            <footer className="flex flex-wrap justify-end gap-3 border-t border-cizgi bg-panel2 p-4">
              {altlik}
            </footer>
          )}
        </div>
      )}
    </div>
  );
}

/** Sekme / hap seçim çubuğu. Rapor sekmeleri, adres seçici, tür seçimi. */
export function Sekmeler<T extends string>({
  secenekler,
  secili,
  sec,
}: {
  secenekler: { deger: T; ad: ReactNode; sayi?: number }[];
  secili: T;
  sec: (d: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2" role="tablist">
      {secenekler.map((s) => {
        const aktif = s.deger === secili;
        return (
          <button
            key={s.deger}
            type="button"
            role="tab"
            aria-selected={aktif}
            onClick={() => sec(s.deger)}
            className={`inline-flex items-center gap-2 rounded-sm border px-4 text-kucuk
              font-semibold transition-colors duration-150 ${
                aktif
                  ? "border-vurgu bg-vurgu text-white"
                  : "border-cizgi-kuvvetli bg-panel text-yazi hover:bg-panel2"
              }`}
          >
            {s.ad}
            {s.sayi !== undefined && (
              <span className={`rakam ${aktif ? "text-white" : "text-solgun"}`}>{s.sayi}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Veri tablosu.
 *
 * Zebra `bg-panel2/40` DEĞİL düz `bg-panel2`: %40 opaklıkta beyaz üzerinde
 * 1.02:1 kalıyor, yani zebra tamamen kayboluyor ve uzun rapor tabloları
 * okunmaz satır yığınına dönüyor.
 *
 * monoSutunlar: barkod ve seri numarası taşıyan sütunlar. Sabit genişlik
 * şart — 0/O ve 1/l ayrımı kötü depo ışığında karşılaştırmayı mümkün kılan
 * tek şey (CLAUDE.md §10.1). */
export function Tablo({
  basliklar,
  satirlar,
  monoSutunlar = [],
  bos = "kayıt yok",
}: {
  basliklar: ReactNode[];
  satirlar: ReactNode[][];
  monoSutunlar?: number[];
  bos?: ReactNode;
}) {
  if (satirlar.length === 0) return <Bos cocuk={bos} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-kucuk">
        <thead>
          <tr className="border-b border-cizgi-kuvvetli">
            {basliklar.map((b, i) => (
              <th
                key={i}
                className="px-3 py-2 text-left text-mikro font-bold tracking-etiket
                  text-solgun uppercase whitespace-nowrap"
              >
                {b}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {satirlar.map((s, i) => (
            <tr key={i} className={`border-b border-cizgi ${i % 2 ? "bg-panel2" : ""}`}>
              {s.map((h, j) => (
                <td
                  key={j}
                  className={`px-3 py-2 align-top ${
                    monoSutunlar.includes(j) ? "rakam font-mono whitespace-nowrap" : ""
                  }`}
                >
                  {h}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Fotoğraf küçük resmi. */
export function Foto({ url, boy = 80, buyut }: { url: string; boy?: number; buyut?: () => void }) {
  const img = (
    <img
      src={url}
      alt="ürün fotoğrafı"
      style={{ width: boy, height: boy }}
      className="rounded-sm border border-cizgi-kuvvetli object-cover"
    />
  );
  if (!buyut) return img;
  return (
    <button
      type="button"
      onClick={buyut}
      aria-label="Fotoğrafı büyüt"
      className="rounded-sm p-0 hover:brightness-95"
      style={{ minHeight: boy }}
    >
      {img}
    </button>
  );
}

/** Fotoğraf büyütme — koyu perde fotoğrafın kendisi için korunuyor. */
export function FotoBuyut({
  url,
  kapat,
  altlik,
}: {
  url: string;
  kapat: () => void;
  altlik?: ReactNode;
}) {
  return (
    <Ortu
      tur="foto"
      kapat={kapat}
      cocuk={
        <>
          <img
            src={url}
            alt="ürün fotoğrafı"
            className="max-h-[80vh] max-w-full rounded-sm border border-cizgi"
          />
          <div className="flex flex-wrap justify-center gap-3">
            <Dugme cocuk="Kapat" tikla={kapat} />
            {altlik}
          </div>
        </>
      }
    />
  );
}

/** Boş durum — italik ve solgun. Veri değil, anlatı; tipografi de öyle desin. */
export function Bos({ cocuk }: { cocuk: ReactNode }) {
  return <p className="py-10 text-center text-xl text-solgun italic">{cocuk}</p>;
}

export function Kod({ cocuk }: { cocuk: ReactNode }) {
  return <span className="font-mono text-kucuk break-all">{cocuk}</span>;
}
