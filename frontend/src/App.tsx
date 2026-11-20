import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Pipelines from "./pages/Pipelines";
import Screener from "./pages/Screener";

export default function App() {
  return (
    <>
      <header className="topbar">
        <strong>Options Platform</strong>
        <nav>
          <NavLink to="/screener">Forward Factor Screener</NavLink>
          <NavLink to="/pipelines">Data Pipelines</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/screener" replace />} />
          <Route path="/screener" element={<Screener />} />
          <Route path="/pipelines" element={<Pipelines />} />
        </Routes>
      </main>
    </>
  );
}
