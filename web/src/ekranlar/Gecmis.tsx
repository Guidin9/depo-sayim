/** 5. ekran — geçmiş sayımlar, tekrar rapor indirme, komut kartı üretimi. */
import { useEffect, useState } from "react";
import { api, type OturumOzeti } from "../api";
import { Bos, Dugme, Panel } from "../bilesenler";
import * as Ik from "../ikonlar";

export default function Gecmis({
  tik,
  geri,
  rapora: raporaGit,
}: {
  tik: number;
  geri: () => void;
  rapora: (oturum: number) => void;
}) {
  const [liste, setListe] = useState<OturumOzeti[]>([]);
  const [raflar, setRaflar] = useState("A1, A2, B1, B2");
  const [kopya, setKopya] = useState(1);
  const [atla, setAtla] = useState(0);

  useEffect(() => {
    void api.oturumlar().then(setListe);
  }, [tik]);

  const rafListesi = () =>
    raflar
      .split(/[,\n;]/)
      .map((r) => r.trim())
      .filter(Boolean);

  function yazdirHtml(html: string) {
    const p = window.open("", "_blank");
    if (!p) return;
    p.document.write(html);
    p.document.close();
    p.focus();
    setTimeout(() => p.print(), 400);
  }

  async function kartYazdir() {
    yazdirHtml(await api.komutKarti(rafListesi()));
  }

  async function rafEtiketYazdir() {
    yazdirHtml(await api.rafEtiketi(rafListesi(), kopya, atla));
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
                    <span>
                      <b className="text-ok">{o.okutulan}</b> okutulan
                    </span>
                    <span>
                      <b className={o.fazla ? "text-hata" : ""}>{o.fazla}</b> fazla
                    </span>
                    <span>
                      <b className={o.kuyruk ? "text-uyari" : ""}>{o.kuyruk}</b> kuyruk
                    </span>
                  </div>
                  <Dugme cocuk="Rapor" tikla={() => raporaGit(o.id)} />
                  <a href={api.raporUrl(o.id)} download>
                    <Dugme
                      cocuk={
                        <>
                          <Ik.Indir /> Excel
                        </>
                      }
                    />
                  </a>
                </li>
              ))}
            </ul>
          )
        }
      />

      <Panel
        baslik="Komut ve raf barkodları"
        cocuk={
          <div className="flex flex-col gap-3">
            <p className="text-kucuk text-solgun">
              Raf adlarını virgülle ayırın. İki çıktı: <b>komut kartı</b> düz kâğıda
              basılıp kesilir ve laminatlanır (komutlar + raf barkodları birlikte);{" "}
              <b>raf etiketi</b> ise yapışkanlı 24&apos;lük A4 sayfaya basılıp doğrudan
              rafa yapıştırılır.
            </p>
            <input
              value={raflar}
              onChange={(e) => setRaflar(e.target.value)}
              placeholder="A1, A2, B1…"
              className="w-full rounded-sm border border-cizgi bg-zemin px-4 py-3 font-mono
                text-govde focus:border-vurgu focus:outline-none"
            />
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex flex-col gap-1">
                <span className="text-mikro font-bold tracking-wider text-solgun uppercase">
                  Her raftan kaç kopya
                </span>
                <input
                  type="number"
                  min={1}
                  max={24}
                  value={kopya}
                  onChange={(e) => setKopya(Math.max(1, Number(e.target.value) || 1))}
                  className="w-24 rounded-sm border border-cizgi bg-zemin px-4 py-3
                    font-mono text-govde focus:border-vurgu focus:outline-none"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-mikro font-bold tracking-wider text-solgun uppercase">
                  Kaçıncı hücreden başla
                </span>
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={atla}
                  onChange={(e) => setAtla(Math.min(23, Math.max(0, Number(e.target.value) || 0)))}
                  className="w-24 rounded-sm border border-cizgi bg-zemin px-4 py-3
                    font-mono text-govde focus:border-vurgu focus:outline-none"
                />
              </label>
              <span className="text-kucuk text-solgun">
                Kopya ve başlangıç hücresi yalnızca yapışkanlı raf etiketi içindir —
                yarım kalmış sayfayı israf etmeyin.
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Dugme
                cocuk={
                  <>
                    <Ik.Yazdir /> Yapışkanlı raf etiketi yazdır
                  </>
                }
                tur="ana"
                tikla={() => void rafEtiketYazdir()}
              />
              <Dugme
                cocuk={
                  <>
                    <Ik.Yazdir /> Komut kartı (laminat) yazdır
                  </>
                }
                tikla={() => void kartYazdir()}
              />
            </div>
          </div>
        }
      />
    </div>
  );
}
