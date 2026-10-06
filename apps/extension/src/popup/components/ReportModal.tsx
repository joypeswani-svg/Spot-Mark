/**
 * ReportModal.tsx — Misinformation Reporting & PIB Fact Check Escalation Modal
 */

import React, { useState } from "react";

interface ReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUrl?: string;
  claimText?: string;
}

export const ReportModal: React.FC<ReportModalProps> = ({
  isOpen,
  onClose,
  currentUrl,
  claimText,
}) => {
  const [category, setCategory] = useState("false_information");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submittedData, setSubmittedData] = useState<any>(null);

  if (!isOpen) return null;

  const handleReportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const response = await fetch("http://localhost:8000/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contentUrl: currentUrl || window.location.href,
          claimText: claimText || "Reported via SpotMark Extension",
          categories: [category],
          notes: notes,
        }),
      });

      const data = await response.json();
      setSubmittedData(data);
    } catch (err) {
      // Offline fallback export payload generator
      const headline = encodeURIComponent(claimText || currentUrl || "Suspicious claim");
      const text = encodeURIComponent(
        `Hello PIB Fact Check Team,\n\nI would like to report suspected misinformation:\n\n"${claimText || currentUrl}"\n\nReported via SpotMark.`
      );
      setSubmittedData({
        reportId: "rep-local",
        message: "Report logged locally. You can also escalate directly to PIB Fact Check below:",
        pibEscalation: {
          pibWhatsAppUrl: `https://wa.me/918799711259?text=${text}`,
          pibEmailUrl: `mailto:pibfactcheck@gmail.com?subject=Fact%20Check%20Request&body=${text}`,
          pibPortalUrl: "https://factcheck.pib.gov.in",
          whatsappNumber: "+918799711259",
          email: "pibfactcheck@gmail.com",
        },
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={styles.overlay}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <h3 style={styles.title}>🚩 Report Misinformation</h3>
          <button style={styles.closeBtn} onClick={onClose}>✕</button>
        </div>

        {!submittedData ? (
          <form onSubmit={handleReportSubmit} style={styles.form}>
            <p style={styles.subtitle}>
              Submitting evidence flags this content in the SpotMark database and offers direct escalation to official fact-checking desks.
            </p>

            <label style={styles.label}>Report Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={styles.select}
            >
              <option value="false_information">False / Misleading Information</option>
              <option value="deepfake">Manipulated Media / Deepfake</option>
              <option value="clickbait">Sensationalist / Clickbait</option>
              <option value="scam">Scam / Impersonation</option>
            </select>

            <label style={styles.label}>Additional Context / Evidence (Optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Why is this claim incorrect? Provide links or evidence if available..."
              style={styles.textarea}
              rows={3}
            />

            <div style={styles.btnRow}>
              <button type="button" onClick={onClose} style={styles.cancelBtn}>
                Cancel
              </button>
              <button type="submit" disabled={submitting} style={styles.submitBtn}>
                {submitting ? "Submitting..." : "Submit Report"}
              </button>
            </div>
          </form>
        ) : (
          <div style={styles.successContainer}>
            <div style={styles.successBadge}>✅ Report Logged</div>
            <p style={styles.successText}>{submittedData.message}</p>

            <div style={styles.pibBox}>
              <h4 style={styles.pibTitle}>🇮🇳 Submit Directly to PIB Fact Check (Govt of India)</h4>
              <p style={styles.pibSubtitle}>
                Escalate this report directly to official verification channels:
              </p>

              <div style={styles.pibBtnGroup}>
                <a
                  href={submittedData.pibEscalation.pibWhatsAppUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={styles.waBtn}
                >
                  🟢 Send via WhatsApp (+91 8799711259)
                </a>

                <a
                  href={submittedData.pibEscalation.pibEmailUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={styles.emailBtn}
                >
                  📧 Email PIB Desk (pibfactcheck@gmail.com)
                </a>

                <a
                  href={submittedData.pibEscalation.pibPortalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={styles.portalBtn}
                >
                  🌐 PIB Fact Check Web Portal
                </a>
              </div>
            </div>

            <button onClick={onClose} style={styles.doneBtn}>
              Done
            </button>
          </div>
        )}
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
    width: "340px",
    maxHeight: "90vh",
    overflowY: "auto",
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
    fontSize: "16px",
    fontWeight: 600,
    color: "#ff4d4d",
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
    marginBottom: "12px",
    lineHeight: "1.4",
  },
  form: {
    display: "flex",
    flexDirection: "column",
  },
  label: {
    fontSize: "12px",
    fontWeight: 600,
    marginBottom: "4px",
    color: "#cccccc",
  },
  select: {
    backgroundColor: "#2a2a3d",
    color: "#fff",
    border: "1px solid #444466",
    borderRadius: "6px",
    padding: "8px",
    fontSize: "12px",
    marginBottom: "12px",
  },
  textarea: {
    backgroundColor: "#2a2a3d",
    color: "#fff",
    border: "1px solid #444466",
    borderRadius: "6px",
    padding: "8px",
    fontSize: "12px",
    marginBottom: "16px",
    resize: "vertical",
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
  submitBtn: {
    backgroundColor: "#e53e3e",
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    padding: "6px 14px",
    fontSize: "12px",
    fontWeight: 600,
    cursor: "pointer",
  },
  successContainer: {
    textAlign: "center",
  },
  successBadge: {
    backgroundColor: "#1c4532",
    color: "#68d391",
    padding: "6px 12px",
    borderRadius: "20px",
    display: "inline-block",
    fontSize: "12px",
    fontWeight: 600,
    marginBottom: "8px",
  },
  successText: {
    fontSize: "12px",
    color: "#cccccc",
    marginBottom: "14px",
  },
  pibBox: {
    backgroundColor: "#161625",
    border: "1px solid #ff9900",
    borderRadius: "8px",
    padding: "12px",
    textAlign: "left",
    marginBottom: "14px",
  },
  pibTitle: {
    margin: 0,
    fontSize: "13px",
    fontWeight: 600,
    color: "#ffaa00",
    marginBottom: "4px",
  },
  pibSubtitle: {
    margin: 0,
    fontSize: "11px",
    color: "#a0a0b8",
    marginBottom: "10px",
  },
  pibBtnGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  waBtn: {
    backgroundColor: "#25D366",
    color: "#000",
    textDecoration: "none",
    fontSize: "11px",
    fontWeight: 600,
    padding: "8px 10px",
    borderRadius: "6px",
    textAlign: "center",
    display: "block",
  },
  emailBtn: {
    backgroundColor: "#3182ce",
    color: "#fff",
    textDecoration: "none",
    fontSize: "11px",
    fontWeight: 600,
    padding: "8px 10px",
    borderRadius: "6px",
    textAlign: "center",
    display: "block",
  },
  portalBtn: {
    backgroundColor: "#4a5568",
    color: "#fff",
    textDecoration: "none",
    fontSize: "11px",
    fontWeight: 600,
    padding: "8px 10px",
    borderRadius: "6px",
    textAlign: "center",
    display: "block",
  },
  doneBtn: {
    width: "100%",
    backgroundColor: "#4a5568",
    color: "#fff",
    border: "none",
    borderRadius: "6px",
    padding: "8px",
    fontSize: "12px",
    cursor: "pointer",
  },
};
