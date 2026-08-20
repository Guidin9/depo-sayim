/** "Telefonu bağla" kutusu — QR + adres.
 *
 * Depoda kimse IP'yi elle yazmasın diye: PC ekranındaki kodu telefon kamerası
 * okutur, doğrudan /telefon monitörü açılır. Laptopta birden çok ağ adresi
 * olabiliyor (Hyper-V / VirtualBox sanal anahtarları da IP taşır); ilk sıradaki
 * gerçek Wi-Fi adresi, çalışmazsa diğerleri elle seçilebilir.
 */
import { useEffect, useState } from "react";
import { api } from "./api";
import { Dugme } from "./bilesenler";
import * as Ik from "./ikonlar";

export default function TelefonKutu({ kapat }: { kapat: () => void }) {
  const [adresler, setAdresler] = useState<string[]>([]);
  const [secili, setSecili] = useState(0);
  const [qrYok, setQrYok] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    void api
      .ag()
      .then((a) => setAdresler(a.telefon ?? a.adresler.map((x) => x + "/telefon")))
      .catch((e) => setHata(e instanceof Error ? e.message : String(e)));
  }, []);

  const adres = adresler[secili] ?? "";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4
      backdrop-blur-md">
      <div className="cam w-full max-w-md rounded-2xl">
        <header className="border-b border-cizgi px-5 py-4">
          <h2 className="flex items-center gap-3 font-serif text-3xl leading-tight">
            <Ik.Telefon boy={26} />
            Telefonu bağla
          </h2>
          <p className="mt-1 text-[13px] text-solgun">
            Telefon kamerasıyla kodu okut — canlı izleme ekranı açılır. Telefon aynı Wi-Fi'da
            olmalı ve sunucu <code className="font-mono">baslat.bat</code> ile açılmış olmalı.
          </p>
        </header>

        <div className="flex flex-col items-center gap-4 p-5">
          {hata && <p className="text-[14px] font-semibold text-hata">{hata}</p>}

          {!hata && adresler.length === 0 && (
            <p className="text-[14px] text-solgun">Ağ adresi bulunamadı.</p>
          )}

          {adres && !qrYok && (
            <img
              src={`/api/telefon-qr.svg?adres=${encodeURIComponent(adres)}`}
              alt="Telefon adresi QR kodu"
              onError={() => setQrYok(true)}
              className="h-56 w-56 rounded-2xl bg-white p-2"
            />
          )}

          {adres && qrYok && (
            <p className="text-center text-[13px] text-uyari">
              QR üretilemedi (segno kurulu değil). Adresi telefona elle yaz:
            </p>
          )}

          {adres && (
            <p className="text-center font-mono text-lg font-bold break-all text-vurgu">{adres}</p>
          )}

          {adresler.length > 1 && (
            <div className="w-full">
              <p className="mb-2 text-[12px] text-solgun">
                Telefon açamıyorsa başka bir ağ adresini dene:
              </p>
              <div className="flex flex-wrap gap-2">
                {adresler.map((a, i) => (
                  <button
                    key={a}
                    type="button"
                    onClick={() => {
                      setSecili(i);
                      setQrYok(false);
                    }}
                    className={`rounded-full border px-3 py-2 font-mono text-[12px] ${
                      i === secili
                        ? "border-vurgu bg-vurgu/15 text-vurgu"
                        : "border-cizgi bg-panel2 text-solgun"
                    }`}
                  >
                    {a.replace(/^https?:\/\//, "").replace("/telefon", "")}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <footer className="flex justify-end border-t border-cizgi px-5 py-4">
          <Dugme cocuk="Kapat" tur="ana" tikla={kapat} />
        </footer>
      </div>
    </div>
  );
}
