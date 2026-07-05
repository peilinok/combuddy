import { ref, watch } from "vue";
import { usePrimeVue } from "primevue/config";

export const PALETTES = ["green", "blue", "cyan", "purple", "amber"] as const;
export const MODES = ["auto", "light", "dark"] as const;
export type Palette = (typeof PALETTES)[number];
export type Mode = (typeof MODES)[number];

const mql = typeof matchMedia !== "undefined"
  ? matchMedia("(prefers-color-scheme: dark)")
  : ({ matches: false, addEventListener() {} } as unknown as MediaQueryList);
const resolve = (mode: Mode) => (mode === "auto" ? (mql.matches ? "dark" : "light") : mode);
export const themeName = (palette: Palette, mode: Mode) => `aura-${resolve(mode)}-${palette}`;

function loadSaved(): { palette: Palette; mode: Mode } {
  try {
    const s = JSON.parse(localStorage.getItem("combuddy-theme") || "{}");
    return {
      palette: (PALETTES as readonly string[]).includes(s.palette) ? s.palette : "green",
      mode: (MODES as readonly string[]).includes(s.mode) ? s.mode : "auto",
    };
  } catch { return { palette: "green", mode: "auto" }; }
}

// 模块级单例状态 —— 所有调用者共享同一份
const saved = loadSaved();
const palette = ref<Palette>(saved.palette);
const mode = ref<Mode>(saved.mode);
let current = themeName(palette.value, mode.value); // = index.html 首屏脚本已应用的主题
let started = false;

export function useTheme() {
  const pv = usePrimeVue();
  if (!started) {
    started = true;
    const apply = () => {
      const next = themeName(palette.value, mode.value);
      if (next !== current) { pv.changeTheme(current, next, "theme-link", () => {}); current = next; }
      localStorage.setItem("combuddy-theme", JSON.stringify({ palette: palette.value, mode: mode.value }));
    };
    watch([palette, mode], apply);
    mql.addEventListener("change", () => { if (mode.value === "auto") apply(); }); // 只装一次,跟随 OS
  }
  return { palette, mode, palettes: PALETTES, modes: MODES, themeName };
}
