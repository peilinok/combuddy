import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchStats, postScan, ApiError } from "./api";

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300, status,
    json: () => body === undefined ? Promise.reject(new Error("no body")) : Promise.resolve(body),
  }));
}

afterEach(() => vi.unstubAllGlobals());

describe("api error propagation", () => {
  it("2xx passes json through", async () => {
    mockFetch(200, { model_count: 1 });
    expect((await fetchStats()).model_count).toBe(1);
  });
  it("409 carries reason from body", async () => {
    mockFetch(409, { started: false, reason: "already running" });
    const err = await postScan().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.detail).toBe("already running");
    expect(String(err)).toContain("already running");
  });
  it("404 carries error field", async () => {
    mockFetch(404, { error: "not found" });
    const err = await fetchStats().catch((e) => e);
    expect(err.detail).toBe("not found");
  });
  it("non-JSON error body degrades to status only", async () => {
    mockFetch(500, undefined);
    const err = await fetchStats().catch((e) => e);
    expect(err.status).toBe(500);
    expect(err.detail).toBe(null);
  });
});
