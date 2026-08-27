/** Etiket basımı ve defteri (CLAUDE.md 12).
 *
 * Depoda yazıcı yok: etiketler ofiste toplu basılıp elde götürülüyor.
 *
 * Ekrandaki sayılar TAVAN, hedef değil. Kesin bir sayı veremeyiz: depodaki
 * ürünlerin birçoğunun kutusunda üretici kodu ya da seri numarası zaten basılı,
 * Tiger'a girilmemiş olsa bile — onlara etiket gerekmez. Bu yüzden ekran karar
 * vermez, öneri yapar; adedi kullanıcı seçer.
 */
import { useEffect, useState } from "react";
import { api, type BasimOzeti, type EtiketIhtiyaci, type EtiketSatiri } from "../api";
import { Bos, Dugme, Panel, Uyari } from "../bilesenler";
import * as Ik from "../ikonlar";

type Tur = "malzeme" | "seri" | "kutu";
type Duzen = "a4" | "rulo";
type Kapsam = "eksik" | "hepsi" | "bos";
/* Kap etiketi iki yoldan basılır: yeni anonim numara ya da içeriği belli
   kapların YENİDEN basımı. Yeniden basım numara tüketmez — kap etiketi
   değişse de kod aynı kalmalı, yoksa depoda aynı kap için iki numara dolaşır
   (KUTU_TASARIM.md 7). */
type KutuKapsam = "yeni" | "tanimli";

const A4_HUCRE = 24; // 3 sütun x 8 satır

/* Üç tür de kendi adıyla görünür. "Malzeme değilse Seri" yazmak, üçüncü sınıf
   eklendiği anda kap etiketlerini defterde "Seri" gösterirdi. */
const TUR_ADI: Record<string, string> = {
  malzeme: "Malzeme",
  seri: "Seri",
  kutu: "Kap",
};

export default function Etiket({
  yukleme,
  ambar,
  tik,
  geri,
}: {
  yukleme: number;
  ambar: string;
  tik: number;
  geri: () => void;
}) {
  const [ihtiyac, setIhtiyac] = useState<EtiketIhtiyaci | null>(null);
  const [defter, setDefter] = useState<EtiketSatiri[]>([]);
  const [basimlar, setBasimlar] = useState<BasimOzeti[]>([]);
  const [tur, setTur] = useState<Tur>("seri");
  const [adet, setAdet] = useState(48);
  const [mAdet, setMAdet] = useState(A4_HUCRE);
  const [kopya, setKopya] = useState(1);
  const [kapsam, setKapsam] = useState<Kapsam>("eksik");
  const [kutuKapsam, setKutuKapsam] = useState<KutuKapsam>("yeni");
  const [kAdet, setKAdet] = useState(A4_HUCRE);
  const [kutuSayisi, setKutuSayisi] = useState(0);
  const [duzen, setDuzen] = useState<Duzen>("a4");
  const [atla, setAtla] = useState(0);
  const [q, setQ] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        setIhtiyac(await api.etiketIhtiyac(yukleme, ambar));
        setBasimlar(await api.basimlar());
        setKutuSayisi((await api.kutular(undefined, true)).length);
      } catch (e) {
        setHata(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [yukleme, ambar, tik]);

  useEffect(() => {
    const zaman = setTimeout(() => {
      void api.etiketler(undefined, q.trim() || undefined).then(setDefter, () => {});
    }, 180);
    return () => clearTimeout(zaman);
  }, [q, tik]);

  /* Komut kartındaki akışın aynısı: sunucudan hazır HTML gelir, yeni sekmede
     açılıp yazdırma penceresi çağrılır. Yazdırma CSS'i o HTML'in içinde. */
  async function yazdir() {
    setHata(null);
    setMesgul(true);
    try {
      const html = await api.etiketBas({
        tur,
        adet: tur === "seri" ? adet : tur === "kutu" ? kAdet : mAdet,
        kopya: tur === "malzeme" ? kopya : 1,
        kapsam:
          tur === "malzeme"
            ? kapsam
            : tur === "kutu" && kutuKapsam === "tanimli"
              ? "tanimli"
              : undefined,
        yukleme: tur === "malzeme" ? yukleme : undefined,
        ambar: tur === "malzeme" ? ambar : undefined,
        duzen,
        atla: duzen === "a4" ? atla : 0,
      });
      const p = window.open("", "_blank");
      if (!p) {
        setHata("Tarayıcı yeni sekmeyi engelledi — açılır pencerelere izin verin.");
        return;
      }
      p.document.write(html);
      p.document.close();
      p.focus();
      setTimeout(() => p.print(), 400);
      setIhtiyac(await api.etiketIhtiyac(yukleme, ambar));
      setBasimlar(await api.basimlar());
      setDefter(await api.etiketler(undefined, q.trim() || undefined));
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    } finally {
      setMesgul(false);
    }
  }

  const bagli = defter.filter((e) => e.malzeme).length;
  const malzemeHavuz =
    kapsam === "eksik" ? (ihtiyac?.malzeme.eksik ?? 0) : (ihtiyac?.malzeme.tekil ?? 0);
  const malzemeToplam =
    (kapsam === "bos" ? mAdet : Math.min(mAdet, malzemeHavuz)) * kopya;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5 p-5">
      <header className="flex items-center gap-4">
        <Dugme
          cocuk={
            <>
              <Ik.Geri /> Geri
            </>
          }
          tikla={geri}
        />
        <h1 className="text-4xl leading-[0.95] font-extrabold tracking-tight">Etiket basımı</h1>
      </header>

      {hata && <Uyari cocuk={hata} />}

      <Panel
        baslik={`Ambar ${ambar} — en fazla ne kadar gerekebilir`}
        cocuk={
          !ihtiyac ? (
            <Bos cocuk="Hesaplanıyor…" />
          ) : (
            <div className="flex flex-col gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Kutu
                  Ikon={Ik.Etiket}
                  baslik="Malzeme etiketi"
                  deger={ihtiyac.malzeme.eksik}
                  birim={`farklı kod · ${ihtiyac.malzeme.basili} / ${ihtiyac.malzeme.tekil} basılmış`}
                  aciklama={
                    <>
                      Malzeme kodunun taranabilir hâli, raf gözüne yapışır. Kod başına{" "}
                      <b>bir</b> numara. Bunlardan{" "}
                      <b className="rakam">{ihtiyac.malzeme.barkodsuz}</b> tanesinin kodu
                      boşluk ya da Türkçe karakter içeriyor — o kodlar hiçbir zaman barkod
                      olamaz, etiket onlarda kesin gerekli. Basımda başa alınırlar.
                    </>
                  }
                />
                <Kutu
                  Ikon={Ik.Barkod}
                  baslik="Seri etiketi"
                  deger={ihtiyac.seri.ust_sinir}
                  birim={`tavan · havuzda ${ihtiyac.seri.havuzda} boş`}
                  aciklama={
                    <>
                      Basıldığında hiçbir ürüne ait değil; hangi ürüne yapıştığı okutma
                      anında belli olur. Bu ambarda {ihtiyac.seri.kirli_kayit} uydurma seri
                      kaydı var.
                    </>
                  }
                />
              </div>
              <p
                className="rounded-sm border border-uyari bg-uyari-tint p-4 text-kucuk
                  leading-snug"
              >
                <b>Bu sayılar hedef değil, tavan.</b> Depodaki ürünlerin birçoğunun
                kutusunda üretici parça numarası ya da seri numarası zaten basılı — Tiger'a
                girilmemiş olsa bile. Onlar okutulduğunda etiket hiç gerekmez. Gerçek
                ihtiyaç ancak bir raf sayıldıktan sonra ortaya çıkar; bu yüzden az basıp
                devam etmek en doğrusu. Numaralar tükenmez, sonraki basım kaldığı yerden
                sürer.
              </p>
            </div>
          )
        }
      />

      <Panel
        baslik="Bas ve yazdır"
        cocuk={
          <div className="flex flex-col gap-4">
            <Alan etiket="Tür">
              <Secim
                secenekler={[
                  ["seri", "Seri etiketi (boş havuz)"],
                  ["malzeme", "Malzeme etiketi (kod başına bir numara)"],
                  ["kutu", "Kap etiketi (bu kapta ne var)"],
                ]}
                deger={tur}
                degistir={(v) => setTur(v as Tur)}
              />
            </Alan>

            {tur === "malzeme" && (
              <>
                <Alan etiket="Hangi havuzdan">
                  <Secim
                    secenekler={[
                      ["eksik", `Etiketi olmayanlar (${ihtiyac?.malzeme.eksik ?? 0})`],
                      ["hepsi", `Ambardaki tümü (${ihtiyac?.malzeme.tekil ?? 0})`],
                      ["bos", "Boş havuz — kodu hiç olmayan ürünler"],
                    ]}
                    deger={kapsam}
                    degistir={(v) => setKapsam(v as Kapsam)}
                  />
                </Alan>
                <Alan etiket="Kaç malzeme">
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      max={5000}
                      value={mAdet}
                      onChange={(e) => setMAdet(Math.max(1, Number(e.target.value) || 1))}
                      className="w-32 rounded-sm border border-cizgi bg-zemin px-4 py-3
                        font-mono text-govde focus:border-vurgu focus:outline-none"
                    />
                    <Dugme cocuk="1 sayfa (24)" tikla={() => setMAdet(A4_HUCRE)} />
                    <Dugme cocuk="4 sayfa (96)" tikla={() => setMAdet(A4_HUCRE * 4)} />
                    {kapsam !== "bos" && ihtiyac && ihtiyac.malzeme.barkodsuz > 0 && (
                      <Dugme
                        cocuk={`Barkodsuz: ${ihtiyac.malzeme.barkodsuz}`}
                        baslik="Kodu hiç barkod olamayan malzemeler — etiket bunlarda kesin
                          gerekli, listenin başında geliyorlar"
                        tikla={() => setMAdet(ihtiyac.malzeme.barkodsuz)}
                      />
                    )}
                    {kapsam !== "bos" && malzemeHavuz > 0 && (
                      <Dugme cocuk={`Tümü: ${malzemeHavuz}`} tikla={() => setMAdet(malzemeHavuz)} />
                    )}
                  </div>
                </Alan>
                <Alan etiket="Her koddan kaç kopya">
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      max={20}
                      value={kopya}
                      onChange={(e) => setKopya(Math.max(1, Number(e.target.value) || 1))}
                      className="w-24 rounded-sm border border-cizgi bg-zemin px-4 py-3
                        font-mono text-govde focus:border-vurgu focus:outline-none"
                    />
                    <span className="text-kucuk text-solgun">
                      Aynı malzeme birden çok rafta duruyorsa. Kopya yeni numara üretmez —
                      hepsi aynı kodu taşır.
                    </span>
                    {ihtiyac && (
                      <span className="text-kucuk text-solgun">
                        Toplam <b className="rakam">{malzemeToplam}</b> etiket
                        {duzen === "a4" &&
                          ` · ${Math.ceil((malzemeToplam + atla) / A4_HUCRE)} sayfa`}
                      </span>
                    )}
                  </div>
                </Alan>
              </>
            )}

            {tur === "kutu" && (
              <>
                <Alan etiket="Hangisi">
                  <Secim
                    secenekler={[
                      ["yeni", "Yeni boş kap numarası"],
                      ["tanimli", `İçeriği belli kapları yeniden bas (${kutuSayisi})`],
                    ]}
                    deger={kutuKapsam}
                    degistir={(v) => setKutuKapsam(v as KutuKapsam)}
                  />
                </Alan>
                <Alan etiket="Adet">
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      max={5000}
                      value={kAdet}
                      onChange={(e) => setKAdet(Math.max(1, Number(e.target.value) || 1))}
                      className="w-32 rounded-sm border border-cizgi bg-zemin px-4 py-3
                        font-mono text-govde focus:border-vurgu focus:outline-none"
                    />
                    <Dugme cocuk="1 sayfa (24)" tikla={() => setKAdet(A4_HUCRE)} />
                    <Dugme cocuk="4 sayfa (96)" tikla={() => setKAdet(A4_HUCRE * 4)} />
                    {kutuKapsam === "tanimli" && kutuSayisi > 0 && (
                      <Dugme cocuk={`Tümü: ${kutuSayisi}`} tikla={() => setKAdet(kutuSayisi)} />
                    )}
                    {duzen === "a4" && (
                      <span className="text-kucuk text-solgun">
                        {Math.ceil((kAdet + atla) / A4_HUCRE)} sayfa
                      </span>
                    )}
                  </div>
                </Alan>
                <p className="rounded-sm border border-cizgi bg-panel2 p-3 text-kucuk
                  text-solgun leading-snug">
                  Kap etiketinde <b>adet yazmaz</b> — içerik ayda bir değişiyor ve depoda
                  yazıcı yok. Kapta "150" yazıp içinde 130 olması, hiç sayı yazmamaktan
                  kötüdür: sayan kişi elindekine değil etikete inanır. Kabın içeriği ilk
                  okutmada sorulur ve kalıcı olarak kaydedilir; adet her sayımda yeniden
                  sorulur.
                  {kutuKapsam === "tanimli" && (
                    <>
                      {" "}
                      Yeniden basım <b>yeni numara tüketmez</b>: aynı kap hep aynı kodu
                      taşır.
                    </>
                  )}
                </p>
              </>
            )}

            {tur === "seri" && (
              <Alan etiket="Adet">
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    max={5000}
                    value={adet}
                    onChange={(e) => setAdet(Math.max(1, Number(e.target.value) || 1))}
                    className="w-32 rounded-sm border border-cizgi bg-zemin px-4 py-3
                      font-mono text-govde focus:border-vurgu focus:outline-none"
                  />
                  <Dugme cocuk="1 sayfa (24)" tikla={() => setAdet(A4_HUCRE)} />
                  <Dugme cocuk="4 sayfa (96)" tikla={() => setAdet(A4_HUCRE * 4)} />
                  {ihtiyac && ihtiyac.seri.ust_sinir > 0 && (
                    <Dugme
                      cocuk={`Tavan: ${ihtiyac.seri.ust_sinir}`}
                      baslik="Ambardaki tüm uydurma seri kayıtlarını karşılar — çoğuna
                        muhtemelen gerekmeyecek"
                      tikla={() => setAdet(ihtiyac.seri.ust_sinir)}
                    />
                  )}
                  {duzen === "a4" && (
                    <span className="text-kucuk text-solgun">
                      {Math.ceil((adet + atla) / A4_HUCRE)} sayfa
                    </span>
                  )}
                </div>
              </Alan>
            )}

            <Alan etiket="Düzen">
              <Secim
                secenekler={[
                  ["a4", "A4 lazer etiket sayfası (3 × 8, 70 × 37,125 mm)"],
                  ["rulo", "Termal rulo (50 × 25 mm, etiket başına bir sayfa)"],
                ]}
                deger={duzen}
                degistir={(v) => setDuzen(v as Duzen)}
              />
            </Alan>

            {duzen === "a4" && (
              <Alan etiket="Kaçıncı hücreden başla">
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="number"
                    min={0}
                    max={A4_HUCRE - 1}
                    value={atla}
                    onChange={(e) =>
                      setAtla(Math.min(A4_HUCRE - 1, Math.max(0, Number(e.target.value) || 0)))
                    }
                    className="w-24 rounded-sm border border-cizgi bg-zemin px-4 py-3
                      font-mono text-govde focus:border-vurgu focus:outline-none"
                  />
                  <span className="text-kucuk text-solgun">
                    Yarım kalmış etiket sayfasını israf etmemek için: ilk {atla} hücre boş
                    basılır.
                  </span>
                </div>
              </Alan>
            )}

            <Dugme
              cocuk={
                <>
                  <Ik.Yazdir /> {mesgul ? "Üretiliyor…" : "Üret ve yazdır"}
                </>
              }
              tur="ana"
              tikla={() => void yazdir()}
            />
            <p className="text-kucuk text-solgun">
              Sahadaki sıra: önce malzeme etiketini okut, sonra havuzdan bir seri etiketi
              al, ÖNCE OKUT sonra ürüne yapıştır, ardından SIRADAKİ ÜRÜN. Kutusunda üretici
              parça numarası ya da seri numarası yazıyorsa onu okut — etiket hiç gerekmez.
              Numara okunuyor ama Tiger&apos;da yoksa aynı grupta elle yazıp Enter&apos;a
              bas; Tiger&apos;a o yazılır.
            </p>
          </div>
        }
      />

      <Panel
        baslik="Etiket defteri"
        sag={
          <span className="rakam text-kucuk text-solgun">
            {bagli} bağlı / {defter.length} kayıt
          </span>
        }
        cocuk={
          <div className="flex flex-col gap-3">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Etiket kodu veya malzeme kodu ara…"
              className="w-full rounded-sm border border-cizgi bg-zemin px-4 py-3
                text-govde focus:border-vurgu focus:outline-none"
            />
            {defter.length === 0 ? (
              <Bos cocuk="Henüz etiket basılmadı." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-kucuk">
                  <thead>
                    <tr className="text-mikro font-bold tracking-wider text-solgun uppercase">
                      <th className="py-2 pr-3">Etiket</th>
                      <th className="py-2 pr-3">Tür</th>
                      <th className="py-2 pr-3">Malzeme</th>
                      <th className="py-2 pr-3">Bağlandığı kayıt</th>
                      <th className="py-2">Raf</th>
                    </tr>
                  </thead>
                  <tbody>
                    {defter.map((e) => (
                      <tr key={e.kod} className="border-t border-cizgi">
                        <td className="py-2 pr-3 font-mono font-bold">{e.gosterim}</td>
                        <td className="py-2 pr-3 text-solgun">
                          {TUR_ADI[e.tur] ?? e.tur}
                        </td>
                        <td className="py-2 pr-3">
                          {e.malzeme ? (
                            <>
                              <span className="font-mono">{e.malzeme}</span>
                              {e.aciklama && (
                                <span className="text-solgun"> · {e.aciklama}</span>
                              )}
                            </>
                          ) : (
                            <span className="text-solgun italic">havuzda bekliyor</span>
                          )}
                        </td>
                        <td className="py-2 pr-3 font-mono text-solgun">{e.slot ?? ""}</td>
                        <td className="py-2 text-solgun">{e.raf ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        }
      />

      <Panel
        baslik="Basım geçmişi"
        cocuk={
          basimlar.length === 0 ? (
            <Bos cocuk="Henüz basım yapılmadı." />
          ) : (
            <ul className="flex flex-col gap-2">
              {basimlar.map((b) => (
                <li
                  key={b.id}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-sm
                    bg-panel2 px-4 py-3 text-kucuk"
                >
                  <span className="font-bold">
                    {TUR_ADI[b.tur as Tur] ?? b.tur}
                  </span>
                  <span className="rakam text-solgun">{b.adet} adet</span>
                  <span className="font-mono text-solgun">
                    {b.ilk} → {b.son}
                  </span>
                  <span className="ml-auto text-kucuk text-solgun">
                    {b.duzen === "a4" ? "A4" : "Rulo"} · {(b.ts ?? "").slice(0, 16).replace("T", " ")}
                  </span>
                </li>
              ))}
            </ul>
          )
        }
      />
    </div>
  );
}

function Kutu({
  Ikon,
  baslik,
  deger,
  birim,
  aciklama,
}: {
  Ikon: typeof Ik.Raf;
  baslik: string;
  deger: number;
  birim: string;
  aciklama: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-sm bg-panel2 p-4">
      <div className="flex items-center gap-2 text-kucuk font-bold tracking-wider
        text-solgun uppercase">
        <Ikon boy={16} /> {baslik}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="rakam text-5xl font-bold">{deger}</span>
        <span className="text-kucuk text-solgun">{birim}</span>
      </div>
      <p className="text-kucuk leading-snug text-solgun">{aciklama}</p>
    </div>
  );
}

function Alan({ etiket, children }: { etiket: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-mikro font-bold tracking-wider text-solgun uppercase">
        {etiket}
      </span>
      {children}
    </label>
  );
}

/* Radyo yerine hap düğmeler: eldivenli parmakla 48px hedef, renk tek başına
   bilgi taşımasın diye seçili olan hem dolgu hem kalın yazı alır. */
function Secim({
  secenekler,
  deger,
  degistir,
}: {
  secenekler: [string, string][];
  deger: string;
  degistir: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {secenekler.map(([v, ad]) => (
        <button
          key={v}
          type="button"
          onClick={() => degistir(v)}
          className={`rounded-sm border px-4 py-2 text-kucuk ${
            v === deger
              ? "border-vurgu bg-vurgu-tint font-bold text-vurgu"
              : "border border-cizgi-kuvvetli bg-panel border-cizgi text-solgun"
          }`}
        >
          {ad}
        </button>
      ))}
    </div>
  );
}
