import {describe, expect, it} from "vitest";

import {canEditJournal, isCompleteSelection} from "./picks";

describe("personal pick rules", () => {
  it("only edits open journals", () => {
    expect(canEditJournal("open")).toBe(true);
    expect(canEditJournal("finalized")).toBe(false);
    expect(canEditJournal("evaluated")).toBe(false);
    expect(canEditJournal(undefined)).toBe(false);
  });

  it("requires one selection for every active match", () => {
    expect(isCompleteSelection([1, 2], {1: "home"})).toBe(false);
    expect(
      isCompleteSelection([1, 2], {1: "home", 2: "draw"}),
    ).toBe(true);
    expect(isCompleteSelection([], {})).toBe(false);
  });
});
