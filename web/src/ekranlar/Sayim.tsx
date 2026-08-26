/** 2. ekran — asıl sayım. Tek input sürekli odaklı, geri bildirim sesli. */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Durum, type OkutmaSonucu } from "../api";
import { Dugme, Kod, Marka, Nokta, Rozet, SayacKutu } from "../bilesenler";
import * as Ik from "../ikonlar";
import Isima, { type IsimaRenk } from "../Isima";
import type { BaglantiHali } from "../olaylar";
import { bip, sesAcikMi, sesiAyarla } from "../ses";
import TelefonKutu from "../TelefonKutu";

type Props = {
  durum: Durum;
  setDurum: (d: Durum) => void;
  canli: BaglantiHali;
  uzaktan: boolean;
  modDegistir: () => void;
  git: (ekran: "kuyruk" | "esleme" | "rapor" | "gecmis" | "ayarlar" | "etiket") => void;
};

const KISAYOL: Record<string, string> = {
  F2: "##SONRAKI##",
  F3: "##FAZLA##",
  F4: "##ATLA##",
  Escape: "##IPTAL##",
  F10: "##BITIR##",
};

/* Şerit rengi ile ambiyans ışımasının rengi tek yerden geliyor: ekranda gördüğü
   renk ile ışımanın rengi ayrışırsa geri bildirim kafa karıştırır. */
const YESIL = { sinif: "border-ok bg-ok-tint text-ok", renk: "ok" as IsimaRenk };
const SARI = { sinif: "border-uyari bg-uyari-tint text-uyari", renk: "uyari" as IsimaRenk };
const KIRMIZI = { sinif: "border-hata bg-hata-tint text-hata", renk: "hata" as IsimaRenk };
const MAVI = { sinif: "border-bilgi bg-bilgi-tint text-bilgi", renk: "bilgi" as IsimaRenk };

type Serit = {
  Ikon: typeof Ik.Onay;
  ana: string;
  alt: string;
  sinif: string;
  renk: IsimaRenk;
};

/** Okutma sonucunu ekranın üstündeki büyük şeride çevirir. */
function seritMetni(r: OkutmaSonucu): Serit | null {
  switch (r.tip) {
    case "eslesti":
      return {
        Ikon: Ik.Onay,
        ana: `${r.kod} — ${r.seri}`,
        alt:
          `${r.aciklama ?? ""}` +
          (r.ogrenilen?.length ? ` · öğrenildi: ${r.ogrenilen.join(", ")}` : "") +
          (r.adet_yersiz ? ` · UYARI: ${r.adet_yersiz} adet uygulanmadı, bu kalem seri takipli` : "") +
          (r.etiket ? ` · etiket ${r.etiket} bağlandı` : ""),
        ...YESIL,
      };
    case "slot":
      // Seri numarası verilmediyse sayım işlendi ama Tiger düzeltmesi
      // ÜRETİLMEDİ. Eskiden buraya malzeme kodu yazılıyor ve Tiger'a kirli bir
      // seri numarası öneriliyordu; şimdi boş bırakılıyor, kullanıcı uyarılıyor.
      return r.sn_yok
        ? {
            Ikon: Ik.Uyari,
            ana: `${r.kod} — sayıldı, seri numarası YOK`,
            alt:
              `${r.aciklama ?? ""} · Tiger'daki uydurma kayıt (${r.eski}) düzelmeyecek. ` +
              "Düzelmesi için üretici S/N'yi okut ya da bir DS- etiketi yapıştırıp okut, " +
              "sonra Ctrl+Z ile bu okutmayı geri al.",
            ...SARI,
          }
        : {
            Ikon: Ik.Onay,
            ana: `${r.kod} — uydurma kayıt düzeltildi`,
            alt:
              `${r.eski} → ${r.yeni} · ${r.aciklama ?? ""}` +
              (r.adet_yersiz ? ` · UYARI: ${r.adet_yersiz} adet uygulanmadı, bu kalem seri takipli` : "") +
              (r.etiket ? ` · etiket ${r.etiket} bağlandı` : ""),
            ...YESIL,
          };
    case "adet":
      // Lot/izlemesiz kalemde boş etiket okutulmuşsa bağlanacak kayıt yok:
      // sayım işlendi ama etiket havuzda kalsın diye kullanıcı uyarılır.
      return r.etiket_yersiz
        ? {
            Ikon: Ik.Uyari,
            ana: `${r.etiket_yersiz} bağlanmadı — ${r.kod} birim izlemeli değil`,
            alt: `Sayıldı (${r.toplam} / ${r.beklenen}). Etiketi çıkarıp havuza geri koy.`,
            ...SARI,
          }
        : {
            Ikon: Ik.Onay,
            ana:
              `${r.kod} — sayılan ${r.toplam} / beklenen ${r.beklenen}` +
              ((r.miktar ?? 1) > 1 ? `  (+${r.miktar})` : ""),
            // Sayaç artık malzemenin geneli değil, yazıldığı SATIR için.
            // Çok lotlu malzemede hangi lota işlendiği görünmezse "1 / 1"
            // sonuçları birbirinin aynısı görünür (CLAUDE.md 2.4).
            alt:
              (r.izleme === "lot" && r.seri ? `Lot ${r.seri} · ` : "") +
              ((r.satir ?? 1) > 1 ? `${r.satir} lot satırına dağıtıldı · ` : "") +
              (r.aciklama ?? ""),
            ...YESIL,
          };
    // Adet girişi (CLAUDE.md 2.4). Henüz sayılmadı — sıradaki grubu bekliyor.
    case "adet_bekliyor":
      return r.miktar
        ? {
            Ikon: Ik.Raf,
            ana: `Sıradaki ürün: ${r.miktar} adet`,
            alt: "Şimdi ürünün barkodunu okut, sonra SIRADAKİ ÜRÜN. Üst üste okutursan toplanır.",
            ...SARI,
          }
        : {
            Ikon: Ik.Raf,
            ana: "Adet sıfırlandı",
            alt: "Sıradaki ürün 1 adet sayılacak.",
            ...SARI,
          };
    case "adet_tavan":
      return {
        Ikon: Ik.Uyari,
        ana: `Adet tavanı aşıldı — ${r.tavan} üstüne çıkılamaz`,
        alt: `Bekleyen adet ${r.miktar} olarak kaldı. Sıfırlamak için ADEDİ SIFIRLA okut.`,
        ...KIRMIZI,
      };
    // Sayım dışı kalem. Hiçbir şey yazılmadı — sessiz kalmak, kullanıcının
    // elindeki fiziksel ürünü mutabakattan buharlaştırıyordu.
    case "haric":
      return {
        Ikon: Ik.Engel,
        ana: `SAYIM DIŞI — ${r.kod}`,
        alt:
          `${r.aciklama ?? ""} · "${r.sebep}" kuralı bu kalemi sayım dışı bırakıyor, ` +
          "sayılmadı. Sayılması gerekiyorsa Kurulum ekranından kuralı kapat.",
        ...SARI,
      };
    case "fazla":
    case "fazla_elle":
      return {
        Ikon: Ik.Uyari,
        ana: `FAZLA — ${r.kod ?? (r.barkodlar ?? []).join(", ")}`,
        alt: r.aciklama ?? "Tiger kaydında karşılığı yok, rapora fazla olarak yazıldı.",
        ...KIRMIZI,
      };
    // Malzeme tanındı ama seri numarası Tiger'daki hiçbir kayıtla eşleşmedi.
    // Bu "stokta yok" demek DEĞİLDİR, o yüzden fazla yazılmaz — kullanıcı
    // karar verene kadar kuyrukta bekler (DEMO_FEEDBACK.md 5).
    case "onay":
      return {
        Ikon: Ik.Soru,
        ana: `KARŞILIĞI BULUNAMADI — ${r.kod}`,
        alt:
          `${r.aciklama ?? ""} · Kuyrukta seni bekliyor: stokta karşılığı var mı, yoksa gerçekten fazla mı?` +
          (r.adet_yersiz ? ` · UYARI: ${r.adet_yersiz} adet uygulanmadı, bu kalem seri takipli` : ""),
        ...SARI,
      };
    case "tekrar":
      return {
        Ikon: Ik.Tekrar,
        ana: `TEKRAR — ${r.kod}`,
        alt: `${r.seri} zaten okutuldu, ikinci kez sayılmadı.`,
        ...SARI,
      };
    case "kuyruk":
      return {
        Ikon: Ik.Soru,
        ana: "KUYRUĞA ATILDI",
        alt: r.bos_etiket?.length
          ? `${r.bos_etiket[0]} boş etiketi tek başına okutuldu — hangi malzeme olduğu belli değil.`
          : `${(r.barkodlar ?? []).join(" + ")} — sayımı durdurma, sonunda çözersin.`,
        ...SARI,
      };
    case "iptal":
      return { Ikon: Ik.Tekrar, ana: "GRUP İPTAL", alt: "Tampon boşaltıldı.", ...SARI };
    case "gerial":
      return {
        Ikon: Ik.Geri,
        ana: r.kapsam === "grup" ? "SON GRUP GERİ ALINDI" : "SON OKUTMA SİLİNDİ",
        // Yan etkiler de geri alındı: öğrenilen barkod unutuldu, etiket havuza
        // döndü. Söylenmezse kullanıcı öğrenmenin durduğunu sanır.
        alt:
          (r.kapsam === "grup" ? (r.barkodlar ?? []).join(", ") : (r.ham ?? "")) +
          (r.unutulan?.length ? ` · unutuldu: ${r.unutulan.join(", ")}` : "") +
          (r.etiket_cozuldu ? ` · ${r.etiket_cozuldu} havuza döndü` : ""),
        ...SARI,
      };
    case "raf":
      return { Ikon: Ik.Raf, ana: `RAF ${r.raf}`, alt: "Sonraki okutmalar bu rafa yazılacak.", ...MAVI };
    case "bitti":
      return { Ikon: Ik.Bitti, ana: "SAYIM BİTTİ", alt: "Rapor ekranına geçebilirsin.", ...MAVI };
    case "raf_engel":
      return {
        Ikon: Ik.Engel,
        ana: `${r.eski_raf} rafında ${r.kuyruk?.length} ürün çözülmedi`,
        alt: "Ürünler hâlâ önündeyken çöz — gün sonunda hangisi olduğunu hatırlaman çok daha zor.",
        ...KIRMIZI,
      };
    case "bitir_engel":
      return {
        Ikon: Ik.Engel,
        ana: `Kuyrukta ${r.kuyruk?.length} çözülmemiş ürün var`,
        alt: "Bitirmeden önce çöz; yoksa hepsi raporda 'fazla' olarak kalır.",
        ...KIRMIZI,
      };
    case "ad_engel":
      return {
        Ikon: Ik.Soru,
        ana: `${r.adsiz?.length} fazla kaydının ne olduğu yazılmamış`,
        alt: "Bu ürünlerin Tiger'da kaydı yok; adı yazılmazsa raporda yalnızca seri numarası ve raf kalır.",
        ...KIRMIZI,
      };
    case "foto_engel":
      return {
        Ikon: Ik.Kamera,
        ana: `${r.fotosuz?.length} fazla kaydının fotoğrafı yok`,
        alt: "Fazla, sayımdan sonra kimsenin doğrulayamayacağı tek çıktı — ürün rafa geri konuyor, geriye bu satır kalıyor.",
        ...KIRMIZI,
      };
    default:
      return null;
  }
}

export default function Sayim({ durum, setDurum, canli, uzaktan, modDegistir, git }: Props) {
  const [son, setSon] = useState<OkutmaSonucu | null>(null);
  const [odak, setOdak] = useState(true);
  const [ses, setSes] = useState(sesAcikMi());
  const [mesgul, setMesgul] = useState(false);
  const [elleGiris, setElleGiris] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const [telefonKutu, setTelefonKutu] = useState(false);
  /* Elle fazla işaretlenen kayıtlar — adı sorulana (ya da geçilene) kadar. */
  const [fazlaIdler, setFazlaIdler] = useState<number[]>([]);
  const [fazlaAd, setFazlaAd] = useState("");
  /* Ambiyans ışımasını yeniden tetiklemek için sayaç: aynı barkod arka arkaya
     okutulduğunda sonuç nesnesi aynı görünse de ışık yine çakmalı. */
  const [isik, setIsik] = useState(0);
  const girisRef = useRef<HTMLInputElement>(null);

  const odakla = useCallback(() => {
    // Uzaktan ekranda (telefon) odaklamıyoruz: ekran klavyesi sürekli açılır,
    // ekranın yarısını kaplar ve izlemek için gelen kullanıcıyı boğar.
    if (uzaktan) return;
    requestAnimationFrame(() => girisRef.current?.focus());
  }, [uzaktan]);

  useEffect(() => {
    odakla();
  }, [odakla]);

  /* Okuyucu saniyede birkaç barkod basabiliyor. İstekler paralel gitseydi
     sunucu bunları farklı thread'lerde işler ve ##SONRAKI## kendinden önceki
     barkodun önüne geçebilirdi — grup eksik kapanırdı. Bu yüzden okutmalar tek
     sıraya dizilip birbiri ardına gönderiliyor. */
  const siraRef = useRef<Promise<void>>(Promise.resolve());
  const bekleyenRef = useRef(0);

  const gonder = useCallback(
    (ham: string, zorla = false) => {
      if (!ham.trim()) return siraRef.current;
      bekleyenRef.current += 1;
      setMesgul(true);
      siraRef.current = siraRef.current.then(async () => {
        try {
          const r = await api.okut(durum.oturum, ham, zorla);
          bip(r.ses ?? "tik");
          setSon(r.tip === "tampon" ? null : r);
          if (r.tip !== "tampon") setIsik((n) => n + 1);
          // Elle fazla: hemen "bu ne?" diye sor, kayıt isimsiz kalmasın.
          if (r.tip === "fazla_elle" && r.okutma?.length) {
            setFazlaIdler(r.okutma);
            setFazlaAd("");
          }
          setHata(null);
          if (r.durum) setDurum(r.durum);
        } catch (e) {
          bip("uyari");
          setHata(e instanceof Error ? e.message : String(e));
        } finally {
          bekleyenRef.current -= 1;
          if (bekleyenRef.current === 0) {
            setMesgul(false);
            odakla();
          }
        }
      });
      return siraRef.current;
    },
    [durum.oturum, setDurum, odakla],
  );

  // Klavye kısayolları — komut kartı elde değilse
  useEffect(() => {
    function tus(e: KeyboardEvent) {
      // BAŞKA bir yazı alanında yazarken kısayollar susar. Escape küresel
      // ##IPTAL## olduğu için, ürün adını yazarken "bu kutuyu kapat" refleksiyle
      // Escape'e basmak o anki grubu sessizce siliyordu.
      //
      // Okuyucu kutusu istisna: barkod okuyucu oraya yazıyor ve komut kartındaki
      // barkodlar da oradan geçiyor — F2/F3/F4 orada çalışmaya devam etmeli.
      const hedef = e.target as HTMLElement | null;
      const yaziAlani =
        hedef instanceof HTMLInputElement ||
        hedef instanceof HTMLTextAreaElement ||
        hedef?.isContentEditable === true;
      if (yaziAlani && hedef !== girisRef.current) return;

      if (e.ctrlKey && e.key.toLowerCase() === "z") {
        e.preventDefault();
        void gonder("##GERIAL##");
        return;
      }
      const komut = KISAYOL[e.key];
      if (!komut) return;
      e.preventDefault();
      if (komut === "##BITIR##" && !confirm("Sayımı bitirip oturumu kapatalım mı?")) return;
      void gonder(komut);
    }
    window.addEventListener("keydown", tus);
    return () => window.removeEventListener("keydown", tus);
  }, [gonder]);

  async function fazlaAdKaydet() {
    const ad = fazlaAd.trim();
    if (!ad) {
      setFazlaIdler([]);
      return;
    }
    try {
      // Grup birden çok barkod taşıyabilir; hepsi aynı ürün, aynı adı alır.
      await Promise.all(fazlaIdler.map((id) => api.okutmaAd(id, ad)));
      bip("ok");
      setFazlaIdler([]);
      setFazlaAd("");
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    } finally {
      odakla();
    }
  }

  const s = durum.sayac;
  const serit = son ? seritMetni(son) : null;
  const engel =
    son && (son.tip === "raf_engel" || son.tip === "bitir_engel") ? son : null;
  const fotoEngel = son?.tip === "foto_engel" ? son : null;
  const adEngel = son?.tip === "ad_engel" ? son : null;

  function zorlaDevam() {
    if (!engel) return;
    const komut = engel.tip === "raf_engel" ? `##RAF-${engel.yeni_raf}##` : "##BITIR##";
    if (!confirm("Çözülmemiş ürünler kuyrukta kalacak. Yine de devam edilsin mi?")) return;
    void gonder(komut, true);
  }

  return (
    <div className="flex h-full flex-col">
      {/* Okutma sonucunun ambiyans ışıması — sesli geri bildirimin görsel eşi. */}
      {serit && <Isima key={isik} renk={serit.renk} />}

      {/* Üst şerit. Yedi düğme iki gruba ayrıldı: soldaki sayıma ait gezinme,
          sağdaki cihaz ayarları. Eskiden iki cam "hap ada"ydı; artık düz
          zeminde duran iki düğme kümesi — kutu içinde kutu olmasın. */}
      <header className="flex flex-wrap items-center gap-4 border-b border-cizgi bg-panel px-5 py-3">
        <Marka boy={30} yazi={false} />
        <div>
          <div className="text-mikro font-semibold tracking-wider text-solgun uppercase">
            Ambar {durum.ambar} · oturum #{durum.oturum}
          </div>
          <div className="text-2xl leading-tight font-bold">
            {durum.aktif_raf ? (
              <span className="inline-flex items-center gap-2 text-uyari">
                <Ik.Raf boy={20} />
                Raf {durum.aktif_raf}
              </span>
            ) : (
              <span className="text-solgun italic">raf seçilmedi</span>
            )}
            {/* Bekleyen adet sessiz kalmamalı: kullanıcı 25 okuttuğunu unutup
                sonraki ürüne geçerse 25 adet yanlış kaleme yazılır. */}
            {durum.bekleyen_adet > 0 && (
              <span className="ml-3 inline-flex items-center gap-1 border border-vurgu
                               bg-vurgu-tint px-2 py-0.5 text-govde font-bold text-vurgu">
                sıradaki: <span className="rakam">{durum.bekleyen_adet}</span> adet
              </span>
            )}
          </div>
        </div>

        <div className="ml-auto flex items-center gap-5">
          <SayacKutu etiket="okutulan" deger={s.okutulan} vurgu="ok" />
          <SayacKutu etiket="kalan" deger={s.kalan} />
          <SayacKutu etiket="fazla" deger={s.fazla} vurgu={s.fazla ? "hata" : undefined} />
          <SayacKutu etiket="kuyruk" deger={s.kuyruk} vurgu={s.kuyruk ? "uyari" : undefined} />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span
            title={
              canli === "canli"
                ? "Canlı bağlantı açık — telefon ekranı kendiliğinden güncelleniyor"
                : "Canlı bağlantı yok — ekranlar yedek yoklamayla güncelleniyor"
            }
            className="px-1"
          >
            <Nokta hal={canli} />
          </span>

          <div className="flex flex-wrap gap-2">
            <Dugme
              cocuk={`Kuyruk${s.kuyruk ? ` (${s.kuyruk})` : ""}`}
              tikla={() => git("kuyruk")}
              tur={s.kuyruk ? "tehlike" : "sade"}
            />
            <Dugme
              cocuk={`Eşleştir${s.fazla ? ` (${s.fazla})` : ""}`}
              tikla={() => git("esleme")}
              tur={s.fazla ? "tehlike" : "sade"}
            />
            <Dugme cocuk="Rapor" tikla={() => git("rapor")} />
            <Dugme cocuk="Etiket" tikla={() => git("etiket")} />
            <Dugme cocuk="Ayarlar" tikla={() => git("ayarlar")} />
          </div>

          <div className="flex flex-wrap gap-2">
            <Dugme
              cocuk={
                <>
                  <Ik.Telefon /> Telefon
                </>
              }
              baslik="Telefonu canlı izleme ekranı olarak bağla (QR)"
              tikla={() => setTelefonKutu(true)}
            />
            <Dugme
              cocuk={
                uzaktan ? (
                  <>
                    <Ik.Telefon /> Uzaktan
                  </>
                ) : (
                  <>
                    <Ik.Okuyucu /> Okuyucu
                  </>
                )
              }
              baslik={
                uzaktan
                  ? "Bu cihaz uzaktan ekran — barkod alanı odaklanmıyor"
                  : "Bu cihazda okuyucu takılı — barkod alanı sürekli odakta"
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
              baslik="Sesli geri bildirim"
              tikla={() => {
                const y = !ses;
                setSes(y);
                sesiAyarla(y);
                if (y) bip("tik");
                odakla();
              }}
            />
          </div>
        </div>
      </header>

      {!odak && !uzaktan && (
        <div className="nabiz flex flex-wrap items-center justify-center gap-2 bg-hata px-5
          py-2 text-center text-govde font-bold text-white">
          <Ik.Uyari boy={18} /> Okuyucu girişi odakta değil — ekrana bir kez dokunun, okutmalar
          kaybolmasın
        </div>
      )}

      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4 overflow-hidden p-5">
        {uzaktan && (
          <div className="flex flex-wrap items-center gap-3 rounded-sm border border-bilgi
            bg-bilgi-tint px-4 py-3">
            <span className="inline-flex items-center gap-2 text-kucuk text-bilgi">
              <Ik.Telefon /> Uzaktan ekran — laptopta okutulanlar buraya canlı düşer.
            </span>
            <span className="ml-auto flex gap-2">
              <Dugme
                cocuk={
                  elleGiris ? (
                    "Klavyeyi gizle"
                  ) : (
                    <>
                      <Ik.Klavye /> Elle barkod gir
                    </>
                  )
                }
                tikla={() => {
                  const y = !elleGiris;
                  setElleGiris(y);
                  if (y) requestAnimationFrame(() => girisRef.current?.focus());
                }}
              />
              <Dugme cocuk="F2 · Sıradaki ürün" tikla={() => void gonder("##SONRAKI##")} />
            </span>
          </div>
        )}
        {/* Giriş. Cam ve animasyon katmanlarının hepsi pointer-events-none —
            okuyucunun yazdığı yerin odağı hiçbir koşulda kaybolmamalı. */}
        <div className={uzaktan && !elleGiris ? "hidden" : ""}>
          <input
            ref={girisRef}
            autoFocus={!uzaktan}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            disabled={durum.durum !== "acik"}
            placeholder={
              uzaktan ? "Barkodu elle yaz, Enter" : "Barkodu okut — ürün bitince SIRADAKİ ÜRÜN okut"
            }
            onFocus={() => setOdak(true)}
            onBlur={() => {
              setOdak(false);
              if (!uzaktan) setTimeout(odakla, 60);
            }}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              const v = e.currentTarget.value;
              e.currentTarget.value = "";
              void gonder(v);
            }}
            /* Gölge YOK (Flat) ve focus:outline-none YOK.
               Eskiden buradaki hâle rgba(76,111,255,0.08) ile sabit kodlanmıştı —
               ESKİ vurgu rengi; jeton değişimini takip etmiyordu ve açık zeminde
               kirli bir gri-mavi lekeye dönüyordu.
               focus:outline-none da kaldırıldı: alan zaten border-vurgu olduğu
               için odaklanınca hiçbir şey değişmiyordu. Artık global 3px odak
               halkası görünüyor — alan sürekli odakta olduğundan halka "imleç
               burada" işareti olarak duruyor, odak kaçtığında kayboluyor ve bu
               tam da kırmızı şeridin uyardığı durum. */
            className="w-full rounded-sm border-2 border-vurgu bg-panel px-5 py-5 font-mono
              text-2xl text-yazi placeholder:text-solgun-hafif
              disabled:bg-panel2 disabled:text-solgun-hafif"
          />
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-mikro text-solgun">
            <span>
              <kbd className="rounded-sm border border-cizgi px-2 py-0.5">F2</kbd> sıradaki ürün
            </span>
            <span>
              <kbd className="rounded-sm border border-cizgi px-2 py-0.5">Esc</kbd> grubu iptal
            </span>
            <span>
              <kbd className="rounded-sm border border-cizgi px-2 py-0.5">Ctrl+Z</kbd> geri al
            </span>
            <span>
              <kbd className="rounded-sm border border-cizgi px-2 py-0.5">F3</kbd> fazla
            </span>
            <span>
              <kbd className="rounded-sm border border-cizgi px-2 py-0.5">F4</kbd> atla
            </span>
            <span>
              <kbd className="rounded-sm border border-cizgi px-2 py-0.5">F10</kbd> bitir
            </span>
            {mesgul && <span className="text-vurgu">işleniyor…</span>}
          </div>
        </div>

        {hata && (
          <div className="rounded-sm border border-hata bg-hata-tint px-4 py-3 font-semibold text-hata">
            {hata}
          </div>
        )}

        {serit && (
          <div className={`girdi flex items-center gap-4 rounded-sm border px-5 py-4 ${serit.sinif}`}>
            <serit.Ikon boy={30} />
            <div className="min-w-0">
              <div className="text-xl font-bold break-words">{serit.ana}</div>
              {serit.alt && <div className="text-kucuk break-words">{serit.alt}</div>}
            </div>
          </div>
        )}

        {/* Elle fazla işaretlenen ürünün Tiger'da kaydı yok: kod da açıklama da
            boş kalır. Adı şimdi sorulmazsa rapordaki satır kimsenin işine
            yaramaz (DEMO_FEEDBACK.md 3). Zorunlu değil — sayımı durdurmaz. */}
        {fazlaIdler.length > 0 && (
          <section className="girdi rounded-sm border border-hata bg-hata-tint p-3">
            <h2 className="mb-2 text-kucuk font-bold tracking-wider text-hata uppercase">
              Bu ürün neydi? · yazılmadan sayım bitirilemez
            </h2>
            <div className="flex flex-wrap gap-2">
              <input
                value={fazlaAd}
                onChange={(e) => setFazlaAd(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && void fazlaAdKaydet()}
                placeholder="örn. Kırmızı HP güç kablosu, 2 m"
                className="min-w-[260px] flex-1 rounded-sm border border-cizgi bg-zemin px-3
                  py-2 text-govde focus:border-vurgu focus:outline-none"
              />
              <Dugme cocuk="Kaydet" tur="ana" tikla={() => void fazlaAdKaydet()} />
              <Dugme cocuk="Sonra yazarım" tikla={() => setFazlaIdler([])} />
            </div>
          </section>
        )}

        {/* "Bu olabilir" aday önerisi kaldırıldı: sahada doğru sonuç
            vermiyordu (DEMO_FEEDBACK.md 4). Kuyruğa düşen kayıt Kuyruk
            ekranından aranarak çözülür — sayım burada durmaz. */}
        {adEngel && (
          <section className="girdi flex flex-wrap items-center gap-3 rounded-sm border
            border-hata bg-hata-tint p-3">
            <p className="min-w-0 flex-1 text-kucuk text-solgun">
              Eşleştirme ekranından bu ürünlerin ne olduğunu yaz — rapordaki satır
              ancak öyle işe yarar.
            </p>
            <Dugme cocuk="Eşleştirmeye git" tur="ana" tikla={() => git("esleme")} />
          </section>
        )}

        {fotoEngel && (
          <section className="girdi flex flex-wrap items-center gap-3 rounded-sm border
            border-hata bg-hata-tint p-3">
            <p className="min-w-0 flex-1 text-kucuk text-solgun">
              Eşleştirme ekranından fotoğrafları ekle — ya da fazla sandığın ürünün
              aslında eksik listesinde durduğunu orada görebilirsin.
            </p>
            <Dugme cocuk="Eşleştirmeye git" tur="ana" tikla={() => git("esleme")} />
          </section>
        )}

        {son?.tip === "kuyruk" && (
          <section className="girdi flex flex-wrap items-center gap-3 rounded-sm border
            border-uyari bg-uyari-tint p-3">
            <p className="min-w-0 flex-1 text-kucuk text-solgun">
              Kuyruğa atıldı — sayımı durdurma. Ürün hâlâ elindeyken çözmek istersen
              Kuyruk ekranından arayıp bağla.
            </p>
            <Dugme cocuk="Kuyruğa git" tikla={() => git("kuyruk")} />
          </section>
        )}

        {/* mevcut grup */}
        <section className="border border-cizgi bg-panel rounded-sm">
          <header className="flex items-center justify-between border-b border-cizgi px-4 py-2">
            <h2 className="text-kucuk font-bold tracking-wider text-solgun uppercase">
              Mevcut grup
            </h2>
            <span className="text-kucuk text-solgun">
              {durum.tampon.length === 0
                ? "boş — ürünün barkodlarını okutmaya başla"
                : `${durum.tampon.length} barkod · SIRADAKİ ÜRÜN ile kapat`}
            </span>
          </header>
          <ul className="flex flex-col gap-2 bg-panel p-3">
            {durum.tampon.map((t, i) => (
              <li
                key={`${t.ham}-${i}`}
                className="girdi flex flex-wrap items-center gap-3 rounded-sm bg-panel2 px-3 py-2"
              >
                <Rozet tip={t.coz} />
                <Kod cocuk={t.ham} />
                {t.kod && (
                  <span className="text-kucuk text-solgun">
                    → <b className="text-yazi">{t.kod}</b> {t.aciklama}
                  </span>
                )}
                {t.not && <span className="text-mikro text-vurgu">({t.not})</span>}
              </li>
            ))}
            {durum.tampon.length === 0 && (
              <li className="px-2 py-4 text-center text-lg text-solgun italic">
                Ürünün üstündeki barkodları sırayla okut: P/N, S/N, UPC — hangisi varsa.
              </li>
            )}
          </ul>
        </section>

        {/* son okutmalar */}
        <section className="border border-cizgi bg-panel flex min-h-0 flex-1 flex-col rounded-sm">
          <header className="border-b border-cizgi px-4 py-2">
            <h2 className="text-kucuk font-bold tracking-wider text-solgun uppercase">
              Son okutmalar
            </h2>
          </header>
          <ul className="flex-1 overflow-y-auto bg-panel">
            {durum.akis.map((a, i) => (
              <li
                key={`${a.ts}-${i}`}
                className={`flex flex-wrap items-baseline gap-3 border-l-4 px-4 py-2 text-kucuk
                  ${
                    a.tip === "fazla" || a.tip === "bilinmiyor"
                      ? "border-l-hata"
                      : a.tip === "kod"
                        ? "border-l-bilgi"
                        : "border-l-ok"
                  } ${i % 2 ? "bg-panel2" : ""}`}
              >
                <span className="rakam text-mikro text-solgun">{a.ts.slice(11, 19)}</span>
                {a.raf && (
                  <span className="inline-flex items-center gap-1 text-mikro text-uyari">
                    <Ik.Raf boy={12} />
                    {a.raf}
                  </span>
                )}
                <b className="font-mono">{a.kod ?? a.ham}</b>
                {a.seri && <span className="font-mono text-solgun">{a.seri}</span>}
                <span className="ml-auto text-mikro text-solgun">{a.not_ || a.tip}</span>
              </li>
            ))}
            {durum.akis.length === 0 && (
              <li className="py-8 text-center text-lg text-solgun italic">
                Henüz okutma yok.
              </li>
            )}
          </ul>
        </section>
      </div>

      {telefonKutu && <TelefonKutu kapat={() => setTelefonKutu(false)} />}

      {engel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-yazi/45 p-4">
          <div className="border border-cizgi bg-panel w-full max-w-2xl rounded-sm ring-2 ring-hata">
            <header className="border-b border-cizgi p-5">
              <h2 className="flex items-center gap-3 text-3xl leading-tight font-bold text-hata">
                <Ik.Engel boy={28} />
                {engel.tip === "raf_engel"
                  ? `${engel.eski_raf} rafından ayrılmadan önce`
                  : "Sayımı bitirmeden önce"}
              </h2>
              <p className="mt-2 text-govde text-solgun">
                {engel.kuyruk?.length} ürün tanınmadı ve kuyrukta bekliyor. Ürünler hâlâ
                elinin altındayken çözmek, gün sonunda barkod listesine bakıp hangisi
                olduğunu hatırlamaya çalışmaktan çok daha kolay.
              </p>
            </header>
            <ul className="max-h-64 overflow-y-auto p-4">
              {engel.kuyruk?.map((k) => (
                <li
                  key={k.id}
                  className="mb-2 rounded-sm border border-cizgi bg-panel2 px-3 py-2"
                >
                  <div className="flex flex-wrap gap-2">
                    {k.barkodlar.map((b) => (
                      <span key={b} className="font-mono text-kucuk">
                        {b}
                      </span>
                    ))}
                  </div>
                  <div className="mt-1 text-mikro text-solgun">
                    {k.raf && (
                      <span className="inline-flex items-center gap-1 text-uyari">
                        <Ik.Raf boy={12} /> {k.raf} ·{" "}
                      </span>
                    )}
                    {k.ts}
                    {k.not_ && <span> · {k.not_}</span>}
                  </div>
                </li>
              ))}
            </ul>
            <footer className="flex flex-wrap gap-3 border-t border-cizgi p-4">
              <Dugme cocuk="Kuyruğu şimdi çöz" tur="ana" tikla={() => git("kuyruk")} />
              <Dugme cocuk="Vazgeç, saymaya devam et" tikla={() => setSon(null)} />
              <span className="ml-auto">
                <Dugme
                  cocuk={engel.tip === "raf_engel" ? "Yine de rafı değiştir" : "Yine de bitir"}
                  tur="tehlike"
                  tikla={zorlaDevam}
                />
              </span>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}
