// Utilitários dos testes: um `window` mínimo (o roteador lê a URL) e renderização no servidor.
import { renderToStaticMarkup } from "react-dom/server";
import { Router } from "../src/router/index.jsx";

export function fakeWindow(url = "/") {
  const parsed = new URL(url, "http://localhost");
  globalThis.window = {
    location: { pathname: parsed.pathname, search: parsed.search, hash: parsed.hash, href: parsed.href },
    history: { pushState() {}, replaceState() {} },
    addEventListener() {},
    removeEventListener() {},
    scrollTo() {},
  };
}

/** Renderiza dentro do roteador e devolve o HTML. */
export function html(element, url = "/") {
  fakeWindow(url);
  return renderToStaticMarkup(<Router>{element}</Router>);
}

export const count = (markup, pattern) => (markup.match(pattern) ?? []).length;
