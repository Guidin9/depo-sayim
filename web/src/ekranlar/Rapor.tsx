/** 4. ekran — sekme önizlemeleri ve Excel indirme. */
import { useEffect, useState } from "react";
import { api, type RaporOnizleme } from "../api";
import { Bos, Dugme, Panel, Uyari } from "../bilesenler";
import * as Ik from "../ikonlar";

const SEKME = ["Eksik", "Fazla", "Eşleşen", "Tiger Düzeltme", "Barkod Tablosu"] as const;

const ACIKLAMA: Record<string, string> = {
  Eksik: "Okutulmamış beklenen kayıtlar — Tiger'da sayım eksikliği fişi.",
  Fazla: "Karşılığı bulunamayan okutmalar — Tiger'da sayım fazlası fişi.",
  Eşleşen: "Başarılı okutmalar, denetim izi.",
  "Tiger Düzeltme": "Uydurma seri no → okutulan gerçek seri no. Seri düzeltme fişi.",
  "Barkod Tablosu": "Öğrenilen barkodlar — malzeme kartı > Birimler > Barkod alanına yazın.",
};

export default function Rapor({
  oturum,
  tik,
  geri,
  bitir,
  acikMi,
}: {
  oturum: number;
  tik: number;
  geri: () => void;
  bitir: () => void;
  acikMi: boolean;
}) {
  const [veri, setVeri] = useState<RaporOnizleme | null>(null);
  const [aktif, setAktif] = useState<string>("Eksik");
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    api
      .onizleme(oturum)
      .then(setVeri)
      .catch((e) => setHata(e instanceof Error ? e.message : String(e)));
  }, [oturum, tik]);

  if (hata) return <Uyari cocuk={hata} />;
  if (!veri) return <p className="p-8 text-center text-solgun">Rapor hazırlanıyor…</p>;

  const s = veri[aktif];

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5 p-5">
      <header className="flex flex-wrap items-center gap-3">
        <Dugme
          cocuk={
            <>
              <Ik.Geri /> {acikMi ? "Sayıma dön" : "Geri"}
            </>
          }
          tikla={geri}
        />
        <h1 className="font-serif text-4xl leading-[0.95] tracking-tight">Rapor — oturum #{oturum}</h1>
        <div className="ml-auto flex gap-2">
          {acikMi && <Dugme cocuk="Sayımı bitir" tur="tehlike" tikla={bitir} />}
          <a href={api.raporUrl(oturum)} download>
            <Dugme
              cocuk={
                <>
                  <Ik.Indir /> Excel indir
                </>
              }
              tur="ana"
            />
          </a>
        </div>
      </header>

      <div className="flex flex-wrap gap-2">
        {SEKME.map((ad) => (
          <button
            key={ad}
            type="button"
            onClick={() => setAktif(ad)}
            className={`ease-kolay rounded-full border px-5 text-[15px] font-semibold
              transition duration-200
              ${
                aktif === ad
                  ? "border-vurgu bg-vurgu/15 text-vurgu"
                  : "border-cizgi bg-panel text-solgun hover:text-yazi"
              }`}
          >
            {ad}
            <span className="rakam ml-2 text-[13px] opacity-70">{veri[ad]?.toplam ?? 0}</span>
          </button>
        ))}
      </div>

      <Panel
        baslik={aktif}
        sag={<span className="text-[13px] text-solgun">{ACIKLAMA[aktif]}</span>}
        cocuk={
          !s || s.satirlar.length === 0 ? (
            <Bos cocuk="Bu sekmede satır yok." />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-[14px]">
                  <thead>
                    <tr>
                      {s.basliklar.map((b) => (
                        <th
                          key={b}
                          className="border-b border-cizgi px-3 py-2 text-left text-[12px]
                            font-bold tracking-wider text-solgun uppercase whitespace-nowrap"
                        >
                          {b}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {s.satirlar.map((satir, i) => (
                      <tr key={i} className={i % 2 ? "bg-panel2/40" : ""}>
                        {satir.map((h, j) => (
                          <td key={j} className="border-b border-cizgi/50 px-3 py-2 align-top">
                            {j === 0 || typeof h === "number" ? (
                              <span className="rakam font-mono">{h}</span>
                            ) : (
                              String(h ?? "")
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {s.toplam > s.satirlar.length && (
                <p className="mt-3 text-[13px] text-solgun">
                  İlk {s.satirlar.length} satır gösteriliyor, toplam{" "}
                  <b className="text-yazi">{s.toplam}</b>. Tamamı Excel dosyasında.
                </p>
              )}
              {s.dipnot.map((d) => (
                <p key={d} className="mt-2 text-[13px] text-solgun italic">
                  {d}
                </p>
              ))}
            </>
          )
        }
      />
    </div>
  );
}
