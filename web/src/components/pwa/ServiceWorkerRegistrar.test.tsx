import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { register } from "@/lib/push";

import { ServiceWorkerRegistrar } from "./ServiceWorkerRegistrar";

vi.mock("@/lib/push", () => ({ register: vi.fn(() => Promise.resolve()) }));

describe("ServiceWorkerRegistrar (T-9.7)", () => {
  it("registers the one worker once, and draws nothing", () => {
    const { container, rerender } = render(<ServiceWorkerRegistrar />);
    rerender(<ServiceWorkerRegistrar />);

    expect(register).toHaveBeenCalledOnce();
    expect(container).toBeEmptyDOMElement();
  });
});
