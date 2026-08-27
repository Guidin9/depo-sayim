/** 3. ekran — çözülmeyi bekleyen gruplar.
 *
 * Kayıtlar rafa göre gruplanır: "hangi rafta okutmuştuk" sorusunun cevabı
 * ekranda hazır dursun. Not ve fotoğraf isteğe bağlı hatırlatıcılardır —
 * fotoğraf telefondan da yüklenebilir (aynı Wi-Fi, telefon monitörü).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type AramaSonucu, type KuyrukSatiri } from "../api";
import { Bos, Dugme, Panel, Uyari } from "../bilesenler";
import * as Ik from "../ikonlar";
import { kucult } from "../foto";
import { suz } from "../liste";
import { GrupluListe } from "../GrupluListe";
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
  /* Kap kaydının cevabı iki parçalı: "içinde ne var" + "kaç tane sayıldı".
     Birincisi KALICI (kap defterine yazılır), ikincisi yalnızca bu oturuma —
     içerik ayda bir değişiyor, adet kalıcı bir gerçek değil. */
  const [kutuMalzeme, setKutuMalzeme] = useState<AramaSonucu | null>(null);
  const [kutuAdet, setKutuAdet] = useState("");
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
    // Onay ve kap kaydında bir aday kod var: aramayı onunla açıyoruz.
    setQ(secili.tur === "bilinmiyor" ? "" : (secili.kod ?? ""));
    setKutuMalzeme(null);
    // Adet alanı yalnızca kayıt TAZEYKEN dolu gelir. 30 günden eski bir kap
    // kaydı bilgi değil tahmindir; boş alan kullanıcıyı saymaya zorlar.
    setKutuAdet(
      secili.tur === "kutu"
        ? secili.kutu?.oneri_adet != null
          ? String(secili.kutu.oneri_adet)
          : secili.adet
            ? String(secili.adet)
            : ""
        : "",
    );
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

  /* Kabın içeriğini yaz ve (serisizse) say. Sunucu ikisini tek işlemde
     yapıyor: kap defteri kalıcı, sayım oturuma ait. */
  async function kutuKaydet() {
    if (!secili) return;
    // Kayıtlı içerik varsa yeniden seçtirmiyoruz: kap zaten "bende bu var"
    // diyor, eksik olan yalnızca adet. Listeden seçim onu EZER.
    const kod = kutuMalzeme?.kod ?? secili.kutu?.malzeme;
    const seriTakipli = (kutuMalzeme?.izleme ?? secili.kutu?.izleme) === "seri";
    if (!kod) return;
    const n = Number(kutuAdet);
    if (!seriTakipli && !(n > 0)) return;
    try {
      const r = await api.kutuCoz(secili.id, kod, seriTakipli ? null : n);
      bip(r.sayildi === false ? "uyari" : "ok");
      // Seri takipli kapta sayım YAPILMAZ: her adet Tiger'da ayrı satır.
      // Kap tanımlandı, cihazlar tek tek okutulacak — kullanıcı bunu bilmeli.
      if (r.sayildi === false)
        setHata(
          `${kod} seri takipli: kap kaydedildi ama sayım yapılmadı. ` +
            "Sayım ekranından cihazların seri numaralarını okut (kodu kilitlersen " +
            "her cihazda malzemeyi tekrar okutman gerekmez).",
        );
      else setHata(null);
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

  /* Kutuda 150 sanıp 130 çıkabilir — kayıt çözülmeden düzeltilebilmeli.
     Boş bırakmak "adet girilmedi" (0) demektir, "1 tane" demek değil. */
  async function adetKaydet(k: KuyrukSatiri, deger: string) {
    const n = deger.trim() === "" ? 0 : Number(deger);
    if (!Number.isFinite(n) || n < 0 || n === k.adet) return;
    try {
      await api.kuyrukAdet(k.id, n);
      await tazele();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
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
                    {/* Kap kaydı: soru "bu hangi ürün" değil, "BU KAPTA ne
                        var, kaç tane". Kabın son bilinen içeriği kartta durur
                        ama tazelik açıkça yazılır — bayat bir adet, sayım
                        sonucu diye onaylanacak bir şey değildir. */}
                    {k.tur === "kutu" && (
                      <div className="mb-3 flex items-start gap-2 rounded-sm border
                        border-bilgi bg-bilgi-tint px-3 py-2">
                        <Ik.Katman boy={16} />
                        <p className="text-kucuk leading-snug">
                          <b className="font-mono">{k.kutu?.gosterim}</b>
                          {k.kutu?.malzeme ? (
                            <>
                              {" "}
                              — kayıtlı içerik <b>{k.kutu.malzeme}</b>
                              {k.kutu.aciklama ? ` (${k.kutu.aciklama})` : ""}
                              <span className="text-solgun">
                                {k.kutu.adet != null && (
                                  <>
                                    {" "}
                                    · son bilinen <b className="text-yazi">{k.kutu.adet}</b> adet
                                  </>
                                )}
                                {k.kutu.yas_gun != null &&
                                  (k.kutu.taze
                                    ? ` · ${k.kutu.yas_gun} gün önce doğrulandı`
                                    : ` · ${Math.round(k.kutu.yas_gun)} gün önce doğrulandı — eski, yeniden say`)}
                              </span>
                            </>
                          ) : (
                            <span className="text-solgun"> — bu kapta ne var? Bir kez söyle, kalıcı olarak kaydedilsin.</span>
                          )}
                        </p>
                      </div>
                    )}

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
                          {/* Girilen adet burada GÖRÜNMEK zorunda: kullanıcı
                              grup kapanırken "150 tane" dedi, ürün tanınmadı.
                              Sayı görünmezse kayıt çözülürken 1'e düşer ve
                              150 sessizce kaybolur. */}
                          {k.adet > 0 && (
                            <span className="inline-flex items-center gap-1 rounded-sm
                              border border-vurgu bg-vurgu-tint px-2.5 py-0.5 font-semibold
                              text-vurgu">
                              <Ik.Katman boy={11} />
                              <span className="rakam">{k.adet}</span> adet
                            </span>
                          )}
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
                        cocuk={
                          k.tur === "fazla_onay"
                            ? "Stokta karşılığını bul"
                            : k.tur === "kutu"
                              ? "Kapta ne var?"
                              : "Malzeme seç"
                        }
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
                      <label className="flex items-center gap-2 text-mikro text-solgun">
                        adet
                        <input
                          type="number"
                          min={0}
                          defaultValue={k.adet || ""}
                          placeholder="1"
                          onBlur={(e) => void adetKaydet(k, e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                          className="rakam w-24 rounded-sm border border-cizgi-kuvvetli
                            bg-zemin px-3 py-2 text-govde"
                        />
                      </label>
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
                {secili.tur === "kutu"
                  ? `${secili.kutu?.gosterim ?? secili.barkodlar.join(" + ")} — bu kapta ne var?`
                  : `${secili.barkodlar.join(" + ")} — hangi malzeme?`}
              </h2>
              <p className="mt-1 text-kucuk text-solgun">
                {secili.tur === "kutu"
                  ? "Malzeme kabın KALICI kaydına yazılır — gelecek sayımda kap kendi içeriğini söyler. Adet kaydedilmez, her sayımda yeniden sorulur."
                  : "Seçtiğin malzemeye bu barkodlar kalıcı olarak bağlanır; bir daha sorulmaz."}
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
            <ul className="flex flex-1 flex-col gap-2 overflow-y-auto px-4 pb-4">
              {araniyor && <li className="py-3 text-center text-kucuk text-solgun">aranıyor…</li>}
              {!araniyor && sonuc.length === 0 && (
                <li className="py-3 text-center text-kucuk text-solgun">Sonuç yok.</li>
              )}
              {/* Aynı malzemenin farklı seri satırları tek grupta toplanır;
                  başlıkta kaç açık kayıt kaldığı yazar, açınca seriler gelir. */}
              <GrupluListe
                satirlar={sonuc}
                anahtar={q + (sadeceKirli ? "K" : "")}
                onSec={(b) => (secili.tur === "kutu" ? setKutuMalzeme(b) : void bagla(b))}
              />
            </ul>
            <footer className="flex flex-col gap-3 border-t border-cizgi p-4">
              {secili.tur === "kutu" && (
                <div className="flex flex-wrap items-center gap-3">
                  <span className="min-w-0 flex-1 text-kucuk">
                    {kutuMalzeme || secili.kutu?.malzeme ? (
                      <>
                        <b className="font-mono">
                          {kutuMalzeme?.kod ?? secili.kutu?.malzeme}
                        </b>{" "}
                        <span className="text-solgun">
                          {kutuMalzeme?.aciklama ?? secili.kutu?.aciklama}
                        </span>
                        {!kutuMalzeme && (
                          <span className="text-solgun"> · kayıtlı içerik</span>
                        )}
                      </>
                    ) : (
                      <span className="text-solgun">Listeden malzemeyi seç.</span>
                    )}
                  </span>
                  {/* Seri takipli kapta adet SORULMAZ: her adet Tiger'da ayrı
                      satır, sayımı seri numaraları yapar. */}
                  {(kutuMalzeme?.izleme ?? secili.kutu?.izleme) === "seri" ? (
                    <span className="text-kucuk text-bilgi">
                      seri takipli — kap kaydedilir, cihazlar tek tek okutulur
                    </span>
                  ) : (
                    <label className="flex items-center gap-2 text-mikro text-solgun">
                      kaç adet sayıldı
                      <input
                        type="number"
                        min={1}
                        value={kutuAdet}
                        onChange={(e) => setKutuAdet(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && void kutuKaydet()}
                        placeholder={
                          secili.kutu?.adet != null ? `son: ${secili.kutu.adet}` : "adet"
                        }
                        className="rakam w-28 rounded-sm border border-cizgi-kuvvetli
                          bg-zemin px-3 py-2 text-govde"
                      />
                    </label>
                  )}
                  <Dugme
                    cocuk="Kaydet ve say"
                    tur="ana"
                    pasif={
                      !(kutuMalzeme?.kod ?? secili.kutu?.malzeme) ||
                      ((kutuMalzeme?.izleme ?? secili.kutu?.izleme) !== "seri" &&
                        !(Number(kutuAdet) > 0))
                    }
                    tikla={() => void kutuKaydet()}
                  />
                </div>
              )}
              <Dugme cocuk="Vazgeç (Esc)" tikla={() => setSecili(null)} genis />
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}
