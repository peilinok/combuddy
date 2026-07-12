import { describe, it, expect, vi, beforeEach } from "vitest";

const fetchTrash = vi.fn();
const postRestore = vi.fn();
vi.mock("./api", () => ({ fetchTrash: (...a: any[]) => fetchTrash(...a),
                          postRestore: (...a: any[]) => postRestore(...a) }));
import { useTrash } from "./useTrash";

const items = [
  { id: 1, model_path: "/r/checkpoints/a.safetensors", dir_type: "checkpoints", size: 100, trashed_at: 1720000000 },
  { id: 2, model_path: "/r/loras/b.safetensors", dir_type: "loras", size: 50, trashed_at: 1720000001 },
];

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

describe("useTrash", () => {
  beforeEach(() => {
    fetchTrash.mockReset().mockResolvedValue({ trash: items });
    postRestore.mockReset().mockResolvedValue({ restored: [1], conflict: [], error: [] });
  });

  it("load fills items and totalBytes", async () => {
    const tr = useTrash(); await tr.load();
    expect(tr.items.value.length).toBe(2);
    expect(tr.totalBytes.value).toBe(150);
  });
  it("restore posts ids, records counts, reloads", async () => {
    const tr = useTrash(); await tr.restore([1]);
    expect(postRestore).toHaveBeenCalledWith([1]);
    expect(tr.lastRestore.value).toEqual({ restored: 1, conflict: 0, error: 0 });
    expect(fetchTrash).toHaveBeenCalled();
  });
  it("restore failure lands in error, not thrown", async () => {
    postRestore.mockRejectedValueOnce(new Error("HTTP 500"));
    const tr = useTrash();
    await expect(tr.restore([2])).resolves.toBeUndefined();
    expect(tr.error.value).toBeTruthy();
  });
  it("clears the previous restore result when the next restore fails", async () => {
    const tr = useTrash(); await tr.restore([1]);
    postRestore.mockRejectedValueOnce(new Error("HTTP 500"));
    await tr.restore([2]);
    expect(tr.lastRestore.value).toBeNull();
    expect(tr.error.value).toBeTruthy();
  });
  it("does not let an older load overwrite the list refreshed after restore", async () => {
    const old = deferred<{ trash: any[] }>();
    fetchTrash.mockReset().mockReturnValueOnce(old.promise).mockResolvedValueOnce({ trash: [] });
    const tr = useTrash();
    const first = tr.load();
    await tr.restore([1]);
    old.resolve({ trash: items }); await first;
    expect(tr.items.value).toEqual([]);
  });
  it("allows only one restore at a time", async () => {
    const pending = deferred<{ restored: number[]; conflict: number[]; error: number[] }>();
    postRestore.mockReturnValueOnce(pending.promise);
    const tr = useTrash();
    const first = tr.restore([1]);
    await expect(tr.restore([2])).resolves.toBeUndefined();
    expect(postRestore).toHaveBeenCalledTimes(1);
    pending.resolve({ restored: [1], conflict: [], error: [] });
    await first;
  });
});
