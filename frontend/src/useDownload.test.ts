import { describe, it, expect, vi, beforeEach } from "vitest";
import * as api from "./api";
import { useDownload } from "./useDownload";
vi.mock("./api");
const D = useDownload();
beforeEach(() => { vi.resetAllMocks(); D.error.value = null; });

it("startDownload 传 spec 并刷新", async () => {
  (api.postDownload as any).mockResolvedValue({ started: true });
  (api.fetchStats as any).mockResolvedValue({ scanning: false, scan: {}, download: { running: true } });
  await D.startDownload({ url: "https://civitai.com/x", sha256: "a".repeat(64), size_kb: 1,
    dir_type: "loras", ref_string: "foo.safetensors", root_id: 1 });
  expect(api.postDownload).toHaveBeenCalled();
});
it("startDownload 错误进 error ref", async () => {
  (api.postDownload as any).mockRejectedValue(Object.assign(new Error(), { detail: "already_running" }));
  await D.startDownload({ url: "https://civitai.com/x", sha256: "a".repeat(64), size_kb: 1,
    dir_type: "loras", ref_string: "foo.safetensors", root_id: 1 });
  expect(D.error.value).toBe("already_running");
});
it("downloadError 从 stats.download.error 派生（后台失败）[B2]", async () => {
  const { stats } = await import("./useScanStatus");
  D.error.value = null;
  stats.value = { ...stats.value, download: { running: false, error: "sha_mismatch" } };
  expect(D.downloadError.value).toBe("sha_mismatch");
});
