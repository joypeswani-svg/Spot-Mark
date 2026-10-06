/**
 * side-panel/index.tsx — TruthLens Chrome Side Panel
 *
 * Full-width analysis view with complete claim details, sources,
 * Report flow, Block flow, Ask TruthLens chat, and community notes.
 *
 * Step 1: Scaffold only — shows placeholder content.
 * Steps 3–6: Real data wired in progressively.
 */

import React from "react";
import { createRoot } from "react-dom/client";

function SidePanel() {
  return (
    <div style={{
      background: "#0F172A",
      color: "#F1F5F9",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
      height: "100vh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      gap: 12,
      padding: 24,
    }}>
      <div style={{ fontSize: 40 }}>🔍</div>
      <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>SpotMark</h1>
      <p style={{ fontSize: 13, color: "#94A3B8", textAlign: "center", lineHeight: 1.6 }}>
        Full analysis panel — coming in Steps 3–6.<br />
        Navigate to a news article and click the SpotMark icon to begin.
      </p>
      <p style={{ fontSize: 11, color: "#64748B", textAlign: "center" }}>
        Step 1: Extension skeleton loaded successfully ✓
      </p>
    </div>
  );
}

const container = document.getElementById("root");
if (container) createRoot(container).render(<SidePanel />);
