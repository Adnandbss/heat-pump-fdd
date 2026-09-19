import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { DiagnosePage } from "./pages/DiagnosePage";
import { EvidencePage } from "./pages/EvidencePage";
import { InsightsPage } from "./pages/InsightsPage";
import { LivePage } from "./pages/LivePage";
import { ModelsPage } from "./pages/ModelsPage";
import { ThermoPage } from "./pages/ThermoPage";

function pageFromPath(pathname: string) {
  if (pathname.startsWith("/evidence")) return "evidence";
  if (pathname.startsWith("/live")) return "live";
  if (pathname.startsWith("/diagnose")) return "diagnose";
  if (pathname.startsWith("/models")) return "models";
  if (pathname.startsWith("/thermo")) return "thermo";
  return "insights";
}

export default function App() {
  const location = useLocation();
  const active = pageFromPath(location.pathname);

  return (
    <div className="relative min-h-screen px-4 py-6 md:px-8 md:py-10">
      <div className="mx-auto max-w-[1180px] flex gap-5 items-start">
        <Sidebar active={active} />
        <main className="glass-shell flex-1 min-w-0 p-5 md:p-8">
          <Header page={active} />
          <ErrorBoundary key={location.pathname}>
            <Routes>
              <Route path="/" element={<InsightsPage />} />
              <Route path="/evidence" element={<EvidencePage />} />
              <Route path="/live" element={<LivePage />} />
              <Route path="/diagnose" element={<DiagnosePage />} />
              <Route path="/models" element={<ModelsPage />} />
              <Route path="/thermo" element={<ThermoPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
