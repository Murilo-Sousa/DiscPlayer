import { useEffect, useRef, useState } from "react";
import { Disc, STATUS_DISC } from "../../components/Disc.jsx";
import { StatusPicker } from "../../components/StatusPicker.jsx";
import { canReplay, hasCompletionDate, hasStarted } from "../../utils/diary.js";
import { STATUS_LABELS } from "../../utils/format.js";

export const STATUS_MEANING = {
  quero_jogar: "Na fila, ainda sem começar.",
  jogando: "Em andamento agora.",
  pausado: "Começou e deixou para depois.",
  zerado: "Terminou. O disco fecha o círculo.",
  abandonado: "Largou pelo caminho.",
};

/** O que o diário libera em cada status. As respostas vêm das mesmas regras que a tela do jogo usa (utils/diary.js). */
export const ABILITIES = [
  { key: "start", label: "Data de início", allowed: hasStarted },
  { key: "end", label: "Data de término", allowed: hasCompletionDate },
  { key: "favorite", label: "Favoritar", allowed: hasStarted },
  { key: "rating", label: "Nota e review", allowed: hasStarted },
  { key: "replay", label: "Jogar de novo", allowed: canReplay },
];

// Quando o disco aparece na tela, ele "joga" um jogo da fila até o zerado, uma vez. Qualquer clique interrompe.
const AUTOPLAY = ["quero_jogar", "jogando", "pausado", "zerado"];
const STEP_MS = 650;

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/**
 * O disco grande da página inicial: escolha um status e veja o disco fechar e o que o diário libera. É a mesma
 * lógica de verdade (o seletor é o do diário), mas nada é salvo: serve para mostrar o produto antes do cadastro.
 * A abertura sozinha só começa quando o disco entra na tela, senão ela terminaria antes de alguém chegar aqui.
 */
export function DiscInstrument() {
  const [status, setStatus] = useState("quero_jogar");
  const [touched, setTouched] = useState(false);
  const stopped = useRef(false);
  const root = useRef(null);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setStatus("zerado");
      return undefined;
    }
    let timers = [];
    const play = () => {
      timers = AUTOPLAY.slice(1).map((next, index) =>
        setTimeout(() => {
          if (!stopped.current) setStatus(next);
        }, 300 + STEP_MS * (index + 1)),
      );
    };
    let observer = null;
    if (typeof IntersectionObserver === "undefined" || !root.current) {
      play();
    } else {
      observer = new IntersectionObserver(
        ([entry]) => {
          if (!entry.isIntersecting) return;
          observer.disconnect();
          play();
        },
        { threshold: 0.3 },
      );
      observer.observe(root.current);
    }
    return () => {
      observer?.disconnect();
      timers.forEach(clearTimeout);
    };
  }, []);

  const choose = (next) => {
    stopped.current = true;
    setTouched(true);
    setStatus(next);
  };

  const shape = STATUS_DISC[status];
  return (
    <div className="instrument" role="group" aria-labelledby="instrument-title" ref={root}>
      <div className="instrument-stage">
        <Disc
          className="instrument-disc"
          data-status={status}
          size={288}
          strokeScale={0.42}
          animate
          quarters={shape.quarters}
          dashed={shape.dashed}
          slash={shape.slash}
        />
        <p className="instrument-caption" aria-live={touched ? "polite" : "off"}>
          <strong>{STATUS_LABELS[status]}</strong>
          <span>{STATUS_MEANING[status]}</span>
        </p>
      </div>
      <div className="instrument-panel">
        <h3 id="instrument-title" className="instrument-title">
          Como esse jogo está para você?
        </h3>
        <StatusPicker value={status} onChange={choose} label="Experimente um status" />
        <dl className="instrument-abilities" aria-label={`O que o diário libera em “${STATUS_LABELS[status]}”`}>
          {ABILITIES.map(({ key, label, allowed }) => (
            <div key={key} className="instrument-ability" data-allowed={allowed(status) || undefined}>
              <dt>{label}</dt>
              <dd>{allowed(status) ? "sim" : "não"}</dd>
            </div>
          ))}
        </dl>
        <p className="instrument-note">Um exemplo para mexer: nada aqui é salvo.</p>
      </div>
    </div>
  );
}
