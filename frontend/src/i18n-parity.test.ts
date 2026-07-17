import { describe, it, expect } from "vitest";
import zh from "./locales/zh";
import en from "./locales/en";

function flatKeys(o: any, prefix = ""): string[] {
  return Object.entries(o).flatMap(([k, v]) =>
    v && typeof v === "object" ? flatKeys(v, prefix + k + ".") : [prefix + k]);
}

describe("i18n zh/en 键奇偶性", () => {
  it("两语言键集合完全一致", () => {
    expect(flatKeys(zh).sort()).toEqual(flatKeys(en).sort());
  });
});
