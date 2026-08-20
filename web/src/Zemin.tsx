/** Izgara zemin — Design.md'nin 1. katmanı.
 *
 * 48px hücreli SVG deseni, imleçle hafifçe kayıyor. Tek işi arayüze düz panel
 * yığını yerine derinlik vermek; hiçbir bilgi taşımıyor, o yüzden opaklığı
 * düşük ve pointer-events yok.
 *
 * Parallax iki durumda hiç kurulmuyor: dokunmatik ekranda (telefonda imleç
 * yok, boşuna rAF döngüsü dönmesin) ve prefers-reduced-motion açıkken. Bu
 * hâllerde ızgara statik çizilir.
 */
import { useEffect, useRef } from "react";

/* Design.md'nin sayıları: offset ekran merkezine göre * 16, lerp katsayısı
   0.06. Normalleştirilmiş imleç konumu -0.5..0.5 olduğu için sapma ±8px —
   fark edilir ama dikkat dağıtmaz. */
const SAPMA = 16;
const YUMUSATMA = 0.06;

export default function Zemin() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const durgun =
      window.matchMedia("(pointer: coarse)").matches ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (durgun) return;

    let hedefX = 0;
    let hedefY = 0;
    let x = 0;
    let y = 0;
    let kare = 0;

    /* Döngü hedefe varınca duruyor ve imleç kıpırdayınca yeniden başlıyor.
       Sürekli dönen bir rAF, sayım ekranı bütün gün açık duran depo
       laptopunda boşuna pil ve GPU yakardı. */
    const dongu = () => {
      x += (hedefX - x) * YUMUSATMA;
      y += (hedefY - y) * YUMUSATMA;
      if (ref.current) ref.current.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      if (Math.abs(hedefX - x) < 0.05 && Math.abs(hedefY - y) < 0.05) {
        kare = 0;
        return;
      }
      kare = requestAnimationFrame(dongu);
    };

    const imlec = (e: MouseEvent) => {
      hedefX = (e.clientX / window.innerWidth - 0.5) * SAPMA;
      hedefY = (e.clientY / window.innerHeight - 0.5) * SAPMA;
      if (!kare) kare = requestAnimationFrame(dongu);
    };

    window.addEventListener("mousemove", imlec, { passive: true });
    return () => {
      window.removeEventListener("mousemove", imlec);
      if (kare) cancelAnimationFrame(kare);
    };
  }, []);

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      {/* Kayma sırasında kenar açılmasın diye desen her yönde 24px taşıyor. */}
      <div ref={ref} className="absolute -inset-6">
        {/* Çizgi rengi bilerek --color-cizgi değil: o renk (#26303e) panel
            kenarları için, zeminden yalnızca bir tık açık. Izgara zeminin
            üstünde durmalı, bu yüzden Design.md'nin açık arduvaz tonu
            kullanılıyor — düşük opaklıkta zar zor seçilen bir doku bırakıyor. */}
        <svg className="h-full w-full opacity-[0.08]" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="izgara" width="48" height="48" patternUnits="userSpaceOnUse">
              <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#64748b" strokeWidth="0.6" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#izgara)" />
        </svg>
      </div>

      {/* Zeminin üst kenarına doğru hafif bir aydınlanma: Design.md'nin katmanlı
          atmosferini ızgara tek başına vermiyor. */}
      <div
        className="absolute inset-x-0 top-0 h-[45vh]"
        style={{
          background:
            "radial-gradient(120% 100% at 50% 0%, rgba(76,111,255,0.10) 0%, transparent 70%)",
        }}
      />
    </div>
  );
}
