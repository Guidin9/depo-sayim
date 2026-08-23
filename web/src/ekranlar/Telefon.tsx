/** Telefon — /telefon adresinde açılır.
 *
 * Barkodu okuyan yine laptoptaki USB okuyucudur; telefon rafın başında elde
 * duran KUMANDADIR. Dört işe yarar:
 *   1. laptopta ne okutulduğunu anlık gösterir (sayaçlar + son okutmalar),
 *   2. sayımı yürütür: sıradaki ürüne geç, geri al, iptal, atla, fazla, raf,
 *   3. kuyruğa düşen tanınmayan ürünün fotoğrafını çektirir,
 *   4. o ürünü ürün hâlâ eldeyken çözdürür.
 *
 * (2) demo geri bildirimiyle geldi: komut barkodu kartına uzanmak sayımı
 * yavaşlatıyordu. Komutlar zaten POST /okut gövdesinden geçiyor, telefon da
 * aynı uca dokunuyor — mimari değişmedi.
 *
 * Bilerek yok: Excel yükleme, ambar seçimi, rapor, oturumu bitirme (##BITIR##).
 * Depoda telefona yanlış dokunup sayımı kapatmak, kolaylıktan daha pahalı.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type AramaSonucu, type Durum, type KuyrukSatiri } from "../api";
import { Nokta } from "../bilesenler";
import { kucult } from "../foto";
import { kademeli, suz } from "../liste";
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
  if (tip === "fazla" || tip === "bilinmiyor") return "border-hata bg-hata-tint text-hata";
  if (tip === "kod") return "border-bilgi bg-bilgi-tint text-bilgi";
  return "border-ok bg-ok-tint text-ok";
}

/** Aynı sonucun ambiyans ışıması rengi — şeritle ayrışmasın. */
function seritRengi(tip: string): IsimaRenk {
  if (tip === "fazla" || tip === "bilinmiyor") return "hata";
  if (tip === "kod") return "bilgi";
  return "ok";
}

export default function Telefon({ durum, canli, tik, tazele }: Props) {
  const [kuyruk, setKuyruk] = useState<KuyrukSatiri[]>([]);
  const [toplam, setToplam] = useState(0);
  /* Aday önerisi kaldırıldı (DEMO_FEEDBACK.md 4); yerine filtreli liste.
     PC'deki Kuyruk modaliyle aynı set. */
  const [sadeceKirli, setSadeceKirli] = useState(false);
  const [acik, setAcik] = useState<number | null>(null);   // açılmış kuyruk kartı
  const [q, setQ] = useState("");
  const [havuz, setHavuz] = useState<AramaSonucu[]>([]);
  const [aramaAcik, setAramaAcik] = useState(false);
  const [fazlaOnay, setFazlaOnay] = useState<number | null>(null);
  const [yuklenen, setYuklenen] = useState<number | null>(null);
  const [buyutulen, setBuyutulen] = useState<number | null>(null);
  const [notAcik, setNotAcik] = useState<number | null>(null);
  const [notMetin, setNotMetin] = useState("");
  /* Kuyruk kaydı başına "bu ürün ne?" metni. Kodu olmayan kayıt fazla
     yazılmadan önce bunu doldurmak zorunda. */
  const [kuyrukAd, setKuyrukAd] = useState<Record<number, string>>({});
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
      // Ekran aşağı kaydırılmış olabilir; kart kendini göstersin.
      requestAnimationFrame(() =>
        document
          .getElementById(`kuyruk-${sonId}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" }),
      );
    }
  }, [kuyruk]);

  /* Liste bir kez ve EKSİKSİZ çekilir; süzme istemcide yapılır.
     Eskiden her tuşta sunucuya limit=40 ile gidiliyordu, sayfalama da yoktu:
     870 satırlık kümenin ilk 40'ı dışına çıkmanın yolu yoktu.

     sadece_acik SABİT true — filtre değil KURAL: bu oturumda zaten sayılmış
     ya da eşleşmiş kayıt elle eşleme listesinde görünmemeli, yoksa iki ayrı
     fiziksel ürün tek kayda bağlanır. Sunucu da aynı kuralı uyguluyor
     (matching.kapasite_kaldi). */
  useEffect(() => {
    if (!oturum || !aramaAcik) {
      setHavuz([]);
      return;
    }
    let iptal = false;
    (async () => {
      try {
        const r = await api.ara(oturum, { sadece_acik: true });
        if (!iptal) {
          setHavuz(r.satirlar);
          setToplam(r.toplam);
        }
      } catch {
        /* liste çekilemezse sayım durmasın */
      }
    })();
    return () => {
      iptal = true;
    };
  }, [oturum, aramaAcik, tik]);

  const sonuc = useMemo(
    () =>
      suz(sadeceKirli ? havuz.filter((b) => b.kirli) : havuz, q.trim(), [
        "kod",
        "aciklama",
        "seri",
      ]),
    [havuz, q, sadeceKirli],
  );
  const pencere = kademeli(sonuc, q + (sadeceKirli ? "K" : ""));

  async function coz(kuyrukId: number, beklenenId: number) {
    try {
      await api.kuyrukCoz(kuyrukId, beklenenId);
      navigator.vibrate?.(60);
      setAcik(null);
      setQ("");
      setAramaAcik(false);
      await kuyrukTazele();
      tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  async function fazlaYaz(k: KuyrukSatiri) {
    const ad = (kuyrukAd[k.id] ?? k.ad ?? "").trim();
    // Kodu olmayan kayıt adsız yazılamaz: raporda geriye yalnızca seri
    // numarası ve raf kalır, ürünün ne olduğu bulunamaz.
    if (!k.kod && !ad) return;
    try {
      await api.kuyrukFazla(k.id, ad || undefined);
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

  /* ------------------------------------------------------- uzaktan kumanda
   *
   * Okuyucu laptopta kalıyor (mimari değişmedi), ama komut barkodunu okutmak
   * için karta uzanmak sayımı yavaşlatıyordu — demo geri bildirimi §1-2.
   * Komutlar zaten POST /okut gövdesinden geçtiği için telefon aynı uca
   * dokunuyor: yeni bir API'ye gerek yok.
   *
   * ##BITIR## bilerek yok: telefona yanlış dokunup sayımı kapatmak, buradaki
   * kolaylıktan pahalı.
   */
  const [mesgul, setMesgul] = useState(false);
  /* Elle fazla işaretlenen kayıtlar — adı yazılana ya da geçilene kadar. */
  const [fazlaIdler, setFazlaIdler] = useState<number[]>([]);
  const [fazlaAd, setFazlaAd] = useState("");

  async function fazlaAdKaydet() {
    const ad = fazlaAd.trim();
    if (!ad) {
      setFazlaIdler([]);
      return;
    }
    try {
      await Promise.all(fazlaIdler.map((id) => api.okutmaAd(id, ad)));
      navigator.vibrate?.(60);
      setFazlaIdler([]);
      setFazlaAd("");
      tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  async function komut(ham: string, zorla = false) {
    if (!oturum || mesgul) return;
    setMesgul(true);
    try {
      const r = await api.okut(oturum, ham, zorla);
      // Raf kapısı: o rafta çözülmemiş kayıt varken raf değiştirilemez.
      // Kararı kullanıcı verir, sessizce aşmayız.
      if (r.tip === "raf_engel") {
        const kalan = r.kuyruk?.length ?? 0;
        if (
          confirm(
            `${r.eski_raf} rafında ${kalan} ürün çözülmedi.\n\n` +
              "Ürünler hâlâ önündeyken çözmek çok daha kolay. Yine de rafı değiştireyim mi?",
          )
        ) {
          await komut(ham, true);
          return;
        }
      }
      // Elle fazla: kayıt isimsiz kalmasın, hemen sor (DEMO_FEEDBACK.md 3).
      if (r.tip === "fazla_elle" && r.okutma?.length) {
        setFazlaIdler(r.okutma);
        setFazlaAd("");
      }
      navigator.vibrate?.(r.tip === "eslesti" || r.tip === "slot" ? 60 : [80, 50, 80]);
      setHata(null);
      await kuyrukTazele();
      tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    } finally {
      setMesgul(false);
    }
  }

  async function rafDegistir() {
    if (!oturum) return;
    const yeni = prompt("Raf adı (örn. A1):", durum?.aktif_raf ?? "")?.trim();
    if (!yeni) return;
    await komut(`##RAF-${yeni.toUpperCase()}##`);
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
            className="min-w-0 flex-1 rounded-sm border border-cizgi bg-zemin px-3 py-3
              text-govde text-yazi placeholder:text-solgun-hafif focus:border-vurgu
              focus:outline-none"
          />
          <button
            type="button"
            onClick={() => void notKaydet(k.id)}
            className="shrink-0 rounded-sm bg-vurgu px-4 py-3 text-govde font-bold text-white"
          >
            Kaydet
          </button>
          <button
            type="button"
            onClick={() => setNotAcik(null)}
            className="border border-cizgi-kuvvetli bg-panel shrink-0 rounded-sm px-3 py-3 text-govde text-solgun"
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
        className="border border-cizgi-kuvvetli bg-panel mt-2 w-full rounded-sm px-4 py-2 text-left text-kucuk text-solgun"
      >
        <span className="inline-flex items-center gap-2">
          <Ik.Not boy={15} /> {k.not_ ? "Notu düzenle" : "Not ekle"}
        </span>
      </button>
    );
  }

  /** Bir kuyruk kartı. vurgulu = en yeni kayıt (rafın başında ilgilenilecek).
   *
   * sira, .kademe'nin 40ms'lik kademeli girişini besliyor: kartlar tek tek
   * yerine dalga hâlinde açılıyor. Sekizden sonrası aynı gecikmede kalıyor,
   * yoksa uzun kuyrukta son kart saniyelerce beklerdi. */
  function kartCiz(k: KuyrukSatiri, vurgulu: boolean, sira: number) {
    const acikMi = acik === k.id;
    return (
      <li
        key={k.id}
        id={`kuyruk-${k.id}`}
        className={`kademe kademe-${Math.min(sira + 1, 8)} rounded-sm border p-3 ${
          vurgulu ? "border-uyari bg-uyari-tint" : "border-cizgi bg-panel2"
        }`}
      >
        <button
          type="button"
          onClick={() => {
            const acilir = !acikMi;
            setAcik(acilir ? k.id : null);
            if (acilir) {
              // Aday önerisi kaldığı için kart açılınca doğrudan liste gelsin;
              // onay kaydında malzeme belli olduğu için arama kodla dolu açılır.
              setQ(k.tur === "fazla_onay" ? (k.kod ?? "") : "");
              setAramaAcik(true);
            }
          }}
          className="flex w-full items-start gap-3 text-left"
        >
          <span className="min-w-0 flex-1">
            {k.tur === "fazla_onay" && (
              <span className="mb-1 block text-mikro font-bold text-uyari">
                <span className="inline-flex items-center gap-1">
                  <Ik.Soru boy={13} /> {k.kod} — karşılığı bulunamadı
                </span>
              </span>
            )}
            <span className="block font-mono text-govde font-bold break-all">
              {k.barkodlar.join(" + ")}
            </span>
            <span className="mt-1 block text-mikro text-solgun">
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
            className="flex-1 rounded-sm bg-vurgu px-3 py-3 text-govde font-bold text-white
              disabled:bg-panel2 disabled:text-solgun-hafif"
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
            className={`flex-1 rounded-sm border px-3 py-3 text-govde font-bold ${
              k.fotolar.length > 0
                ? "border-ok bg-ok-tint text-ok"
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
                className="h-20 w-20 rounded-sm border border-cizgi object-cover"
              />
            ))}
          </div>
        )}

        {notAlani(k)}

        {!acikMi && (
          <button
            type="button"
            onClick={() => setAcik(k.id)}
            className="border border-cizgi-kuvvetli bg-panel ease-kolay mt-2 w-full rounded-sm px-4 py-2 text-kucuk
              font-semibold text-solgun transition duration-200"
          >
            <span className="inline-flex items-center justify-center gap-2">
              burada çözmek istersen <Ik.OkSag boy={16} />
            </span>
          </button>
        )}

        {acikMi && (
          <div className="mt-3 border-t border-cizgi pt-3">
            <p className="mb-2 text-mikro font-semibold tracking-wider text-solgun uppercase">
              {k.tur === "fazla_onay" ? "Stokta karşılığı var mı?" : "Bu hangi malzeme?"}
            </p>
            {k.tur === "fazla_onay" && (
              <p className="mb-2 text-kucuk leading-snug text-solgun">
                {k.aciklama || k.kod} tanındı, ama seri numarası Tiger'daki hiçbir
                kayıtla eşleşmedi. Aşağıdan doğru kaydı seç, ya da gerçekten fazlaysa
                fazla yaz.
              </p>
            )}
            {/* "Bu olabilir" aday önerisi kaldırıldı: sahada doğru sonuç
                vermiyordu (DEMO_FEEDBACK.md 4). Yerine kullanıcının kendi
                aradığı, filtrelediği liste — PC'deki Kuyruk modaliyle aynı. */}
            <button
              type="button"
              onClick={() => setAramaAcik((a) => !a)}
              className="border border-cizgi-kuvvetli bg-panel w-full rounded-sm px-4 py-3 text-govde font-semibold"
            >
              <span className="inline-flex items-center justify-center gap-2">
                {aramaAcik ? (
                  "Listeyi kapat"
                ) : (
                  <>
                    <Ik.Ara boy={17} /> Malzeme ara / listele
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
                  placeholder="kod, açıklama veya seri no…"
                  className="mt-2 w-full rounded-sm border border-cizgi bg-zemin px-4 py-3
                    text-govde text-yazi placeholder:text-solgun-hafif focus:border-vurgu
                    focus:outline-none"
                />
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {[
                    { e: "Uydurma kayıtlı", a: sadeceKirli, f: () => setSadeceKirli((v) => !v) },
                  ].map((x) => (
                    <button
                      key={x.e}
                      type="button"
                      onClick={x.f}
                      className={`rounded-sm border px-3 py-2 text-kucuk font-semibold ${
                        x.a
                          ? "border-vurgu bg-vurgu-tint text-vurgu"
                          : "border-cizgi bg-panel text-solgun"
                      }`}
                    >
                      {x.e}
                    </button>
                  ))}
                  <span className="ml-auto text-mikro text-solgun">
                    {sonuc.length === toplam
                      ? `${toplam} eşleşmemiş kayıt`
                      : `${sonuc.length} / ${toplam}`}
                  </span>
                </div>
                <ul className="mt-2 flex max-h-72 flex-col gap-2 overflow-y-auto">
                  {pencere.gorunur.map((b) => (
                    <li key={b.id}>
                      <button
                        type="button"
                        onClick={() => void coz(k.id, b.id)}
                        className="w-full rounded-sm border border-cizgi bg-panel px-3 py-3
                          text-left"
                      >
                        <span className="block font-mono text-kucuk font-bold text-vurgu">
                          {b.kod}
                        </span>
                        <span className="block truncate text-mikro text-solgun">
                          {b.aciklama}
                        </span>
                        <span className="mt-1 block text-mikro text-solgun">
                          {b.seri && <span className="font-mono">{b.seri} </span>}
                          {b.kirli ? (
                            <span className="inline-flex items-center gap-1 text-uyari">
                              <Ik.Uyari boy={11} /> uydurma kayıt
                            </span>
                          ) : null}
                          {b.ayni_raf > 0 ? (
                            <span className="inline-flex items-center gap-1 text-uyari">
                              {" "}
                              <Ik.Raf boy={11} /> bu rafta
                            </span>
                          ) : null}
                        </span>
                      </button>
                    </li>
                  ))}
                  {/* Gözcü: görünür olunca pencere büyür. Kesme değil —
                      tüm satırlara erişilebilir, yalnızca çizim ertelenir. */}
                  {pencere.kalan > 0 && (
                    <li ref={pencere.bitis}>
                      <button
                        type="button"
                        onClick={pencere.daha}
                        className="w-full rounded-sm border border-cizgi bg-panel2 px-3 py-3
                          text-mikro font-semibold text-solgun"
                      >
                        {pencere.kalan} kayıt daha
                      </button>
                    </li>
                  )}
                  {sonuc.length === 0 && (
                    <li className="py-6 text-center text-govde text-solgun italic">
                      eşleşen kayıt yok
                    </li>
                  )}
                </ul>
              </>
            )}

            {/* Fazla yazmadan önce "bu ne?" — kodu olmayan kayıtta zorunlu.
                Yepyeni ürün (kendi etiketimizle giren dahil) tam bu yoldan
                geçiyor; adı sorulmazsa raporda bulunamaz hâle geliyor. */}
            {fazlaOnay === k.id && !k.kod && (
              <div className="mt-3 rounded-sm border border-hata bg-hata-tint p-3">
                <p className="mb-2 text-mikro font-bold tracking-wider text-hata uppercase">
                  Bu ürün ne?
                </p>
                <p className="mb-2 text-kucuk leading-snug text-solgun">
                  Tiger'da kaydı yok. Yazmazsan raporda yalnızca seri numarası ve
                  raf kalır.
                </p>
                <input
                  autoFocus
                  value={kuyrukAd[k.id] ?? k.ad ?? ""}
                  onChange={(e) =>
                    setKuyrukAd((o) => ({ ...o, [k.id]: e.target.value }))
                  }
                  placeholder="örn. Kırmızı HP güç kablosu, 2 m"
                  className="w-full rounded-sm border border-cizgi bg-zemin px-4 py-3
                    text-govde text-yazi placeholder:text-solgun-hafif focus:border-vurgu
                    focus:outline-none"
                />
              </div>
            )}

            <button
              type="button"
              disabled={
                fazlaOnay === k.id &&
                !k.kod &&
                !(kuyrukAd[k.id] ?? k.ad ?? "").trim()
              }
              onClick={() => (fazlaOnay === k.id ? void fazlaYaz(k) : setFazlaOnay(k.id))}
              className={`mt-3 w-full rounded-sm border px-4 py-3 text-govde font-semibold
                disabled:bg-panel2 disabled:text-solgun-hafif ${
                  fazlaOnay === k.id
                    ? "border-hata bg-hata-tint text-hata"
                    : "border-hata bg-hata-tint text-hata"
                }`}
            >
              {fazlaOnay === k.id
                ? k.kod
                  ? "Emin misin? Fazla yazmak için tekrar dokun"
                  : "Adını yaz, sonra dokun"
                : k.tur === "fazla_onay"
                  ? "Evet, gerçekten fazla"
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
    /* Oturum yokken gösterilecek veri yok. Düz zemin, logo ve tek bir büyük
       söz — hiyerarşi yazı tipiyle değil kalınlıkla kuruluyor. */
    return (
      <div className="flex min-h-full flex-col items-center justify-center gap-6 p-8 text-center">
        <span className="border border-cizgi bg-panel rounded-sm px-4 py-2">{baglantiSeridi}</span>
        <img src="/logo.png" alt="" width={72} height={72} className="object-contain" />
        <h1 className="text-6xl leading-[0.9] font-extrabold tracking-tight sm:text-7xl">
          Depo
          <br />
          Sayım
        </h1>
        <p className="max-w-xs text-xl text-solgun italic">Sayım başlamadı.</p>
        <p className="max-w-xs text-govde text-solgun">
          Laptopta sayım açılınca burası kendiliğinden dolar. Bu ekranı açık bırakabilirsin.
        </p>
        <a href="/" className="mt-6 text-kucuk text-solgun underline">
          tam sürüme geç
        </a>
      </div>
    );
  }

  /* ------------------------------------------------------- monitör */
  return (
    /* pb-28: sabit alt kumanda çubuğunun altında kalan içerik olmasın. */
    <div className="flex min-h-full flex-col gap-3 p-3 pb-28">
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
      <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-cizgi bg-panel px-4 py-3">
        <img src="/logo.png" alt="" width={26} height={26} className="shrink-0 object-contain" />
        <div className="min-w-0">
          <div className="text-mikro font-semibold tracking-wider text-solgun uppercase">
            Ambar {durum.ambar} · oturum #{durum.oturum}
          </div>
          <div className="truncate text-2xl leading-tight font-bold">
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
        <div className="rounded-sm border border-hata bg-hata-tint px-4 py-3 text-kucuk
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
          <div key={x.e} className="border border-cizgi bg-panel rounded-sm py-3 text-center">
            <div className={`rakam text-4xl leading-none font-bold tracking-tight ${x.s}`}>
              {x.d}
            </div>
            <div className="mt-1 text-mikro font-semibold tracking-wider text-solgun uppercase">
              {x.e}
            </div>
          </div>
        ))}
      </div>

      {/* Elle fazla işaretlenen ürünün Tiger'da kaydı yok; adı şimdi
          yazılmazsa rapordaki satır kimsenin işine yaramaz. */}
      {fazlaIdler.length > 0 && (
        <section className="rounded-sm border border-hata bg-hata-tint p-3">
          <p className="mb-2 text-mikro font-bold tracking-wider text-hata uppercase">
            Bu ürün neydi?
          </p>
          <input
            value={fazlaAd}
            onChange={(e) => setFazlaAd(e.target.value)}
            autoFocus
            placeholder="örn. Kırmızı HP güç kablosu, 2 m"
            className="w-full rounded-sm border border-cizgi bg-zemin px-4 py-3 text-govde
              text-yazi placeholder:text-solgun-hafif focus:border-vurgu focus:outline-none"
          />
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              onClick={() => setFazlaIdler([])}
              className="border border-cizgi-kuvvetli bg-panel w-[38%] rounded-sm py-3 text-govde font-semibold"
            >
              Geç
            </button>
            <button
              type="button"
              onClick={() => void fazlaAdKaydet()}
              className="flex-1 rounded-sm bg-vurgu py-3 text-govde font-bold text-white"
            >
              Kaydet
            </button>
          </div>
        </section>
      )}

      {/* İkincil kumanda. Birincil iki eylem alt çubukta; bunlar daha seyrek
          ama yine de karta uzanmadan erişilebilmeli. */}
      <div className="grid grid-cols-4 gap-2">
        {[
          { e: "Raf", I: Ik.Raf, f: () => void rafDegistir() },
          { e: "İptal", I: Ik.Kapat, f: () => void komut("##IPTAL##") },
          { e: "Atla", I: Ik.Soru, f: () => void komut("##ATLA##") },
          { e: "Fazla", I: Ik.Uyari, f: () => void komut("##FAZLA##") },
        ].map((x) => (
          <button
            key={x.e}
            type="button"
            disabled={mesgul}
            onClick={x.f}
            className="border border-cizgi-kuvvetli bg-panel flex flex-col items-center justify-center gap-1 rounded-sm
              py-2 text-mikro font-semibold disabled:bg-panel2 disabled:text-solgun-hafif"
          >
            <x.I boy={18} />
            {x.e}
          </button>
        ))}
      </div>

      {son && (
        <div className={`girdi rounded-sm border px-4 py-3 ${seritSinifi(son.tip)}`}>
          <div className="text-mikro font-semibold tracking-wider uppercase">
            son okutma · {son.ts.slice(11, 19)}
            {son.raf ? ` · raf ${son.raf}` : ""}
          </div>
          <div className="text-lg font-bold break-all">{son.kod ?? son.ham}</div>
          <div className="text-kucuk break-all">
            {son.seri}
            {son.not_ ? ` · ${son.not_}` : ""}
          </div>
        </div>
      )}

      {/* Kuyruk yalnızca iş varken görünür. Boşken panel yer kaplamasın: ekranın
          üstü canlı bilgiye kalsın, kuyruk sayacı zaten yukarıda duruyor. */}
      {aktifler.length > 0 && (
        <section className="border border-cizgi bg-panel rounded-sm ring-1 ring-uyari">
          <header className="flex items-center justify-between border-b border-cizgi px-4 py-3">
            <h2 className="text-kucuk font-bold tracking-wider text-uyari uppercase">
              Kuyruk — ilgilenilecek
            </h2>
            <span className="text-kucuk text-solgun">{aktifler.length} açık</span>
          </header>
          <ul className="flex flex-col gap-3 bg-panel p-3">
            {aktifler.map((k, i) => kartCiz(k, i === 0, i))}
          </ul>
        </section>
      )}

      {/* laptopta o an okutulan grup */}
      <section className="border border-cizgi bg-panel rounded-sm">
        <header className="border-b border-cizgi px-4 py-3">
          <h2 className="text-kucuk font-bold tracking-wider text-solgun uppercase">
            Laptopta okutulan grup
          </h2>
        </header>
        <ul className="flex flex-col gap-2 bg-panel p-3">
          {durum.tampon.map((t, i) => (
            <li key={`${t.ham}-${i}`} className="rounded-sm bg-panel2 px-3 py-2">
              <span className="font-mono text-kucuk break-all">{t.ham}</span>
              {t.kod && (
                <span className="block text-mikro text-solgun">
                  → <b className="text-yazi">{t.kod}</b> {t.aciklama}
                </span>
              )}
            </li>
          ))}
          {durum.tampon.length === 0 && (
            <li className="py-3 text-center text-lg text-solgun italic">grup boş</li>
          )}
        </ul>
      </section>

      <section className="border border-cizgi bg-panel rounded-sm">
        <header className="border-b border-cizgi px-4 py-3">
          <h2 className="text-kucuk font-bold tracking-wider text-solgun uppercase">
            Son okutmalar
          </h2>
        </header>
        <ul className="bg-panel">
          {durum.akis.slice(0, 15).map((a, i) => (
            <li
              key={`${a.ts}-${i}`}
              className={`flex flex-wrap items-baseline gap-2 border-l-4 px-3 py-2 text-kucuk ${
                a.tip === "fazla" || a.tip === "bilinmiyor"
                  ? "border-l-hata"
                  : a.tip === "kod"
                    ? "border-l-bilgi"
                    : "border-l-ok"
              } ${i % 2 ? "bg-panel2" : ""}`}
            >
              <span className="rakam text-mikro text-solgun">{a.ts.slice(11, 19)}</span>
              {a.raf && (
                <span className="inline-flex items-center gap-1 text-mikro text-uyari">
                  <Ik.Raf boy={11} />
                  {a.raf}
                </span>
              )}
              <b className="font-mono break-all">{a.kod ?? a.ham}</b>
              {a.seri && <span className="font-mono break-all text-solgun">{a.seri}</span>}
            </li>
          ))}
          {durum.akis.length === 0 && (
            <li className="py-6 text-center text-lg text-solgun italic">
              Henüz okutma yok.
            </li>
          )}
        </ul>
      </section>

      {/* En altta: telefonda fotoğraflanıp ertelenenler. Burada iş yok, arşiv —
          çözümü raf bitince laptop başında toplu yapılıyor. */}
      {parktakiler.length > 0 && (
        <section className="border border-cizgi bg-panel rounded-sm ring-1 ring-bilgi">
          <header className="flex items-center justify-between border-b border-bilgi px-4 py-3">
            <h2 className="flex items-center gap-2 text-kucuk font-bold tracking-wider
              text-bilgi uppercase">
              <Ik.Duraklat boy={14} /> PC'de çözülecek
            </h2>
            <span className="text-kucuk text-solgun">{parktakiler.length} kayıt</span>
          </header>
          <ul className="flex flex-col gap-2 bg-bilgi-tint p-3">
            {parktakiler.map((k) => (
              <li key={k.id} className="rounded-sm border border-cizgi bg-panel2 px-3 py-2">
                <div className="flex items-center gap-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-kucuk">
                      {k.barkodlar.join(" + ")}
                    </span>
                    <span className="block text-mikro text-solgun">
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
                    className="border border-cizgi-kuvvetli bg-panel shrink-0 rounded-sm px-3 py-2 text-kucuk font-semibold
                      disabled:bg-panel2 disabled:text-solgun-hafif"
                  >
                    {yuklenen === k.id ? "…" : <Ik.Kamera boy={17} />}
                  </button>
                  <button
                    type="button"
                    onClick={() => void bekletAyarla(k.id, false)}
                    className="border border-cizgi-kuvvetli bg-panel shrink-0 rounded-sm px-3 py-2 text-kucuk font-semibold
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
                        className="h-14 w-14 rounded-sm border border-cizgi object-cover"
                      />
                    ))}
                  </div>
                )}
                {notAlani(k)}
              </li>
            ))}
          </ul>
          <p className="bg-bilgi-tint px-4 pb-3 text-mikro text-solgun">
            Bunlar kuyrukta duruyor, raf değiştirmeni engellemez. Sayımı bitirmeden önce
            laptoptaki Kuyruk ekranından çözülmeleri gerekir.
          </p>
        </section>
      )}

      <a href="/" className="mt-2 text-center text-kucuk text-solgun underline">
        tam sürüme geç
      </a>

      {/* Birincil kumanda: sabit alt çubuk. Sahada en sık yapılan iki şey
          "bu ürün bitti, sıradakine geç" ve "yanlış okuttum, geri al" —
          ikisi de başparmağın durduğu yerde olmalı. Üstteki liste kaydırılırken
          bile erişilebilir kalsın diye fixed. */}
      <div
        className="fixed inset-x-0 bottom-0 z-40 flex gap-2 border-t border-cizgi bg-panel px-3 pt-3"
        style={{ paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))" }}
      >
        <button
          type="button"
          disabled={mesgul}
          onClick={() => void komut("##GERIAL##")}
          className="border border-cizgi-kuvvetli bg-panel flex w-[38%] items-center justify-center gap-2 rounded-sm
            py-4 text-govde font-bold disabled:bg-panel2 disabled:text-solgun-hafif"
        >
          <Ik.Geri boy={18} /> Geri al
        </button>
        <button
          type="button"
          disabled={mesgul}
          onClick={() => void komut("##SONRAKI##")}
          className="flex flex-1 items-center justify-center gap-2 rounded-sm bg-vurgu
            py-4 text-xl font-bold text-white disabled:bg-panel2 disabled:text-solgun-hafif"
        >
          Sıradaki ürün <Ik.OkSag boy={20} />
        </button>
      </div>

      {buyutulen !== null && (
        <div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4
            bg-yazi/85 p-4"
          onClick={() => setBuyutulen(null)}
        >
          <img
            src={api.fotoUrl(buyutulen)}
            alt="kuyruk fotoğrafı"
            className="max-h-[75vh] max-w-full rounded-sm object-contain"
          />
          <button
            type="button"
            className="border border-cizgi-kuvvetli bg-panel rounded-sm px-6 py-3 text-govde font-semibold"
          >
            Kapat
          </button>
        </div>
      )}
    </div>
  );
}
