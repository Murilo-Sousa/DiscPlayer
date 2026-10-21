import { useState } from "react";
import { Cover } from "../components/Cover.jsx";
import { Loader } from "../components/States.jsx";
import { ErrorState } from "../components/States.jsx";
import { useDocumentTitle } from "../hooks/useDocumentTitle.js";
import { useAsync } from "../hooks/useAsync.js";
import { Icon } from "../components/Icon.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useParams } from "../router/index.jsx";
import { gamesApi } from "../services/api.js";
import { ApiError } from "../services/http.js";
import { RatingDiscs } from "../components/Disc.jsx";
import { formatAverage, formatDate, paragraphs, parseGameParam, plural } from "../utils/format.js";
import NotFoundPage from "./NotFoundPage.jsx";
import { CommunityCard, RawgCard } from "./game/CommunityBlock.jsx";
import { DiaryPanel } from "./game/DiaryPanel.jsx";
import { ListsPanel } from "./game/ListsPanel.jsx";
import { ReviewPanel } from "./game/ReviewPanel.jsx";
import { ReviewsList } from "./game/ReviewsList.jsx";
import { LoginPrompt } from "./game/DiaryPanel.jsx";

const LONG_TEXT = 700;

function Description({ text }) {
  const [open, setOpen] = useState(false);
  const blocks = paragraphs(text);
  if (blocks.length === 0) return null;
  const long = text.length > LONG_TEXT;
  const shown = long && !open ? [blocks[0].slice(0, LONG_TEXT).trimEnd() + (blocks[0].length > LONG_TEXT ? "…" : "")] : blocks;
  return (
    <div className="game-description prose">
      {shown.map((paragraph, index) => (
        <p key={index}>{paragraph}</p>
      ))}
      {long && (
        <button type="button" className="link-btn" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          {open ? "Mostrar menos" : "Ler descrição completa"}
        </button>
      )}
    </div>
  );
}

export default function GamePage() {
  const { id } = useParams();
  const { user, ready } = useAuth();
  const rawgId = parseGameParam(id);
  const state = useAsync(
    (signal) =>
      rawgId === null
        ? Promise.reject(new ApiError({ status: 404, code: "not_found", message: "Jogo não encontrado." }))
        : gamesApi.detail(rawgId, { signal }),
    [rawgId],
  );
  const [reviewsKey, setReviewsKey] = useState(0);
  const data = state.data;
  useDocumentTitle(data?.game.name ?? "Jogo");

  if (state.error && !data) {
    if (state.error.status === 404) {
      return (
        <NotFoundPage title="Jogo não encontrado">Não encontramos esse jogo. Procure pelo nome no catálogo.</NotFoundPage>
      );
    }
    return (
      <div className="container page">
        <ErrorState error={state.error} onRetry={state.reload} />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="container page page-loading">
        <Loader label="Carregando o jogo" />
      </div>
    );
  }

  const { game, community, viewer, notice } = data;
  const year = game.released ? game.released.slice(0, 4) : null;
  const creators = [...(game.developers ?? [])].slice(0, 3).join(", ");

  const patchViewer = (changes) => state.setData((current) => ({ ...current, viewer: { ...current.viewer, ...changes } }));
  const refreshAll = () => {
    state.reload();
    setReviewsKey((value) => value + 1);
  };

  return (
    <div className="container page game">
      {notice && (
        <p className="notice" role="status">
          {notice.message} Mostrando os dados que já temos deste jogo.
        </p>
      )}
      <header className="game-head">
        <div className="game-poster">
          <Cover game={game} ratio="poster" alt={`Capa de ${game.name}`} eager original />
        </div>
        <div className="game-head-text">
          <p className="eyebrow">{creators ? `${creators}${year ? `, ${year}` : ""}` : year}</p>
          <h1 className="game-title">{game.name}</h1>
          <ul className="chips" aria-label="Gêneros">
            {(game.genres ?? []).map((genre) => (
              <li key={genre} className="chip">
                {genre}
              </li>
            ))}
          </ul>
          {(game.platforms ?? []).length > 0 && (
            <p className="game-platforms">
              <span className="sr-only">Plataformas: </span>
              {game.platforms.join(", ")}
            </p>
          )}
          <p className="game-score">
            <RatingDiscs value={community.average} size={18} />
            {community.count > 0 ? (
              <>
                <strong>{formatAverage(community.average)}</strong>
                <span>média de {plural(community.count, "nota", "notas")} no DiscPlayer</span>
              </>
            ) : (
              <span>Ainda sem notas no DiscPlayer</span>
            )}
          </p>
          <Description text={game.description ?? ""} />
          <dl className="facts">
            {game.released && (
              <div>
                <dt>Lançamento</dt>
                <dd>{formatDate(game.released)}</dd>
              </div>
            )}
            {game.publishers?.length > 0 && (
              <div>
                <dt>Publicação</dt>
                <dd>{game.publishers.slice(0, 3).join(", ")}</dd>
              </div>
            )}
            {game.playtime && (
              <div>
                <dt>Tempo médio (RAWG)</dt>
                <dd>{game.playtime} h</dd>
              </div>
            )}
            {game.esrb && (
              <div>
                <dt>Classificação (ESRB)</dt>
                <dd>{game.esrb}</dd>
              </div>
            )}
          </dl>
          {game.website && (
            <a className="ext-link" href={game.website} target="_blank" rel="noopener noreferrer">
              Site oficial <Icon name="external" size={15} />
              <span className="sr-only"> (abre em outra aba)</span>
            </a>
          )}
        </div>
      </header>

      <div className="game-body">
        <div className="game-main">
          {!ready ? null : user ? (
            <>
              <DiaryPanel
                rawgId={game.rawg_id}
                entry={viewer?.entry ?? null}
                playthroughs={viewer?.playthroughs ?? []}
                onSaved={(entry) => {
                  patchViewer({ entry });
                  state.reload();
                }}
                onReplayed={({ entry, playthroughs }) => {
                  patchViewer({ entry, playthroughs });
                  state.reload();
                }}
                onPlaythroughsChanged={({ entry, playthroughs }) => {
                  patchViewer({ entry, playthroughs });
                  state.reload();
                }}
                onRemoved={() => {
                  patchViewer({ entry: null, playthroughs: [] });
                  state.reload();
                }}
              />
              <ReviewPanel rawgId={game.rawg_id} review={viewer?.review ?? null} onChanged={refreshAll} />
              <ListsPanel rawgId={game.rawg_id} memberIds={viewer?.list_ids ?? []} onChange={(list_ids) => patchViewer({ list_ids })} />
            </>
          ) : (
            <section className="panel" aria-labelledby="guest-title">
              <h2 id="guest-title" className="panel-title">
                Registre este jogo
              </h2>
              <LoginPrompt>Entre na sua conta para colocar o jogo no seu diário, dar uma nota de 0 a 10, escrever uma review e guardá-lo em listas.</LoginPrompt>
            </section>
          )}
          <ReviewsList rawgId={game.rawg_id} refreshKey={reviewsKey} />
        </div>
        <aside className="game-side" aria-label="Notas e dados do jogo">
          <CommunityCard community={community} />
          <RawgCard game={game} />
          {game.screenshots?.length > 0 && (
            <section className="shots" aria-labelledby="shots-title">
              <h2 id="shots-title" className="score-title">
                Imagens
              </h2>
              <ul className="shots-grid">
                {game.screenshots.slice(0, 4).map((src) => (
                  <li key={src}>
                    <img src={src} alt={`Captura de tela de ${game.name}`} loading="lazy" decoding="async" referrerPolicy="no-referrer" />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
