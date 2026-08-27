/** Telefon şeridinin rengi — ARKA UÇ METNİNE bağlı sözleşme.
 *
 * Telefon `OkutmaSonucu` görmez, AKIŞ SATIRI görür (barkodu laptop okutuyor,
 * telefon izliyor). Bu yüzden "sayıldı ama bir şey söylenmeli" kararı
 * `okutma.not_` alanındaki metinden okunuyor.
 *
 * Kırılganlığı burada: `matching.py` o notu değiştirirse telefon sessizce
 * yeşile döner ve rafın başındaki kullanıcı uyarıyı hiç görmez. Bu dosya
 * arayüz tarafını, `tests/test_telefon_notu.py` arka uç tarafını tutar —
 * ikisi birlikte sözleşmeyi kapatır.
 */
import { describe, expect, it } from "vitest";

import { DIKKAT_NOT, dikkatMi } from "./Telefon";

describe("dikkatMi — hangi not sarı yakar", () => {
  it("çelişkili grup notu dikkat ister", () => {
    expect(
      dikkatMi("çelişkili grup — SIRADAKİ ÜRÜN unutulmuş olabilir | okutulanlar: A + B"),
    ).toBe(true);
  });

  it("seçilmemiş seri no notu dikkat ister", () => {
    expect(dikkatMi("slot dolduruldu | seri no seçilmedi, tahmin edildi")).toBe(true);
  });

  it("normal slot doldurma dikkat İSTEMEZ (yeşil kalır)", () => {
    expect(dikkatMi("slot dolduruldu")).toBe(false);
  });

  it("boş / null not dikkat istemez", () => {
    expect(dikkatMi(null)).toBe(false);
    expect(dikkatMi("")).toBe(false);
  });

  it("sözleşme metinleri arka uçtakiyle birebir", () => {
    // Bu iki dize `app/matching.py` içinde geçiyor. Değiştirilirse buradaki
    // liste de değişmeli — `tests/test_telefon_notu.py` arka uçtan doğrular.
    expect(DIKKAT_NOT).toEqual(["çelişkili grup", "seri no seçilmedi"]);
  });
});
