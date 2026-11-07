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

/** Dados que vêm do IGDB. Ficam num cartão à parte e não entram na média do DiscPlayer. */
export function IgdbCard({ game }) {
  const hasAny = game.igdb_rating || game.critic_score;
  if (!hasAny) return null;
  return (
    <section className="score-card score-card-external" aria-labelledby="igdb-title">
      <h2 id="igdb-title" className="score-title">
        Dados do IGDB <span className="score-tag">fonte externa</span>
      </h2>
      <dl className="score-facts">
        {game.igdb_rating && (
          <div>
            <dt>Nota dos jogadores no IGDB</dt>
            <dd>
              {formatAverage(game.igdb_rating)} <span className="muted">de 10</span>
              {game.igdb_ratings_count > 0 && <span className="muted">, {plural(game.igdb_ratings_count, "voto", "votos")}</span>}
            </dd>
          </div>
        )}
        {game.critic_score && (
          <div>
            <dt>Nota da crítica</dt>
            <dd>
              {game.critic_score} <span className="muted">de 100</span>
            </dd>
          </div>
        )}
      </dl>
      <p className="score-note">Estas notas não entram na média da comunidade DiscPlayer.</p>
    </section>
  );
}
