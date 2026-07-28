import {createBrowserRouter, RouterProvider} from "react-router-dom";

import {Layout} from "./components/Layout";
import {AskPitchProphetPage} from "./pages/AskPitchProphetPage";
import {NextRoundPage} from "./pages/NextRoundPage";
import {PerformancePage} from "./pages/PerformancePage";
import {PersonalPicksPage} from "./pages/PersonalPicksPage";
import {RoundResultsPage} from "./pages/RoundResultsPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      {index: true, element: <NextRoundPage />},
      {path: "quiniela", element: <PersonalPicksPage />},
      {path: "resultados", element: <RoundResultsPage />},
      {path: "rendimiento", element: <PerformancePage />},
      {path: "preguntar", element: <AskPitchProphetPage />},
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
