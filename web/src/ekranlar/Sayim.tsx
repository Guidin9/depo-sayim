/** 2. ekran — asıl sayım. Tek input sürekli odaklı, geri bildirim sesli. */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type AkisSatiri, type Durum, type OkutmaSonucu } from "../api";
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

/** Okutma sonucunu ekranın üstündeki büyük şeride çevirir.
 *
 * `export` yalnızca test içindir (`Sayim.serit.test.ts`) — bileşenin dışından
 * çağrılmıyor. Saf fonksiyon: girdi sunucu yanıtı, çıktı renk + ikon + metin.
 * Sahadaki en kritik karar burada veriliyor: kullanıcı ekrandaki RENGE bakıp
 * sonraki ürüne geçiyor. Yanlış renk = üstünden geçilen hata.
 */
export function seritMetni(r: OkutmaSonucu): Serit | null {
  switch (r.tip) {
    case "eslesti":
      return {
        Ikon: Ik.Onay,
        ana: `${r.kod} — ${r.seri}`,
        alt:
          `${r.aciklama ?? ""}` +
          (r.ogrenilen?.length ? ` · öğrenildi: ${r.ogrenilen.join(", ")}` : "") +
          (r.tekrar_seri
            ? ` · UYARI: ${r.tekrar_seri} bu grupta ikinci kez okutuldu, sayılmadı`
            : "") +
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
            // Karar bekleyen kayıt YEŞİL olmamalı: "tamam" rengi kullanıcıyı
            // sorunun üstünden geçirir. Sayım doğru ama Tiger'a gidecek değer
            // henüz bir tahmin.
            Ikon: r.sn_secim?.length ? Ik.Soru : Ik.Onay,
            ...(r.sn_secim?.length ? SARI : YESIL),
            ana: r.sn_secim?.length
              ? `${r.kod} — sayıldı, seri numarası SEÇİLMELİ`
              : `${r.kod} — uydurma kayıt düzeltildi`,
            alt:
              `${r.eski} → ${r.yeni} · ${r.aciklama ?? ""}` +
              (r.sn_secim?.length
                ? " · Üründe birden çok tanınmayan barkod var; hangisinin cihaza ait olduğunu aşağıdan seç."
                : "") +
              (r.adet_yersiz ? ` · UYARI: ${r.adet_yersiz} adet uygulanmadı, bu kalem seri takipli` : "") +
              (r.etiket ? ` · etiket ${r.etiket} bağlandı` : ""),
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
        // `not` kirli slot yolundan geliyor: "bu seri numarası az önce
        // 0WGP72SAYIM1 slotuna yazıldı". Kullanıcı hangi cihazı ikinci kez
        // elinde tuttuğunu bilmeli.
        alt: r.not ?? `${r.seri} zaten okutuldu, ikinci kez sayılmadı.`,
        ...SARI,
      };
    /* ##SONRAKI## unutulmuş: tek grupta birden çok cihaz. Hepsi sayıldı —
       eskiden yalnızca ilki sayılıp gerisi sessizce kayboluyordu. */
    case "coklu":
      return {
        Ikon: Ik.Uyari,
        ana: `${r.sayi} AYRI CİHAZ SAYILDI`,
        alt:
          "SIRADAKİ ÜRÜN okutmayı unutmuş olabilirsin — hepsi ayrı ayrı sayıldı, " +
          "hiçbiri kaybolmadı. Yanlışsa Ctrl+Z ile son cihazı geri al. " +
          (r.kayitlar ?? []).map((k) => `${k.kod} ${k.seri}`).join(" · ") +
          (r.ogrenilmedi?.length
            ? ` · ÖĞRENİLMEDİ: ${r.ogrenilmedi.join(", ")} (hangi cihaza ait belli değil)`
            : ""),
        ...SARI,
      };
    /* ##BITIR## komut kartında basılı ve kazara okutulabiliyor: tek okutma
       günlerce süren bir sayımı kapatmamalı. */
    case "bitir_onay":
      return {
        Ikon: Ik.Uyari,
        ana: "SAYIMI BİTİRMEK İÇİN BİR KEZ DAHA OKUT",
        alt:
          `Kazara okutmaya karşı çift onay. ${r.saniye ?? 60} saniye içinde ` +
          "SAYIMI BİTİR barkodunu tekrar okut. Araya başka bir okutma girerse iptal olur.",
        ...SARI,
      };
    /* Engel DEĞİL, bilgi: sayım doğru, eksik olan bilgi. */
    case "bitir_uyari":
      return {
        Ikon: Ik.Uyari,
        ana: "BİTİRMEDEN ÖNCE BAK",
        alt:
          [
            r.eksik_lot?.length
              ? `${r.eksik_lot.length} lot satırında sayılan < beklenen: ` +
                r.eksik_lot
                  .slice(0, 4)
                  .map((x) => `${x.kod} ${x.sayilan}/${x.beklenen}`)
                  .join(", ")
              : "",
            r.sn_secilmemis?.length
              ? `${r.sn_secilmemis.length} kayıtta Tiger'a önerilen seri numarası tahmin`
              : "",
          ]
            .filter(Boolean)
            .join(" · ") +
          ` · Sayım DOĞRU, bunlar bilgi. Bitirmek için ${r.saniye ?? 60} saniye ` +
          "içinde SAYIMI BİTİR barkodunu tekrar okut.",
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
    /* Kap okutması (KUTU_TASARIM.md). Kap "içinde NE var" der, "kaç tane"
       demez: içerik ayda bir değişiyor, sayım yılda bir yapılıyor. Kayıttaki
       adet bir varsayımdır ve sorulmadan sayıma yazılmaz. */
    case "kutu_tanimsiz":
      return {
        Ikon: Ik.Soru,
        ana: `TANIMSIZ KAP — ${r.kutu}`,
        alt: "Bu kapta ne olduğunu bir kez söyle; kalıcı olarak kaydedilir ve "
          + "gelecek sayımlarda kap kendi malzemesini söyler.",
        ...SARI,
      };
    case "kutu_yabanci":
      return {
        Ikon: Ik.Soru,
        ana: `KAP BAŞKA MALZEMEYE KAYITLI — ${r.kutu}`,
        alt:
          `Kayıtlı içeriği (${r.eski_kod}) bu ambarda yok. Kabın içeriği değişmiş ` +
          "olabilir: kuyruktan doğru malzemeyi seç ya da fazla olarak yaz.",
        ...SARI,
      };
    case "kutu_sor":
      return {
        Ikon: Ik.Katman,
        ana: `${r.kutu} — ${r.kod}: kaç adet?`,
        alt:
          `${r.aciklama ?? ""} · ` +
          (r.oneri_adet != null
            ? `Kayıtta ${r.oneri_adet} yazıyor (yeni doğrulanmış). Doğrula ya da düzelt.`
            : r.adet != null
              ? `Son bilinen ${r.adet} adet ama kayıt eski — sayıp yaz.`
              : "Kapta kaç adet olduğunu yaz."),
        ...SARI,
      };
    case "kutu_acildi":
      return {
        Ikon: Ik.Kilit,
        // Zaten açık kabı yeniden okutmak sayacı SIFIRLAMAZ; ekran da
        // "açıldı" demez, kaç okutulduğunu söyler.
        ana: r.zaten_acik
          ? `KAP ZATEN AÇIK · ${r.kutu} — ${r.sayilan} okutuldu`
          : `KAP AÇILDI · ${r.kutu} — ${r.kod}`,
        alt:
          `${r.aciklama ?? ""} · Malzeme kilitlendi: şimdi yalnızca seri numaralarını ` +
          "okut, her cihazda malzemeyi tekrarlama. Bittiğinde KABI KAPAT." +
          (r.adet != null ? ` Kapta son bilinen ${r.adet} adet.` : "") +
          (r.onceki_kutu
            ? ` · Önceki kap ${r.onceki_kutu.kutu} kapandı (${r.onceki_kutu.sayilan} okutuldu).`
            : "") +
          (r.adet_yersiz ? ` · UYARI: ${r.adet_yersiz} adet uygulanmadı, bu kalem seri takipli` : ""),
        ...MAVI,
      };
    // Kapanış ENGELLEMEZ, söyler: "kapta 150 yazıyordu, 12 okuttun" bir
    // bulgudur. Eksik gerçekten eksikse raporda zaten görünecek.
    case "kutu_kapandi":
      if (r.kayit_yok)
        return {
          Ikon: Ik.Uyari,
          ana: `KAP KAPANDI · ${r.kutu}`,
          alt:
            "Kabın kaydı bulunamadı — arada boşaltılmış olabilir. Kilit bırakıldı, " +
            "sayaç okunamadı. Kabı yeniden okutup içeriğini söyleyebilirsin.",
          ...SARI,
        };
      return r.eksik
        ? {
            Ikon: Ik.Uyari,
            ana: `KAP KAPANDI · ${r.sayilan} / ${r.beklenen} — ${r.eksik} eksik`,
            alt:
              `${r.kutu} · ${r.kod} ${r.aciklama ?? ""} — kapta yazan sayıdan az okutuldu. ` +
              "Kapta yazan sayı son sayımdan kalma bir ipucudur, gerçek değil: " +
              "eksik gerçekse raporda görünecek.",
            ...SARI,
          }
        : {
            Ikon: Ik.Onay,
            ana: `KAP KAPANDI · ${r.sayilan} okutuldu`,
            alt: `${r.kutu} · ${r.kod} ${r.aciklama ?? ""} — kilit açıldı.`,
            ...YESIL,
          };
    case "kutu_yok":
      return {
        Ikon: Ik.Engel,
        ana: "AÇIK KAP YOK",
        alt: "Kapatılacak bir kap yok — kap etiketini okutunca kap açılır.",
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
    case "kilit":
      return {
        Ikon: Ik.Kilit,
        ana: `KİLİTLENDİ · ${r.kod}`,
        alt:
          (r.aciklama ?? "") +
          " — artık yalnız seri numaralarını okut, malzeme kodunu her cihazda tekrarlama.",
        ...MAVI,
      };
    case "kilitac":
      return {
        Ikon: Ik.KilitAcik,
        ana: "KİLİT AÇILDI",
        // Kilit kabın kilidiyse kap da kapandı — sessiz kalmıyoruz, yoksa
        // kullanıcı kabın hâlâ açık olduğunu sanır.
        alt: r.kutu_kapandi
          ? `${r.kutu_kapandi.kutu} kabı da kapandı — ${r.kutu_kapandi.sayilan} okutuldu.`
          : "Normal sayıma dönüldü.",
        ...MAVI,
      };
    case "kilit_yok":
      return {
        Ikon: Ik.Engel,
        ana: "KİLİTLENECEK MALZEME YOK",
        // Sessizce kilitlememek şart: kullanıcı kilitlendiğini sanıp onlarca
        // seri numarası okutur, hepsi kuyruğa düşerdi.
        alt: "Önce malzeme kodunu okut, sonra kilit barkodunu.",
        ...KIRMIZI,
      };
    case "yedek_mod":
      return r.acik
        ? {
            Ikon: Ik.Vida,
            ana: "YEDEK PARÇA MODU AÇIK",
            alt: "Okutulanlar Tiger kayıtlarında ARANMAZ, doğrudan yedek parça yazılır.",
            ...KIRMIZI,
          }
        : { Ikon: Ik.Vida, ana: "YEDEK PARÇA MODU KAPALI", alt: "Normal sayıma dönüldü.", ...MAVI };
    case "yedek_modda_gecersiz":
      return {
        Ikon: Ik.Engel,
        ana: "YEDEK PARÇA MODUNDA GEÇERSİZ",
        alt: "Fazla / Atla burada anlamsız — kayıt zaten aranmıyor. Önce modu kapat.",
        ...KIRMIZI,
      };
    case "yedek":
      return {
        Ikon: Ik.Vida,
        ana: "YEDEK PARÇA KAYDEDİLDİ",
        alt:
          (r.barkodlar ?? []).join(", ") +
          ((r.miktar ?? 1) > 1 ? ` · ${r.miktar} adet` : "") +
          " — ne olduğunu yazmayı unutma.",
        ...SARI,
      };
    case "silindi":
      return {
        Ikon: Ik.Cop,
        // Kuyruktan doğmuş bir fazla silinince kayıt kuyruğa GERİ DÖNER —
        // sayaç yeniden artar, söylenmezse hata sanılır.
        ana:
          (r.silinen ?? 1) > 1 ? `${r.silinen} SATIR SİLİNDİ` : "OKUTMA SİLİNDİ",
        alt:
          (r.barkodlar ?? []).join(", ") +
          (r.unutulan?.length ? ` · unutuldu: ${r.unutulan.join(", ")}` : "") +
          (r.etiket_cozuldu ? ` · ${r.etiket_cozuldu} havuza döndü` : "") +
          (r.kuyruk_acildi ? " · kayıt kuyruğa geri döndü" : ""),
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
  /* Kap sayısı. Alan ODAKLANMIYOR (autoFocus yok) — okuyucu hep barkod
     kutusuna yazmalı, yoksa okutulan barkod adet alanına düşer. */
  const [kutuAdet, setKutuAdet] = useState("");
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
          // Elle fazla ve yedek parça: hemen "bu ne?" diye sor, kayıt
          // isimsiz kalmasın. Yedek parça Tiger'da hiç yok — adı yazılmazsa
          // raporda yalnızca barkod ve raf kalır.
          if ((r.tip === "fazla_elle" || r.tip === "yedek") && r.okutma?.length) {
            setFazlaIdler(r.okutma);
            setFazlaAd("");
          }
          // Taze kayıtta alan dolu gelir, bayatta BOŞ: 30 günden eski bir
          // adet bilgi değil tahmindir (KUTU_TASARIM.md 6).
          if (r.tip === "kutu_sor") setKutuAdet(r.oneri_adet != null ? String(r.oneri_adet) : "");
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

  /* Akıştan silme (I1). ##GERIAL## yalnızca sonuncuyu alır; yanlış okutma
     sahada bazen birkaç ürün sonra fark ediliyor.

     Okutmalarla AYNI sıraya diziliyor: silme isteği araya girip yarım kalmış
     bir grubun önüne geçmemeli. Kapsam grup — bir grup bir üründür. */
  const sil = useCallback(
    (a: AkisSatiri) => {
      const ne = a.kod ?? a.ham ?? "bu okutma";
      if (!window.confirm(`${ne} okutması silinsin mi?

Öğrenilen barkod unutulur, bağlanan etiket havuza döner.`))
        return siraRef.current;
      bekleyenRef.current += 1;
      setMesgul(true);
      siraRef.current = siraRef.current.then(async () => {
        try {
          const r = await api.okutmaSil(a.id);
          bip("uyari");
          setSon(r);
          setIsik((n) => n + 1);
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
    [setDurum, odakla],
  );

  const kilitAc = useCallback(async () => {
    try {
      const r = await api.sabitKod(durum.oturum, null);
      bip("tik");
      if (r.durum) setDurum(r.durum);
    } catch (e) {
      setHata(e instanceof Error ? e.message : String(e));
    }
  }, [durum.oturum, setDurum]);

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

  /* Kaptaki adedi yaz ve say. Sunucuda `kutu_coz` çalışır: hem kabın son
     bilinen adedi tazelenir hem sayım işlenir — ikisi tek yerden. */
  async function kutuSay() {
    if (son?.tip !== "kutu_sor" || !son.kuyruk_id || !son.kod) return;
    const n = Number(kutuAdet);
    if (!Number.isFinite(n) || n <= 0) return;
    try {
      await api.kutuCoz(son.kuyruk_id, son.kod, n);
      bip("ok");
      setSon(null);
      setKutuAdet("");
      setDurum(await api.durum(durum.oturum));
    } catch (e) {
      bip("uyari");
      setHata(e instanceof Error ? e.message : String(e));
    } finally {
      odakla();
    }
  }

  /* Belirsiz kalan seri numarasının kararı. Sayım ZATEN işlendi; burada
     yalnızca Tiger Düzeltme sekmesine hangi değerin gideceği kapanıyor.
     Boş dize = "hiçbiri seri numarası değil" -> öneri üretilmez. */
  async function seriSec(okutmaId: number, secim: string) {
    try {
      await api.seriSec(okutmaId, secim);
      bip("ok");
      // Şeritteki soruyu kapat: karar verildi.
      setSon((o) => (o ? { ...o, sn_secim: [], yeni: secim } : o));
      setDurum(await api.durum(durum.oturum));
    } catch (e) {
      bip("uyari");
      setHata(e instanceof Error ? e.message : String(e));
    } finally {
      odakla();
    }
  }

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
          {/* Kilit ve yedek parça modu SESSİZ KALAMAZ. İkisi de açık
              unutulursa bütün raf yanlış malzemeye ya da yedek parçaya yazılır
              ve bu ancak rapor açılınca fark edilir. */}
          {durum.sabit_kod && (
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 border border-bilgi
                               bg-bilgi-tint px-2 py-0.5 text-kucuk font-bold text-bilgi">
                <Ik.Kilit boy={14} />
                <span className="font-mono">{durum.sabit_kod}</span>
                {durum.sabit_aciklama && (
                  <span className="font-normal">· {durum.sabit_aciklama}</span>
                )}
              </span>
              <button
                type="button"
                onClick={() => void kilitAc()}
                disabled={mesgul}
                className="border-cizgi-kuvvetli text-solgun hover:text-yazi inline-flex
                  items-center gap-1 rounded-sm border px-2 py-1 text-mikro disabled:opacity-40"
              >
                <Ik.KilitAcik boy={13} /> Kilidi aç
              </button>
            </div>
          )}
          {/* Açık kap: kilit ve yedek parça gibi KALICI kip, ekranda durmak
              zorunda. Sayaç "150'nin 12'si" — 150 son bilinen adet, gerçek
              değil (KUTU_TASARIM.md 3). */}
          {durum.acik_kutu && (
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 border border-vurgu
                               bg-vurgu-tint px-2 py-0.5 text-kucuk font-bold text-vurgu">
                <Ik.Katman boy={14} />
                <span className="font-mono">{durum.acik_kutu.kutu}</span>
                <span className="rakam">
                  {durum.acik_kutu.sayilan}
                  {durum.acik_kutu.beklenen != null && ` / ${durum.acik_kutu.beklenen}`}
                </span>
                <span className="font-normal">
                  {durum.acik_kutu.beklenen != null ? "okutuldu (son bilinen)" : "okutuldu"}
                </span>
              </span>
              <button
                type="button"
                onClick={() => void gonder("##KUTUKAPAT##")}
                disabled={mesgul}
                className="border-cizgi-kuvvetli text-solgun hover:text-yazi inline-flex
                  items-center gap-1 rounded-sm border px-2 py-1 text-mikro disabled:opacity-40"
              >
                <Ik.Bitti boy={13} /> Kabı kapat
              </button>
            </div>
          )}
          {durum.yedek_parca && (
            <div className="mt-1">
              <span className="inline-flex items-center gap-1 border border-hata
                               bg-hata-tint px-2 py-0.5 text-kucuk font-bold text-hata">
                <Ik.Vida boy={14} /> YEDEK PARÇA MODU — okutulanlar Tiger'da aranmıyor
              </span>
            </div>
          )}
        </div>

        <div className="ml-auto flex items-center gap-5">
          {/* ADET bazında. Lot satırı tek satırda çok adet taşır: satır saymak
              77 adetlik bir lotu tek okutmayla "bitmiş" gösteriyor, ekran
              "KALAN 0" derken rapor 202 adet eksik yazıyordu. */}
          <SayacKutu etiket="okutulan adet" deger={s.okutulan} vurgu="ok" />
          <SayacKutu
            etiket="kalan adet"
            deger={s.kalan}
            vurgu={s.kalan ? "uyari" : "ok"}
          />
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
            <Dugme cocuk="Barkod" tikla={() => git("etiket")} />
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
        {/* Mod düğmeleri (I2 / I4). Komut barkodunun ikizi: sahada karta uzanmak
            zaman yiyor (DEMO_FEEDBACK.md 1-2), ama okuyucu laptopta olduğu için
            PC'de de erişilebilmeli. İkisi de `okut()` borusundan geçiyor. */}
        <div className="flex flex-wrap items-center gap-2">
          <Dugme
            cocuk={
              durum.sabit_kod ? (
                <>
                  <Ik.KilitAcik /> Kilidi aç
                </>
              ) : (
                <>
                  <Ik.Kilit /> Bu malzemeye okut
                </>
              )
            }
            baslik={
              durum.sabit_kod
                ? "Malzeme kilidini kaldır"
                : "Önce malzeme kodunu okut, sonra buna bas — sonrasında yalnız seri numaralarını okut"
            }
            pasif={mesgul}
            tikla={() => void (durum.sabit_kod ? kilitAc() : gonder("##KILIT##"))}
          />
          <Dugme
            cocuk={
              <>
                <Ik.Vida /> Yedek parça{durum.yedek_parca ? " (açık)" : ""}
              </>
            }
            tur={durum.yedek_parca ? "tehlike" : "sade"}
            baslik="Açıkken okutulanlar Tiger kayıtlarında aranmaz, doğrudan yedek parça yazılır"
            pasif={mesgul}
            tikla={() => void gonder("##YEDEK##")}
          />
        </div>

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

        {/* Tiger'a önerilecek seri numarası BELİRSİZ: üründe birden çok
            tanınmayan barkod var (P/N + S/N gibi) ve hangisinin cihaza özel
            olduğu bilinemez. Sayım işlendi, akış DURMAZ — bu yalnızca "Tiger
            Düzeltme sekmesine hangi değer yazılsın" sorusu. Cevaplanmazsa
            bitirmede uyarı çıkar ve rapor dipnotta "tahmin" der. */}
        {son?.tip === "slot" && !!son.sn_secim?.length && son.sn_okutma != null && (
          <section className="girdi rounded-sm border border-uyari bg-uyari-tint p-3">
            <h2 className="mb-1 text-kucuk font-bold tracking-wider text-uyari uppercase">
              Hangisi cihazın seri numarası?
            </h2>
            <p className="mb-2 text-mikro text-solgun">
              {son.kod} · Tiger'daki uydurma kayıt <b className="text-yazi">{son.eski}</b>{" "}
              bunun yerine yazılacak. Seçmezsen en uzunu kullanılır ve raporda
              "tahmin" olarak işaretlenir.
            </p>
            <div className="flex flex-wrap gap-2">
              {son.sn_secim!.map((a) => (
                <button
                  key={a}
                  onClick={() => void seriSec(son.sn_okutma!, a)}
                  className={`rounded-sm border px-3 py-2 font-mono text-kucuk
                    ${a === son.yeni
                      ? "border-vurgu bg-vurgu-tint text-vurgu"
                      : "border-cizgi-kuvvetli bg-panel text-yazi"}`}
                >
                  {a}
                </button>
              ))}
              <Dugme
                cocuk="Hiçbiri seri no değil"
                tikla={() => void seriSec(son.sn_okutma!, "")}
              />
            </div>
          </section>
        )}

        {/* Kap: "kaç adet?" cevabı burada verilir — ürün elde, kap açık.
            Alan autoFocus DEĞİL: okuyucu barkod kutusuna yazmaya devam etmeli,
            yoksa okutulan barkod adet alanına düşer. */}
        {son?.tip === "kutu_sor" && (
          <section className="girdi flex flex-wrap items-center gap-3 rounded-sm border
            border-uyari bg-uyari-tint p-3">
            <p className="min-w-0 flex-1 text-kucuk text-solgun">
              <b className="text-yazi">{son.kutu}</b> · {son.kod} {son.aciklama}
              {son.oneri_adet == null && son.adet != null && (
                <> · son bilinen <b className="text-yazi">{son.adet}</b> adet, kayıt eski</>
              )}
            </p>
            <input
              type="number"
              min={1}
              value={kutuAdet}
              onChange={(e) => setKutuAdet(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void kutuSay();
                if (e.key === "Escape") e.currentTarget.blur();
              }}
              placeholder="adet"
              className="rakam w-28 rounded-sm border border-cizgi-kuvvetli bg-zemin px-3
                py-2 text-govde"
            />
            <Dugme
              cocuk="Say"
              tur="ana"
              pasif={!(Number(kutuAdet) > 0)}
              tikla={() => void kutuSay()}
            />
          </section>
        )}

        {/* Tanımsız / içeriği değişmiş kap: kuyrukta duruyor, oturum kapanmadan
            cevaplanacak. Malzeme seçimi Kuyruk ekranında (arama + filtreler). */}
        {(son?.tip === "kutu_tanimsiz" || son?.tip === "kutu_yabanci") && (
          <section className="girdi flex flex-wrap items-center gap-3 rounded-sm border
            border-uyari bg-uyari-tint p-3">
            <p className="min-w-0 flex-1 text-kucuk text-solgun">
              <b className="text-yazi">{son.kutu}</b> kuyrukta seni bekliyor. Kapta ne
              olduğunu bir kez söyle — kayıt kalıcıdır, gelecek sayımda kap kendi
              malzemesini söyler.
            </p>
            <Dugme cocuk="Kuyruğa git" tur="ana" tikla={() => git("kuyruk")} />
          </section>
        )}

        {/* Seri takipli kap: sayımı seri numaraları yapar, kap yalnızca
            malzemeyi getirir. Kilit tam da bu tekrarı kaldırmak için var. */}
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
                key={a.id}
                className={`flex flex-wrap items-baseline gap-3 border-l-4 px-4 py-2 text-kucuk
                  ${
                    a.tip === "fazla" || a.tip === "bilinmiyor"
                      ? "border-l-hata"
                      : a.tip === "yedek"
                        ? "border-l-uyari"
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
                <button
                  type="button"
                  onClick={() => void sil(a)}
                  disabled={mesgul}
                  title="Bu okutmayı sil"
                  aria-label={`${a.kod ?? a.ham} okutmasını sil`}
                  className="border-cizgi text-solgun-hafif hover:border-hata hover:text-hata
                    focus-visible:outline-vurgu inline-flex h-8 w-8 shrink-0 items-center
                    justify-center rounded-sm border focus-visible:outline-2 disabled:opacity-40"
                >
                  <Ik.Cop boy={14} />
                </button>
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
