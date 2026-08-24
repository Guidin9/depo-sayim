/** Malzemeye göre gruplanmış, açılır seçim listesi.
 *
 * Üç ekran aynı listeyi çiziyordu (Kuyruk · Eşleme · Telefon) ve üçü de aynı
 * kodun 21 seri satırını düz akıtıyordu — kullanıcı doğru ürünü 21 satırın
 * içinde arıyordu (bildirim 2026-08-24). Artık:
 *
 *   • Aynı malzeme (kod + açıklama) tek satırda toplanır; yanında **kaç açık
 *     kayıt kaldığını** gösteren sayaç kutusu durur.
 *   • Satıra basınca o malzemenin seri numaraları açılır, kullanıcı seçer.
 *   • Tek seri satırı olan malzeme açmaya gerek kalmadan doğrudan seçilir.
 *   • Sayılan/eşleşen kayıt zaten `sadece_acik` süzgeciyle gelmez; bir kayıt
 *     çözülünce liste tazelenir ve hem satır hem sayaç düşer.
 *
 * `<ul>`'yi çağıran ekran çizer (kaydırma yüksekliği ekrana göre değişiyor);
 * bu bileşen yalnızca `<li>`'leri döndürür, böylece kademeli çizim gözcüsü
 * ekranın kendi kaydırma kabını bulur (bkz. liste.ts `kaydirilanAta`). */
import { useMemo, useState } from "react";
import { grupla, kademeli, type Grup, type ListeSatiri } from "./liste";
import * as Ik from "./ikonlar";

/** Bir üründen kaç açık kayıt kaldığını gösteren sayaç kutusu. */
function Sayac({ adet, birim }: { adet: number; birim: string }) {
  return (
    <span className="inline-flex shrink-0 items-baseline gap-1">
      <span
        className="rakam rounded-sm border border-cizgi-kuvvetli bg-panel px-2 py-0.5
          text-kucuk font-bold text-yazi"
      >
        {adet}
      </span>
      <span className="text-mikro text-solgun">{birim || "adet"}</span>
    </span>
  );
}

/** Uydurma / bu rafta rozetleri — leaf ve grup başlığında ortak. */
function Isaretler({ kirli, ayniRaf }: { kirli: boolean; ayniRaf: boolean }) {
  return (
    <>
      {kirli && (
        <span
          className="rounded border border-uyari bg-uyari-tint px-1.5 text-mikro font-bold
            text-uyari"
        >
          <span className="inline-flex items-center gap-1">
            <Ik.Uyari boy={11} /> uydurma kayıt
          </span>
        </span>
      )}
      {ayniRaf && (
        <span
          className="rounded border border-uyari bg-uyari-tint px-1.5 text-mikro font-bold
            text-uyari"
        >
          <span className="inline-flex items-center gap-1">
            <Ik.Raf boy={11} /> bu rafta
          </span>
        </span>
      )}
    </>
  );
}

/** Tek bir seri satırı (açılmış grubun altı, ya da tek satırlı grubun kendisi). */
function SeriSatiri<T extends ListeSatiri>({
  s,
  onSec,
  pasif,
  ic,
}: {
  s: T;
  onSec: (r: T) => void;
  pasif: boolean;
  /** Grubun içindeyse (girintili, seri öne çıkar); değilse tek satırlı grup. */
  ic: boolean;
}) {
  return (
    <button
      type="button"
      disabled={pasif}
      onClick={() => onSec(s)}
      className={`flex w-full items-center gap-2 rounded-sm border px-3 py-2.5 text-left
        transition enabled:hover:border-vurgu enabled:hover:bg-vurgu-tint
        disabled:text-solgun-hafif ${
          ic ? "border-cizgi bg-panel" : "border-cizgi bg-panel2"
        }`}
    >
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-baseline gap-2">
          {ic ? (
            <b className="font-mono text-govde break-all text-yazi">{s.seri || "—"}</b>
          ) : (
            <>
              <b className="font-mono text-vurgu break-all">{s.kod || "—"}</b>
              <span className="text-kucuk">{s.aciklama}</span>
            </>
          )}
          <Isaretler kirli={s.kirli === 1} ayniRaf={(s.ayni_raf ?? 0) > 0} />
          {s.sayildi === 1 && (
            <span
              className="rounded border border-ok bg-ok-tint px-1.5 text-mikro font-bold text-ok"
            >
              <span className="inline-flex items-center gap-1">
                <Ik.Onay boy={11} /> bu oturumda sayıldı
              </span>
            </span>
          )}
        </span>
        {!ic && (
          <span className="mt-1 block font-mono text-mikro text-solgun break-all">
            {s.seri || "—"} · {s.izleme}
          </span>
        )}
      </span>
      {/* Tek satırlı malzemede de sayaç kutusu dursun (adet = 1). */}
      {!ic && <Sayac adet={s.miktar || 1} birim={s.birim} />}
    </button>
  );
}

/** Çok seri satırlı bir malzeme grubu: başlık + açılınca seri listesi. */
function GrupSatiri<T extends ListeSatiri>({
  g,
  acik,
  ac,
  onSec,
  pasif,
}: {
  g: Grup<T>;
  acik: boolean;
  ac: () => void;
  onSec: (r: T) => void;
  pasif: boolean;
}) {
  return (
    <div className="rounded-sm border border-cizgi bg-panel2">
      <button
        type="button"
        onClick={ac}
        aria-expanded={acik}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left"
      >
        <Ik.Cevron acik={acik} boy={16} />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-baseline gap-2">
            <b className="font-mono text-vurgu break-all">{g.kod || "—"}</b>
            <span className="text-kucuk">{g.aciklama}</span>
            <Isaretler kirli={g.kirli} ayniRaf={g.ayni_raf > 0} />
          </span>
          <span className="mt-0.5 block text-mikro text-solgun">
            {g.izleme} · seri seçmek için aç
          </span>
        </span>
        <Sayac adet={g.adet} birim={g.birim} />
      </button>

      {acik && (
        <ul className="flex flex-col gap-1.5 border-t border-cizgi p-2">
          {g.satirlar.map((s) => (
            <li key={s.id}>
              <SeriSatiri s={s} onSec={onSec} pasif={pasif} ic />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function GrupluListe<T extends ListeSatiri>({
  satirlar,
  anahtar,
  onSec,
  pasif = false,
  hepsiAcik = false,
}: {
  /** Süzülmüş leaf satırlar (arama + filtre çağıran ekranda uygulanır). */
  satirlar: T[];
  /** Kademeli pencereyi başa saran anahtar (arama metni + filtre). */
  anahtar: string;
  onSec: (r: T) => void;
  /** Seçimi kapat (Eşleme ekranında fazla seçilmeden). */
  pasif?: boolean;
  /** Tüm grupları açık başlat: seçim aktifken (Eşleme'de fazla seçiliyken)
      kullanıcı ürüne basınca grup açılmasını beklemez, serileri hemen görüp
      seçer — eski düz liste davranışı, görsel olarak gruplu. */
  hepsiAcik?: boolean;
}) {
  const gruplar = useMemo(() => grupla(satirlar), [satirlar]);
  const [acikSet, setAcikSet] = useState<Set<string>>(new Set());

  /* Tek grup kaldıysa (fazla_onay'da kod önceden yazılı, ya da arama tek ürüne
     indirdi) elle açmaya gerek yok — doğrudan açık gelsin. */
  const tekGrup = gruplar.length === 1 ? gruplar[0].anahtar : null;
  const pencere = kademeli(gruplar, anahtar, 40);

  function ac(a: string) {
    setAcikSet((eski) => {
      const yeni = new Set(eski);
      if (yeni.has(a)) yeni.delete(a);
      else yeni.add(a);
      return yeni;
    });
  }

  return (
    <>
      {pencere.gorunur.map((g) =>
        g.satirlar.length === 1 ? (
          <li key={g.anahtar}>
            <SeriSatiri s={g.satirlar[0]} onSec={onSec} pasif={pasif} ic={false} />
          </li>
        ) : (
          <li key={g.anahtar}>
            <GrupSatiri
              g={g}
              acik={hepsiAcik || acikSet.has(g.anahtar) || g.anahtar === tekGrup}
              ac={() => ac(g.anahtar)}
              onSec={onSec}
              pasif={pasif}
            />
          </li>
        ),
      )}
      {/* Gözcü: görünür olunca pencere büyür. Kesme değil — tüm gruplara
          erişilebilir, yalnızca çizim ertelenir. */}
      {pencere.kalan > 0 && (
        <li ref={pencere.bitis}>
          <button
            type="button"
            onClick={pencere.daha}
            className="w-full rounded-sm border border-cizgi bg-panel2 px-3 py-2
              text-mikro font-semibold text-solgun"
          >
            {pencere.kalan} malzeme daha
          </button>
        </li>
      )}
    </>
  );
}
