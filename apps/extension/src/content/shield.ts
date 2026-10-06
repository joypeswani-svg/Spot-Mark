/**
 * shield.ts — Content script module for blocked domain safety banner
 *
 * Checks if the current domain is in the user's local blocklist.
 * If blocked, injects a top shield banner at the very top of the page.
 */

export function initShieldBanner(): void {
  if (typeof chrome === "undefined" || !chrome.storage) return;

  const currentDomain = window.location.hostname.replace("www.", "").toLowerCase();

  chrome.storage.sync.get(["blockedDomains"], (result) => {
    const list: string[] = result.blockedDomains || [];

    if (list.includes(currentDomain)) {
      injectShieldBanner(currentDomain);
    }
  });
}

function injectShieldBanner(domain: string): void {
  if (document.getElementById("truthlens-shield-banner")) return;

  const banner = document.createElement("div");
  banner.id = "truthlens-shield-banner";
  banner.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    background-color: #1a1a2e;
    color: #ffffff;
    border-bottom: 2px solid #e53e3e;
    padding: 10px 16px;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 13px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    z-index: 2147483647;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  `;

  banner.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px;">
      <span style="font-size: 16px;">🛡️</span>
      <span>
        <strong>TruthLens Shield Active:</strong> You previously blocked content from <code>${domain}</code>.
      </span>
    </div>
    <div style="display: flex; gap: 8px;">
      <button id="tl-shield-unblock" style="background-color: #319795; color: #fff; border: none; border-radius: 4px; padding: 4px 10px; font-size: 11px; cursor: pointer; font-weight: 600;">
        Unblock Source
      </button>
      <button id="tl-shield-dismiss" style="background-color: transparent; color: #aaa; border: 1px solid #555; border-radius: 4px; padding: 4px 8px; font-size: 11px; cursor: pointer;">
        Dismiss
      </button>
    </div>
  `;

  document.body.prepend(banner);

  document.getElementById("tl-shield-dismiss")?.addEventListener("click", () => {
    banner.remove();
  });

  document.getElementById("tl-shield-unblock")?.addEventListener("click", () => {
    chrome.storage.sync.get(["blockedDomains"], (result) => {
      let list: string[] = result.blockedDomains || [];
      list = list.filter((d) => d !== domain);
      chrome.storage.sync.set({ blockedDomains: list }, () => {
        banner.remove();
      });
    });
  });
}

// Auto-run on script execution
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initShieldBanner);
} else {
  initShieldBanner();
}
