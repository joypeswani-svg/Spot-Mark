/**
 * options/index.tsx — TruthLens Options Page
 *
 * Full settings page: toggle highlighting, notifications,
 * ELI5 mode, Family Shield, backend URL override.
 *
 * Step 1: Scaffold only.
 * Step 10: Full account + preferences wired in.
 */

import React from "react";
import { createRoot } from "react-dom/client";

function OptionsPage() {
  return (
    <div style={{
      background: "#0F172A",
      color: "#F1F5F9",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
      minHeight: "100vh",
      padding: 32,
      maxWidth: 640,
      margin: "0 auto",
    }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8, color: "#6366F1" }}>
        TruthLens Settings
      </h1>
      <p style={{ color: "#94A3B8", fontSize: 14, marginBottom: 24 }}>
        Full settings page coming in Step 10 (account + cross-device sync).
      </p>
      <div style={{
        background: "#1E293B",
        border: "1px solid #334155",
        borderRadius: 10,
        padding: 20,
        fontSize: 13,
        color: "#94A3B8",
        lineHeight: 1.6,
      }}>
        <strong style={{ color: "#F1F5F9" }}>Upcoming settings:</strong>
        <ul style={{ marginTop: 8, paddingLeft: 20, listStyleType: "disc" }}>
          <li>Inline highlighting — on/off</li>
          <li>Auto-analyze articles — on/off</li>
          <li>"Explain Like I'm 5" mode</li>
          <li>Family Shield — manage linked devices</li>
          <li>Notifications — trending misinformation alerts</li>
          <li>Backend URL override (for self-hosted instances)</li>
          <li>Account login + cross-device block list sync</li>
          <li>Bias Compass — configure your preferred sources</li>
        </ul>
      </div>
    </div>
  );
}

const container = document.getElementById("root");
if (container) createRoot(container).render(<OptionsPage />);
