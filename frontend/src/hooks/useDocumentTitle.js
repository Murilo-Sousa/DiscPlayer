import { useEffect } from "react";

export const SITE_NAME = "DiscPlayer";

/** Define o título da aba (e o texto anunciado a leitores de tela ao trocar de página). */
export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} | ${SITE_NAME}` : SITE_NAME;
  }, [title]);
}
