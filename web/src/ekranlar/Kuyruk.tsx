/** 3. ekran — çözülmeyi bekleyen gruplar.
 *
 * Kayıtlar rafa göre gruplanır: "hangi rafta okutmuştuk" sorusunun cevabı
 * ekranda hazır dursun. Not ve fotoğraf isteğe bağlı hatırlatıcılardır —
 * fotoğraf telefondan da yüklenebilir (aynı Wi-Fi, telefon monitörü).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type AramaSonucu, type KuyrukSatiri } from "../api";
import { Bos, Dugme, Kod, Panel, Uyari } from "../bilesenler";
import * as Ik from "../ikonlar";
import { kucult } from "../foto";
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
  const [sonuc, setSonuc] = useState<AramaSonucu[]>([]);
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
    setQ("");
    setSonuc([]);
    setTimeout(() => aramaRef.current?.focus(), 30);
  }, [secili]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setSonuc([]);
      return;
    }
    let iptal = false;
    setAraniyor(true);
    const zaman = setTimeout(async () => {
      try {
        const r = await api.ara(oturum, q.trim());
        if (!iptal) setSonuc(r);
      } finally {
        if (!iptal) setAraniyor(false);
      }
    }, 180);
    return () => {
      iptal = true;
      clearTimeout(zaman);
    };
  }, [q, oturum]);

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

  async function fazlaYaz(k: KuyrukSatiri) {
    if (!confirm("Bu ürünün Tiger'da karşılığı yok mu? Fazla olarak raporlanacak.")) return;
    await api.kuyrukFazla(k.id);
    bip("uyari");
    setSecili(null);
    await tazele();
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
        <h1 className="font-serif text-4xl leading-[0.95] tracking-tight">Kuyruk</h1>
        <span className="ml-auto text-[15px] text-solgun">{kuyruk.length} çözülmemiş grup</span>
      </header>

      {hata && <Uyari cocuk={hata} />}

      {kuyruk.length === 0 ? (
        <Panel cocuk={<Bos cocuk="Kuyruk boş — çözülmeyi bekleyen grup yok." />} />
      ) : (
        <>
          {telefonAdresi && (
            <p className="text-[13px] text-solgun">
              <Ik.Kamera boy={15} className="inline align-text-bottom" /> Telefondan
              fotoğraf eklemek için aynı Wi-Fi'dan{" "}
              <b className="font-mono text-yazi">{telefonAdresi}</b> adresini açın (sunucu{" "}
              <span className="font-mono">baslat.bat</span> ile başlatılmış olmalı).
            </p>
          )}

          {raflar.map((raf) => (
            <section key={raf} className="flex flex-col gap-3">
              <h2 className="text-[13px] font-bold tracking-wider uppercase">
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
                    className={`rounded-2xl border bg-panel p-4 ${
                      k.beklet ? "border-bilgi/50" : "border-cizgi"
                    }`}
                  >
                    <div className="flex flex-wrap items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap gap-2">
                          {k.barkodlar.map((b) => (
                            <span
                              key={b}
                              className="rounded-full border border-cizgi bg-panel2 px-2.5 py-1
                                font-mono text-[14px]"
                            >
                              {b}
                            </span>
                          ))}
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-[12px]
                          text-solgun">
                          <span>{k.ts}</span>
                          {k.beklet && (
                            <span
                              title="Telefonda fotoğraflanıp ertelendi — çözümü sana bırakıldı"
                              className="rounded-full border border-bilgi/40 bg-bilgi/10 px-2.5 py-0.5
                                font-semibold text-bilgi"
                            >
                              <span className="inline-flex items-center gap-1">
                                <Ik.Duraklat boy={11} /> telefondan ertelendi
                              </span>
                            </span>
                          )}
                        </div>
                      </div>
                      <Dugme cocuk="Malzeme seç" tur="ana" tikla={() => setSecili(k)} />
                      <Dugme cocuk="Fazla olarak yaz" tur="tehlike" tikla={() => void fazlaYaz(k)} />
                    </div>

                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <input
                        defaultValue={k.not_}
                        placeholder="not (isteğe bağlı): siyah kutu, üst raf, HP yazıyor…"
                        onBlur={(e) => void notKaydet(k, e.target.value.trim())}
                        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                        className="min-w-[240px] flex-1 rounded-xl border border-cizgi bg-zemin
                          px-3 py-2 text-[14px] focus:border-vurgu focus:outline-none"
                      />
                      <label
                        className="cursor-pointer rounded-full border border-cizgi bg-panel2 px-4
                          py-2 text-[14px] font-semibold hover:bg-cizgi"
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
                          className="h-12 w-12 overflow-hidden rounded-xl border border-cizgi"
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

      {buyutulen !== null && (
        <div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-black/90 p-4"
          onClick={(e) => e.target === e.currentTarget && setBuyutulen(null)}
        >
          <img
            src={api.fotoUrl(buyutulen)}
            alt="kuyruk fotoğrafı"
            className="max-h-[80vh] max-w-full rounded-2xl"
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
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 p-4 sm:p-10"
          onClick={(e) => e.target === e.currentTarget && setSecili(null)}
        >
          <div className="cam flex max-h-full w-full max-w-2xl flex-col rounded-2xl">
            <header className="border-b border-cizgi p-4">
              <h2 className="text-lg font-bold">
                {secili.barkodlar.join(" + ")} — hangi malzeme?
              </h2>
              <p className="mt-1 text-[13px] text-solgun">
                Seçtiğin malzemeye bu barkodlar kalıcı olarak bağlanır; bir daha sorulmaz.
              </p>
              {secili.not_ && <p className="mt-2 text-[13px] text-uyari">not: {secili.not_}</p>}
              {secili.fotolar.length > 0 && (
                <div className="mt-2 flex gap-2">
                  {secili.fotolar.map((f) => (
                    <img
                      key={f}
                      src={api.fotoUrl(f)}
                      alt="kuyruk fotoğrafı"
                      className="h-20 w-20 rounded-xl border border-cizgi object-cover"
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
                placeholder="kod veya açıklama ara… (en az 2 harf)"
                className="w-full rounded-xl border border-cizgi bg-zemin px-4 py-3 text-[16px]
                  focus:border-vurgu focus:outline-none"
              />
            </div>
            <ul className="flex-1 overflow-y-auto px-4 pb-4">
              {araniyor && <li className="py-3 text-center text-[14px] text-solgun">aranıyor…</li>}
              {!araniyor && q.trim().length >= 2 && sonuc.length === 0 && (
                <li className="py-3 text-center text-[14px] text-solgun">Sonuç yok.</li>
              )}
              {sonuc.map((b) => (
                <li key={b.id}>
                  <button
                    type="button"
                    onClick={() => void bagla(b)}
                    className="mb-2 w-full rounded-xl border border-cizgi bg-panel2 px-3 py-3
                      text-left transition hover:border-vurgu hover:bg-vurgu/10"
                  >
                    <div className="flex flex-wrap items-baseline gap-2">
                      <b className="font-mono text-vurgu">{b.kod}</b>
                      <span className="text-[14px]">{b.aciklama}</span>
                      {b.kirli === 1 && (
                        <span className="rounded border border-uyari/40 bg-uyari/15 px-1.5 text-[11px] font-bold text-uyari">
                          <span className="inline-flex items-center gap-1">
                            <Ik.Uyari boy={11} /> uydurma kayıt
                          </span>
                        </span>
                      )}
                      {b.sayildi === 1 && (
                        <span className="rounded border border-ok/40 bg-ok/15 px-1.5 text-[11px] font-bold text-ok">
                          <span className="inline-flex items-center gap-1">
                            <Ik.Onay boy={11} /> bu oturumda sayıldı
                          </span>
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-[12px] text-solgun">
                      <Kod cocuk={b.seri || "—"} /> · {b.izleme} · {b.miktar} {b.birim}
                    </div>
                  </button>
                </li>
              ))}
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
