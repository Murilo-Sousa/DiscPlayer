// O que cada status do diário permite. É o espelho de backend/app/services/library.py: o servidor é quem
// manda (ele recusa o que não vale), e a interface usa estas regras para só oferecer o que faz sentido.
// Um teste do back-end (test_diary_rules.py) confere que as listas abaixo são as mesmas do servidor.
import { formatDate, localToday } from "./format.js";

// A pessoa já começou o jogo: só nesses status há data de início, favorito, nota e review.
export const STARTED = ["jogando", "pausado", "abandonado", "zerado"];
// Só um jogo zerado tem data de término.
export const COMPLETABLE = ["zerado"];
// "Jogar de novo" vale para a jogada que terminou ou foi largada. Um jogo pausado se retoma voltando para "Jogando".
export const REPLAYABLE = ["zerado", "abandonado"];

export const hasStarted = (status) => STARTED.includes(status);
export const hasCompletionDate = (status) => COMPLETABLE.includes(status);
export const canReplay = (status) => REPLAYABLE.includes(status);

/** O jogo já saiu? Sem data de lançamento conhecida, vale que sim: ninguém é barrado por falta de dado. */
export function isReleased(released, today = localToday()) {
  return !released || released <= today;
}

/**
 * Por que este status não pode ser escolhido agora (texto para a pessoa), ou `null` se pode.
 * `game.released`: data de lançamento; `hasRating`: já há nota sua; `playthroughs`: jogadas anteriores guardadas.
 */
export function statusBlockedReason(status, { game, hasRating = false, playthroughs = 0, today } = {}) {
  if (status === "quero_jogar") {
    if (hasRating) return "Você já avaliou este jogo, então ele não volta para a fila. Exclua a sua nota antes, se quiser.";
    if (playthroughs > 0) return "Este jogo já tem jogadas anteriores no seu histórico, então ele não volta para a fila.";
    return null;
  }
  if (!isReleased(game?.released, today)) {
    return `Só sai em ${formatDate(game.released)}. Até lá, só dá para colocá-lo em “Quero jogar”.`;
  }
  return null;
}

/**
 * Se a pessoa pode dar nota ao jogo agora. Devolve `{ allowed, reason }`: `reason` explica, em uma frase, o que falta.
 * Só avalia quem já começou o jogo (e o jogo precisa ter sido lançado).
 */
export function ratingAccess({ entry, game, today }) {
  if (!isReleased(game?.released, today)) {
    return { allowed: false, reason: `Este jogo só será lançado em ${formatDate(game.released)}. Dá para avaliar depois que você jogar.` };
  }
  if (!entry) {
    return { allowed: false, reason: "Registre o jogo no seu diário como Jogando, Pausado, Abandonado ou Zerado para poder avaliá-lo." };
  }
  if (!hasStarted(entry.status)) {
    return { allowed: false, reason: "Você marcou este jogo como “Quero jogar”. Quando começar a jogar, mude o status e a nota é liberada." };
  }
  return { allowed: true, reason: null };
}
