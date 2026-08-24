/** 8. ekran — sayım sonu eşleştirme.
 *
 * Rapordan ÖNCEKİ adım. Sahadaki gerçek şu: fazla çıkan ürün çoğu zaman eksik
 * görünen kaydın ta kendisidir, sadece seri numarası tutmamıştır. Sistem bunu
 * kendiliğinden tahmin etmeye çalışmaz (denedi, tutmadı — DEMO_FEEDBACK.md 4);
 * ikisini yan yana koyar, kararı kullanıcı verir.
 *
 * Eksik listesi rapordaki Eksik sekmesiyle aynı kaynaktan gelir
 * (reports.eksik_kayitlar) — ekranla rapor ayrı şeyler söylemesin.
 */
import { useCallback, useEffect, useState } from "react";
import { api, type EksikKaydi, type EslemeVerisi, type FazlaKaydi } from "../api";
import { Bos, Dugme, Panel, Uyari } from "../bilesenler";
import { kucult } from "../foto";
import { suz } from "../liste";
import { GrupluListe } from "../GrupluListe";
import * as Ik from "../ikonlar";
import { bip } from "../ses";

export default function Esleme({
  oturum,
  tik,
  geri,
  rapora,
}: {
  oturum: number;
  tik: number;
  geri: () => void;
  rapora: () => void;
}) {
  const [veri, setVeri] = useState<EslemeVerisi>({ fazla: [], eksik: [] });
  const [secili, setSecili] = useState<FazlaKaydi | null>(null);
  const [q, setQ] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [buyutulen, setBuyutulen] = useState<number | null>(null);
  /* Fazla kaydının adı burada da düzeltilebilir: gün sonunda raporu açmadan
     önce son fırsat. Kodu olmayan kayıtta ad zorunlu (bitirme kapısı). */
  const [adlar, setAdlar] = useState<Record<number, string>>({});

  const tazele = useCallback(async () => {
    try {
      setVeri(await api.esleme(oturum));
      setHata(null);
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }, [oturum]);

  useEffect(() => {
    void tazele();
  }, [tazele, tik]);

  async function bagla(e: EksikKaydi) {
    if (!secili) return;
    try {
      await api.fazlaBagla(secili.id, e.id);
      bip("ok");
      setSecili(null);
      setQ("");
      await tazele();
    } catch (x) {
      setHata(x instanceof Error ? x.message : String(x));
    }
  }

  async function adKaydet(f: FazlaKaydi) {
    const ad = (adlar[f.id] ?? f.ad ?? "").trim();
    if (!ad || ad === (f.ad ?? "")) return;
    try {
      await api.okutmaAd(f.id, ad);
      bip("ok");
      await tazele();
    } catch (x) {
      setHata(x instanceof Error ? x.message : String(x));
    }
  }

  async function fotoEkle(f: FazlaKaydi, dosya: File) {
    try {
      await api.okutmaFotosu(f.id, await kucult(dosya));
      bip("tik");
      await tazele();
    } catch (x) {
      setHata(x instanceof Error ? x.message : String(x));
    }
  }

  /* Otomatik öneri YOK. Kullanıcı yazdıkça eksik listesi daralır; hiçbir şey
     yazmazsa TÜM eksikler durur. Sıralamaya karışmıyoruz.

     Süzme çok terimli: "dell ssd" hem "DELL 1.92TB SSD" hem "SSD Dell Gen14"
     satırını bulur — tek parça arama bunu yapamıyordu. */
  const eksikler = suz(veri.eksik, q.trim(), ["kod", "aciklama", "seri"]);

  /* Fotoğrafsız fazla artık oturumu ENGELLEMİYOR: kodu ya da adı olan kayıt
     zaten denetlenebilir (matching.fotosuz_fazlalar). Sayı yine gösteriliyor,
     çünkü fotoğraf hâlâ en iyi denetim izi — ama karar kullanıcının. */
  const fotosuz = veri.fazla.filter((f) => f.fotolar.length === 0).length;
  /* Kodu olmayan kayıtta rapor açıklamayı üretemez; adı yoksa satır
     kullanılamaz hâlde. Oturum bunlar dolmadan kapanmıyor. */
  const adsiz = veri.fazla.filter((f) => !f.kod && !f.ad).length;

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5 p-5">
      <header className="flex flex-wrap items-center gap-4">
        <Dugme
          cocuk={
            <>
              <Ik.Geri /> Sayıma dön
            </>
          }
          tikla={geri}
        />
        <h1 className="text-4xl leading-[0.95] font-extrabold tracking-tight">Eşleştirme</h1>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-govde text-solgun">
            {veri.fazla.length} fazla · {veri.eksik.length} eksik
          </span>
          <Dugme cocuk="Rapora geç" tur="ana" tikla={rapora} />
        </div>
      </header>

      {hata && <Uyari cocuk={hata} />}

      {adsiz > 0 && (
        <div className="flex items-start gap-2 rounded-sm border border-hata
          bg-hata-tint px-4 py-3">
          <Ik.Soru boy={18} />
          <p className="text-kucuk leading-snug">
            <b>{adsiz} fazla kaydının ne olduğu yazılmamış.</b>{" "}
            <span className="text-solgun">
              Bu ürünlerin Tiger'da kaydı yok, bu yüzden raporda açıklamaları
              üretilemiyor — geriye yalnızca seri numarası ve raf kalıyor. Aşağıdan
              adlarını yazın; oturum bunlar doldurulmadan kapanmaz.
            </span>
          </p>
        </div>
      )}

      {fotosuz > 0 && (
        <div className="flex items-start gap-2 rounded-sm border border-uyari
          bg-uyari-tint px-4 py-3">
          <Ik.Kamera boy={18} />
          <p className="text-kucuk leading-snug">
            <b>{fotosuz} fazla kaydının fotoğrafı yok.</b>{" "}
            <span className="text-solgun">
              Fazla, sayımdan sonra kimsenin doğrulayamayacağı tek çıktıdır: ürün rafa
              geri konur, geriye yalnızca bu satır kalır. Adı yazılmışsa satır zaten
              bulunabilir — fotoğraf oturumu <b>engellemez</b>, ama en iyi denetim izidir.
            </span>
          </p>
        </div>
      )}

      {veri.fazla.length === 0 ? (
        <Panel cocuk={<Bos cocuk="Fazla çıkan kayıt yok — eşleştirecek bir şey de yok." />} />
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          {/* --------------------------------------------------------- fazlalar */}
          <Panel
            baslik={`Fazla çıkanlar (${veri.fazla.length})`}
            cocuk={
              <ul className="flex flex-col gap-2">
                {veri.fazla.map((f) => (
                  <li
                    key={f.id}
                    className={`rounded-sm border p-3 ${
                      secili?.id === f.id
                        ? "border-vurgu bg-vurgu-tint"
                        : "border-cizgi bg-panel2"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setSecili(secili?.id === f.id ? null : f)}
                      className="w-full text-left"
                    >
                      <div className="flex flex-wrap items-baseline gap-2">
                        <b className="font-mono text-govde break-all">{f.ham}</b>
                        {f.kod && <span className="text-kucuk text-vurgu">{f.kod}</span>}
                      </div>
                      <div className="mt-1 text-mikro text-solgun">
                        {f.ad && <span className="text-yazi">{f.ad} · </span>}
                        {f.raf && `raf ${f.raf} · `}
                        {f.ts.slice(11, 16)}
                        {f.not_ && ` · ${f.not_}`}
                      </div>
                    </button>

                    {/* Kodu olmayan kayıtta ad şart; kodu olanda isteğe bağlı
                        (açıklama zaten beklenen tablosundan geliyor). */}
                    {!f.kod && (
                      <input
                        value={adlar[f.id] ?? f.ad ?? ""}
                        onChange={(e) =>
                          setAdlar((o) => ({ ...o, [f.id]: e.target.value }))
                        }
                        onBlur={() => void adKaydet(f)}
                        onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                        placeholder="bu ürün ne? — örn. Kırmızı HP güç kablosu, 2 m"
                        className={`mt-2 w-full rounded-sm border bg-zemin px-3 py-2
                          text-kucuk focus:outline-none ${
                            f.ad
                              ? "border-cizgi focus:border-vurgu"
                              : "border-hata focus:border-hata"
                          }`}
                      />
                    )}

                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <label
                        className={`cursor-pointer rounded-sm border px-3 py-1.5 text-kucuk
                          font-semibold ${
                            f.fotolar.length
                              ? "border-cizgi bg-panel text-solgun"
                              : "border-uyari bg-uyari-tint text-uyari"
                          }`}
                      >
                        <span className="inline-flex items-center gap-1.5">
                          <Ik.Kamera boy={13} />
                          {f.fotolar.length ? "Fotoğraf ekle" : "Fotoğraf çek"}
                        </span>
                        <input
                          type="file"
                          accept="image/*"
                          capture="environment"
                          className="hidden"
                          onChange={(x) => {
                            const d = x.target.files?.[0];
                            if (d) void fotoEkle(f, d);
                            x.target.value = "";
                          }}
                        />
                      </label>
                      {f.fotolar.map((id) => (
                        <button
                          key={id}
                          type="button"
                          onClick={() => setBuyutulen(id)}
                          className="h-10 w-10 overflow-hidden rounded-sm border border-cizgi"
                          title="Büyüt"
                        >
                          <img
                            src={api.fotoUrl(id)}
                            alt="fazla fotoğrafı"
                            className="h-full w-full object-cover"
                          />
                        </button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            }
          />

          {/* ---------------------------------------------------------- eksikler */}
          <Panel
            baslik={
              secili
                ? `${secili.ham} hangi eksik kayıt?`
                : `Eksik kalanlar (${veri.eksik.length})`
            }
            cocuk={
              <>
                {!secili && (
                  <p className="mb-3 text-kucuk text-solgun">
                    Soldan bir fazla kaydı seç, sonra buradan karşılığını bul.
                  </p>
                )}
                <input
                  value={q}
                  onChange={(x) => setQ(x.target.value)}
                  placeholder="kod, açıklama veya seri no ile daralt…"
                  className="mb-3 w-full rounded-sm border border-cizgi bg-zemin px-4 py-2.5
                    text-govde focus:border-vurgu focus:outline-none"
                />
                {eksikler.length === 0 ? (
                  <Bos cocuk="Eşleşen eksik kayıt yok." />
                ) : (
                  /* Aynı malzemenin farklı seri satırları tek grupta toplanır;
                     başlıkta kaç eksik kayıt kaldığı yazar, açınca seriler
                     gelir. Fazla seçili değilken seçim pasif. */
                  <ul className="flex max-h-[60vh] flex-col gap-2 overflow-y-auto">
                    <GrupluListe
                      satirlar={eksikler}
                      anahtar={q}
                      onSec={(e) => void bagla(e)}
                      pasif={!secili}
                    />
                  </ul>
                )}
              </>
            }
          />
        </div>
      )}

      {buyutulen !== null && (
        <div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4
            bg-yazi/85 p-4"
          onClick={() => setBuyutulen(null)}
        >
          <img
            src={api.fotoUrl(buyutulen)}
            alt="fazla fotoğrafı"
            className="max-h-[75vh] max-w-full rounded-sm object-contain"
          />
          <Dugme cocuk="Kapat" tikla={() => setBuyutulen(null)} />
        </div>
      )}
    </div>
  );
}
