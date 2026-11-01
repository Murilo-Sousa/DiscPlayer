import { GameShelf, LibraryGameCard, ShelfItem } from "../../components/GameShelf.jsx";
import { useAsync } from "../../hooks/useAsync.js";
import { useDiaryEntries } from "../../hooks/useDiaryEntries.js";
import { Link } from "../../router/index.jsx";
import { gamesApi } from "../../services/api.js";

/**
 * "Mais em {gênero}": jogos populares do primeiro gênero do jogo, para seguir descobrindo. É um extra: se a RAWG não
 * responder (ou o jogo não tiver gênero), a prateleira simplesmente não aparece.
 */
export function RelatedShelf({ rawgId }) {
  const state = useAsync((signal) => gamesApi.related(rawgId, { signal }), [rawgId]);
  const items = state.data?.items ?? [];
  const diary = useDiaryEntries(items.map((game) => game.rawg_id));
  if (!state.data?.genre || items.length === 0) return null;
  const { genre } = state.data;
  return (
    <GameShelf
      className="game-related"
      title={`Mais em ${genre.name}`}
      action={
        <Link to={`/jogos?genero=${encodeURIComponent(genre.slug)}`} className="section-link">
          Ver todos
        </Link>
      }
    >
      {items.map((game) => (
        <ShelfItem key={game.rawg_id}>
          <LibraryGameCard game={game} diary={diary} />
        </ShelfItem>
      ))}
    </GameShelf>
  );
}
