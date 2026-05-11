import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";

import { App } from "@/App";
import { ConfigProvider } from "@/context/config-context";
import "@/styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HashRouter>
      <ConfigProvider>
        <App />
      </ConfigProvider>
    </HashRouter>
  </React.StrictMode>,
);
