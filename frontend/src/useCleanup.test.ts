import { describe, it, expect, vi } from "vitest";
vi.mock("./api", () => ({
  fetchUnreferenced: vi.fn().mockResolvedValue({ models: [{ id: 1, filename: "a", size: 100 }, { id: 2, filename: "b", size: 50 }] }),
  postTrash: vi.fn().mockResolvedValue({ moved: [1], skipped: [] }),
}));
import { useCleanup } from "./useCleanup";

describe("useCleanup", () => {
  it("toggle tracks selected bytes", async () => {
    const c = useCleanup(); await c.load();
    c.toggle(1); c.toggle(2);
    expect(c.selectedBytes.value).toBe(150);
    c.toggle(1);
    expect(c.selectedBytes.value).toBe(50);
  });
  it("trashSelected reloads", async () => {
    const c = useCleanup(); await c.load(); c.toggle(1);
    await c.trashSelected();
    const api = await import("./api");
    expect(api.postTrash).toHaveBeenCalledWith([1]);
  });
});
