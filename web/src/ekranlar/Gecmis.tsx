/** 5. ekran — geçmiş sayımlar ve tekrar rapor indirme.
 *
 * Komut kartı ve raf barkodları buradan ALINDI (2026-08-27): ikisi de basılan
 * kâğıt ve oturumla ilgileri yok. Artık basılan her şey tek ekranda —
 * `ekranlar/Etiket.tsx`, üst menüdeki **Barkod** düğmesi. Orası açık oturum
 * istemiyor, yani Tiger raporu yüklenmeden de barkod bastırılabiliyor.
 */
import { useEffect, useState } from "react";
import { api, type OturumOzeti } from "../api";
import { Bos, Dugme, IndirBaglantisi, Panel } from "../bilesenler";
import * as Ik from "../ikonlar";

export default function Gecmis({
  tik,
  geri,
  rapora: raporaGit,
  sayima,
}: {
  tik: number;
  geri: () => void;
  rapora: (oturum: number) => void;
  /** Oturum geri açıldıktan sonra sayıma dönüş. Verilmezse düğme çizilmez. */
  sayima?: () => void;
}) {
  const [liste, setListe] = useState<OturumOzeti[]>([]);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    void api.oturumlar().then(setListe);
  }, [tik]);

  /* Kazara kapanan oturumu geri açar. Yeni oturum açmak çözüm DEĞİL: beklenen
     kayıtlarla eşleşme oturum bazlı, o ana kadar sayılan her şey "eksik"
     olurdu. ##BITIR## komut kartında basılı ve depo sayımı günlerce sürüyor. */
  async function yenidenAc(id: number) {
    if (!window.confirm(`Oturum #${id} yeniden açılsın mı?

` +
        "Sayılan her şey korunur, sayıma kaldığı yerden devam edilir."))
      return;
    try {
      setHata(null);
      await api.oturumYenidenAc(id);
      setListe(await api.oturumlar());
      sayima?.();
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5 p-5">
      <header className="flex items-center gap-4">
        <Dugme
          cocuk={
            <>
              <Ik.Geri /> Geri
            </>
          }
          tikla={geri}
        />
        <h1 className="text-4xl leading-[0.95] font-extrabold tracking-tight">Oturum geçmişi</h1>
      </header>

      {hata && (
        <div className="rounded-sm border border-hata bg-hata-tint px-4 py-3 text-kucuk
          text-hata">
          {hata}
        </div>
      )}

      <Panel
        baslik="Sayımlar"
        cocuk={
          liste.length === 0 ? (
            <Bos cocuk="Henüz sayım yapılmadı." />
          ) : (
            <ul className="flex flex-col gap-2">
              {liste.map((o) => (
                <li
                  key={o.id}
                  className="flex flex-wrap items-center gap-3 rounded-sm border border-cizgi
                    bg-panel2 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="font-bold">
                      Oturum #{o.id} · Ambar {o.ambar}
                      {o.durum === "acik" && (
                        <span className="ml-2 rounded border border-ok bg-ok-tint px-1.5 text-mikro text-ok">
                          açık
                        </span>
                      )}
                    </div>
                    <div className="rakam mt-1 text-kucuk text-solgun">
                      {o.basla?.slice(0, 16).replace("T", " ")}
                      {o.bitir && ` → ${o.bitir.slice(11, 16)}`} · {o.dosya_adi ?? "—"}
                    </div>
                  </div>
                  <div className="rakam flex gap-4 text-kucuk">
                    {/* Adet bazında — Sayım ekranındaki sayaçla aynı sayı.
                        Payda olmadan "171" tek başına anlamsız: 1075'in 171'i
                        ile 200'ün 171'i aynı şeyi söylemiyor. */}
                    <span>
                      <b className="text-ok">{o.okutulan}</b>
                      <span className="text-solgun"> / {o.toplam}</span> adet
                    </span>
                    <span>
                      <b className={o.fazla ? "text-hata" : ""}>{o.fazla}</b> fazla
                    </span>
                    <span>
                      <b className={o.kuyruk ? "text-uyari" : ""}>{o.kuyruk}</b> kuyruk
                    </span>
                  </div>
                  {o.durum !== "acik" && (
                    <Dugme cocuk="Yeniden aç" tikla={() => void yenidenAc(o.id)} />
                  )}
                  <Dugme cocuk="Rapor" tikla={() => raporaGit(o.id)} />
                  <IndirBaglantisi
                    yol={api.raporUrl(o.id)}
                    cocuk={
                      <>
                        <Ik.Indir /> Excel
                      </>
                    }
                  />
                </li>
              ))}
            </ul>
          )
        }
      />
    </div>
  );
}
