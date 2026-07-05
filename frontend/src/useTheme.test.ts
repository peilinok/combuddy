import { describe, it, expect, vi, beforeEach } from "vitest";
const changeTheme = vi.fn();
vi.mock("primevue/config", () => ({ usePrimeVue: () => ({ changeTheme }) }));
// 固定 matchMedia 为「亮色」
const mql: any = { matches: false, addEventListener: vi.fn() };
vi.stubGlobal("matchMedia", () => mql);
// node 下没有 localStorage,用 Map 打一个假的
const store = new Map<string, string>();
vi.stubGlobal("localStorage", {
  getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
  setItem: (k: string, v: string) => store.set(k, v),
  clear: () => store.clear(),
});
import { useTheme, themeName } from "./useTheme";

beforeEach(() => { localStorage.clear(); changeTheme.mockClear(); });

describe("useTheme", () => {
  it("themeName maps palette + resolved mode", () => {
    expect(themeName("blue", "dark")).toBe("aura-dark-blue");
    expect(themeName("green", "light")).toBe("aura-light-green");
    expect(themeName("amber", "auto")).toBe("aura-light-amber"); // matchMedia=false → light
  });
  it("defaults to green + auto", () => {
    const t = useTheme();
    expect(t.palette.value).toBe("green"); expect(t.mode.value).toBe("auto");
  });
  it("changing palette swaps theme + persists", async () => {
    const t = useTheme(); t.palette.value = "purple";
    await Promise.resolve();
    expect(changeTheme).toHaveBeenCalledWith("aura-light-green", "aura-light-purple", "theme-link", expect.any(Function));
    expect(JSON.parse(localStorage.getItem("combuddy-theme")!).palette).toBe("purple");
  });
  it("loads persisted choice", () => {
    localStorage.setItem("combuddy-theme", JSON.stringify({ palette: "blue", mode: "dark" }));
    const t = useTheme(); expect(t.palette.value).toBe("blue"); expect(t.mode.value).toBe("dark");
  });
});
