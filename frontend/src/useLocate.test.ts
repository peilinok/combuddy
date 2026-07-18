import { describe, it, expect, vi, beforeEach } from "vitest";
import * as api from "./api";
import { useLocate } from "./useLocate";

vi.mock("./api");

const L = useLocate();   // 模块级单例

beforeEach(() => {                       // 模块单例:状态跨测试保留,须逐个手动重置(含 loading)[M5]
  vi.resetAllMocks();
  L.result.value = null; L.error.value = null; L.open.value = false;
  L.mode.value = null; L.query.value = ""; L.target.value = null; L.loading.value = false;
});

describe("openFor", () => {
  it("预填搜索词为去扩展名基名(去子目录前缀)", async () => {
    await L.openFor({ ref_string: "SD1.5/juggernautXL_v9.safetensors", dir_type: "checkpoints" });
    expect(L.query.value).toBe("juggernautXL_v9");
    expect(L.open.value).toBe(true);
  });
  it("多点扩展名只去最后一段", async () => {
    await L.openFor({ ref_string: "model.v2.safetensors" });
    expect(L.query.value).toBe("model.v2");
  });
  it("纯 CJK 无扩展名原样保留", async () => {
    await L.openFor({ ref_string: "龙模型" });
    expect(L.query.value).toBe("龙模型");
  });
  it("反斜杠子目录前缀被剥掉(q 不含路径,隐私钉子) [L2]", async () => {
    await L.openFor({ ref_string: "SD1.5\\foo.safetensors" });
    expect(L.query.value).toBe("foo");
    expect(L.query.value).not.toContain("/");
    expect(L.query.value).not.toContain("\\");
  });
  it("无 sha 时不自动搜索(停待搜索态) [H3]", async () => {
    await L.openFor({ ref_string: "foo.safetensors", dir_type: "loras" });
    expect(api.fetchLocate).not.toHaveBeenCalled();
    expect(L.result.value).toBeNull();
  });
  it("有 sha 时自动 by-hash", async () => {
    (api.fetchLocate as any).mockResolvedValue({ mode: "hash", found: true, candidate: {} });
    await L.openFor({ ref_string: "foo.safetensors", sha256: "a".repeat(64) });
    expect(api.fetchLocate).toHaveBeenCalledWith({ sha256: "a".repeat(64) });
    expect(L.mode.value).toBe("hash");
  });
  it("切换 target 时清空上一个 target 残留的下载失败提示 [review Important I-4]", async () => {
    const { useDownload } = await import("./useDownload");
    const { stats } = await import("./useScanStatus");
    const Dl = useDownload();
    Dl.error.value = null;
    stats.value = { ...stats.value, download: { running: false, error: "disk_full", revision: 9 } };
    expect(Dl.downloadError.value).toBe("disk_full");            // target A 的下载失败仍在展示
    await L.openFor({ ref_string: "bar.safetensors", dir_type: "loras" });   // 切到新 target B
    expect(Dl.downloadError.value).toBeNull();                   // B 的对话框不该带着 A 的失败码
  });
});

describe("search", () => {
  it("发 q + ref(完整基名) + dir_type", async () => {
    (api.fetchLocate as any).mockResolvedValue({ mode: "name", candidates: [] });
    await L.openFor({ ref_string: "sub/foo.safetensors", dir_type: "loras" });
    await L.search();
    expect(api.fetchLocate).toHaveBeenCalledWith({ q: "foo", ref: "foo.safetensors", dir_type: "loras" });
  });
  it("searchUnfiltered 带 nofilter=1、不带 dir_type", async () => {
    (api.fetchLocate as any).mockResolvedValue({ mode: "name", candidates: [] });
    await L.openFor({ ref_string: "foo.safetensors", dir_type: "loras" });
    await L.searchUnfiltered();
    expect(api.fetchLocate).toHaveBeenCalledWith({ q: "foo", ref: "foo.safetensors", nofilter: "1" });
  });
});

describe("fallbackToName", () => {
  it("hash 404 后转名称搜索", async () => {
    (api.fetchLocate as any).mockResolvedValue({ mode: "name", candidates: [] });
    L.target.value = { ref_string: "foo.safetensors", dir_type: "loras" };
    await L.fallbackToName();
    expect(api.fetchLocate).toHaveBeenCalledWith({ q: "foo", ref: "foo.safetensors", dir_type: "loras" });
  });
});

describe("error mapping", () => {
  it("ApiError.detail(reason) 进 error ref", async () => {
    (api.fetchLocate as any).mockRejectedValue(Object.assign(new Error(), { detail: "rate_limited" }));
    await L.openFor({ ref_string: "x.safetensors", sha256: "a".repeat(64) });
    expect(L.error.value).toBe("rate_limited");
  });
  it("无 detail 落 unknown", async () => {
    (api.fetchLocate as any).mockRejectedValue(new Error("boom"));
    await L.openFor({ ref_string: "x.safetensors", sha256: "a".repeat(64) });
    expect(L.error.value).toBe("unknown");
  });
});

describe("expectedPath / siteSearchUrl", () => {
  it("dir_type + ref,反斜杠归一", () => {
    expect(L.expectedPath({ ref_string: "SD1.5\\foo.safetensors", dir_type: "checkpoints" }))
      .toBe("checkpoints/SD1.5/foo.safetensors");
  });
  it("无 dir_type 时只归一 ref", () => {
    expect(L.expectedPath({ ref_string: "foo.safetensors" })).toBe("foo.safetensors");
  });
  it("siteSearchUrl 编码 query", () => {
    L.query.value = "龙 & x";
    expect(L.siteSearchUrl()).toBe("https://civitai.com/search/models?query=" + encodeURIComponent("龙 & x"));
  });
});
