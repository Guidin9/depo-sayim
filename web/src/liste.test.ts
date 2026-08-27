/** Eşleştirme listesinin süzme mantığı (`liste.suz`).
 *
 * Neden burası: kullanıcı fazla çıkan bir ürünü eksik listesinden bulup
 * bağlayacak. Süzme yanlış çalışırsa aradığı satır listede GÖRÜNMEZ ve ürün
 * "gerçekten fazla" diye kapatılır — sayım sonucu bozulur. Bu, sunucudan gelen
 * veri eksiksiz olsa bile arayüzde kaybedilebilecek tek yer.
 *
 * Sahadaki gerçek sorun (bildirim 2026-08-23) tam olarak buydu: liste
 * Excel'dekinin çok altında ürün gösteriyordu.
 *
 * Türkçe kritik: depodaki açıklamalar Türkçe ve `toLowerCase()` yetmiyor —
 * "I" harfi Türkçede "ı"ya, İngilizcede "i"ye düşer. Kullanıcı "ışık" yazıp
 * "IŞIK" satırını bulamazsa aradığı ürün yok sanır.
 */
import { describe, expect, it } from "vitest";

import { suz } from "./liste";

type Satir = { kod: string; aciklama: string; seri: string };

const VERI: Satir[] = [
  { kod: "0FH1W9", aciklama: "DELL 1.92TB SSD SATA", seri: "13W0A0S3T1FJ" },
  { kod: "210-ACXU-TİP2", aciklama: "SSD Dell Gen14 Kızak", seri: "5S47WC2" },
  { kod: "JW473AAE", aciklama: "ARUBA LİSANS E-LTU", seri: "" },
  { kod: "0,70MM TEL", aciklama: "IŞIKLI GÖSTERGE KABLOSU", seri: "" },
  { kod: "BC-U6030", aciklama: "BEEK PATCH CORD CAT 6 UTP 3MT", seri: "BC-U6030SAYIM1" },
];

const ALANLAR = ["kod", "aciklama", "seri"] as const;

function ara(q: string) {
  return suz(VERI, q, [...ALANLAR]).map((r) => r.kod);
}

describe("suz — çok terimli arama", () => {
  it("boş sorgu her şeyi döner (liste gezilebilmeli)", () => {
    expect(suz(VERI, "", [...ALANLAR])).toHaveLength(VERI.length);
    expect(suz(VERI, "   ", [...ALANLAR])).toHaveLength(VERI.length);
  });

  it("terimlerin SIRASI önemsiz — 'dell ssd' ve 'ssd dell' aynı kümeyi bulur", () => {
    // Sunucudaki tek parça LIKE bunu yapamıyordu.
    expect(ara("dell ssd").sort()).toEqual(ara("ssd dell").sort());
    expect(ara("dell ssd").sort()).toEqual(["0FH1W9", "210-ACXU-TİP2"]);
  });

  it("her terim geçmeli (VE mantığı, VEYA değil)", () => {
    // "dell kızak" yalnızca ikisini birden taşıyan satırı bulmalı.
    expect(ara("dell kızak")).toEqual(["210-ACXU-TİP2"]);
  });

  it("seri numarasından da bulur", () => {
    expect(ara("13W0A0S3T1FJ")).toEqual(["0FH1W9"]);
  });

  it("malzeme kodundan bulur — boşluklu kod dahil", () => {
    expect(ara("0,70MM")).toEqual(["0,70MM TEL"]);
  });
});

describe("suz — Türkçe (depodaki metinler Türkçe)", () => {
  it("büyük İ, DÜZ i ile aranınca bulunur (telefon klavyesi için şart)", () => {
    // "TİP2".toLocaleLowerCase("tr") -> "tip2": İ düz i'ye düşer. Bu ISTENEN
    // davranış — depoda telefonla arayan kullanıcı şapkasız yazar. Ters yönde
    // çalışmaz ve çalışmamalı: "I" -> "ı" olduğu için "ısık" ile "IŞIK"
    // bulunur, "isik" ile bulunmaz (aşağıdaki test).
    expect(ara("lisans")).toEqual(["JW473AAE"]);
    expect(ara("tip2")).toEqual(["210-ACXU-TİP2"]);
    expect(ara("tİp2")).toEqual(["210-ACXU-TİP2"]);
  });

  it("büyük I, ı ile bulunur — i ile BULUNMAZ", () => {
    // Türkçede "I" -> "ı". `toLowerCase()` (yerel ayarsız) bunu "i" yapar ve
    // liste sessizce yanlış süzülürdü. Kullanıcı aradığını bulamayınca ürünü
    // "gerçekten fazla" diye kapatır — sayım sonucu bozulur.
    expect(ara("ışıklı")).toEqual(["0,70MM TEL"]);
    expect(ara("isikli")).toEqual([]);
  });

  it("büyük/küçük harf farkı sonucu değiştirmez", () => {
    expect(ara("BEEK")).toEqual(ara("beek"));
    expect(ara("beek")).toEqual(["BC-U6030"]);
  });
});

describe("suz — bulunamama durumu sessiz ve doğru", () => {
  it("eşleşme yoksa boş dizi döner, hata atmaz", () => {
    expect(ara("boyle-bir-urun-yok")).toEqual([]);
  });

  it("null / undefined alanlar satırı düşürmez", () => {
    const bozuk = [{ kod: "X1", aciklama: null, seri: undefined }] as unknown as Satir[];
    expect(suz(bozuk, "x1", [...ALANLAR])).toHaveLength(1);
  });
});
