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

  useEffect(() => {
    void api.oturumlar().then(setListe);
  }, [tik]);

  async function kartYazdir() {
    const html = await api.komutKarti(
      raflar
        .split(/[,\n;]/)
        .map((r) => r.trim())
        .filter(Boolean),
    );
    const p = window.open("", "_blank");
    if (!p) return;
    p.document.write(html);
    p.document.close();
    p.focus();
    setTimeout(() => p.print(), 400);
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
        <h1 className="font-serif text-4xl leading-[0.95] tracking-tight">Oturum geçmişi</h1>
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
                  className="flex flex-wrap items-center gap-3 rounded-xl border border-cizgi
                    bg-panel2 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="font-bold">
                      Oturum #{o.id} · Ambar {o.ambar}
                      {o.durum === "acik" && (
                        <span className="ml-2 rounded border border-ok/40 bg-ok/15 px-1.5 text-[11px] text-ok">
                          açık
                        </span>
                      )}
                    </div>
                    <div className="rakam mt-1 text-[13px] text-solgun">
                      {o.basla?.slice(0, 16).replace("T", " ")}
                      {o.bitir && ` → ${o.bitir.slice(11, 16)}`} · {o.dosya_adi ?? "—"}
                    </div>
                  </div>
                  <div className="rakam flex gap-4 text-[13px]">
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
        baslik="Komut barkodu kartı"
        cocuk={
          <div className="flex flex-col gap-3">
            <p className="text-[14px] text-solgun">
              Yazdır, kes, laminatla. Sahada klavyeye dokunmadan komut vermek için. Raf
              barkodlarını virgülle ayırın.
            </p>
            <input
              value={raflar}
              onChange={(e) => setRaflar(e.target.value)}
              placeholder="A1, A2, B1…"
              className="w-full rounded-xl border border-cizgi bg-zemin px-4 py-3 font-mono
                text-[15px] focus:border-vurgu focus:outline-none"
            />
            <Dugme
              cocuk={
                <>
                  <Ik.Yazdir /> Kartı üret ve yazdır
                </>
              }
              tur="ana"
              tikla={() => void kartYazdir()}
            />
          </div>
        }
      />
    </div>
  );
}
