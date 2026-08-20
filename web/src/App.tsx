/** Ekran yönlendirmesi, açık oturum durumu ve canlı güncelleme.
 *
 * Kritik veri localStorage'a yazılmaz — açık oturum, tampon ve aktif raf
 * SQLite'ta durur, uygulama kapanıp açılsa bile /api/oturum/acik ile geri gelir.
 * localStorage yalnızca "bu cihaz okuyucu mu, uzaktan ekran mı" tercihini tutar.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Durum } from "./api";
import { Dugme, Marka, Uyari } from "./bilesenler";
import Ayarlar from "./ekranlar/Ayarlar";
import Gecmis from "./ekranlar/Gecmis";
import Kurulum from "./ekranlar/Kurulum";
import Kuyruk from "./ekranlar/Kuyruk";
import Rapor from "./ekranlar/Rapor";
import Sayim from "./ekranlar/Sayim";
import Telefon from "./ekranlar/Telefon";
import { olaylariDinle, type BaglantiHali } from "./olaylar";
import Zemin from "./Zemin";

type Ekran = "kurulum" | "sayim" | "kuyruk" | "rapor" | "gecmis" | "ayarlar";

/* Telefon monitörü ayrı adreste: http://<laptop-ip>:8000/telefon
   Ekran boyutu tahminine güvenmiyoruz — adres neyse mod odur. Laptop kökten
   girer, telefon PC'deki QR'ı okutup buraya düşer. */
const TELEFON_MODU = window.location.pathname.replace(/\/+$/, "") === "/telefon";

/** Dokunmatik ve dar ekran = telefon; okuyucu takılı laptop değil. */
function uzaktanTahmin() {
  const kayit = localStorage.getItem("uzaktan");
  if (kayit === "1" || kayit === "0") return kayit === "1";
  return window.matchMedia("(pointer: coarse)").matches || window.innerWidth < 820;
}

export default function App() {
  const [ekran, setEkran] = useState<Ekran>("kurulum");
  const [durum, setDurum] = useState<Durum | null>(null);
  const [raporOturum, setRaporOturum] = useState<number | null>(null);
  const [hazir, setHazir] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const [tik, setTik] = useState(0);
  const [canli, setCanli] = useState<BaglantiHali>("baglaniyor");
  const [uzaktan, setUzaktan] = useState(uzaktanTahmin);
  const oturumRef = useRef<number | null>(null);

  oturumRef.current = durum?.oturum ?? null;

  const tazele = useCallback(async (oturumId?: number) => {
    const d = oturumId ? await api.durum(oturumId) : await api.acikOturum();
    setDurum(d);
    return d;
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const d = await api.acikOturum();
        setDurum(d);
        setEkran(d ? "sayim" : "kurulum");
      } catch (e) {
        setHata(e instanceof Error ? e.message : String(e));
      } finally {
        setHazir(true);
      }
    })();
  }, []);

  /* Canlı güncelleme: başka bir cihazda (ya da laptopta) bir şey değişince
     kendi ekranımızı tazeleriz. tik sayacı alt ekranlara "verini yenile" der. */
  useEffect(
    () =>
      olaylariDinle(() => {
        setTik((t) => t + 1);
        const id = oturumRef.current;
        void (id ? api.durum(id) : api.acikOturum())
          .then(setDurum)
          .catch(() => undefined);
      }, setCanli),
    [],
  );

  async function oturumBasla(id: number) {
    await tazele(id);
    setEkran("sayim");
  }

  async function oturumBitir(zorla = false) {
    if (!durum) return;
    try {
      await api.bitir(durum.oturum, zorla);
      setDurum(await api.durum(durum.oturum));
    } catch (e) {
      const mesaj = e instanceof Error ? e.message : String(e);
      if (mesaj.includes("çözülmemiş") && confirm(`${mesaj}\n\nYine de bitirilsin mi?`)) {
        await oturumBitir(true);
        return;
      }
      setHata(mesaj);
    }
  }

  function modDegistir() {
    const yeni = !uzaktan;
    setUzaktan(yeni);
    localStorage.setItem("uzaktan", yeni ? "1" : "0");
  }

  if (!hazir)
    return (
      <>
        <Zemin />
        <p className="relative z-10 p-10 text-center font-serif text-2xl text-solgun italic">
          Yükleniyor…
        </p>
      </>
    );

  /* Telefon: sade monitör. Kurulum, rapor ve oturum kapatma bilerek yok. */
  if (TELEFON_MODU)
    return (
      <>
        <Zemin />
        <div className="relative z-10 min-h-full">
          <Telefon
            durum={durum?.durum === "acik" ? durum : null}
            canli={canli}
            tik={tik}
            tazele={() => void tazele(oturumRef.current ?? undefined).catch(() => undefined)}
          />
        </div>
      </>
    );

  const acikMi = durum?.durum === "acik";

  return (
    <>
      <Zemin />
      <div className="relative z-10 flex h-full flex-col">
        {hata && (
          <div className="p-4">
            <Uyari cocuk={`Sunucuya ulaşılamadı: ${hata}`} />
          </div>
        )}

        {/* Design.md'nin yüzen hap navigasyonu. Marka serif, düğmeler tek bir
            cam adada — üst şerit sayfayı kesen bir çizgi değil, üstünde duran
            bir nesne. */}
        {ekran !== "sayim" && (
          <nav className="flex flex-wrap items-center gap-3 px-5 py-3">
            <Marka />
            <div className="cam ml-auto flex flex-wrap gap-1.5 rounded-full p-1.5">
              {durum && acikMi && (
                <Dugme cocuk="Sayıma dön" tur="ana" tikla={() => setEkran("sayim")} />
              )}
              {durum && <Dugme cocuk="Ayarlar" tikla={() => setEkran("ayarlar")} />}
              <Dugme cocuk="Geçmiş" tikla={() => setEkran("gecmis")} />
              {!acikMi && <Dugme cocuk="Yeni sayım" tikla={() => setEkran("kurulum")} />}
            </div>
          </nav>
        )}

        <main className="min-h-0 flex-1 overflow-y-auto">
          {ekran === "kurulum" && <Kurulum basla={oturumBasla} />}

          {ekran === "sayim" && durum && (
            <Sayim
              durum={durum}
              setDurum={setDurum}
              canli={canli}
              uzaktan={uzaktan}
              modDegistir={modDegistir}
              git={(e) => {
                if (e === "rapor") setRaporOturum(durum.oturum);
                setEkran(e);
              }}
            />
          )}
          {ekran === "sayim" && !durum && (
            <div className="p-8 text-center">
              <p className="mb-4 text-solgun">Açık oturum yok.</p>
              <Dugme cocuk="Kuruluma git" tur="ana" tikla={() => setEkran("kurulum")} />
            </div>
          )}

          {ekran === "kuyruk" && durum && (
            <Kuyruk
              oturum={durum.oturum}
              tik={tik}
              geri={() => setEkran("sayim")}
              yenile={() => void tazele(durum.oturum)}
            />
          )}

          {ekran === "ayarlar" && durum && (
            <Ayarlar
              durum={durum}
              tik={tik}
              uzaktan={uzaktan}
              modDegistir={modDegistir}
              geri={() => setEkran(acikMi ? "sayim" : "gecmis")}
              setDurum={setDurum}
            />
          )}

          {ekran === "rapor" && (raporOturum ?? durum?.oturum) && (
            <Rapor
              oturum={(raporOturum ?? durum?.oturum) as number}
              tik={tik}
              acikMi={!!acikMi && (raporOturum ?? durum?.oturum) === durum?.oturum}
              geri={() => setEkran(acikMi && durum ? "sayim" : "gecmis")}
              bitir={() => void oturumBitir()}
            />
          )}

          {ekran === "gecmis" && (
            <Gecmis
              tik={tik}
              geri={() => setEkran(acikMi && durum ? "sayim" : "kurulum")}
              rapora={(o) => {
                setRaporOturum(o);
                setEkran("rapor");
              }}
            />
          )}
        </main>
      </div>
    </>
  );
}
