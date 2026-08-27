/** 4. ekran — sekme önizlemeleri ve Excel indirme.
 *
 * SEKME dizisi sunucudaki reports.SEKME ile aynı sırada olmalı; yeni sekme
 * eklenirken iki yer birden güncellenir. */
import { useEffect, useState } from "react";
import { api, type RaporOnizleme } from "../api";
import { Bos, Dugme, Panel, Uyari } from "../bilesenler";
import * as Ik from "../ikonlar";

/* `reports.SEKME` ile aynı sırada olmalı — sunucu veriyi sekme adına göre
   veriyor, buradaki liste yalnızca çizim sırasını ve açıklamayı taşıyor. */
const SEKME = [
  "Eksik",
  "Fazla",
  "Eşleşen",
  "Yedek Parça",
  "Tiger Düzeltme",
  "Barkod Tablosu",
  "Etiketler",
] as const;

const ACIKLAMA: Record<string, string> = {
  Eksik: "Okutulmamış beklenen kayıtlar — Tiger'da sayım eksikliği fişi.",
  Fazla: "Karşılığı bulunamayan okutmalar — Tiger'da sayım fazlası fişi.",
  Eşleşen: "Başarılı okutmalar, denetim izi — okutulan barkodlarla birlikte.",
  "Yedek Parça":
    "Yedek parça modunda okutulanlar. Tiger'da aranmadılar; eksik ya da fazla sayılmazlar.",
  "Tiger Düzeltme": "Uydurma seri no → okutulan gerçek seri no. Seri düzeltme fişi.",
  "Barkod Tablosu": "Öğrenilen barkodlar — malzeme kartı > Birimler > Barkod alanına yazın.",
  Etiketler:
    "Kendi bastığımız etiketlerin defteri: hangi numara neye yapıştı. Malzemesi boş olanlar havuzda bekliyor.",
};

export default function Rapor({
  oturum,
  tik,
  geri,
  bitir,
  esleme,
  acikMi,
}: {
  oturum: number;
  tik: number;
  geri: () => void;
  bitir: () => void;
  esleme?: () => void;
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
        <h1 className="text-4xl leading-[0.95] font-extrabold tracking-tight">Rapor — oturum #{oturum}</h1>
        <div className="ml-auto flex gap-2">
          {/* Bitirmeden önceki adım: fazla çıkanların çoğu aslında eksik
              görünen kaydın kendisidir (DEMO_FEEDBACK.md 6). */}
          {acikMi && esleme && <Dugme cocuk="Önce eşleştir" tikla={esleme} />}
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
            className={`ease-kolay rounded-sm border px-5 text-govde font-semibold
              transition duration-200
              ${
                aktif === ad
                  ? "border-vurgu bg-vurgu-tint text-vurgu"
                  : "border-cizgi bg-panel text-solgun hover:text-yazi"
              }`}
          >
            {ad}
            <span className="rakam ml-2 text-kucuk">{veri[ad]?.toplam ?? 0}</span>
          </button>
        ))}
      </div>

      <Panel
        baslik={aktif}
        sag={<span className="text-kucuk text-solgun">{ACIKLAMA[aktif]}</span>}
        cocuk={
          !s || s.satirlar.length === 0 ? (
            <Bos cocuk="Bu sekmede satır yok." />
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-kucuk">
                  <thead>
                    <tr>
                      {s.basliklar.map((b) => (
                        <th
                          key={b}
                          className="border-b border-cizgi px-3 py-2 text-left text-mikro
                            font-bold tracking-wider text-solgun uppercase whitespace-nowrap"
                        >
                          {b}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {s.satirlar.map((satir, i) => (
                      <tr key={i} className={i % 2 ? "bg-panel2" : ""}>
                        {satir.map((h, j) => (
                          <td key={j} className="border-b border-cizgi px-3 py-2 align-top">
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
                <p className="mt-3 text-kucuk text-solgun">
                  İlk {s.satirlar.length} satır gösteriliyor, toplam{" "}
                  <b className="text-yazi">{s.toplam}</b>. Tamamı Excel dosyasında.
                </p>
              )}
              {s.dipnot.map((d) => (
                <p key={d} className="mt-2 text-kucuk text-solgun italic">
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
