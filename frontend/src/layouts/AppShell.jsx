import { useEffect, useRef } from "react";
import { Disc } from "../components/Disc.jsx";
import { Icon } from "../components/Icon.jsx";
import { Logo } from "../components/Logo.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { Link, NavLink, useLocation } from "../router/index.jsx";
import { userPath } from "../utils/format.js";
import { SearchBox } from "./SearchBox.jsx";
import { UserMenu } from "./UserMenu.jsx";

function Header() {
  const { user, ready } = useAuth();
  return (
    <header className="site-header">
      <div className="container site-header-inner">
        <Logo />
        <nav className="site-nav" aria-label="Principal">
          <NavLink to="/jogos" className="site-nav-link">
            Jogos
          </NavLink>
          <NavLink to="/listas" className="site-nav-link">
            Listas
          </NavLink>
          {user && (
            <NavLink to="/diario" className="site-nav-link">
              Diário
            </NavLink>
          )}
        </nav>
        <SearchBox className="site-search" />
        <div className="site-account">
          {!ready ? null : user ? (
            <UserMenu />
          ) : (
            <>
              <Link to="/entrar" className="btn btn-quiet">
                Entrar
              </Link>
              <Link to="/cadastro" className="btn btn-primary">
                Criar conta
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

function MobileNav() {
  const { user } = useAuth();
  return (
    <nav className="mobile-nav" aria-label="Navegação principal">
      <NavLink to="/" end className="mobile-nav-link">
        <Icon name="home" size={22} />
        <span>Início</span>
      </NavLink>
      <NavLink to="/jogos" className="mobile-nav-link">
        <Disc quarters={1} size={22} />
        <span>Jogos</span>
      </NavLink>
      <NavLink to="/buscar" className="mobile-nav-link">
        <Icon name="search" size={22} />
        <span>Buscar</span>
      </NavLink>
      <NavLink to="/listas" className="mobile-nav-link">
        <Icon name="list" size={22} />
        <span>Listas</span>
      </NavLink>
      <NavLink to={user ? "/diario" : "/entrar"} className="mobile-nav-link">
        <Icon name={user ? "book" : "user"} size={22} />
        <span>{user ? "Diário" : "Entrar"}</span>
      </NavLink>
    </nav>
  );
}

function Footer() {
  const { user } = useAuth();
  return (
    <footer className="site-footer">
      <div className="container site-footer-inner">
        <div className="site-footer-brand">
          <Logo size={22} />
          <p>O diário de quem joga.</p>
        </div>
        <nav className="site-footer-links" aria-label="Rodapé">
          <Link to="/jogos">Catálogo</Link>
          <Link to="/listas">Listas</Link>
          {user ? <Link to={userPath(user.username)}>Meu perfil</Link> : <Link to="/cadastro">Criar conta</Link>}
        </nav>
        <p className="site-footer-credit">
          Dados e imagens dos jogos: <a href="https://rawg.io" target="_blank" rel="noopener noreferrer">RAWG</a>
        </p>
      </div>
    </footer>
  );
}

export function AppShell({ children }) {
  const { pathname } = useLocation();
  const mainRef = useRef(null);
  const shownPath = useRef(pathname);

  // Ao trocar de página, o foco vai para o conteúdo: leitores de tela anunciam a nova página
  // e quem usa teclado não precisa percorrer o cabeçalho de novo. Na primeira carga, não mexe no foco.
  useEffect(() => {
    if (shownPath.current === pathname) return;
    shownPath.current = pathname;
    mainRef.current?.focus({ preventScroll: true });
  }, [pathname]);

  return (
    <>
      <a className="skip-link" href="#conteudo">
        Ir para o conteúdo
      </a>
      <Header />
      <main id="conteudo" className="main" ref={mainRef} tabIndex={-1}>
        {children}
      </main>
      <Footer />
      <MobileNav />
    </>
  );
}
