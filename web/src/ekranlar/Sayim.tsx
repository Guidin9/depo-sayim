/** 2. ekran — asıl sayım. Tek input sürekli odaklı, geri bildirim sesli. */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Aday, type Durum, type OkutmaSonucu } from "../api";
import { Dugme, Kod, Marka, Nokta, Rozet, SayacKutu } from "../bilesenler";
import * as Ik from "../ikonlar";
import Isima, { type IsimaRenk } from "../Isima";
import type { BaglantiHali } from "../olaylar";
import { bip, sesAcikMi, sesiAyarla } from "../ses";
import TelefonKutu from "../TelefonKutu";

type Props = {
  durum: Durum;
  setDurum: (d: Durum) => void;
  canli: BaglantiHali;
  uzaktan: boolean;
  modDegistir: () => void;
  git: (ekran: "kuyruk" | "rapor" | "gecmis" | "ayarlar") => void;
};

const KISAYOL: Record<string, string> = {
  F2: "##SONRAKI##",
  F3: "##FAZLA##",
  F4: "##ATLA##",
  Escape: "##IPTAL##",
  F10: "##BITIR##",
};

/* Şerit rengi ile ambiyans ışımasının rengi tek yerden geliyor: ekranda gördüğü
   renk ile ışımanın rengi ayrışırsa geri bildirim kafa karıştırır. */
const YESIL = { sinif: "border-ok/50 bg-ok/12 text-ok", renk: "ok" as IsimaRenk };
const SARI = { sinif: "border-uyari/50 bg-uyari/12 text-uyari", renk: "uyari" as IsimaRenk };
const KIRMIZI = { sinif: "border-hata/50 bg-hata/12 text-hata", renk: "hata" as IsimaRenk };
const MAVI = { sinif: "border-bilgi/50 bg-bilgi/12 text-bilgi", renk: "bilgi" as IsimaRenk };

type Serit = {
  Ikon: typeof Ik.Onay;
  ana: string;
  alt: string;
  sinif: string;
  renk: IsimaRenk;
};

/** Okutma sonucunu ekranın üstündeki büyük şeride çevirir. */
function seritMetni(r: OkutmaSonucu): Serit | null {
  switch (r.tip) {
    case "eslesti":
      return {
        Ikon: Ik.Onay,
        ana: `${r.kod} — ${r.seri}`,
        alt: `${r.aciklama ?? ""}${r.ogrenilen?.length ? ` · öğrenildi: ${r.ogrenilen.join(", ")}` : ""}`,
        ...YESIL,
      };
    case "slot":
      return {
        Ikon: Ik.Onay,
        ana: `${r.kod} — uydurma kayıt düzeltildi`,
        alt: `${r.eski} → ${r.yeni || "?"} · ${r.aciklama ?? ""}`,
        ...YESIL,
      };
    case "adet":
      return {
        Ikon: Ik.Onay,
        ana: `${r.kod} — sayılan ${r.toplam} / beklenen ${r.beklenen}`,
        alt: r.aciklama ?? "",
        ...YESIL,
      };
    case "fazla":
    case "fazla_elle":
      return {
        Ikon: Ik.Uyari,
        ana: `FAZLA — ${r.kod ?? (r.barkodlar ?? []).join(", ")}`,
        alt: r.aciklama ?? "Tiger kaydında karşılığı yok, rapora fazla olarak yazıldı.",
        ...KIRMIZI,
      };
    case "tekrar":
      return {
        Ikon: Ik.Tekrar,
        ana: `TEKRAR — ${r.kod}`,
        alt: `${r.seri} zaten okutuldu, ikinci kez sayılmadı.`,
        ...SARI,
      };
    case "kuyruk":
      return {
        Ikon: Ik.Soru,
        ana: "KUYRUĞA ATILDI",
        alt: `${(r.barkodlar ?? []).join(" + ")} — sayımı durdurma, sonunda çözersin.`,
        ...SARI,
      };
    case "iptal":
      return { Ikon: Ik.Tekrar, ana: "GRUP İPTAL", alt: "Tampon boşaltıldı.", ...SARI };
    case "gerial":
      return {
        Ikon: Ik.Geri,
        ana: r.kapsam === "grup" ? "SON GRUP GERİ ALINDI" : "SON OKUTMA SİLİNDİ",
        alt: r.kapsam === "grup" ? (r.barkodlar ?? []).join(", ") : (r.ham ?? ""),
        ...SARI,
      };
    case "raf":
      return { Ikon: Ik.Raf, ana: `RAF ${r.raf}`, alt: "Sonraki okutmalar bu rafa yazılacak.", ...MAVI };
    case "bitti":
      return { Ikon: Ik.Bitti, ana: "SAYIM BİTTİ", alt: "Rapor ekranına geçebilirsin.", ...MAVI };
    case "raf_engel":
      return {
        Ikon: Ik.Engel,
        ana: `${r.eski_raf} rafında ${r.kuyruk?.length} ürün çözülmedi`,
        alt: "Ürünler hâlâ önündeyken çöz — gün sonunda hangisi olduğunu hatırlaman çok daha zor.",
        ...KIRMIZI,
      };
    case "bitir_engel":
      return {
        Ikon: Ik.Engel,
        ana: `Kuyrukta ${r.kuyruk?.length} çözülmemiş ürün var`,
        alt: "Bitirmeden önce çöz; yoksa hepsi raporda 'fazla' olarak kalır.",
        ...KIRMIZI,
      };
    default:
      return null;
  }
}

export default function Sayim({ durum, setDurum, canli, uzaktan, modDegistir, git }: Props) {
  const [son, setSon] = useState<OkutmaSonucu | null>(null);
  const [odak, setOdak] = useState(true);
  const [ses, setSes] = useState(sesAcikMi());
  const [mesgul, setMesgul] = useState(false);
  const [elleGiris, setElleGiris] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const [telefonKutu, setTelefonKutu] = useState(false);
  /* Ambiyans ışımasını yeniden tetiklemek için sayaç: aynı barkod arka arkaya
     okutulduğunda sonuç nesnesi aynı görünse de ışık yine çakmalı. */
  const [isik, setIsik] = useState(0);
  const girisRef = useRef<HTMLInputElement>(null);

  const odakla = useCallback(() => {
    // Uzaktan ekranda (telefon) odaklamıyoruz: ekran klavyesi sürekli açılır,
    // ekranın yarısını kaplar ve izlemek için gelen kullanıcıyı boğar.
    if (uzaktan) return;
    requestAnimationFrame(() => girisRef.current?.focus());
  }, [uzaktan]);

  useEffect(() => {
    odakla();
  }, [odakla]);

  /* Okuyucu saniyede birkaç barkod basabiliyor. İstekler paralel gitseydi
     sunucu bunları farklı thread'lerde işler ve ##SONRAKI## kendinden önceki
     barkodun önüne geçebilirdi — grup eksik kapanırdı. Bu yüzden okutmalar tek
     sıraya dizilip birbiri ardına gönderiliyor. */
  const siraRef = useRef<Promise<void>>(Promise.resolve());
  const bekleyenRef = useRef(0);

  const gonder = useCallback(
    (ham: string, zorla = false) => {
      if (!ham.trim()) return siraRef.current;
      bekleyenRef.current += 1;
      setMesgul(true);
      siraRef.current = siraRef.current.then(async () => {
        try {
          const r = await api.okut(durum.oturum, ham, zorla);
          bip(r.ses ?? "tik");
          setSon(r.tip === "tampon" ? null : r);
          if (r.tip !== "tampon") setIsik((n) => n + 1);
          setHata(null);
          if (r.durum) setDurum(r.durum);
        } catch (e) {
          bip("uyari");
          setHata(e instanceof Error ? e.message : String(e));
        } finally {
          bekleyenRef.current -= 1;
          if (bekleyenRef.current === 0) {
            setMesgul(false);
            odakla();
          }
        }
      });
      return siraRef.current;
    },
    [durum.oturum, setDurum, odakla],
  );

  // Klavye kısayolları — komut kartı elde değilse
  useEffect(() => {
    function tus(e: KeyboardEvent) {
      if (e.ctrlKey && e.key.toLowerCase() === "z") {
        e.preventDefault();
        void gonder("##GERIAL##");
        return;
      }
      const komut = KISAYOL[e.key];
      if (!komut) return;
      e.preventDefault();
      if (komut === "##BITIR##" && !confirm("Sayımı bitirip oturumu kapatalım mı?")) return;
      void gonder(komut);
    }
    window.addEventListener("keydown", tus);
    return () => window.removeEventListener("keydown", tus);
  }, [gonder]);

  /* Kuyruğa düşen grup için aday seçimi. Rakam tuşları KULLANILMIYOR: okuyucu
     barkodu tuş tuş yazıyor, "1" ile başlayan her barkod yanlışlıkla aday
     seçerdi. Alt+1..5 okuyucunun asla üretmediği bir kombinasyon. */
  const adaySec = useCallback(
    async (aday: Aday) => {
      if (!son?.kuyruk_id) return;
      try {
        await api.kuyrukCoz(son.kuyruk_id, aday.id);
        bip("ok");
        setSon({ tip: "eslesti", kod: aday.kod, aciklama: aday.aciklama, seri: "" });
        setIsik((n) => n + 1);
        setDurum(await api.durum(durum.oturum));
      } catch (e) {
        bip("uyari");
        setHata(e instanceof Error ? e.message : String(e));
      } finally {
        odakla();
      }
    },
    [son, durum.oturum, setDurum, odakla],
  );

  useEffect(() => {
    const liste = son?.tip === "kuyruk" ? (son.adaylar ?? []) : [];
    if (!liste.length) return;
    function tus(e: KeyboardEvent) {
      if (!e.altKey) return;
      const i = Number(e.key) - 1;
      if (Number.isNaN(i) || i < 0 || i >= liste.length) return;
      e.preventDefault();
      void adaySec(liste[i]);
    }
    window.addEventListener("keydown", tus);
    return () => window.removeEventListener("keydown", tus);
  }, [son, adaySec]);

  const s = durum.sayac;
  const serit = son ? seritMetni(son) : null;
  const engel = son && (son.tip === "raf_engel" || son.tip === "bitir_engel") ? son : null;
  const adaylar = son?.tip === "kuyruk" ? (son.adaylar ?? []) : [];

  function zorlaDevam() {
    if (!engel) return;
    const komut = engel.tip === "raf_engel" ? `##RAF-${engel.yeni_raf}##` : "##BITIR##";
    if (!confirm("Çözülmemiş ürünler kuyrukta kalacak. Yine de devam edilsin mi?")) return;
    void gonder(komut, true);
  }

  return (
    <div className="flex h-full flex-col">
      {/* Okutma sonucunun ambiyans ışıması — sesli geri bildirimin görsel eşi. */}
      {serit && <Isima key={isik} renk={serit.renk} />}

      {/* Üst şerit. Yedi düğme iki cam hap adasına ayrıldı: soldaki sayıma ait
          gezinme, sağdaki cihaz ayarları. İşlev ve sıra aynı, gözün taraması
          kolaylaştı. */}
      <header className="cam flex flex-wrap items-center gap-4 px-5 py-3">
        <Marka boy={30} yazi={false} />
        <div>
          <div className="text-[11px] font-semibold tracking-wider text-solgun uppercase">
            Ambar {durum.ambar} · oturum #{durum.oturum}
          </div>
          <div className="font-serif text-2xl leading-tight">
            {durum.aktif_raf ? (
              <span className="inline-flex items-center gap-2 text-uyari">
                <Ik.Raf boy={20} />
                Raf {durum.aktif_raf}
              </span>
            ) : (
              <span className="text-solgun italic">raf seçilmedi</span>
            )}
          </div>
        </div>

        <div className="ml-auto flex items-center gap-5">
          <SayacKutu etiket="okutulan" deger={s.okutulan} vurgu="ok" />
          <SayacKutu etiket="kalan" deger={s.kalan} />
          <SayacKutu etiket="fazla" deger={s.fazla} vurgu={s.fazla ? "hata" : undefined} />
          <SayacKutu etiket="kuyruk" deger={s.kuyruk} vurgu={s.kuyruk ? "uyari" : undefined} />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span
            title={
              canli === "canli"
                ? "Canlı bağlantı açık — telefon ekranı kendiliğinden güncelleniyor"
                : "Canlı bağlantı yok — ekranlar yedek yoklamayla güncelleniyor"
            }
            className="px-1"
          >
            <Nokta hal={canli} />
          </span>

          <div className="cam flex flex-wrap gap-1.5 rounded-full p-1.5">
            <Dugme
              cocuk={`Kuyruk${s.kuyruk ? ` (${s.kuyruk})` : ""}`}
              tikla={() => git("kuyruk")}
              tur={s.kuyruk ? "tehlike" : "sade"}
            />
            <Dugme cocuk="Rapor" tikla={() => git("rapor")} />
            <Dugme cocuk="Ayarlar" tikla={() => git("ayarlar")} />
          </div>

          <div className="cam flex flex-wrap gap-1.5 rounded-full p-1.5">
            <Dugme
              cocuk={
                <>
                  <Ik.Telefon /> Telefon
                </>
              }
              baslik="Telefonu canlı izleme ekranı olarak bağla (QR)"
              tikla={() => setTelefonKutu(true)}
            />
            <Dugme
              cocuk={
                uzaktan ? (
                  <>
                    <Ik.Telefon /> Uzaktan
                  </>
                ) : (
                  <>
                    <Ik.Okuyucu /> Okuyucu
                  </>
                )
              }
              baslik={
                uzaktan
                  ? "Bu cihaz uzaktan ekran — barkod alanı odaklanmıyor"
                  : "Bu cihazda okuyucu takılı — barkod alanı sürekli odakta"
              }
              tikla={modDegistir}
            />
            <Dugme
              cocuk={
                ses ? (
                  <>
                    <Ik.SesAcik /> Ses açık
                  </>
                ) : (
                  <>
                    <Ik.SesKapali /> Ses kapalı
                  </>
                )
              }
              baslik="Sesli geri bildirim"
              tikla={() => {
                const y = !ses;
                setSes(y);
                sesiAyarla(y);
                if (y) bip("tik");
                odakla();
              }}
            />
          </div>
        </div>
      </header>

      {!odak && !uzaktan && (
        <div className="nabiz flex flex-wrap items-center justify-center gap-2 bg-hata px-5
          py-2 text-center text-[15px] font-bold text-white">
          <Ik.Uyari boy={18} /> Okuyucu girişi odakta değil — ekrana bir kez dokunun, okutmalar
          kaybolmasın
        </div>
      )}

      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4 overflow-hidden p-5">
        {uzaktan && (
          <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-bilgi/40
            bg-bilgi/5 px-4 py-3">
            <span className="inline-flex items-center gap-2 text-[14px] text-bilgi">
              <Ik.Telefon /> Uzaktan ekran — laptopta okutulanlar buraya canlı düşer.
            </span>
            <span className="ml-auto flex gap-2">
              <Dugme
                cocuk={
                  elleGiris ? (
                    "Klavyeyi gizle"
                  ) : (
                    <>
                      <Ik.Klavye /> Elle barkod gir
                    </>
                  )
                }
                tikla={() => {
                  const y = !elleGiris;
                  setElleGiris(y);
                  if (y) requestAnimationFrame(() => girisRef.current?.focus());
                }}
              />
              <Dugme cocuk="F2 · Sıradaki ürün" tikla={() => void gonder("##SONRAKI##")} />
            </span>
          </div>
        )}
        {/* Giriş. Cam ve animasyon katmanlarının hepsi pointer-events-none —
            okuyucunun yazdığı yerin odağı hiçbir koşulda kaybolmamalı. */}
        <div className={uzaktan && !elleGiris ? "hidden" : ""}>
          <input
            ref={girisRef}
            autoFocus={!uzaktan}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            disabled={durum.durum !== "acik"}
            placeholder={
              uzaktan ? "Barkodu elle yaz, Enter" : "Barkodu okut — ürün bitince SIRADAKİ ÜRÜN okut"
            }
            onFocus={() => setOdak(true)}
            onBlur={() => {
              setOdak(false);
              if (!uzaktan) setTimeout(odakla, 60);
            }}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              const v = e.currentTarget.value;
              e.currentTarget.value = "";
              void gonder(v);
            }}
            className="w-full rounded-2xl border-2 border-vurgu bg-zemin px-5 py-5 font-mono
              text-2xl text-yazi shadow-[0_0_0_6px_rgba(76,111,255,0.08)]
              placeholder:text-solgun/60 focus:border-vurgu focus:outline-none
              disabled:opacity-50"
          />
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-solgun">
            <span>
              <kbd className="rounded-full border border-cizgi px-2 py-0.5">F2</kbd> sıradaki ürün
            </span>
            <span>
              <kbd className="rounded-full border border-cizgi px-2 py-0.5">Esc</kbd> grubu iptal
            </span>
            <span>
              <kbd className="rounded-full border border-cizgi px-2 py-0.5">Ctrl+Z</kbd> geri al
            </span>
            <span>
              <kbd className="rounded-full border border-cizgi px-2 py-0.5">F3</kbd> fazla
            </span>
            <span>
              <kbd className="rounded-full border border-cizgi px-2 py-0.5">F4</kbd> atla
            </span>
            <span>
              <kbd className="rounded-full border border-cizgi px-2 py-0.5">F10</kbd> bitir
            </span>
            {mesgul && <span className="text-vurgu">işleniyor…</span>}
          </div>
        </div>

        {hata && (
          <div className="rounded-xl border border-hata/50 bg-hata/10 px-4 py-3 font-semibold text-hata">
            {hata}
          </div>
        )}

        {serit && (
          <div className={`girdi flex items-center gap-4 rounded-2xl border px-5 py-4 ${serit.sinif}`}>
            <serit.Ikon boy={30} />
            <div className="min-w-0">
              <div className="text-xl font-bold break-words">{serit.ana}</div>
              {serit.alt && <div className="text-[14px] break-words opacity-80">{serit.alt}</div>}
            </div>
          </div>
        )}

        {adaylar.length > 0 && (
          <section className="girdi rounded-2xl border border-uyari/40 bg-uyari/5 p-3">
            <h2 className="mb-2 text-[13px] font-bold tracking-wider text-uyari uppercase">
              Bunlardan biri mi? · seçmezsen kuyrukta kalır, sayım durmaz
            </h2>
            <ul className="grid gap-2 sm:grid-cols-2">
              {adaylar.map((a, i) => (
                <li key={a.kod}>
                  <button
                    type="button"
                    onClick={() => void adaySec(a)}
                    className="ease-kolay flex w-full items-center gap-3 rounded-xl border
                      border-cizgi bg-panel2 px-3 py-2 text-left transition duration-200
                      hover:border-vurgu hover:bg-vurgu/10"
                  >
                    <kbd className="shrink-0 rounded-full border border-cizgi px-2.5 py-1
                      text-[12px] text-solgun">
                      Alt+{i + 1}
                    </kbd>
                    <span className="min-w-0 flex-1">
                      <span className="block font-mono text-[14px] font-bold text-vurgu">
                        {a.kod}
                      </span>
                      <span className="block truncate text-[13px] text-solgun">{a.aciklama}</span>
                    </span>
                    <span className="shrink-0 text-right text-[11px] text-solgun">
                      {a.ayni_raf > 0 && (
                        <span className="flex items-center justify-end gap-1 text-uyari">
                          <Ik.Raf boy={12} /> bu rafta
                        </span>
                      )}
                      {a.acik_kirli > 0 && (
                        <span className="flex items-center justify-end gap-1">
                          <Ik.Uyari boy={12} /> {a.acik_kirli} uydurma
                        </span>
                      )}
                      <span className="block">{a.acik_satir} açık</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* mevcut grup */}
        <section className="cam rounded-2xl">
          <header className="flex items-center justify-between border-b border-cizgi px-4 py-2">
            <h2 className="text-[13px] font-bold tracking-wider text-solgun uppercase">
              Mevcut grup
            </h2>
            <span className="text-[13px] text-solgun">
              {durum.tampon.length === 0
                ? "boş — ürünün barkodlarını okutmaya başla"
                : `${durum.tampon.length} barkod · SIRADAKİ ÜRÜN ile kapat`}
            </span>
          </header>
          <ul className="flex flex-col gap-2 bg-panel p-3">
            {durum.tampon.map((t, i) => (
              <li
                key={`${t.ham}-${i}`}
                className="girdi flex flex-wrap items-center gap-3 rounded-xl bg-panel2 px-3 py-2"
              >
                <Rozet tip={t.coz} />
                <Kod cocuk={t.ham} />
                {t.kod && (
                  <span className="text-[13px] text-solgun">
                    → <b className="text-yazi">{t.kod}</b> {t.aciklama}
                  </span>
                )}
                {t.not && <span className="text-[12px] text-vurgu">({t.not})</span>}
              </li>
            ))}
            {durum.tampon.length === 0 && (
              <li className="px-2 py-4 text-center font-serif text-lg text-solgun italic">
                Ürünün üstündeki barkodları sırayla okut: P/N, S/N, UPC — hangisi varsa.
              </li>
            )}
          </ul>
        </section>

        {/* son okutmalar */}
        <section className="cam flex min-h-0 flex-1 flex-col rounded-2xl">
          <header className="border-b border-cizgi px-4 py-2">
            <h2 className="text-[13px] font-bold tracking-wider text-solgun uppercase">
              Son okutmalar
            </h2>
          </header>
          <ul className="flex-1 overflow-y-auto bg-panel">
            {durum.akis.map((a, i) => (
              <li
                key={`${a.ts}-${i}`}
                className={`flex flex-wrap items-baseline gap-3 border-l-4 px-4 py-2 text-[14px]
                  ${
                    a.tip === "fazla" || a.tip === "bilinmiyor"
                      ? "border-l-hata"
                      : a.tip === "kod"
                        ? "border-l-bilgi"
                        : "border-l-ok"
                  } ${i % 2 ? "bg-panel2/40" : ""}`}
              >
                <span className="rakam text-[12px] text-solgun">{a.ts.slice(11, 19)}</span>
                {a.raf && (
                  <span className="inline-flex items-center gap-1 text-[12px] text-uyari">
                    <Ik.Raf boy={12} />
                    {a.raf}
                  </span>
                )}
                <b className="font-mono">{a.kod ?? a.ham}</b>
                {a.seri && <span className="font-mono text-solgun">{a.seri}</span>}
                <span className="ml-auto text-[12px] text-solgun">{a.not_ || a.tip}</span>
              </li>
            ))}
            {durum.akis.length === 0 && (
              <li className="py-8 text-center font-serif text-lg text-solgun italic">
                Henüz okutma yok.
              </li>
            )}
          </ul>
        </section>
      </div>

      {telefonKutu && <TelefonKutu kapat={() => setTelefonKutu(false)} />}

      {engel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
          <div className="cam w-full max-w-2xl rounded-2xl ring-2 ring-hata">
            <header className="border-b border-cizgi p-5">
              <h2 className="flex items-center gap-3 font-serif text-3xl leading-tight text-hata">
                <Ik.Engel boy={28} />
                {engel.tip === "raf_engel"
                  ? `${engel.eski_raf} rafından ayrılmadan önce`
                  : "Sayımı bitirmeden önce"}
              </h2>
              <p className="mt-2 text-[15px] text-solgun">
                {engel.kuyruk?.length} ürün tanınmadı ve kuyrukta bekliyor. Ürünler hâlâ
                elinin altındayken çözmek, gün sonunda barkod listesine bakıp hangisi
                olduğunu hatırlamaya çalışmaktan çok daha kolay.
              </p>
            </header>
            <ul className="max-h-64 overflow-y-auto p-4">
              {engel.kuyruk?.map((k) => (
                <li
                  key={k.id}
                  className="mb-2 rounded-xl border border-cizgi bg-panel2 px-3 py-2"
                >
                  <div className="flex flex-wrap gap-2">
                    {k.barkodlar.map((b) => (
                      <span key={b} className="font-mono text-[14px]">
                        {b}
                      </span>
                    ))}
                  </div>
                  <div className="mt-1 text-[12px] text-solgun">
                    {k.raf && (
                      <span className="inline-flex items-center gap-1 text-uyari">
                        <Ik.Raf boy={12} /> {k.raf} ·{" "}
                      </span>
                    )}
                    {k.ts}
                    {k.not_ && <span> · {k.not_}</span>}
                  </div>
                </li>
              ))}
            </ul>
            <footer className="flex flex-wrap gap-3 border-t border-cizgi p-4">
              <Dugme cocuk="Kuyruğu şimdi çöz" tur="ana" tikla={() => git("kuyruk")} />
              <Dugme cocuk="Vazgeç, saymaya devam et" tikla={() => setSon(null)} />
              <span className="ml-auto">
                <Dugme
                  cocuk={engel.tip === "raf_engel" ? "Yine de rafı değiştir" : "Yine de bitir"}
                  tur="tehlike"
                  tikla={zorlaDevam}
                />
              </span>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}
