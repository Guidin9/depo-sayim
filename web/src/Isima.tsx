/** Okutma ışıması — Design.md'nin imleç spot ışığının işlevsel karşılığı.
 *
 * Orijinalde imleç bir videoyu ortaya çıkarıyor. Bizde video yok, telefonda
 * imleç de yok; onun yerine barkod okutulduğunda ekranın üstünden sonucun
 * rengiyle kısa bir ışık geçiyor. Sesli geri bildirimin görsel eşi: telefon
 * rafta dururken ya da kulaklık takılıyken bile sonuç uzaktan fark ediliyor.
 *
 * Kullanım: <Isima key={sayac} renk="ok" /> — key değişince bileşen yeniden
 * mount olur ve animasyon baştan çalar.
 *
 * prefers-reduced-motion altında stil.css bunu display:none yapıyor.
 */
export type IsimaRenk = "ok" | "uyari" | "hata" | "bilgi";

const RENK: Record<IsimaRenk, string> = {
  ok: "var(--color-ok)",
  uyari: "var(--color-uyari)",
  hata: "var(--color-hata)",
  bilgi: "var(--color-bilgi)",
};

export default function Isima({ renk }: { renk: IsimaRenk }) {
  return (
    <div
      aria-hidden
      className="isima pointer-events-none fixed inset-x-0 top-0 z-20 h-64"
      style={{
        mixBlendMode: "screen",
        background: `radial-gradient(140% 100% at 50% 0%,
          color-mix(in srgb, ${RENK[renk]} 42%, transparent) 0%, transparent 72%)`,
      }}
    />
  );
}
