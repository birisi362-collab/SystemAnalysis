import React from "react";
import { createRoot } from "react-dom/client";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import "./review.css";
import App from "./workspace.jsx";

createRoot(document.getElementById("root")).render(<App />);
