/** Sayım şeridi — okutma sonucunun RENGİ ve metni.
 *
 * Neden burası: sahada kullanıcı ekrandaki renge bakıp sonraki ürüne geçiyor.
 * Yanlış renk, üstünden geçilen bir hatadır — ve tip denetimi bunu görmez.
 *
 * Bu dosyanın varlık sebebi gerçek bir hata: seri numarası seçimi eklenirken
 * şerit YEŞİL + onay işareti kaldı, üstünde "seri numarası SEÇİLMELİ" yazarken.
 * Sebep bir spread sırasıydı — `{ ...SARI, ana: "...", ...YESIL }` — sondaki
 * öndekini eziyordu. `tsc` temizdi, 443 arka uç testi geçiyordu; hata yalnızca
 * ekran görüntüsüne bakılarak yakalandı (2026-08-27).
 *
 * Kural: karar bekleyen ya da bir şey kaybedilmiş olabilecek her sonuç SARI ya
 * da KIRMIZI olmalı. Yeşil "tamam, geç" demektir.
 */
import { describe, expect, it } from "vitest";

import type { OkutmaSonucu } from "../api";
import { seritMetni } from "./Sayim";

/** Şeridin rengini sınıf dizesinden okur (`border-ok bg-ok-tint ...`). */
function renk(r: OkutmaSonucu) {
  const s = seritMetni(r);
  if (!s) return null;
  return s.renk;
}

const SAYILDI_SESSIZ: OkutmaSonucu = {
  tip: "eslesti",
  kod: "0FH1W9",
  seri: "13W0A0S3T1FJ",
  aciklama: "DELL 480GB SSD",
};

describe("şerit rengi — yeşil yalnızca 'tamam, geç' demektir", () => {
  it("temiz eşleşme yeşil", () => {
    expect(renk(SAYILDI_SESSIZ)).toBe("ok");
  });

  it("seri numarası seçilmesi gereken slot YEŞİL OLAMAZ", () => {
    // Regresyon: bu tam olarak sahaya gitmek üzereyken yakalanan hata.
    expect(
      renk({
        tip: "slot",
        kod: "BC-U6030",
        eski: "BC-U6030SAYIM1",
        yeni: "PN-4XB7A17069",
        sn_secim: ["PN-4XB7A17069", "SN-WK22DPX01"],
        sn_okutma: 12,
      }),
    ).toBe("uyari");
  });

  it("seri numarası seçilmişse (tek aday) yeşil olabilir", () => {
    expect(
      renk({ tip: "slot", kod: "BC-U6030", eski: "BC-U6030SAYIM1", yeni: "SN-9911" }),
    ).toBe("ok");
  });

  it("seri numarası hiç verilmeyen slot sarı", () => {
    expect(
      renk({ tip: "slot", kod: "BC-U6030", eski: "BC-U6030SAYIM1", yeni: "", sn_yok: true }),
    ).toBe("uyari");
  });

  it("çelişkili grup (##SONRAKI## unutulmuş) sarı", () => {
    expect(
      renk({
        tip: "coklu",
        sayi: 3,
        kayitlar: [
          { okutma: 1, kod: "0FH1W9", seri: "A1", aciklama: null, ham: "A1" },
          { okutma: 2, kod: "0FH1W9", seri: "A2", aciklama: null, ham: "A2" },
          { okutma: 3, kod: "0FH1W9", seri: "A3", aciklama: null, ham: "A3" },
        ],
      }),
    ).toBe("uyari");
  });

  it("sayım dışı kalem sarı — hiçbir şey yazılmadı", () => {
    expect(renk({ tip: "haric", kod: "JW473AAE", sebep: "aciklama:LICENSE" })).toBe("uyari");
  });

  it("tekrar sarı", () => {
    expect(renk({ tip: "tekrar", kod: "0FH1W9", seri: "13W0A0S3T1FJ" })).toBe("uyari");
  });

  it("fazla kırmızı", () => {
    expect(renk({ tip: "fazla_elle", barkodlar: ["YOK-123"] })).toBe("hata");
  });

  it("bitirme uyarısı sarı", () => {
    expect(
      renk({
        tip: "bitir_uyari",
        saniye: 60,
        eksik_lot: [
          {
            kod: "0C5RNH",
            seri: "0C5RNHLOT1221",
            aciklama: null,
            izleme: "lot",
            beklenen: 77,
            sayilan: 1,
          },
        ],
      }),
    ).toBe("uyari");
  });
});

describe("şerit metni — kullanıcının okuduğu şey", () => {
  it("çelişkili grupta kaç cihaz sayıldığını söyler", () => {
    const s = seritMetni({
      tip: "coklu",
      sayi: 3,
      kayitlar: [
        { okutma: 1, kod: "0FH1W9", seri: "A1", aciklama: null, ham: "A1" },
        { okutma: 2, kod: "0FH1W9", seri: "A2", aciklama: null, ham: "A2" },
        { okutma: 3, kod: "0FH1W9", seri: "A3", aciklama: null, ham: "A3" },
      ],
    });
    expect(s?.ana).toContain("3");
    expect(s?.alt).toContain("SIRADAKİ ÜRÜN");
    // Kullanıcı yanlışlıkla yaptıysa çıkış yolunu görmeli.
    expect(s?.alt).toContain("Ctrl+Z");
  });

  it("çelişkili grupta öğrenilmeyen barkodları söyler", () => {
    const s = seritMetni({
      tip: "coklu",
      sayi: 2,
      kayitlar: [{ okutma: 1, kod: "X", seri: "A1", aciklama: null, ham: "A1" }],
      ogrenilmedi: ["190017273624"],
    });
    expect(s?.alt).toContain("190017273624");
  });

  it("tekrar uyarısında hangi slota yazıldığını söyler", () => {
    const s = seritMetni({
      tip: "tekrar",
      kod: "BC-U6030",
      seri: "BC-U6030SAYIM1",
      not: "bu seri numarası az önce BC-U6030SAYIM1 slotuna yazıldı",
    });
    expect(s?.alt).toContain("BC-U6030SAYIM1");
  });

  it("eşleşmede yutulan tekrar uyarısı görünür", () => {
    // Grupta hem yeni bir seri hem daha önce okutulmuş bir barkod varsa
    // `tekrar` dalı `not seri_h` koşuluyla atlanıyor; uyarı buradan çıkmalı.
    const s = seritMetni({ ...SAYILDI_SESSIZ, tekrar_seri: "5S47WC2" });
    expect(s?.alt).toContain("5S47WC2");
    expect(s?.renk).toBe("ok");
  });

  it("bitirme uyarısı eksik lotu sayıyla gösterir", () => {
    const s = seritMetni({
      tip: "bitir_uyari",
      saniye: 60,
      eksik_lot: [
        {
          kod: "0C5RNH",
          seri: "0C5RNHLOT1221",
          aciklama: null,
          izleme: "lot",
          beklenen: 77,
          sayilan: 1,
        },
      ],
    });
    expect(s?.alt).toContain("0C5RNH 1/77");
    expect(s?.alt).toContain("tekrar okut");
  });

  it("çift onay penceresini saniyesiyle söyler", () => {
    const s = seritMetni({ tip: "bitir_onay", saniye: 60 });
    expect(s?.ana).toContain("BİR KEZ DAHA");
    expect(s?.alt).toContain("60");
  });

  it("adet uygulanamadıysa sessiz kalmaz", () => {
    const s = seritMetni({ ...SAYILDI_SESSIZ, adet_yersiz: 25 });
    expect(s?.alt).toContain("25");
  });

  it("bilinmeyen tip ekranı çökertmez", () => {
    expect(seritMetni({ tip: "boyle-bir-tip-yok" })).toBeNull();
  });
});
