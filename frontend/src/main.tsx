import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import App from "./App";
import "./index.css";
import { AuthProvider } from "./context/AuthContext";
import { CampaignWorkspaceProvider } from "./context/CampaignWorkspaceContext";
import { InstallationProfileProvider } from "./context/InstallationProfileContext";
import { PermissionProvider } from "./context/PermissionContext";
import { RuntimeConnectionProvider } from "./context/RuntimeConnectionContext";
import { detectTauriRuntime } from "./config/runtime";

const Router = import.meta.env.VITE_ROUTER_MODE === "hash" || detectTauriRuntime() ? HashRouter : BrowserRouter;

console.info("[ProfileFix] remaining-sidebar-blocker-v3 20260723-01");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Router>
      <RuntimeConnectionProvider>
        <InstallationProfileProvider>
          <AuthProvider>
            <PermissionProvider>
              <CampaignWorkspaceProvider>
                <App />
              </CampaignWorkspaceProvider>
            </PermissionProvider>
          </AuthProvider>
        </InstallationProfileProvider>
      </RuntimeConnectionProvider>
    </Router>
  </React.StrictMode>,
);
