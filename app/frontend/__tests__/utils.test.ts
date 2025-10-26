import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("cn utility", () => {
  it("should merge class names correctly", () => {
    expect(cn("text-red-500", "bg-blue-500")).toBe("text-red-500 bg-blue-500");
  });

  it("should handle conditional classes", () => {
    expect(cn("base", true && "conditional", false && "excluded")).toBe("base conditional");
  });

  it("should override conflicting Tailwind classes", () => {
    // tailwind-merge should keep the last class when there's a conflict
    expect(cn("p-4", "p-8")).toBe("p-8");
  });

  it("should handle empty inputs", () => {
    expect(cn()).toBe("");
    expect(cn("", undefined, null)).toBe("");
  });
});
