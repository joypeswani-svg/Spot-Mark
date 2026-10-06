/**
 * storage.ts — TruthLens Extension: chrome.storage.local Wrappers
 *
 * Typed, Promise-based wrappers around chrome.storage.local.
 * All per-tab state, block lists, and preferences go through here.
 */

import type { ExtensionPageState, BlockList } from "@truthlens/types";

// ── Page State ────────────────────────────────────────────────────────────────

export function getPageState(tabId: number): Promise<ExtensionPageState | null> {
  return new Promise((resolve) => {
    chrome.storage.local.get([`pageState_${tabId}`], (result) => {
      resolve(result[`pageState_${tabId}`] ?? null);
    });
  });
}

export function setPageState(tabId: number, state: ExtensionPageState): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.set({ [`pageState_${tabId}`]: state }, resolve);
  });
}

export function clearPageState(tabId: number): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.remove([`pageState_${tabId}`], resolve);
  });
}

// ── Block List ────────────────────────────────────────────────────────────────

export function getBlockList(): Promise<BlockList> {
  return new Promise((resolve) => {
    chrome.storage.local.get(["blockList"], (result) => {
      resolve(result.blockList ?? { domains: [], accounts: [], channels: [], updatedAt: new Date().toISOString() });
    });
  });
}

export function addToBlockList(
  type: keyof Omit<BlockList, "updatedAt">,
  value: string
): Promise<BlockList> {
  return new Promise(async (resolve) => {
    const current = await getBlockList();
    if (!current[type].includes(value)) {
      current[type].push(value);
      current.updatedAt = new Date().toISOString();
      chrome.storage.local.set({ blockList: current }, () => resolve(current));
    } else {
      resolve(current);
    }
  });
}

export function removeFromBlockList(
  type: keyof Omit<BlockList, "updatedAt">,
  value: string
): Promise<BlockList> {
  return new Promise(async (resolve) => {
    const current = await getBlockList();
    current[type] = current[type].filter((v) => v !== value);
    current.updatedAt = new Date().toISOString();
    chrome.storage.local.set({ blockList: current }, () => resolve(current));
  });
}

// ── Preferences ───────────────────────────────────────────────────────────────

export interface TruthLensPreferences {
  highlightingEnabled: boolean;
  notificationsEnabled: boolean;
  explainLikeImFive: boolean;
  familyShieldEnabled: boolean;
  autoAnalyze: boolean;
}

export function getPreferences(): Promise<TruthLensPreferences> {
  return new Promise((resolve) => {
    chrome.storage.local.get(["preferences"], (result) => {
      resolve(result.preferences ?? {
        highlightingEnabled: true,
        notificationsEnabled: false,
        explainLikeImFive: false,
        familyShieldEnabled: false,
        autoAnalyze: true,
      });
    });
  });
}

export function setPreferences(prefs: Partial<TruthLensPreferences>): Promise<void> {
  return new Promise(async (resolve) => {
    const current = await getPreferences();
    chrome.storage.local.set({ preferences: { ...current, ...prefs } }, resolve);
  });
}
