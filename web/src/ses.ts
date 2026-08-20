/** Ekrana bakmadan geri bildirim (prototipteki desenler birebir).
 *
 * tık    : okutma alındı
 * ok     : grup eşleşti
 * uyarı  : çift alçak bip  (tekrar / fazla)
 * kuyruk : üç bip          (çözülemedi, sayım durmadı)
 * bitti  : yükselen üçlü   (oturum kapandı)
 */
import type { Ses } from "./api";

const DESEN: Record<Ses, [number, number][]> = {
  tik: [[900, 0.035]],
  ok: [[1250, 0.09]],
  uyari: [
    [500, 0.12],
    [0, 0.05],
    [500, 0.12],
  ],
  kuyruk: [
    [750, 0.07],
    [0, 0.04],
    [750, 0.07],
    [0, 0.04],
    [750, 0.07],
  ],
  bitti: [
    [900, 0.1],
    [0, 0.05],
    [1200, 0.1],
    [0, 0.05],
    [1500, 0.18],
  ],
};

let ac: AudioContext | null = null;
let acik = true;

export function sesiAyarla(deger: boolean) {
  acik = deger;
}

export function sesAcikMi() {
  return acik;
}

export function bip(tip: Ses = "tik") {
  if (!acik) return;
  try {
    ac = ac ?? new AudioContext();
    if (ac.state === "suspended") void ac.resume();
    let t = ac.currentTime;
    for (const [frekans, sure] of DESEN[tip] ?? DESEN.tik) {
      if (frekans) {
        const o = ac.createOscillator();
        const v = ac.createGain();
        o.frequency.value = frekans;
        o.type = "square";
        v.gain.value = 0.14;
        o.connect(v);
        v.connect(ac.destination);
        o.start(t);
        o.stop(t + sure);
      }
      t += sure;
    }
  } catch {
    /* ses yoksa sayım yine de sürsün */
  }
}
