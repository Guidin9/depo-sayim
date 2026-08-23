/** Canlı güncelleme aboneliği.
 *
 * Sunucu "bir şey değişti" der, biz kendi verimizi tazeleriz. Böylece laptopta
 * okutulan barkod telefonda, telefonda yapılan seçim laptopta anında görünür.
 *
 * Kendi yaptığımız değişikliğin haberi geri geldiğinde yoksayıyoruz: o isteğin
 * yanıtı zaten güncel durumu taşıyordu, ikinci kez çekmeye gerek yok.
 *
 * Tek başına EventSource sahada yetmiyor (CLAUDE.md 9): telefon cebe girince
 * mobil tarayıcı bağlantıyı askıya alıyor, geri dönünce aradaki olaylar
 * kayboluyor. Bu yüzden üç katman var:
 *   1. EventSource — normal durumda anında haber,
 *   2. görünürlük — ekran geri açılınca bir kez tazele,
 *   3. yedek yoklama — bağlantı yokken 3 sn'de bir, varken 15 sn'de bir emniyet
 *      çekimi. Yerel ağda maliyeti yok, "ekran donmuş" şikâyetini bitirir.
 */

/** Bu tarayıcı sekmesinin kimliği — her istekte X-Istemci başlığıyla gider. */
export const ISTEMCI =
  Math.random().toString(36).slice(2, 8) + "-" + Date.now().toString(36).slice(-4);

export type BaglantiHali = "baglaniyor" | "canli" | "kopuk";

const KOPUK_YOKLAMA = 3000;   // bağlantı yokken sık yokla
const CANLI_YOKLAMA = 15000;  // bağlantı varken emniyet çekimi

export function olaylariDinle(
  tazele: () => void,
  bildir?: (hal: BaglantiHali) => void,
): () => void {
  let kaynak: EventSource | null = null;
  let hal: BaglantiHali = "baglaniyor";
  let sonCekim = Date.now();
  let kapandi = false;
  let zamanlayici: number | undefined;

  function halAyarla(yeni: BaglantiHali) {
    if (hal === yeni) return;
    hal = yeni;
    bildir?.(yeni);
  }

  function cek() {
    sonCekim = Date.now();
    tazele();
  }

  function kur() {
    if (kapandi || kaynak) return;
    try {
      kaynak = new EventSource("/api/olaylar");
    } catch {
      halAyarla("kopuk");
      return;
    }
    kaynak.onopen = () => {
      // Yeniden bağlandıysak aradaki olayları kaçırmışızdır — bir kez tazele.
      const yenidenBaglandi = hal === "kopuk";
      halAyarla("canli");
      if (yenidenBaglandi) cek();
    };
    kaynak.onerror = () => {
      halAyarla("kopuk");
      // Tarayıcı kendi yeniden bağlanmasını yapar; tamamen kapandıysa biz kurarız.
      if (kaynak && kaynak.readyState === EventSource.CLOSED) {
        kaynak.close();
        kaynak = null;
      }
    };
    kaynak.addEventListener("guncel", ((e: MessageEvent) => {
      halAyarla("canli");
      try {
        const veri = JSON.parse(e.data) as { surum: number; istemci: string | null };
        if (veri.istemci === ISTEMCI) return;
      } catch {
        /* gövde bozuksa yine de tazele */
      }
      cek();
    }) as EventListener);
  }

  function yenidenKur() {
    // Mobil tarayıcı arka planda bağlantıyı kapatmış olabilir.
    if (kaynak && kaynak.readyState === EventSource.CLOSED) {
      kaynak.close();
      kaynak = null;
      halAyarla("kopuk");
    }
    if (!kaynak) kur();
  }

  function gorunurluk() {
    if (document.visibilityState !== "visible") return;
    yenidenKur();
    cek();   // arkadayken kaçan olaylar için tek seferlik tazeleme
  }

  zamanlayici = window.setInterval(() => {
    if (kapandi || document.visibilityState !== "visible") return;
    yenidenKur();
    const gecen = Date.now() - sonCekim;
    if (gecen >= (hal === "canli" ? CANLI_YOKLAMA : KOPUK_YOKLAMA)) cek();
  }, KOPUK_YOKLAMA);

  document.addEventListener("visibilitychange", gorunurluk);
  kur();
  bildir?.(hal);

  return () => {
    kapandi = true;
    document.removeEventListener("visibilitychange", gorunurluk);
    if (zamanlayici) window.clearInterval(zamanlayici);
    kaynak?.close();
    kaynak = null;
  };
}
