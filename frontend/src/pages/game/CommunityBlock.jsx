import { StatusDisc, RatingDiscs } from "../../components/Disc.jsx";
import { Histogram } from "../../components/Layout.jsx";
import { RATING_LABELS, RATING_SR, STATUS_LABELS, STATUS_PROGRESS, formatAverage, plural } from "../../utils/format.js";

/** Nota da comunidade DiscPlayer: calculada só com as notas dadas aqui. */
export function CommunityCard({ community }) {
  const { average, count, with_text: withText, distribution, library } = community;
  return (
    <section className="score-card" aria-labelledby="community-title">
      <h2 id="community-title" className="score-title">
        Comunidade DiscPlayer
      </h2>
      {count === 0 ? (
        <p className="score-empty">Ainda sem notas. A sua pode ser a primeira.</p>
      ) : (
        <>
          <div className="score-main">
            <span className="score-number">
              <span className="sr-only">Média </span>
              {formatAverage(average)}
            </span>
            <span className="score-of">de 10</span>
            <RatingDiscs value={average} size={18} />
          </div>
          <p className="score-meta">
            {plural(count, "nota", "notas")}
            {withText > 0 && `, ${withText} com texto`}
          </p>
          <Histogram
            values={distribution}
            labels={RATING_LABELS}
            srLabels={RATING_SR}
            caption="Distribuição das notas da comunidade DiscPlayer"
          />
          <p className="score-note">Cada barra reúne a nota inteira e a meia nota seguinte (a barra 8 inclui 8 e 8,5); a última é só a nota 10.</p>
        </>
      )}
      {library.total > 0 && (
        <div className="score-library">
          <h3 className="score-subtitle">No diário de {plural(library.total, "pessoa", "pessoas")}</h3>
          <ul className="score-statuses">
            {STATUS_PROGRESS.filter((status) => library[status] > 0).map((status) => (
              <li key={status}>
                <StatusDisc status={status} size={16} />
                <span>{STATUS_LABELS[status]}</span>
                <strong>{library[status]}</strong>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/** Dados que vêm da RAWG. Ficam num cartão à parte e não entram na média do DiscPlayer. */
export function RawgCard({ game }) {
  const hasAny = game.rawg_rating || game.metacritic;
  if (!hasAny) return null;
  return (
    <section className="score-card score-card-external" aria-labelledby="rawg-title">
      <h2 id="rawg-title" className="score-title">
        Dados da RAWG <span className="score-tag">fonte externa</span>
      </h2>
      <dl className="score-facts">
        {game.rawg_rating && (
          <div>
            <dt>Nota na RAWG</dt>
            <dd>
              {formatAverage(game.rawg_rating)} <span className="muted">de 5</span>
              {game.rawg_ratings_count > 0 && <span className="muted">, {plural(game.rawg_ratings_count, "voto", "votos")}</span>}
            </dd>
          </div>
        )}
        {game.metacritic && (
          <div>
            <dt>Metacritic</dt>
            <dd>
              {game.metacritic} <span className="muted">de 100</span>
            </dd>
          </div>
        )}
      </dl>
      <p className="score-note">Estas notas não entram na média da comunidade DiscPlayer.</p>
    </section>
  );
}
