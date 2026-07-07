import { describe, it, expect } from "vitest";
import { view, cleanupTab } from "./useNav";

describe("useNav", () => {
  it("defaults to dashboard + unreferenced, and is mutable module-level state", () => {
    expect(view.value).toBe("dashboard");
    expect(cleanupTab.value).toBe("unreferenced");
    cleanupTab.value = "duplicates"; view.value = "cleanup";
    expect(cleanupTab.value).toBe("duplicates");
    expect(view.value).toBe("cleanup");
  });
});
