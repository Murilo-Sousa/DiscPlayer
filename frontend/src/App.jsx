import { RequireAuth } from "./components/RequireAuth.jsx";
import { AppShell } from "./layouts/AppShell.jsx";
import CatalogPage from "./pages/CatalogPage.jsx";
import DiaryPage from "./pages/DiaryPage.jsx";
import GamePage from "./pages/GamePage.jsx";
import HomePage from "./pages/HomePage.jsx";
import ListPage from "./pages/ListPage.jsx";
import ListsPage from "./pages/ListsPage.jsx";
import { LoginPage, RegisterPage } from "./pages/AuthPages.jsx";
import NotFoundPage from "./pages/NotFoundPage.jsx";
import ProfilePage from "./pages/ProfilePage.jsx";
import RetrospectivePage from "./pages/RetrospectivePage.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import { Routes } from "./router/index.jsx";

export const routes = [
  { path: "/", element: <HomePage /> },
  { path: "/jogos", element: <CatalogPage /> },
  { path: "/jogos/:id", element: <GamePage /> },
  { path: "/buscar", element: <SearchPage /> },
  { path: "/listas", element: <ListsPage /> },
  { path: "/listas/:id", element: <ListPage /> },
  { path: "/u/:username", element: <ProfilePage /> },
  { path: "/u/:username/retrospectiva", element: <RetrospectivePage /> },
  { path: "/u/:username/retrospectiva/:year", element: <RetrospectivePage /> },
  { path: "/diario", element: <RequireAuth><DiaryPage /></RequireAuth> },
  { path: "/configuracoes", element: <RequireAuth><SettingsPage /></RequireAuth> },
  { path: "/entrar", element: <LoginPage /> },
  { path: "/cadastro", element: <RegisterPage /> },
  { path: "*", element: <NotFoundPage /> },
];

export default function App() {
  return (
    <AppShell>
      <Routes routes={routes} />
    </AppShell>
  );
}
