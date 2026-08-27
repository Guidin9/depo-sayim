import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

/* Test yapılandırması `vite.config.ts`'ten AYRI dosyada.
 *
 * Sebep: `npm run build` yalnızca `vite.config.ts`'i okur. Test ayarları oraya
 * yazılsaydı, testlerle ilgili her değişiklik derleme yolunun içinden geçerdi —
 * sahaya giden çıktıyı bozma riski test yazmanın maliyeti olurdu. Bu dosya
 * derlemeye HİÇ girmez; `app/static` çıktısı testler eklenmeden önceki hâliyle
 * bit bazında aynı kalır (doğrulandı).
 *
 * Tailwind eklentisi de bilerek yok: testler CSS'e bakmıyor, DOM'a bakıyor.
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    restoreMocks: true,
  },
});
