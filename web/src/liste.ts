/** Eşleştirme listelerinin ortak mantığı.
 *
 * Sahadaki sorun (bildirim 2026-08-23): elle eşleştirme listesi Excel'dekinin
 * çok altında ürün gösteriyordu. Sebep sunucu değil arayüzdü — Telefon 40,
 * Kuyruk 50, Eşleme ilk 100 satırı çiziyordu ve **hiçbirinde sayfalama,
 * sonsuz kaydırma ya da "daha fazla" yoktu.** `toplam` ekranda yazıyor ama ilk
 * sayfadan ötesine erişmenin yolu yoktu; kullanıcı listede olmayan ürünü elle
 * tahmin edip aramak zorunda kalıyordu.
 *
 * Çözüm iki parçalı:
 *
 * 1. **Veri eksiksiz gelir.** `api.ara` limitsiz çağrılır (sunucuda limit=0).
 *    ~870 satır ≈ 130 KB; depo LAN'ında sorun değil ve arama artık sunucuya
 *    hiç gitmediği için tuş başına anında süzülüyor.
 * 2. **Çizim kademeli.** 870 satırı aynı anda DOM'a basmak telefonda ağır.
 *    `kademeli()` görünür pencereyi tutar, kullanıcı listenin sonuna gelince
 *    büyür. Kesme DEĞİL: tüm satırlara erişilebilir, yalnızca çizim ertelenir.
 *
 * Yeni bağımlılık yok — sanallaştırma kütüphanesi eklenmedi (çevrimdışı
 * kurulum ve küçük bundle korunuyor).
 */
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";

/** Türkçe duyarlı normalizasyon.
 *
 * `toLowerCase()` YETMEZ: "İSTASYON".toLowerCase() → "i̇stasyon" (birleşik
 * nokta) ve "I" → "i" olur, oysa Türkçede "I" → "ı". Sunucu tarafındaki SQL
 * LIKE karşılaştırması da aksanlara duyarsız değil; bu yüzden istemcide arama
 * kasten daha GENİŞ tutuldu — aday gizlemektense fazla göstermek yeğdir. */
function kucult(s: string): string {
  return (s || "").toLocaleLowerCase("tr");
}

/** Çok terimli süzme: her kelime ayrı ayrı geçmeli (sıra önemsiz).
 *
 * "dell ssd" hem "DELL 1.92TB SSD" hem "SSD Dell Gen14" satırını bulur.
 * Sunucudaki tek parça LIKE bunu yapamıyordu. */
export function suz<T extends Record<string, unknown>>(
  satirlar: T[],
  q: string,
  alanlar: (keyof T)[],
): T[] {
  const terimler = kucult(q).split(/\s+/).filter(Boolean);
  if (terimler.length === 0) return satirlar;
  return satirlar.filter((r) => {
    const metin = kucult(alanlar.map((a) => String(r[a] ?? "")).join(" "));
    return terimler.every((t) => metin.includes(t));
  });
}

/** Kademeli çizim penceresi.
 *
 * `anahtar` değişince (arama metni, filtre) pencere başa döner — yoksa
 * kullanıcı yeni araması için 400 satır aşağıda başlıyordu.
 *
 * Döndürülen `bitis` ref'i listenin sonuna konur; kaydırma dibe yaklaşınca
 * pencere `adim` kadar büyür. Kaydırma olayı hiç gelmezse (dokunmatik jest,
 * klavye) `daha()` düğmesi hâlâ elle çalışır. */
export function kademeli<T>(hepsi: T[], anahtar: string, adim = 60) {
  return useKademeli(hepsi, anahtar, adim);
}

/** Elemanın kendi içinde kaydırılan en yakın atası; yoksa null (ekran). */
function kaydirilanAta(el: HTMLElement): HTMLElement | null {
  let p = el.parentElement;
  while (p) {
    const o = getComputedStyle(p).overflowY;
    if ((o === "auto" || o === "scroll") && p.scrollHeight > p.clientHeight) return p;
    p = p.parentElement;
  }
  return null;
}

function useKademeli<T>(hepsi: T[], anahtar: string, adim: number) {
  const [sayi, setSayi] = useState(adim);
  /* Gözcü herhangi bir eleman olabilir: <li>, <div>, <tr>. */
  const bitis = useRef<HTMLElement | null>(null);

  useEffect(() => setSayi(adim), [anahtar, adim]);

  const daha = useCallback(
    () => setSayi((n) => Math.min(n + adim, hepsi.length)),
    [adim, hepsi.length],
  );

  useEffect(() => {
    const el = bitis.current;
    if (!el || sayi >= hepsi.length) return;

    /* IntersectionObserver DEĞİL, doğrudan kaydırma olayı.
       IO iki kez denendi ve tetiklenmedi: root=null (ekran) ile gözcü hiç
       görünür alana girmiyordu — listeler `max-h-[60vh] overflow-y-auto` ile
       kendi içinde kayıyor ve kabın alt kenarı ekranın altına taşıyor
       (ölçüldü: gözcü top=707, ekran 600). root=kap ile de geri çağrı hiç
       çalışmadı. Kaydırma olayı bu kurulumda basit ve öngörülebilir. */
    const kap = kaydirilanAta(el);
    const hedef: HTMLElement | Window = kap ?? window;
    const kontrol = () => {
      const k = kap ?? document.documentElement;
      // 400px kala büyüt: kullanıcı dibi görmeden liste uzasın
      if (k.scrollTop + k.clientHeight >= k.scrollHeight - 400) daha();
    };
    hedef.addEventListener("scroll", kontrol, { passive: true });
    kontrol(); // liste kısa ya da zaten dipteyse hemen büyüsün
    return () => hedef.removeEventListener("scroll", kontrol);
  }, [sayi, hepsi.length, daha]);

  return {
    gorunur: hepsi.slice(0, sayi),
    kalan: Math.max(0, hepsi.length - sayi),
    bitis: bitis as React.Ref<never>,
    daha,
  };
}
