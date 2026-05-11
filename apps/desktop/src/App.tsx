import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/app/AppLayout";
import { AgentsPage } from "@/features/agents/AgentsPage";
import { BootScreen } from "@/features/boot/BootScreen";
import { ControlDeckPage } from "@/features/control/ControlDeckPage";
import { ConsolePage } from "@/features/console/ConsolePage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { MetricsPage } from "@/features/metrics/MetricsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { CopilotPage } from "@/features/copilot/CopilotPage";
import { SystemEvolutionPage } from "@/features/evolution/SystemEvolutionPage";
import { SlackHubPage } from "@/features/slack/SlackHubPage";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<BootScreen />} />
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/metrics" element={<MetricsPage />} />
        <Route path="/console" element={<ConsolePage />} />
        <Route path="/control" element={<ControlDeckPage />} />
        <Route path="/slack" element={<SlackHubPage />} />
        <Route path="/copilot" element={<CopilotPage />} />
        <Route path="/evolution" element={<SystemEvolutionPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
