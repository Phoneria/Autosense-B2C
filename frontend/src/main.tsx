import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import "./tokens.css";
import "./shell.css";
import "./analysis.css";
import "./data.css";
import "./vivid.css";
import "./fresh.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
