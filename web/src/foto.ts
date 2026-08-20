/** Telefonla çekilen kuyruk fotoğrafları için ortak yardımcı.
 *
 * Hem laptoptaki Kuyruk ekranı hem telefon monitörü aynı işi yapıyor: dosyayı
 * küçültüp POST /api/kuyruk/{id}/foto ucuna gönderiyor.
 */

/** Telefon fotoğrafı 4-5 MB gelir; yüklemeden önce 1280px/JPEG'e indiriyoruz. */
export async function kucult(dosya: File, enBuyuk = 1280, kalite = 0.72): Promise<Blob> {
  try {
    const gorsel = await createImageBitmap(dosya, { imageOrientation: "from-image" });
    const oran = Math.min(1, enBuyuk / Math.max(gorsel.width, gorsel.height));
    const g = Math.round(gorsel.width * oran);
    const y = Math.round(gorsel.height * oran);
    const tuval = document.createElement("canvas");
    tuval.width = g;
    tuval.height = y;
    tuval.getContext("2d")?.drawImage(gorsel, 0, 0, g, y);
    const kucuk = await new Promise<Blob | null>((c) => tuval.toBlob(c, "image/jpeg", kalite));
    return kucuk ?? dosya;
  } catch {
    return dosya; // küçültme başarısızsa aslını gönder
  }
}
