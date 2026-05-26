import React from "react";
import { createRoot } from "react-dom/client";

function App() {
  return (
    <div style={{
      background:"#0b2d46",
      color:"#ffffff",
      minHeight:"100vh",
      padding:"20px",
      fontFamily:"Arial"
    }}>
      <h1>Webshake Trading v1.8.3 Beta</h1>

      <div style={{
        background:"#123a57",
        padding:"20px",
        borderRadius:"12px",
        marginTop:"20px"
      }}>
        <h2>Dashboard</h2>

        <p>UI-Hotfix aktiv.</p>
        <p>Frontend erfolgreich geladen.</p>

        <hr />

        <h3>KI Status</h3>
        <p>Bereit</p>

        <h3>Startschutz</h3>
        <p>60 Sekunden</p>

        <h3>Paper-Trading</h3>
        <p>Aktiv</p>

        <h3>Multi-Timeframe-Analyse</h3>
        <p>Backend verbindet...</p>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
