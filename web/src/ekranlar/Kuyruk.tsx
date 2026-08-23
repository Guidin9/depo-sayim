/** 3. ekran — çözülmeyi bekleyen gruplar.
 *
 * Kayıtlar rafa göre gruplanır: "hangi rafta okutmuştuk" sorusunun cevabı
 * ekranda hazır dursun. Not ve fotoğraf isteğe bağlı hatırlatıcılardır —
 * fotoğraf telefondan da yüklenebilir (aynı Wi-Fi, telefon monitörü).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type AramaSonucu, type KuyrukSatiri } from "../api";
import { Bos, Dugme, Kod, Panel, Uyari } from "../bilesenler";
import * as Ik from "../ikonlar";
import { kucult } from "../foto";
import { kademeli, suz } from "../liste";
import { bip } from "../ses";

export default function Kuyruk({
  oturum,
  tik,
  geri,
  yenile,
}: {
  oturum: number;
  tik: number;          // canlı güncelleme sayacı — arttıkça listeyi tazeler
  geri: () => void;
  yenile: () => void;
}) {
  const [kuyruk, setKuyruk] = useState<KuyrukSatiri[]>([]);
  const [secili, setSecili] = useState<KuyrukSatiri | null>(null);
  const [buyutulen, setBuyutulen] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const [havuz, setHavuz] = useState<AramaSonucu[]>([]);
  const [toplam, setToplam] = useState(0);
  /* Aday önerisinin yerini alan filtreler (DEMO_FEEDBACK.md 4). Telefondaki
     panelle aynı seti sunuyor ki iki ekranda iki ayrı davranış olmasın. */
  const [sadeceKirli, setSadeceKirli] = useState(false);
  /* Fazla yazmadan önce "bu ne?" kutusu. Kodu olmayan kayıtta ad ZORUNLU:
     yoksa raporda yalnızca seri numarası ve raf kalır, ürün bulunamaz. */
  const [fazlaAdayi, setFazlaAdayi] = useState<KuyrukSatiri | null>(null);
  const [fazlaAd, setFazlaAd] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [araniyor, setAraniyor] = useState(false);
  const [telefonAdresi, setTelefonAdresi] = useState<string | null>(null);
  const aramaRef = useRef<HTMLInputElement>(null);

  const tazele = useCallback(async () => {
    setKuyruk(await api.kuyruk(oturum));
    yenile();
  }, [oturum, yenile]);

  useEffect(() => {
    void tazele();
    void api
      .ag()
      .then((a) => setTelefonAdresi(a.adresler[0] ?? null))
      .catch(() => undefined);
  }, [tazele, tik]);

  useEffect(() => {
    if (!secili) return;
    // Onay kaydında malzeme zaten belli: aramayı o kodla açıp kullanıcıyı
    // doğrudan o kodun sayılmamış satırlarının önüne koyuyoruz.
    setQ(secili.tur === "fazla_onay" ? (secili.kod ?? "") : "");
    setTimeout(() => aramaRef.current?.focus(), 30);
  }, [secili]);

  /* Liste bir kez ve EKSİKSİZ çekilir; süzme istemcide. Eskiden her tuşta
     sunucuya limit=50 ile gidiliyordu ve sayfalama yoktu — 870 satırlık
     kümenin ilk 50'si dışına çıkmanın yolu yoktu.

     sadece_acik SABİT true — filtre değil kural: bu oturumda sayılmış kayıt
     elle eşleme listesinde görünmez, yoksa iki fiziksel ürün tek kayda
     bağlanır (matching.kapasite_kaldi sunucuda da reddediyor). */
  useEffect(() => {
    if (!secili) return;
    let iptal = false;
    setAraniyor(true);
    (async () => {
      try {
        const r = await api.ara(oturum, { sadece_acik: true });
        if (!iptal) {
          setHavuz(r.satirlar);
          setToplam(r.toplam);
        }
      } finally {
        if (!iptal) setAraniyor(false);
      }
    })();
    return () => {
      iptal = true;
    };
  }, [oturum, secili]);

  const sonuc = useMemo(
    () =>
      suz(sadeceKirli ? havuz.filter((b) => b.kirli) : havuz, q.trim(), [
        "kod",
        "aciklama",
        "seri",
      ]),
    [havuz, q, sadeceKirli],
  );
  const pencere = kademeli(sonuc, q + (sadeceKirli ? "K" : ""), 80);

  async function bagla(b: AramaSonucu) {
    if (!secili) return;
    try {
      await api.kuyrukCoz(secili.id, b.id);
      bip("ok");
      setSecili(null);
      await tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  function fazlaSor(k: KuyrukSatiri) {
    setFazlaAdayi(k);
    setFazlaAd(k.ad ?? "");
  }

  async function fazlaYaz() {
    const k = fazlaAdayi;
    if (!k) return;
    const ad = fazlaAd.trim();
    // Malzeme kodu biliniyorsa açıklama rapora JOIN ile geliyor, ad isteğe
    // bağlı. Bilinmiyorsa kayıt adsız hiçbir işe yaramaz.
    if (!k.kod && !ad) return;
    try {
      await api.kuyrukFazla(k.id, ad || undefined);
      bip("uyari");
      setFazlaAdayi(null);
      setFazlaAd("");
      setSecili(null);
      await tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  async function notKaydet(k: KuyrukSatiri, deger: string) {
    if (deger === k.not_) return;
    await api.kuyrukNot(k.id, deger);
    await tazele();
  }

  async function fotoEkle(k: KuyrukSatiri, dosya: File) {
    try {
      await api.fotoYukle(k.id, await kucult(dosya));
      bip("tik");
      await tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  // rafa göre grupla — "hangi raftaydı" sorusu ekranda cevaplansın
  const raflar = [...new Set(kuyruk.map((k) => k.raf ?? ""))];

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5 p-5">
      <header className="flex flex-wrap items-center gap-4">
        <Dugme
          cocuk={
            <>
              <Ik.Geri /> Sayıma dön
            </>
          }
          tikla={geri}
        />
        <h1 className="text-4xl leading-[0.95] font-extrabold tracking-tight">Kuyruk</h1>
        <span className="ml-auto text-govde text-solgun">{kuyruk.length} çözülmemiş grup</span>
      </header>

      {hata && <Uyari cocuk={hata} />}

      {kuyruk.length === 0 ? (
        <Panel cocuk={<Bos cocuk="Kuyruk boş — çözülmeyi bekleyen grup yok." />} />
      ) : (
        <>
          {telefonAdresi && (
            <p className="text-kucuk text-solgun">
              <Ik.Kamera boy={15} className="inline align-text-bottom" /> Telefondan
              fotoğraf eklemek için aynı Wi-Fi'dan{" "}
              <b className="font-mono text-yazi">{telefonAdresi}</b> adresini açın (sunucu{" "}
              <span className="font-mono">baslat.bat</span> ile başlatılmış olmalı).
            </p>
          )}

          {raflar.map((raf) => (
            <section key={raf} className="flex flex-col gap-3">
              <h2 className="text-kucuk font-bold tracking-wider uppercase">
                {raf ? (
                  <span className="inline-flex items-center gap-1.5 text-uyari">
                    <Ik.Raf boy={15} /> Raf {raf}
                  </span>
                ) : (
                  <span className="text-solgun">raf belirtilmemiş</span>
                )}
              </h2>

              {kuyruk
                .filter((k) => (k.raf ?? "") === raf)
                .map((k) => (
                  <div
                    key={k.id}
                    className={`rounded-sm border bg-panel p-4 ${
                      k.beklet ? "border-bilgi" : "border-cizgi"
                    }`}
                  >
                    {/* Onay kaydında malzeme bellidir; soru "bu ne?" değil,
                        "stokta karşılığı var mı?"dır. Kart bunu söylemezse
                        kullanıcı iki kaydı aynı sanır. */}
                    {k.tur === "fazla_onay" && (
                      <div className="mb-3 flex items-start gap-2 rounded-sm border
                        border-uyari bg-uyari-tint px-3 py-2">
                        <Ik.Soru boy={16} />
                        <p className="text-kucuk leading-snug">
                          <b>{k.kod}</b>
                          {k.aciklama ? ` — ${k.aciklama}` : ""}
                          <span className="text-solgun">
                            {" "}
                            · seri numarası Tiger'daki kayıtlarla eşleşmedi. Stokta
                            karşılığı var mı, yoksa gerçekten fazla mı?
                          </span>
                        </p>
                      </div>
                    )}

                    <div className="flex flex-wrap items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap gap-2">
                          {k.barkodlar.map((b) => (
                            <span
                              key={b}
                              className="rounded-sm border border-cizgi bg-panel2 px-2.5 py-1
                                font-mono text-kucuk"
                            >
                              {b}
                            </span>
                          ))}
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-mikro
                          text-solgun">
                          <span>{k.ts}</span>
                          {k.beklet && (
                            <span
                              title="Telefonda fotoğraflanıp ertelendi — çözümü sana bırakıldı"
                              className="rounded-sm border border-bilgi bg-bilgi-tint px-2.5 py-0.5
                                font-semibold text-bilgi"
                            >
                              <span className="inline-flex items-center gap-1">
                                <Ik.Duraklat boy={11} /> telefondan ertelendi
                              </span>
                            </span>
                          )}
                        </div>
                      </div>
                      <Dugme
                        cocuk={k.tur === "fazla_onay" ? "Stokta karşılığını bul" : "Malzeme seç"}
                        tur="ana"
                        tikla={() => setSecili(k)}
                      />
                      <Dugme
                        cocuk={k.tur === "fazla_onay" ? "Evet, gerçekten fazla" : "Fazla olarak yaz"}
                        tur="tehlike"
                        tikla={() => fazlaSor(k)}
                      />
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <input
                        defaultValue={k.not_}
                        placeholder="not (isteğe bağlı): siyah kutu, üst raf, HP yazıyor…"
                        onBlur={(e) => void notKaydet(k, e.target.value.trim())}
                        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                        className="min-w-[240px] flex-1 rounded-sm border border-cizgi bg-zemin
                          px-3 py-2 text-kucuk focus:border-vurgu focus:outline-none"
                      />
                      <label
                        className="cursor-pointer rounded-sm border border-cizgi bg-panel2 px-4
                          py-2 text-kucuk font-semibold hover:bg-cizgi"
                      >
                        <span className="inline-flex items-center gap-1.5">
                          <Ik.Kamera boy={14} /> Fotoğraf
                        </span>
                        <input
                          type="file"
                          accept="image/*"
                          capture="environment"
                          className="hidden"
                          onChange={(e) => {
                            const d = e.target.files?.[0];
                            if (d) void fotoEkle(k, d);
                            e.target.value = "";
                          }}
                        />
                      </label>
                      {k.fotolar.map((f) => (
                        <button
                          key={f}
                          type="button"
                          onClick={() => setBuyutulen(f)}
                          className="h-12 w-12 overflow-hidden rounded-sm border border-cizgi"
                          title="Büyüt"
                        >
                          <img
                            src={api.fotoUrl(f)}
                            alt="kuyruk fotoğrafı"
                            className="h-full w-full object-cover"
                          />
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
            </section>
          ))}
        </>
      )}

      {/* Fazla yazmadan önce: bu ürün ne? Kodu olmayan kayıtta zorunlu —
          rapordaki satırda geriye yalnızca seri numarası ve raf kalıyor,
          gün sonunda ürünün ne olduğu bulunamıyor. */}
      {fazlaAdayi && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-yazi/45 p-4 sm:p-10"
          onClick={(e) => e.target === e.currentTarget && setFazlaAdayi(null)}
        >
          <div className="border border-cizgi bg-panel w-full max-w-lg rounded-sm p-5">
            <h2 className="text-lg font-bold">
              {fazlaAdayi.kod
                ? `${fazlaAdayi.kod} — gerçekten fazla mı?`
                : "Bu ürün ne? Fazla olarak yazılacak."}
            </h2>
            <p className="mt-1 text-kucuk text-solgun">
              {fazlaAdayi.kod ? (
                <>
                  Stokta karşılığı yoksa fazla olarak raporlanır. İstersen ek bir
                  açıklama yazabilirsin.
                </>
              ) : (
                <>
                  Bu ürünün Tiger'da kaydı yok, bu yüzden raporda açıklaması
                  üretilemiyor. <b className="text-yazi">Ne olduğunu yaz</b> — yoksa
                  gün sonunda elinde yalnızca seri numarası ve raf kalır.
                </>
              )}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {fazlaAdayi.barkodlar.map((b) => (
                <span
                  key={b}
                  className="rounded-sm border border-cizgi bg-panel2 px-2.5 py-1
                    font-mono text-kucuk"
                >
                  {b}
                </span>
              ))}
            </div>
            <input
              autoFocus
              value={fazlaAd}
              onChange={(e) => setFazlaAd(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void fazlaYaz();
                if (e.key === "Escape") setFazlaAdayi(null);
              }}
              placeholder="örn. Kırmızı HP güç kablosu, 2 m"
              className="mt-3 w-full rounded-sm border border-cizgi bg-zemin px-4 py-3
                text-govde focus:border-vurgu focus:outline-none"
            />
            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <Dugme cocuk="Vazgeç" tikla={() => setFazlaAdayi(null)} />
              <Dugme
                cocuk="Fazla olarak yaz"
                tur="tehlike"
                pasif={!fazlaAdayi.kod && !fazlaAd.trim()}
                tikla={() => void fazlaYaz()}
              />
            </div>
          </div>
        </div>
      )}

      {buyutulen !== null && (
        <div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-yazi/85 p-4"
          onClick={(e) => e.target === e.currentTarget && setBuyutulen(null)}
        >
          <img
            src={api.fotoUrl(buyutulen)}
            alt="kuyruk fotoğrafı"
            className="max-h-[80vh] max-w-full rounded-sm"
          />
          <div className="flex gap-3">
            <Dugme cocuk="Kapat" tikla={() => setBuyutulen(null)} />
            <Dugme
              cocuk="Fotoğrafı sil"
              tur="tehlike"
              tikla={async () => {
                await api.fotoSil(buyutulen);
                setBuyutulen(null);
                await tazele();
              }}
            />
          </div>
        </div>
      )}

      {secili && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-yazi/45 p-4 sm:p-10"
          onClick={(e) => e.target === e.currentTarget && setSecili(null)}
        >
          <div className="border border-cizgi bg-panel flex max-h-full w-full max-w-2xl flex-col rounded-sm">
            <header className="border-b border-cizgi p-4">
              <h2 className="text-lg font-bold">
                {secili.barkodlar.join(" + ")} — hangi malzeme?
              </h2>
              <p className="mt-1 text-kucuk text-solgun">
                Seçtiğin malzemeye bu barkodlar kalıcı olarak bağlanır; bir daha sorulmaz.
              </p>
              {secili.not_ && <p className="mt-2 text-kucuk text-uyari">not: {secili.not_}</p>}
              {secili.fotolar.length > 0 && (
                <div className="mt-2 flex gap-2">
                  {secili.fotolar.map((f) => (
                    <img
                      key={f}
                      src={api.fotoUrl(f)}
                      alt="kuyruk fotoğrafı"
                      className="h-20 w-20 rounded-sm border border-cizgi object-cover"
                    />
                  ))}
                </div>
              )}
            </header>
            <div className="p-4">
              <input
                ref={aramaRef}
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Escape" && setSecili(null)}
                placeholder="kod, açıklama veya seri no ara…"
                className="w-full rounded-sm border border-cizgi bg-zemin px-4 py-3 text-govde
                  focus:border-vurgu focus:outline-none"
              />
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {[
                  { e: "Uydurma kayıtlı", a: sadeceKirli, f: () => setSadeceKirli((v) => !v) },
                ].map((x) => (
                  <button
                    key={x.e}
                    type="button"
                    onClick={x.f}
                    className={`rounded-sm border px-3 py-1.5 text-kucuk font-semibold ${
                      x.a
                        ? "border-vurgu bg-vurgu-tint text-vurgu"
                        : "border-cizgi bg-panel2 text-solgun"
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
            </div>
            <ul className="flex-1 overflow-y-auto px-4 pb-4">
              {araniyor && <li className="py-3 text-center text-kucuk text-solgun">aranıyor…</li>}
              {!araniyor && sonuc.length === 0 && (
                <li className="py-3 text-center text-kucuk text-solgun">Sonuç yok.</li>
              )}
              {pencere.gorunur.map((b) => (
                <li key={b.id}>
                  <button
                    type="button"
                    onClick={() => void bagla(b)}
                    className="mb-2 w-full rounded-sm border border-cizgi bg-panel2 px-3 py-3
                      text-left transition hover:border-vurgu hover:bg-vurgu-tint"
                  >
                    <div className="flex flex-wrap items-baseline gap-2">
                      <b className="font-mono text-vurgu">{b.kod}</b>
                      <span className="text-kucuk">{b.aciklama}</span>
                      {b.kirli === 1 && (
                        <span className="rounded border border-uyari bg-uyari-tint px-1.5 text-mikro font-bold text-uyari">
                          <span className="inline-flex items-center gap-1">
                            <Ik.Uyari boy={11} /> uydurma kayıt
                          </span>
                        </span>
                      )}
                      {b.sayildi === 1 && (
                        <span className="rounded border border-ok bg-ok-tint px-1.5 text-mikro font-bold text-ok">
                          <span className="inline-flex items-center gap-1">
                            <Ik.Onay boy={11} /> bu oturumda sayıldı
                          </span>
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-mikro text-solgun">
                      <Kod cocuk={b.seri || "—"} /> · {b.izleme} · {b.miktar} {b.birim}
                    </div>
                  </button>
                </li>
              ))}
              {/* Gözcü: görünür olunca pencere büyür. Kesme değil — tüm
                  satırlara erişilebilir, yalnızca çizim ertelenir. */}
              {pencere.kalan > 0 && (
                <li ref={pencere.bitis}>
                  <button
                    type="button"
                    onClick={pencere.daha}
                    className="w-full rounded-sm border border-cizgi bg-panel2 px-3 py-2
                      text-mikro font-semibold text-solgun"
                  >
                    {pencere.kalan} kayıt daha
                  </button>
                </li>
              )}
            </ul>
            <footer className="border-t border-cizgi p-4">
              <Dugme cocuk="Vazgeç (Esc)" tikla={() => setSecili(null)} genis />
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}
