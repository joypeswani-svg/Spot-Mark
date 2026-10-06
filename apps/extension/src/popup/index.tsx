/**
 * index.tsx — Popup entry point
 * Mounts the React app into the #root div.
 */

import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./popup.css";

const container = document.getElementById("root");
if (!container) throw new Error("Root element not found");

createRoot(container).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
