import { describe, it, expect, vi, beforeEach } from "vitest";
const changeTheme = vi.fn();
vi.mock("primevue/config", () => ({ usePrimeVue: () => ({ changeTheme }) }));

let store: Record<string, string>;
const mql = { matches: false, addEventListener: vi.fn() };
beforeEach(() => {
  vi.resetModules();          // 丢掉已加载的 useTheme,使下面的动态 import 重跑模块级初始化
  changeTheme.mockClear();
  store = {};
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v; },
    clear: () => { store = {}; },
  });
  vi.stubGlobal("matchMedia", () => mql);
});

describe("useTheme", () => {
  it("themeName maps palette + resolved mode", async () => {
    const { themeName } = await import("./useTheme");
    expect(themeName("blue", "dark")).toBe("aura-dark-blue");
    expect(themeName("green", "light")).toBe("aura-light-green");
    expect(themeName("amber", "auto")).toBe("aura-light-amber"); // matchMedia matches=false → light
  });
  it("defaults to green + auto", async () => {
    const { useTheme } = await import("./useTheme");
    const t = useTheme();
    expect(t.palette.value).toBe("green"); expect(t.mode.value).toBe("auto");
  });
  it("changing palette swaps theme + persists", async () => {
    const { useTheme } = await import("./useTheme");
    const t = useTheme(); t.palette.value = "purple";
    await Promise.resolve();
    expect(changeTheme).toHaveBeenCalledWith("aura-light-green", "aura-light-purple", "theme-link", expect.any(Function));
    expect(JSON.parse(store["combuddy-theme"]).palette).toBe("purple");
  });
  it("loads persisted choice", async () => {
    store["combuddy-theme"] = JSON.stringify({ palette: "blue", mode: "dark" });
    const { useTheme } = await import("./useTheme");
    const t = useTheme();
    expect(t.palette.value).toBe("blue"); expect(t.mode.value).toBe("dark");
  });
});
