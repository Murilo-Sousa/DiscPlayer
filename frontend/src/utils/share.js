// Compartilhamento de links. Sem dependências do React: dá para testar com um `navigator` falso.

/**
 * Compartilha um endereço: usa o menu de compartilhar do aparelho quando existe (celulares, alguns
 * navegadores) e, sem ele, copia o endereço.
 *
 * Resultado: "shared" (menu usado), "copied" (endereço copiado), "cancelled" (a pessoa fechou o menu:
 * não é erro e nada é copiado) ou "failed" (nenhum dos dois meios funcionou).
 */
export async function shareLink({ url, title, text }, nav = globalThis.navigator) {
  if (typeof nav?.share === "function") {
    try {
      await nav.share({ title, text, url });
      return "shared";
    } catch (error) {
      if (error?.name === "AbortError") return "cancelled";
      // Qualquer outro erro (menu indisponível, permissão): tenta copiar.
    }
  }
  if (typeof nav?.clipboard?.writeText === "function") {
    try {
      await nav.clipboard.writeText(url);
      return "copied";
    } catch {
      return "failed";
    }
  }
  return "failed";
}
