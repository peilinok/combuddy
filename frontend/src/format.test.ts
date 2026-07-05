import { describe, it, expect } from "vitest";
import { humanSize } from "./format";

describe("humanSize", () => {
  it("formats GB", () => expect(humanSize(464 * 1024 ** 3)).toBe("464.0 GB"));
  it("formats MB", () => expect(humanSize(1536 * 1024)).toBe("1.5 MB"));
  it("zero", () => expect(humanSize(0)).toBe("0 B"));
});
