import {NavLink, Outlet} from "react-router-dom";

const links = [
  ["/", "Siguiente jornada", "01"],
  ["/quiniela", "Mi quiniela", "02"],
  ["/resultados", "Resultados", "03"],
  ["/rendimiento", "Rendimiento", "04"],
  ["/preguntar", "Ask PitchProphet", "05"],
];

export function Layout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">PP</span>
          <div>
            <strong>PitchProphet</strong>
            <small>Liga MX · Apertura 2026</small>
          </div>
        </div>
        <nav>
          {links.map(([to, label, number]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({isActive}) => (isActive ? "active" : "")}
            >
              <span>{number}</span>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="pulse" />
          Motor local activo
        </div>
      </aside>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
