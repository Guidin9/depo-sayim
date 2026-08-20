/** Telefon monitörü — /telefon adresinde açılır.
 *
 * Bu ekran sayım yapmaz, sayımı GÖSTERİR. Okuyucu laptopta; telefon rafın
 * başında elde durur ve üç işe yarar:
 *   1. laptopta ne okutulduğunu anlık gösterir (sayaçlar + son okutmalar),
 *   2. kuyruğa düşen tanınmayan ürünün fotoğrafını çektirir,
 *   3. o ürünü ürün hâlâ eldeyken çözdürür (aday / arama).
 *
 * Bilerek yok: Excel yükleme, ambar seçimi, rapor, oturumu bitirme. Depoda
 * telefona yanlış dokunup sayımı bozmak, kolaylıktan daha pahalı.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Aday, type AramaSonucu, type Durum, type KuyrukSatiri } from "../api";
import { Nokta } from "../bilesenler";
import { kucult } from "../foto";
import * as Ik from "../ikonlar";
import Isima, { type IsimaRenk } from "../Isima";
import type { BaglantiHali } from "../olaylar";

type Props = {
  durum: Durum | null;
  canli: BaglantiHali;
  tik: number;                 // canlı güncelleme sayacı — arttıkça kuyruğu tazeler
  tazele: () => void;          // App'in durumu yeniden çekmesi
};

/** Akış satırını renkli şeride çevirir (laptoptaki okutmanın özeti). */
function seritSinifi(tip: string) {
  if (tip === "fazla" || tip === "bilinmiyor") return "border-hata/50 bg-hata/12 text-hata";
  if (tip === "kod") return "border-bilgi/50 bg-bilgi/12 text-bilgi";
  return "border-ok/50 bg-ok/12 text-ok";
}

/** Aynı sonucun ambiyans ışıması rengi — şeritle ayrışmasın. */
function seritRengi(tip: string): IsimaRenk {
  if (tip === "fazla" || tip === "bilinmiyor") return "hata";
  if (tip === "kod") return "bilgi";
  return "ok";
}

export default function Telefon({ durum, canli, tik, tazele }: Props) {
  const [kuyruk, setKuyruk] = useState<KuyrukSatiri[]>([]);
  const [adaylar, setAdaylar] = useState<Aday[]>([]);
  const [acik, setAcik] = useState<number | null>(null);   // açılmış kuyruk kartı
  const [q, setQ] = useState("");
  const [sonuc, setSonuc] = useState<AramaSonucu[]>([]);
  const [aramaAcik, setAramaAcik] = useState(false);
  const [fazlaOnay, setFazlaOnay] = useState<number | null>(null);
  const [yuklenen, setYuklenen] = useState<number | null>(null);
  const [buyutulen, setBuyutulen] = useState<number | null>(null);
  const [notAcik, setNotAcik] = useState<number | null>(null);
  const [notMetin, setNotMetin] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  /* Laptopta yeni bir okutma göründüğünde ekranın üstünden sonucun rengiyle
     ışık geçiyor. Telefon rafın başında elde ya da cepte duruyor; bakışını
     çeviren şey bu. İlk açılışta çakmasın diye ilk ts sessizce kaydediliyor. */
  const [isik, setIsik] = useState(0);
  const [isikRenk, setIsikRenk] = useState<IsimaRenk>("ok");
  const sonTsRef = useRef<string | null>(null);
  const fotoRef = useRef<HTMLInputElement>(null);
  const fotoHedefRef = useRef<number | null>(null);
  const gorulenRef = useRef<number>(0);

  const oturum = durum?.oturum ?? null;

  useEffect(() => {
    const a = durum?.akis?.[0];
    if (!a || a.ts === sonTsRef.current) return;
    const ilk = sonTsRef.current === null;
    sonTsRef.current = a.ts;
    if (ilk) return;
    setIsikRenk(seritRengi(a.tip));
    setIsik((n) => n + 1);
  }, [durum]);

  const kuyrukTazele = useCallback(async () => {
    if (!oturum) {
      setKuyruk([]);
      return;
    }
    try {
      setKuyruk(await api.kuyruk(oturum));
      setAdaylar(await api.adaylar(oturum, 6));
      setHata(null);
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }, [oturum]);

  useEffect(() => {
    void kuyrukTazele();
  }, [kuyrukTazele, tik]);

  /* Yeni kuyruk kaydı düştüğünde kart kendiliğinden açılsın ve telefon titresin:
     kullanıcı ekrana bakmıyor olabilir ama ürün hâlâ elinde. */
  useEffect(() => {
    const bekleyen = kuyruk.filter((k) => !k.cozuldu && !k.beklet);
    if (!bekleyen.length) return;
    const sonId = bekleyen[bekleyen.length - 1].id;
    if (sonId > gorulenRef.current) {
      if (gorulenRef.current) navigator.vibrate?.([120, 60, 120]);
      gorulenRef.current = sonId;
      setAcik(sonId);
      setAramaAcik(false);
      setQ("");
      setSonuc([]);
      // Ekran aşağı kaydırılmış olabilir; kart kendini göstersin.
      requestAnimationFrame(() =>
        document
          .getElementById(`kuyruk-${sonId}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" }),
      );
    }
  }, [kuyruk]);

  useEffect(() => {
    if (q.trim().length < 2 || !oturum) {
      setSonuc([]);
      return;
    }
    let iptal = false;
    const zaman = setTimeout(async () => {
      try {
        const r = await api.ara(oturum, q.trim());
        if (!iptal) setSonuc(r);
      } catch {
        /* arama başarısızsa liste boş kalsın, sayım durmasın */
      }
    }, 200);
    return () => {
      iptal = true;
      clearTimeout(zaman);
    };
  }, [q, oturum]);

  async function coz(kuyrukId: number, beklenenId: number) {
    try {
      await api.kuyrukCoz(kuyrukId, beklenenId);
      navigator.vibrate?.(60);
      setAcik(null);
      setQ("");
      setSonuc([]);
      setAramaAcik(false);
      await kuyrukTazele();
      tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  async function fazlaYaz(kuyrukId: number) {
    try {
      await api.kuyrukFazla(kuyrukId);
      setFazlaOnay(null);
      setAcik(null);
      await kuyrukTazele();
      tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  async function bekletAyarla(kuyrukId: number, beklet: boolean) {
    try {
      await api.kuyrukBeklet(kuyrukId, beklet);
      if (beklet) setAcik(null);
      navigator.vibrate?.(40);
      await kuyrukTazele();
      tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  async function notKaydet(kuyrukId: number) {
    try {
      await api.kuyrukNot(kuyrukId, notMetin.trim());
      setNotAcik(null);
      navigator.vibrate?.(40);
      await kuyrukTazele();
      tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  function fotoIste(kuyrukId: number) {
    fotoHedefRef.current = kuyrukId;
    fotoRef.current?.click();
  }

  async function fotoYukle(dosya: File) {
    const kid = fotoHedefRef.current;
    if (!kid) return;
    setYuklenen(kid);
    try {
      await api.fotoYukle(kid, await kucult(dosya));
      navigator.vibrate?.(60);
      await kuyrukTazele();
      tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    } finally {
      setYuklenen(null);
    }
  }

  const bekleyen = kuyruk.filter((k) => !k.cozuldu);
  /* Rafın başında ilgilenilecekler ile "fotoğrafını çektim, PC'de çözerim"
     denilenler ayrı: ikincisi ekranı ve raf kapısını meşgul etmemeli. */
  const aktifler = [...bekleyen.filter((k) => !k.beklet)].reverse();
  const parktakiler = [...bekleyen.filter((k) => k.beklet)].reverse();
  const son = durum?.akis?.[0];

  /** Kısa hatırlatma notu — hem açık kartta hem ertelenenler listesinde.
   *
   * Klavye kendiliğinden açılmıyor: düğmeye basınca giriş çıkıyor. Depoda
   * ekran klavyesinin yarım ekranı kaplaması, izlemek için bakan kullanıcıyı
   * boğuyor (aynı sebeple barkod alanı da odaklanmıyor).
   */
  function notAlani(k: KuyrukSatiri) {
    if (notAcik === k.id)
      return (
        <div className="mt-2 flex gap-2">
          <input
            autoFocus
            value={notMetin}
            onChange={(e) => setNotMetin(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void notKaydet(k.id);
            }}
            placeholder="siyah kutu, üst raf, HP yazıyor…"
            className="min-w-0 flex-1 rounded-xl border border-cizgi bg-zemin px-3 py-3
              text-[16px] text-yazi placeholder:text-solgun/60 focus:border-vurgu
              focus:outline-none"
          />
          <button
            type="button"
            onClick={() => void notKaydet(k.id)}
            className="shrink-0 rounded-full bg-vurgu px-4 py-3 text-[15px] font-bold text-white"
          >
            Kaydet
          </button>
          <button
            type="button"
            onClick={() => setNotAcik(null)}
            className="cam-hafif shrink-0 rounded-full px-3 py-3 text-[15px] text-solgun"
            aria-label="vazgeç"
          >
            <Ik.Kapat boy={16} />
          </button>
        </div>
      );
    return (
      <button
        type="button"
        onClick={() => {
          setNotAcik(k.id);
          setNotMetin(k.not_);
        }}
        className="cam-hafif mt-2 w-full rounded-full px-4 py-2 text-left text-[13px] text-solgun"
      >
        <span className="inline-flex items-center gap-2">
          <Ik.Not boy={15} /> {k.not_ ? "Notu düzenle" : "Not ekle"}
        </span>
      </button>
    );
  }

  /** Bir kuyruk kartı. vurgulu = en yeni kayıt (rafın başında ilgilenilecek).
   *
   * sira, Design.md'nin 60ms'lik kademeli girişini besliyor: kartlar tek tek
   * yerine dalga hâlinde açılıyor. Sekizden sonrası aynı gecikmede kalıyor,
   * yoksa uzun kuyrukta son kart saniyelerce beklerdi. */
  function kartCiz(k: KuyrukSatiri, vurgulu: boolean, sira: number) {
    const acikMi = acik === k.id;
    return (
      <li
        key={k.id}
        id={`kuyruk-${k.id}`}
        className={`kademe kademe-${Math.min(sira + 1, 8)} rounded-2xl border p-3 ${
          vurgulu ? "border-uyari/60 bg-uyari/5" : "border-cizgi bg-panel2"
        }`}
      >
        <button
          type="button"
          onClick={() => setAcik(acikMi ? null : k.id)}
          className="flex w-full items-start gap-3 text-left"
        >
          <span className="min-w-0 flex-1">
            <span className="block font-mono text-[15px] font-bold break-all">
              {k.barkodlar.join(" + ")}
            </span>
            <span className="mt-1 block text-[12px] text-solgun">
              {k.raf && <span className="text-uyari">raf {k.raf} · </span>}
              {k.ts.slice(11, 16)}
              {k.fotolar.length > 0 && ` · ${k.fotolar.length} fotoğraf`}
              {k.not_ && ` · ${k.not_}`}
            </span>
          </span>
          <span className="shrink-0 pt-0.5 text-solgun">
            <Ik.Cevron acik={acikMi} boy={18} />
          </span>
        </button>

        {/* İki ana eylem: fotoğrafla ve bırak, ya da burada çöz. */}
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => fotoIste(k.id)}
            disabled={yuklenen === k.id}
            className="flex-1 rounded-full bg-vurgu px-3 py-3 text-[16px] font-bold text-white
              disabled:opacity-50"
          >
            {yuklenen === k.id ? (
              "yükleniyor…"
            ) : (
              <span className="inline-flex items-center justify-center gap-2">
                <Ik.Kamera boy={20} /> Foto çek
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => void bekletAyarla(k.id, true)}
            className={`flex-1 rounded-full border px-3 py-3 text-[16px] font-bold ${
              k.fotolar.length > 0
                ? "border-ok/60 bg-ok/15 text-ok"
                : "border-cizgi bg-panel text-yazi"
            }`}
          >
            <span className="inline-flex items-center justify-center gap-2">
              {k.fotolar.length > 0 ? <Ik.Onay boy={20} /> : <Ik.Duraklat boy={20} />} Sonra çöz
            </span>
          </button>
        </div>

        {k.fotolar.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {k.fotolar.map((f) => (
              <img
                key={f}
                src={api.fotoUrl(f)}
                alt="kuyruk fotoğrafı"
                onClick={() => setBuyutulen(f)}
                className="h-20 w-20 rounded-xl border border-cizgi object-cover"
              />
            ))}
          </div>
        )}

        {notAlani(k)}

        {!acikMi && (
          <button
            type="button"
            onClick={() => setAcik(k.id)}
            className="cam-hafif ease-kolay mt-2 w-full rounded-full px-4 py-2 text-[14px]
              font-semibold text-solgun transition duration-200"
          >
            <span className="inline-flex items-center justify-center gap-2">
              burada çözmek istersen <Ik.OkSag boy={16} />
            </span>
          </button>
        )}

        {acikMi && (
          <div className="mt-3 border-t border-cizgi pt-3">
            <p className="mb-2 text-[12px] font-semibold tracking-wider text-solgun uppercase">
              Bu hangi malzeme?
            </p>
            <ul className="flex flex-col gap-2">
              {adaylar.map((a) => (
                <li key={a.kod}>
                  <button
                    type="button"
                    onClick={() => void coz(k.id, a.id)}
                    className="flex w-full items-center gap-3 rounded-xl border border-cizgi
                      bg-panel px-3 py-3 text-left"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block font-mono text-[14px] font-bold text-vurgu">
                        {a.kod}
                      </span>
                      <span className="block truncate text-[12px] text-solgun">{a.aciklama}</span>
                    </span>
                    <span className="shrink-0 text-right text-[11px] text-solgun">
                      {a.ayni_raf > 0 && (
                        <span className="flex items-center justify-end gap-1 text-uyari">
                          <Ik.Raf boy={11} /> bu rafta
                        </span>
                      )}
                      <span className="block">{a.acik_satir} açık</span>
                    </span>
                  </button>
                </li>
              ))}
              {adaylar.length === 0 && (
                <li className="text-[13px] text-solgun">Öneri yok — aramayı kullan.</li>
              )}
            </ul>

            <button
              type="button"
              onClick={() => setAramaAcik((a) => !a)}
              className="cam-hafif mt-3 w-full rounded-full px-4 py-3 text-[15px] font-semibold"
            >
              <span className="inline-flex items-center justify-center gap-2">
                {aramaAcik ? (
                  "Aramayı kapat"
                ) : (
                  <>
                    <Ik.Ara boy={17} /> Kod / açıklama ara
                  </>
                )}
              </span>
            </button>

            {aramaAcik && (
              <>
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  autoComplete="off"
                  placeholder="kod veya açıklama…"
                  className="mt-2 w-full rounded-xl border border-cizgi bg-zemin px-4 py-3
                    text-[16px] text-yazi placeholder:text-solgun/60 focus:border-vurgu
                    focus:outline-none"
                />
                <ul className="mt-2 flex max-h-72 flex-col gap-2 overflow-y-auto">
                  {sonuc.map((b) => (
                    <li key={b.id}>
                      <button
                        type="button"
                        onClick={() => void coz(k.id, b.id)}
                        className="w-full rounded-xl border border-cizgi bg-panel px-3 py-3
                          text-left"
                      >
                        <span className="block font-mono text-[14px] font-bold text-vurgu">
                          {b.kod}
                        </span>
                        <span className="block truncate text-[12px] text-solgun">
                          {b.aciklama}
                        </span>
                        <span className="mt-1 block text-[11px] text-solgun">
                          {b.seri && <span className="font-mono">{b.seri} </span>}
                          {b.kirli ? (
                            <span className="inline-flex items-center gap-1 text-uyari">
                              <Ik.Uyari boy={11} /> uydurma kayıt
                            </span>
                          ) : null}
                          {b.sayildi ? <span className="text-hata"> · zaten sayıldı</span> : null}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}

            <button
              type="button"
              onClick={() => (fazlaOnay === k.id ? void fazlaYaz(k.id) : setFazlaOnay(k.id))}
              className={`mt-3 w-full rounded-full border px-4 py-3 text-[15px] font-semibold ${
                fazlaOnay === k.id
                  ? "border-hata bg-hata/20 text-hata"
                  : "border-hata/40 bg-hata/10 text-hata"
              }`}
            >
              {fazlaOnay === k.id
                ? "Emin misin? Fazla yazmak için tekrar dokun"
                : "Tiger'da karşılığı yok — fazla yaz"}
            </button>
          </div>
        )}
      </li>
    );
  }

  const baglantiSeridi = <Nokta hal={canli} />;

  /* ------------------------------------------------------- oturum yokken */
  if (!durum) {
    /* Design.md'nin hero katmanının doğrudan karşılığı: ızgara zeminin üstünde
       tek bir büyük serif söz. Burada gösterilecek veri yok, karakter var. */
    return (
      <div className="flex min-h-full flex-col items-center justify-center gap-6 p-8 text-center">
        <span className="cam rounded-full px-4 py-2">{baglantiSeridi}</span>
        <img src="/logo.png" alt="" width={72} height={72} className="object-contain" />
        <h1 className="font-serif text-6xl leading-[0.9] tracking-tight sm:text-7xl">
          Depo
          <br />
          Sayım
        </h1>
        <p className="max-w-xs font-serif text-xl text-solgun italic">Sayım başlamadı.</p>
        <p className="max-w-xs text-[15px] text-solgun">
          Laptopta sayım açılınca burası kendiliğinden dolar. Bu ekranı açık bırakabilirsin.
        </p>
        <a href="/" className="mt-6 text-[13px] text-solgun underline">
          tam sürüme geç
        </a>
      </div>
    );
  }

  /* ------------------------------------------------------- monitör */
  return (
    <div className="flex min-h-full flex-col gap-3 p-3 pb-10">
      <Isima key={isik} renk={isikRenk} />

      <input
        ref={fotoRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const d = e.currentTarget.files?.[0];
          e.currentTarget.value = "";
          if (d) void fotoYukle(d);
        }}
      />

      {/* Yapışkan: sayfa uzun, aktif raf ile bağlantı hâli kaydırırken de
          görünmeli — telefonun asıl işi zaten bunları göstermek. */}
      <header className="cam cam-yogun sticky top-0 z-30 flex items-center gap-3 rounded-2xl px-4 py-3">
        <img src="/logo.png" alt="" width={26} height={26} className="shrink-0 object-contain" />
        <div className="min-w-0">
          <div className="text-[11px] font-semibold tracking-wider text-solgun uppercase">
            Ambar {durum.ambar} · oturum #{durum.oturum}
          </div>
          <div className="truncate font-serif text-2xl leading-tight">
            {durum.aktif_raf ? (
              <span className="inline-flex items-center gap-2 text-uyari">
                <Ik.Raf boy={18} />
                Raf {durum.aktif_raf}
              </span>
            ) : (
              <span className="text-solgun italic">raf seçilmedi</span>
            )}
          </div>
        </div>
        <div className="ml-auto shrink-0">{baglantiSeridi}</div>
      </header>

      {hata && (
        <div className="rounded-xl border border-hata/50 bg-hata/10 px-4 py-3 text-[14px]
          font-semibold text-hata">
          {hata}
        </div>
      )}

      <div className="grid grid-cols-4 gap-2">
        {[
          { e: "okutulan", d: durum.sayac.okutulan, s: "text-ok" },
          { e: "kalan", d: durum.sayac.kalan, s: "text-yazi" },
          { e: "fazla", d: durum.sayac.fazla, s: durum.sayac.fazla ? "text-hata" : "text-yazi" },
          { e: "kuyruk", d: durum.sayac.kuyruk, s: durum.sayac.kuyruk ? "text-uyari" : "text-yazi" },
        ].map((x) => (
          <div key={x.e} className="cam rounded-2xl py-3 text-center">
            <div className={`rakam text-4xl leading-none font-bold tracking-tight ${x.s}`}>
              {x.d}
            </div>
            <div className="mt-1 text-[10px] font-semibold tracking-wider text-solgun uppercase">
              {x.e}
            </div>
          </div>
        ))}
      </div>

      {son && (
        <div className={`girdi rounded-2xl border px-4 py-3 ${seritSinifi(son.tip)}`}>
          <div className="text-[11px] font-semibold tracking-wider uppercase opacity-70">
            son okutma · {son.ts.slice(11, 19)}
            {son.raf ? ` · raf ${son.raf}` : ""}
          </div>
          <div className="text-lg font-bold break-all">{son.kod ?? son.ham}</div>
          <div className="text-[13px] break-all opacity-80">
            {son.seri}
            {son.not_ ? ` · ${son.not_}` : ""}
          </div>
        </div>
      )}

      {/* Kuyruk yalnızca iş varken görünür. Boşken panel yer kaplamasın: ekranın
          üstü canlı bilgiye kalsın, kuyruk sayacı zaten yukarıda duruyor. */}
      {aktifler.length > 0 && (
        <section className="cam rounded-2xl ring-1 ring-uyari/50">
          <header className="flex items-center justify-between border-b border-cizgi px-4 py-3">
            <h2 className="text-[13px] font-bold tracking-wider text-uyari uppercase">
              Kuyruk — ilgilenilecek
            </h2>
            <span className="text-[13px] text-solgun">{aktifler.length} açık</span>
          </header>
          <ul className="flex flex-col gap-3 bg-panel p-3">
            {aktifler.map((k, i) => kartCiz(k, i === 0, i))}
          </ul>
        </section>
      )}

      {/* laptopta o an okutulan grup */}
      <section className="cam rounded-2xl">
        <header className="border-b border-cizgi px-4 py-3">
          <h2 className="text-[13px] font-bold tracking-wider text-solgun uppercase">
            Laptopta okutulan grup
          </h2>
        </header>
        <ul className="flex flex-col gap-2 bg-panel p-3">
          {durum.tampon.map((t, i) => (
            <li key={`${t.ham}-${i}`} className="rounded-xl bg-panel2 px-3 py-2">
              <span className="font-mono text-[14px] break-all">{t.ham}</span>
              {t.kod && (
                <span className="block text-[12px] text-solgun">
                  → <b className="text-yazi">{t.kod}</b> {t.aciklama}
                </span>
              )}
            </li>
          ))}
          {durum.tampon.length === 0 && (
            <li className="py-3 text-center font-serif text-lg text-solgun italic">grup boş</li>
          )}
        </ul>
      </section>

      <section className="cam rounded-2xl">
        <header className="border-b border-cizgi px-4 py-3">
          <h2 className="text-[13px] font-bold tracking-wider text-solgun uppercase">
            Son okutmalar
          </h2>
        </header>
        <ul className="bg-panel">
          {durum.akis.slice(0, 15).map((a, i) => (
            <li
              key={`${a.ts}-${i}`}
              className={`flex flex-wrap items-baseline gap-2 border-l-4 px-3 py-2 text-[13px] ${
                a.tip === "fazla" || a.tip === "bilinmiyor"
                  ? "border-l-hata"
                  : a.tip === "kod"
                    ? "border-l-bilgi"
                    : "border-l-ok"
              } ${i % 2 ? "bg-panel2/40" : ""}`}
            >
              <span className="rakam text-[11px] text-solgun">{a.ts.slice(11, 19)}</span>
              {a.raf && (
                <span className="inline-flex items-center gap-1 text-[11px] text-uyari">
                  <Ik.Raf boy={11} />
                  {a.raf}
                </span>
              )}
              <b className="font-mono break-all">{a.kod ?? a.ham}</b>
              {a.seri && <span className="font-mono break-all text-solgun">{a.seri}</span>}
            </li>
          ))}
          {durum.akis.length === 0 && (
            <li className="py-6 text-center font-serif text-lg text-solgun italic">
              Henüz okutma yok.
            </li>
          )}
        </ul>
      </section>

      {/* En altta: telefonda fotoğraflanıp ertelenenler. Burada iş yok, arşiv —
          çözümü raf bitince laptop başında toplu yapılıyor. */}
      {parktakiler.length > 0 && (
        <section className="cam rounded-2xl ring-1 ring-bilgi/40">
          <header className="flex items-center justify-between border-b border-bilgi/30 px-4 py-3">
            <h2 className="flex items-center gap-2 text-[13px] font-bold tracking-wider
              text-bilgi uppercase">
              <Ik.Duraklat boy={14} /> PC'de çözülecek
            </h2>
            <span className="text-[13px] text-solgun">{parktakiler.length} kayıt</span>
          </header>
          <ul className="flex flex-col gap-2 bg-bilgi/5 p-3">
            {parktakiler.map((k) => (
              <li key={k.id} className="rounded-xl border border-cizgi bg-panel2 px-3 py-2">
                <div className="flex items-center gap-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-[13px]">
                      {k.barkodlar.join(" + ")}
                    </span>
                    <span className="block text-[11px] text-solgun">
                      {k.raf && <span className="text-uyari">raf {k.raf} · </span>}
                      {k.ts.slice(11, 16)}
                      {k.fotolar.length > 0
                        ? ` · ${k.fotolar.length} fotoğraf`
                        : " · fotoğrafsız"}
                      {k.not_ && ` · ${k.not_}`}
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => fotoIste(k.id)}
                    disabled={yuklenen === k.id}
                    className="cam-hafif shrink-0 rounded-full px-3 py-2 text-[13px] font-semibold
                      disabled:opacity-50"
                  >
                    {yuklenen === k.id ? "…" : <Ik.Kamera boy={17} />}
                  </button>
                  <button
                    type="button"
                    onClick={() => void bekletAyarla(k.id, false)}
                    className="cam-hafif shrink-0 rounded-full px-3 py-2 text-[13px] font-semibold
                      text-solgun"
                  >
                    geri al
                  </button>
                </div>
                {k.fotolar.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {k.fotolar.map((f) => (
                      <img
                        key={f}
                        src={api.fotoUrl(f)}
                        alt="kuyruk fotoğrafı"
                        onClick={() => setBuyutulen(f)}
                        className="h-14 w-14 rounded-xl border border-cizgi object-cover"
                      />
                    ))}
                  </div>
                )}
                {notAlani(k)}
              </li>
            ))}
          </ul>
          <p className="bg-bilgi/5 px-4 pb-3 text-[12px] text-solgun">
            Bunlar kuyrukta duruyor, raf değiştirmeni engellemez. Sayımı bitirmeden önce
            laptoptaki Kuyruk ekranından çözülmeleri gerekir.
          </p>
        </section>
      )}

      <a href="/" className="mt-2 text-center text-[13px] text-solgun underline">
        tam sürüme geç
      </a>

      {buyutulen !== null && (
        <div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4
            bg-black/80 p-4 backdrop-blur-md"
          onClick={() => setBuyutulen(null)}
        >
          <img
            src={api.fotoUrl(buyutulen)}
            alt="kuyruk fotoğrafı"
            className="max-h-[75vh] max-w-full rounded-2xl object-contain"
          />
          <button
            type="button"
            className="cam-hafif rounded-full px-6 py-3 text-[15px] font-semibold"
          >
            Kapat
          </button>
        </div>
      )}
    </div>
  );
}
