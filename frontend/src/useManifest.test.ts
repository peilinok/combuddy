import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchWorkflowBundle, verifyManifest } from "./api";
import { report, error, verifying, exportBundle, verifyBundle, BODY_MAX } from "./useManifest";

vi.mock("./api", () => ({
  fetchWorkflowBundle: vi.fn(),
  verifyManifest: vi.fn(),
}));

const apiError = (status: number, detail: string) => Object.assign(new Error("x"), { status, detail });

// Mock DOM APIs for tests
class MockAnchor {
  href: string = "";
  download: string = "";
  click() {}
  remove() {}
}

describe("useManifest", () => {
  beforeEach(() => {
    report.value = null; error.value = null; verifying.value = false;
    vi.clearAllMocks();

    // Stub document.createElement
    const mockDocument = {
      createElement: (tag: string) => {
        if (tag === "a") return new MockAnchor();
        return {};
      },
      body: { appendChild: vi.fn(), removeChild: vi.fn() }
    };
    vi.stubGlobal("document", mockDocument);
    vi.stubGlobal("HTMLAnchorElement", MockAnchor);

    (globalThis as any).URL.createObjectURL = vi.fn(() => "blob:x");
    (globalThis as any).URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("exportBundle downloads a blob via a native anchor", async () => {
    (fetchWorkflowBundle as any).mockResolvedValue(new Blob(["z"]));
    const click = vi.spyOn(MockAnchor.prototype, "click").mockImplementation(() => {});
    await exportBundle(7, "flow.combuddy.zip");
    expect(fetchWorkflowBundle).toHaveBeenCalledWith(7);
    expect(click).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalled();
    expect(error.value).toBe(null);
  });

  it("exportBundle surfaces the backend reason instead of a silent fake zip", async () => {
    (fetchWorkflowBundle as any).mockRejectedValue(apiError(409, "source_missing"));
    await exportBundle(7, "flow.combuddy.zip");
    expect(error.value).toBe("source_missing");
  });

  it("verifyBundle fills report and toggles verifying", async () => {
    let seen = false;
    (verifyManifest as any).mockImplementation(async () => { seen = verifying.value; return { summary: { total: 3 } }; });
    await verifyBundle(new File(["z"], "a.zip"));
    expect(seen).toBe(true);
    expect(report.value.summary.total).toBe(3);
    expect(verifying.value).toBe(false);
  });

  it("verifyBundle maps errors to reason codes", async () => {
    (verifyManifest as any).mockRejectedValue(apiError(400, "bad_zip"));
    await verifyBundle(new File(["z"], "a.zip"));
    expect(error.value).toBe("bad_zip");
    expect(verifying.value).toBe(false);
  });

  it("verifyBundle rejects oversized files locally without a request", async () => {
    const big = new File(["z"], "big.zip");
    Object.defineProperty(big, "size", { value: BODY_MAX + 1 });
    await verifyBundle(big);
    expect(verifyManifest).not.toHaveBeenCalled();
    expect(error.value).toBe("too_large");
  });
});
