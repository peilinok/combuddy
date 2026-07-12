import { describe, it, expect, vi, beforeEach } from "vitest";

const fetchDuplicates = vi.fn();
const postTrash = vi.fn();
vi.mock("./api", () => ({ fetchStats: vi.fn().mockResolvedValue({ scanning: false, scan: { phase: "idle" } }),
                          fetchDuplicates: (...a: any) => fetchDuplicates(...a),
                          postTrash: (...a: any) => postTrash(...a) }));
import { useDuplicates, reclaimableOf } from "./useDuplicates";

const members = [
  { id: 1, size: 100, inode: "0:1", deletable: false, ref_count: 0 }, // keep
  { id: 2, size: 100, inode: "0:2", deletable: true,  ref_count: 0 },
  { id: 3, size: 100, inode: "0:2", deletable: true,  ref_count: 0 }, // 与 2 同 inode
];

describe("reclaimableOf", () => {
  it("dedupes by inode, excludes keep + non-deletable", () => {
    expect(reclaimableOf(members, 1)).toBe(100);  // 2 与 3 同 inode 只计一次
  });
});

describe("useDuplicates", () => {
  beforeEach(() => { fetchDuplicates.mockReset(); postTrash.mockReset(); });
  it("loads, derives deleteIds from deletable, and warns on skipped", async () => {
    fetchDuplicates.mockResolvedValue({
      groups: [{ sha256: "S", suggested_keep_id: 1, members }],
      total_reclaimable: 100, unhashed_count: 2 });
    const d = useDuplicates();
    await d.load();
    expect(d.unhashedCount.value).toBe(2);
    expect(d.selectedIds.value.sort()).toEqual([2, 3]);
    postTrash.mockResolvedValue({ moved: [2], skipped: [3] });
    await d.trashSelected();
    expect(d.error.value).toMatch(/1/);           // skipped 提示含数量
  });
});
