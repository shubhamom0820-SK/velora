import { isValidElement, type ReactElement, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { InstallBanner } from "@/components/pwa/InstallBanner";
import { ServiceWorkerRegistrar } from "@/components/pwa/ServiceWorkerRegistrar";
import { AppShell } from "@/components/shell/AppShell";

import AppGroupLayout from "./(app)/layout";
import RootLayout from "./layout";

type Props = { children?: ReactNode };

/** Every element in a layout's returned tree, without rendering it. */
function elements(node: ReactNode): ReactElement<Props>[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!isValidElement<Props>(node)) return [];
  return [node, ...elements(node.props.children)];
}

describe("where the PWA's parts are mounted (T-9.7)", () => {
  it("registers the worker on every page, from the root layout (D-1041)", () => {
    const tree = elements(
      RootLayout({ children: null } as Parameters<typeof RootLayout>[0]),
    );
    expect(
      tree.filter((el) => el.type === ServiceWorkerRegistrar),
    ).toHaveLength(1);
  });

  it("puts the install banner first on every app screen, inside the shell", () => {
    const tree = elements(AppGroupLayout({ children: <main /> }));
    const shell = tree.find((el) => el.type === AppShell);
    const inside = elements(shell?.props.children);
    expect(inside[0]?.type).toBe(InstallBanner);
  });
});
