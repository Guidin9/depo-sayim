/** Ayarlar — telefondan da erişilebilsin diye ayrı ekran.
 *
 * Sayım sürerken laptopun başına dönmeden yapılabilecekler: rafı değiştirmek,
 * sayım dışı kuralını açıp kapatmak, sesi kısmak, cihaz modunu seçmek.
 */
import { useEffect, useState } from "react";
import { api, type Durum, type Kural } from "../api";
import { Dugme, Kod, Panel, Uyari } from "../bilesenler";
import * as Ik from "../ikonlar";
import { bip, sesAcikMi, sesiAyarla } from "../ses";

export default function Ayarlar({
  durum,
  tik,
  uzaktan,
  modDegistir,
  geri,
  setDurum,
}: {
  durum: Durum;
  tik: number;
  uzaktan: boolean;
  modDegistir: () => void;
  geri: () => void;
  setDurum: (d: Durum) => void;
}) {
  const [kurallar, setKurallar] = useState<Kural[]>([]);
  const [raflar, setRaflar] = useState<string[]>([]);
  const [yeniRaf, setYeniRaf] = useState("");
  const [ses, setSes] = useState(sesAcikMi());
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    void api.kurallar(durum.yukleme).then(setKurallar).catch(() => undefined);
    void api.raflar(durum.oturum).then(setRaflar).catch(() => undefined);
  }, [durum.yukleme, durum.oturum, tik]);

  async function kuralDegistir(k: Kural, aktif: boolean) {
    setKurallar((e) => e.map((x) => (x.id === k.id ? { ...x, aktif } : x)));
    setKurallar(await api.kurallariGuncelle(durum.yukleme, [{ id: k.id, aktif }]));
    setDurum(await api.durum(durum.oturum));
  }

  async function rafAyarla(raf: string, zorla = false) {
    if (!raf.trim()) return;
    const r = await api.rafAyarla(durum.oturum, raf, zorla);
    if (r.tip === "raf_engel") {
      setHata(
        `${r.eski_raf} rafında ${r.kuyruk?.length} ürün çözülmedi. Önce kuyruğu çöz — ` +
          "ya da bilerek geçmek istiyorsan tekrar dokun.",
      );
      if (confirm("Çözülmemiş ürünler kuyrukta kalacak. Yine de rafı değiştirelim mi?")) {
        await rafAyarla(raf, true);
      }
      return;
    }
    setHata(null);
    bip("ok");
    setYeniRaf("");
    if (r.durum) setDurum(r.durum);
    setRaflar(await api.raflar(durum.oturum));
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 p-5">
      <header className="flex items-center gap-4">
        <Dugme
          cocuk={
            <>
              <Ik.Geri /> Geri
            </>
          }
          tikla={geri}
        />
        <h1 className="text-4xl leading-[0.95] font-extrabold tracking-tight">Ayarlar</h1>
      </header>

      {hata && <Uyari cocuk={hata} />}

      <Panel
        baslik="Bu cihaz"
        cocuk={
          <div className="flex flex-col gap-3">
            <p className="text-kucuk text-solgun">
              {uzaktan
                ? "Uzaktan ekran: barkod giriş alanı odaklanmaz, telefon klavyesi kendiliğinden açılmaz. Sayımı laptop yapar, buradan izler ve seçim yaparsın."
                : "Okuyucu cihazı: barkod giriş alanı sürekli odakta kalır."}
            </p>
            <Dugme
              cocuk={
              uzaktan ? (
                <>
                  <Ik.Okuyucu /> Okuyucu cihazı yap
                </>
              ) : (
                <>
                  <Ik.Telefon /> Uzaktan ekran yap
                </>
              )
            }
              tikla={modDegistir}
            />
            <Dugme
              cocuk={
              ses ? (
                <>
                  <Ik.SesAcik /> Ses açık
                </>
              ) : (
                <>
                  <Ik.SesKapali /> Ses kapalı
                </>
              )
            }
              tikla={() => {
                const y = !ses;
                setSes(y);
                sesiAyarla(y);
                if (y) bip("tik");
              }}
            />
          </div>
        }
      />

      <Panel
        baslik="Aktif raf"
        sag={
          <span className="text-kucuk text-solgun">
            {durum.aktif_raf ? `şu an raf ${durum.aktif_raf}` : "seçilmedi"}
          </span>
        }
        cocuk={
          <div className="flex flex-col gap-3">
            <p className="text-kucuk text-solgun">
              Raf barkodunu okutmadan da değiştirebilirsin. Çözülmemiş kuyruk varsa
              burada da uyarır.
            </p>
            {raflar.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {raflar.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => void rafAyarla(r)}
                    className={`ease-kolay rounded-sm border px-5 py-2 text-govde
                      font-bold transition duration-200
                      ${
                        r === durum.aktif_raf
                          ? "border-uyari bg-uyari-tint text-uyari"
                          : "border-cizgi bg-panel2 hover:border-vurgu"
                      }`}
                  >
                    <span className="inline-flex items-center gap-1.5">
                      <Ik.Raf boy={15} /> {r}
                    </span>
                  </button>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <input
                value={yeniRaf}
                onChange={(e) => setYeniRaf(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && void rafAyarla(yeniRaf)}
                placeholder="yeni raf adı (A1, B2…)"
                className="min-w-0 flex-1 rounded-sm border border-cizgi bg-zemin px-4 py-3
                  font-mono text-govde uppercase focus:border-vurgu focus:outline-none"
              />
              <Dugme cocuk="Rafa geç" tur="ana" tikla={() => void rafAyarla(yeniRaf)} />
            </div>
          </div>
        }
      />

      <Panel
        baslik="Sayım dışı kalemler"
        cocuk={
          <ul className="flex flex-col gap-2">
            {kurallar.map((k) => (
              <li
                key={k.id}
                className={`flex items-center gap-3 rounded-sm border px-3 py-2
                  ${k.satir ? "border-cizgi bg-panel2" : "border-cizgi text-solgun-hafif"}`}
              >
                <input
                  id={`ayar-kural-${k.id}`}
                  type="checkbox"
                  checked={k.aktif}
                  onChange={(e) => void kuralDegistir(k, e.target.checked)}
                  className="h-6 w-6 accent-[var(--color-vurgu)]"
                />
                <label htmlFor={`ayar-kural-${k.id}`} className="flex-1 cursor-pointer">
                  <Kod cocuk={k.desen} />
                  <span className="ml-2 text-mikro text-solgun">
                    {k.tip === "tur" ? "türde" : "açıklamada"}
                  </span>
                </label>
                <span className="rakam text-kucuk text-solgun">
                  {k.satir ? `${k.satir} satır` : "—"}
                </span>
              </li>
            ))}
          </ul>
        }
      />
    </div>
  );
}
