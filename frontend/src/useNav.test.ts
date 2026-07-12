import { describe, it, expect } from "vitest";
import { view, cleanupTab, pendingWorkflowId, pendingModelId } from "./useNav";

describe("useNav", () => {
  it("defaults to dashboard + unreferenced, and is mutable module-level state", () => {
    expect(view.value).toBe("dashboard");
    expect(cleanupTab.value).toBe("unreferenced");
    cleanupTab.value = "duplicates"; view.value = "cleanup";
    expect(cleanupTab.value).toBe("duplicates");
    expect(view.value).toBe("cleanup");
  });

  it("holds one-shot workflow and model ids", () => {
    expect(pendingWorkflowId.value).toBeNull();
    expect(pendingModelId.value).toBeNull();
    pendingWorkflowId.value = 7;
    pendingModelId.value = 3;
    expect(pendingWorkflowId.value).toBe(7);
    expect(pendingModelId.value).toBe(3);
    pendingWorkflowId.value = null;
    pendingModelId.value = null;
    expect(pendingWorkflowId.value).toBeNull();
    expect(pendingModelId.value).toBeNull();
  });
});
