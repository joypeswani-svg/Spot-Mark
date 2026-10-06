/**
 * BlockModal.tsx — Personal Domain Blocking & Muting Modal
 */

import React, { useState, useEffect } from "react";

interface BlockModalProps {
  isOpen: boolean;
  onClose: () => void;
  domain?: string;
}

export const BlockModal: React.FC<BlockModalProps> = ({
  isOpen,
  onClose,
  domain,
}) => {
  const [isBlocked, setIsBlocked] = useState(false);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");

  const targetDomain = domain || (typeof window !== "undefined" ? window.location.hostname.replace("www.", "") : "current domain");

  useEffect(() => {
    if (isOpen && typeof chrome !== "undefined" && chrome.storage) {
      chrome.storage.sync.get(["blockedDomains"], (result) => {
        const list: string[] = result.blockedDomains || [];
        setIsBlocked(list.includes(targetDomain));
      });
    }
  }, [isOpen, targetDomain]);

  if (!isOpen) return null;

  const handleToggleBlock = async () => {
    setLoading(true);
    const action = isBlocked ? "unblock" : "block";

    try {
      // 1. Sync local extension storage
      if (typeof chrome !== "undefined" && chrome.storage) {
        chrome.storage.sync.get(["blockedDomains"], (result) => {
          let list: string[] = result.blockedDomains || [];
          if (action === "block") {
            if (!list.includes(targetDomain)) list.push(targetDomain);
          } else {
            list = list.filter((d) => d !== targetDomain);
          }
          chrome.storage.sync.set({ blockedDomains: list });
        });
      }

      // 2. Sync backend API
      await fetch("http://localhost:8000/api/block", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target: targetDomain,
          targetType: "domain",
          action: action,
        }),
      });

      setIsBlocked(!isBlocked);
      setStatusMsg(
        action === "block"
          ? `🛡️ ${targetDomain} blocked. SpotMark shield banner will protect your visits.`
          : `Removed ${targetDomain} from your blocklist.`
      );
    } catch (err) {
      setStatusMsg(`Updated local blocklist for ${targetDomain}.`);
      setIsBlocked(!isBlocked);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <h3 style={styles.title}>🚫 Block Domain Source</h3>
          <button style={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        <p style={styles.subtitle}>
          Blocking is a <strong>personal safety shield</strong>. SpotMark will show a protective banner whenever you visit <code>{targetDomain}</code>.
        </p>

        <div style={styles.card}>
          <span style={styles.domainName}>{targetDomain}</span>
          <span style={isBlocked ? styles.badgeBlocked : styles.badgeActive}>
            {isBlocked ? "BLOCKED" : "ACTIVE"}
          </span>
        </div>

        {statusMsg && <div style={styles.statusBox}>{statusMsg}</div>}

        <div style={styles.btnRow}>
          <button onClick={onClose} style={styles.cancelBtn}>
            Close
          </button>
          <button
            onClick={handleToggleBlock}
            disabled={loading}
            style={isBlocked ? styles.unblockBtn : styles.blockBtn}
          >
            {loading
              ? "Updating..."
              : isBlocked
              ? "Unblock Source"
              : "Block This Source"}
          </button>
        </div>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0, 0, 0, 0.65)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 10000,
    fontFamily: "system-ui, -apple-system, sans-serif",
  },
  modal: {
    backgroundColor: "#1e1e2d",
    color: "#ffffff",
    borderRadius: "12px",
    padding: "20px",
    width: "320px",
    boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
    border: "1px solid #33334d",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottom: "1px solid #33334d",
    paddingBottom: "10px",
    marginBottom: "12px",
  },
  title: {
    margin: 0,
    fontSize: "15px",
    fontWeight: 600,
    color: "#e2e8f0",
  },
  closeBtn: {
    background: "none",
    border: "none",
    color: "#888",
    fontSize: "18px",
    cursor: "pointer",
  },
  subtitle: {
    fontSize: "12px",
    color: "#a0a0b8",
    marginTop: 0,
    marginBottom: "14px",
    lineHeight: "1.4",
  },
  card: {
    backgroundColor: "#161625",
    border: "1px solid #33334d",
    borderRadius: "8px",
    padding: "12px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "14px",
  },
  domainName: {
    fontSize: "13px",
    fontWeight: 600,
    color: "#fff",
  },
  badgeBlocked: {
    backgroundColor: "#742a2a",
    color: "#feb2b2",
    fontSize: "10px",
    fontWeight: 700,
    padding: "2px 8px",
    borderRadius: "4px",
  },
  badgeActive: {
    backgroundColor: "#22543d",
    color: "#9ae6b4",
    fontSize: "10px",
    fontWeight: 700,
    padding: "2px 8px",
    borderRadius: "4px",
  },
  statusBox: {
    backgroundColor: "#2a2a3d",
    color: "#cbd5e0",
    fontSize: "11px",
    padding: "8px 10px",
    borderRadius: "6px",
    marginBottom: "14px",
    lineHeight: "1.3",
  },
  btnRow: {
    display: "flex",
    justifyContent: "flex-end",
    gap: "8px",
  },
  cancelBtn: {
    backgroundColor: "transparent",
    color: "#aaa",
    border: "1px solid #555",
    borderRadius: "6px",
    padding: "6px 12px",
    fontSize: "12px",
    cursor: "pointer",
  },
  blockBtn: {
    backgroundColor: "#e53e3e",
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    padding: "6px 14px",
    fontSize: "12px",
    fontWeight: 600,
    cursor: "pointer",
  },
  unblockBtn: {
    backgroundColor: "#319795",
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    padding: "6px 14px",
    fontSize: "12px",
    fontWeight: 600,
    cursor: "pointer",
  },
};
