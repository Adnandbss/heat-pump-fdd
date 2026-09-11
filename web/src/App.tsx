import { useState } from "react";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { DiagnosePage } from "./pages/DiagnosePage";
import { InsightsPage } from "./pages/InsightsPage";
import { LivePage } from "./pages/LivePage";
import { ModelsPage } from "./pages/ModelsPage";
import { ThermoPage } from "./pages/ThermoPage";

export default function App() {
  const [active, setActive] = useState("insights");

  return (
    <div className="relative min-h-screen px-4 py-6 md:px-8 md:py-10">
      <div className="mx-auto max-w-[1180px] flex gap-5 items-start">
        <Sidebar active={active} onSelect={setActive} />
        <main className="glass-shell flex-1 min-w-0 p-5 md:p-8">
          <Header page={active} />
          {active === "insights" ? <InsightsPage /> : null}
          {active === "live" ? <LivePage /> : null}
          {active === "diagnose" ? <DiagnosePage /> : null}
          {active === "models" ? <ModelsPage /> : null}
          {active === "thermo" ? <ThermoPage /> : null}
        </main>
      </div>
    </div>
  );
}
