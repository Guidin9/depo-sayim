/** 1. ekran — Tiger raporunu yükle, sayım dışı filtreyi onayla, ambarı seç. */
import { useEffect, useRef, useState } from "react";
import { api, type Ambar, type Kural, type Ozet } from "../api";
import { Baslik, Bos, Dugme, Kod, Panel, SayacKutu, Uyari } from "../bilesenler";
import * as Ik from "../ikonlar";

const IZLEME_ADI: Record<string, string> = {
  seri: "Seri No.",
  lot: "Lot (Parti) No.",
  yok: "İzleme yok",
};

export default function Kurulum({ basla }: { basla: (oturumId: number) => void }) {
  const [ozet, setOzet] = useState<Ozet | null>(null);
  const [kurallar, setKurallar] = useState<Kural[]>([]);
  const [ambarlar, setAmbarlar] = useState<Ambar[]>([]);
  const [gecmisYukleme, setGecmisYukleme] = useState<
    { id: number; dosya_adi: string; ts: string; satir: number }[]
  >([]);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const [suruklu, setSuruklu] = useState(false);
  const dosyaRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    void api.yuklemeler().then(setGecmisYukleme).catch(() => undefined);
  }, []);

  async function yukle(dosya: File, ekle = false) {
    setYukleniyor(true);
    setHata(null);
    try {
      const o = await api.yukle(dosya, ekle && ozet ? ozet.yukleme : undefined);
      setOzet(o);
      setKurallar(o.kurallar ?? []);
      setAmbarlar(await api.ambarlar(o.yukleme));
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    } finally {
      setYukleniyor(false);
    }
  }

  async function mevcuduSec(id: number) {
    setYukleniyor(true);
    try {
      const o = await api.yuklemeOzeti(id);
      setOzet(o);
      setKurallar(o.kurallar ?? []);
      setAmbarlar(await api.ambarlar(id));
    } finally {
      setYukleniyor(false);
    }
  }

  async function kuralDegistir(k: Kural, aktif: boolean) {
    if (!ozet) return;
    setKurallar((eski) => eski.map((x) => (x.id === k.id ? { ...x, aktif } : x)));
    const yeni = await api.kurallariGuncelle(ozet.yukleme, [{ id: k.id, aktif }]);
    setKurallar(yeni);
    setAmbarlar(await api.ambarlar(ozet.yukleme));
  }

  async function ambarSec(ambar: string) {
    if (!ozet) return;
    setHata(null);
    try {
      const o = await api.oturumAc(ozet.yukleme, ambar);
      basla(o.id);
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }

  const haricToplam = kurallar.filter((k) => k.aktif).reduce((t, k) => t + k.satir, 0);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5 p-5">
      <Baslik
        cocuk="Sayım kurulumu"
        alt={
          <>
            Tiger'ın <b>Lot / Seri Envanter Raporu</b>'nu yükleyin. Adet bazlı{" "}
            <b>Envanter Raporu</b>'nu ikinci dosya olarak ekleyebilirsiniz.
          </>
        }
      />

      {hata && <Uyari cocuk={hata} />}

      {!ozet && (
        <>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setSuruklu(true);
            }}
            onDragLeave={() => setSuruklu(false)}
            onDrop={(e) => {
              e.preventDefault();
              setSuruklu(false);
              const d = e.dataTransfer.files?.[0];
              if (d) void yukle(d);
            }}
            onClick={() => dosyaRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && dosyaRef.current?.click()}
            className={`ease-kolay flex cursor-pointer flex-col items-center gap-2 rounded-sm
              border-2 border-dashed p-12 text-center transition duration-200
              ${suruklu ? "border-vurgu bg-vurgu-tint" : "border-cizgi bg-panel/60 hover:border-solgun"}`}
          >
            <Ik.Yukle boy={40} className="text-solgun" />
            <div className="text-3xl leading-tight font-bold">
              {yukleniyor ? "Okunuyor…" : "Rapor dosyasını buraya bırakın"}
            </div>
            <div className="text-kucuk text-solgun">.xlsx veya .json — ya da tıklayıp seçin</div>
            <input
              ref={dosyaRef}
              type="file"
              accept=".xlsx,.xls,.xlsm,.json"
              className="hidden"
              onChange={(e) => {
                const d = e.target.files?.[0];
                if (d) void yukle(d);
                e.target.value = "";
              }}
            />
          </div>

          {gecmisYukleme.length > 0 && (
            <Panel
              baslik="Daha önce yüklenenler"
              cocuk={
                <ul className="flex flex-col gap-2">
                  {gecmisYukleme.slice(0, 5).map((y) => (
                    <li key={y.id}>
                      <button
                        type="button"
                        onClick={() => void mevcuduSec(y.id)}
                        className="ease-kolay flex w-full items-center justify-between gap-3
                          rounded-sm border border-cizgi bg-panel2 px-4 py-3 text-left
                          transition duration-200 hover:bg-cizgi"
                      >
                        <span className="font-semibold">{y.dosya_adi}</span>
                        <span className="rakam text-kucuk text-solgun">
                          {y.satir} satır · {y.ts.slice(0, 16).replace("T", " ")}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              }
            />
          )}
        </>
      )}

      {ozet && (
        <>
          <Panel
            baslik="Yükleme özeti"
            sag={
              <span className="text-kucuk text-solgun">
                {ozet.dosya} · yükleme #{ozet.yukleme}
              </span>
            }
            cocuk={
              <div className="flex flex-col gap-5">
                <div className="flex flex-wrap justify-around gap-4">
                  <SayacKutu etiket="satır" deger={ozet.satir} buyuk />
                  {ozet.izleme.map((i) => (
                    <SayacKutu
                      key={i.izleme}
                      etiket={`${IZLEME_ADI[i.izleme] ?? i.izleme} · ${i.malzeme} malzeme`}
                      deger={i.izleme === "seri" ? i.satir : `${i.adet ?? 0} ad`}
                      buyuk
                    />
                  ))}
                  <SayacKutu etiket="kirli seri kaydı" deger={ozet.kirli} vurgu="uyari" buyuk />
                </div>

                {ozet.kirli > 0 && (
                  <div className="rounded-sm border border-uyari bg-uyari-tint p-4">
                    <p className="text-kucuk font-semibold text-uyari">
                      {ozet.kirli} seri numarası gerçek görünmüyor — sayım farkını kapatmak için
                      açılmış kayıtlar. Doğru barkodu okuttuğunuzda bunlar{" "}
                      <b>Tiger Düzeltme</b> sekmesine düşecek.
                    </p>
                    <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-kucuk text-solgun">
                      {ozet.kirli_sebep.map((s) => (
                        <li key={s.sebep}>
                          <span className="rakam font-bold text-yazi">{s.satir}</span> {s.sebep}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="flex flex-wrap gap-3">
                  <Dugme
                    cocuk="İkinci rapor ekle (Envanter Raporu)"
                    tikla={() => dosyaRef.current?.click()}
                  />
                  <Dugme
                    cocuk="Başka dosya yükle"
                    tikla={() => {
                      setOzet(null);
                      setAmbarlar([]);
                    }}
                  />
                  <input
                    ref={dosyaRef}
                    type="file"
                    accept=".xlsx,.xls,.xlsm,.json"
                    className="hidden"
                    onChange={(e) => {
                      const d = e.target.files?.[0];
                      if (d) void yukle(d, true);
                      e.target.value = "";
                    }}
                  />
                </div>
              </div>
            }
          />

          <Panel
            baslik="Sayım dışı kalemler"
            sag={
              <span className="text-kucuk text-solgun">
                <span className="rakam font-bold text-yazi">{haricToplam}</span> satır çıkarılacak
              </span>
            }
            cocuk={
              <div className="flex flex-col gap-3">
                <p className="text-kucuk text-solgun">
                  Lisans, hizmet, nakliye gibi kalemler fiziksel nesne değildir; sayılmazsa
                  hepsi "eksik" görünür. <b>Kuralı kapatmadan önce etkilediği satır sayısına
                  bakın</b> — desen beklenmedik bir malzemeyi de yakalayabilir.
                </p>
                <ul className="flex flex-col gap-2">
                  {kurallar.map((k) => (
                    <li
                      key={k.id}
                      className={`flex items-center gap-3 rounded-sm border px-3 py-2
                        ${k.satir ? "border-cizgi bg-panel2" : "border-cizgi text-solgun-hafif"}`}
                    >
                      <input
                        id={`kural-${k.id}`}
                        type="checkbox"
                        checked={k.aktif}
                        onChange={(e) => void kuralDegistir(k, e.target.checked)}
                        className="h-5 w-5 accent-[var(--color-vurgu)]"
                      />
                      <label htmlFor={`kural-${k.id}`} className="flex-1 cursor-pointer">
                        <Kod cocuk={k.desen} />
                        <span className="ml-2 text-mikro text-solgun">
                          {k.tip === "tur" ? "malzeme türünde" : "açıklamada"} geçenler
                        </span>
                      </label>
                      <span className="rakam text-kucuk text-solgun">
                        {k.satir ? `${k.satir} satır · ${k.adet} adet` : "eşleşme yok"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            }
          />

          <Panel
            baslik="Ambar seçin"
            cocuk={
              ambarlar.length === 0 ? (
                <Bos cocuk="Bu yüklemede ambar bulunamadı." />
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {ambarlar.map((a) => (
                    <button
                      key={a.ambar}
                      type="button"
                      onClick={() => void ambarSec(a.ambar)}
                      className="ease-kolay rounded-sm border border-cizgi bg-panel2 p-4
                        text-left transition duration-200 hover:border-vurgu hover:bg-vurgu-tint"
                    >
                      <div className="text-3xl leading-tight font-bold">
                        Ambar {a.ambar}
                        {a.ambar === "?" && (
                          <span className="ml-2 text-mikro font-normal text-uyari">
                            ambar bilgisi boş
                          </span>
                        )}
                      </div>
                      <div className="rakam mt-2 text-kucuk text-solgun">
                        {a.satir} satır · {a.malzeme} malzeme · {a.adet} adet
                      </div>
                      <div className="rakam mt-1 text-kucuk text-solgun">
                        {a.kirli} kirli kayıt · {a.haric} sayım dışı
                      </div>
                      <div className="mt-3 flex items-center gap-2 text-kucuk font-bold
                        text-vurgu">
                        Sayımı başlat <Ik.OkSag boy={16} />
                      </div>
                    </button>
                  ))}
                </div>
              )
            }
          />
        </>
      )}
    </div>
  );
}
