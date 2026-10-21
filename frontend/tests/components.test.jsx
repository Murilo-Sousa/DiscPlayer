import assert from "node:assert/strict";
import { test } from "node:test";
import { ActivityItem } from "../src/components/ActivityItem.jsx";
import { Avatar } from "../src/components/Avatar.jsx";
import { Cover } from "../src/components/Cover.jsx";
import { Disc, RatingDiscs } from "../src/components/Disc.jsx";
import { Field } from "../src/components/Field.jsx";
import { GameCard } from "../src/components/GameCard.jsx";
import { Histogram } from "../src/components/Layout.jsx";
import { Pagination } from "../src/components/Pagination.jsx";
import { RatingInput } from "../src/components/RatingInput.jsx";
import { ReviewCard } from "../src/components/ReviewCard.jsx";
import { StatusPicker } from "../src/components/StatusPicker.jsx";
import { Tabs } from "../src/components/Tabs.jsx";
import { buildOptions } from "../src/layouts/SearchBox.jsx";
import { safeNext } from "../src/pages/AuthPages.jsx";
import { PHOTO_MAX_BYTES, checkPhotoFile } from "../src/pages/SettingsPage.jsx";
import { count, html } from "./helpers.jsx";

const game = { rawg_id: 3, name: "Hades", slug: "hades", cover_url: "https://media.rawg.io/a.jpg", cover_thumb_url: "https://media.rawg.io/t.jpg", released: "2020-09-17" };
const user = { username: "ana", display_name: "Ana Souza", avatar_url: null };
const review = {
  id: 1,
  rating: 8.5,
  body: "Primeiro parágrafo.\n\nSegundo parágrafo.",
  created_at: "2026-10-01T10:00:00Z",
  updated_at: "2026-10-01T10:00:00Z",
  like_count: 2,
  liked: false,
  user,
  game,
};

// ----------------------------------------------------------------------------- discos
test("Disc desenha um quarto por unidade, no máximo quatro", () => {
  const filled = (quarters) => count(html(<Disc quarters={quarters} />), /fill="currentColor"/g);
  assert.equal(filled(0), 0);
  assert.equal(filled(1), 1);
  assert.equal(filled(3), 3);
  assert.equal(filled(9), 4);
  assert.equal(filled(-2), 0);
});

test("Disc: anel tracejado (quero jogar) e risco (abandonado)", () => {
  assert.match(html(<Disc dashed />), /stroke-dasharray/);
  assert.doesNotMatch(html(<Disc />), /stroke-dasharray/);
  assert.match(html(<Disc slash />), /stroke-linecap="round"/);
});

test("RatingDiscs: 5 discos, 1 quarto por 0,5 ponto, com texto alternativo", () => {
  const eightHalf = html(<RatingDiscs value={8.5} />);
  assert.equal(count(eightHalf, /<svg/g), 5);
  assert.equal(count(eightHalf, /fill="currentColor"/g), 17); // 4 discos cheios (16 quartos) + 1 quarto
  assert.match(eightHalf, /aria-label="Nota 8,5 de 10"/);

  assert.equal(count(html(<RatingDiscs value={10} />), /fill="currentColor"/g), 20);
  assert.equal(count(html(<RatingDiscs value={0.5} />), /fill="currentColor"/g), 1);
  const none = html(<RatingDiscs value={null} />);
  assert.equal(count(none, /fill="currentColor"/g), 0);
  assert.match(none, /aria-label="Sem nota"/);
});

// ----------------------------------------------------------------------------- status e nota
test("StatusPicker: cinco opções e só a escolhida fica pressionada", () => {
  const markup = html(<StatusPicker value="zerado" onChange={() => {}} />);
  for (const label of ["Quero jogar", "Jogando", "Pausado", "Zerado", "Abandonado"]) assert.match(markup, new RegExp(label));
  assert.equal(count(markup, /aria-pressed="true"/g), 1);
  assert.equal(count(markup, /aria-pressed="false"/g), 4);
  assert.equal(count(html(<StatusPicker value={null} onChange={() => {}} />), /aria-pressed="true"/g), 0);
});

test("RatingInput: controle de 0 a 10 em passos de 0,5, com texto de valor acessível", () => {
  const set = html(<RatingInput value={8.5} onChange={() => {}} />);
  assert.match(set, /type="range"/);
  assert.match(set, /min="0"/);
  assert.match(set, /max="10"/);
  assert.match(set, /step="0.5"/);
  assert.match(set, /aria-valuetext="8,5 de 10"/);
  assert.match(set, /Limpar nota/);

  const empty = html(<RatingInput value={null} onChange={() => {}} />);
  assert.match(empty, /Sem nota/);
  assert.doesNotMatch(empty, /Limpar nota/);
  assert.match(empty, /data-empty="true"/);
});

// ----------------------------------------------------------------------------- reviews
test("ReviewCard escapa HTML do texto (nunca interpreta marcação)", () => {
  const hostile = { ...review, body: '<script>alert(1)</script><img src=x onerror="alert(2)">' };
  const markup = html(<ReviewCard review={hostile} />);
  assert.doesNotMatch(markup, /<script/);
  assert.doesNotMatch(markup, /<img src=x/);
  assert.match(markup, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
});

test("ReviewCard: parágrafos, autor, nota e indicação de edição", () => {
  const markup = html(<ReviewCard review={review} />);
  assert.equal(count(markup, /<p>(Primeiro|Segundo) parágrafo\.<\/p>/g), 2);
  assert.match(markup, /Ana Souza/);
  assert.match(markup, /href="\/u\/ana"/);
  assert.match(markup, /8,5/);
  assert.doesNotMatch(markup, /editada em/);
  assert.match(html(<ReviewCard review={{ ...review, updated_at: "2026-10-05T10:00:00Z" }} />), /editada em/);
});

test("ReviewCard sem texto mostra só a nota", () => {
  const markup = html(<ReviewCard review={{ ...review, body: null }} />);
  assert.doesNotMatch(markup, /review-body/);
  assert.match(markup, /8,5/);
});

test("ReviewCard com spoilers esconde o texto: ele nem chega ao HTML antes do clique", () => {
  const secret = { ...review, body: "O mentor era o vilão desde o começo.", has_spoilers: true };
  const markup = html(<ReviewCard review={secret} />);
  assert.doesNotMatch(markup, /mentor/);
  assert.doesNotMatch(markup, /review-body/);
  assert.match(markup, /Contém spoilers/);
  assert.match(markup, /Esta review conta partes da história/);
  assert.match(markup, /<button[^>]*aria-expanded="false"[^>]*>Mostrar texto<\/button>/);
  assert.match(markup, /8,5/, "a nota continua visível");
  assert.match(markup, /Ana Souza/, "o autor continua visível");
});

test("ReviewCard com spoilers: o autor vê o próprio texto e review sem aviso não muda", () => {
  const secret = { ...review, body: "O mentor era o vilão.", has_spoilers: true };
  const own = html(<ReviewCard review={secret} alwaysShow />);
  assert.match(own, /O mentor era o vilão\./);
  assert.match(own, /Contém spoilers/, "o selo continua, para quem escreveu saber que está marcada");
  assert.doesNotMatch(own, /Mostrar texto/);

  const normal = html(<ReviewCard review={{ ...review, has_spoilers: false }} />);
  assert.doesNotMatch(normal, /spoiler/i);
  assert.match(normal, /Primeiro parágrafo/);
});

test("ReviewCard marcada com spoilers mas sem texto não mostra aviso nenhum", () => {
  const markup = html(<ReviewCard review={{ ...review, body: null, has_spoilers: true }} />);
  assert.doesNotMatch(markup, /spoiler/i);
  assert.doesNotMatch(markup, /Mostrar texto/);
});

test("ReviewCard com spoilers continua escapando HTML depois de revelado", () => {
  const hostile = { ...review, body: "<img src=x onerror=alert(1)>", has_spoilers: true };
  const markup = html(<ReviewCard review={hostile} alwaysShow />);
  assert.doesNotMatch(markup, /<img src=x/);
  assert.match(markup, /&lt;img src=x/);
});

test("ReviewCard: botão de curtir (pressionado) ou só a contagem", () => {
  const liked = html(<ReviewCard review={{ ...review, liked: true }} onLike={() => {}} canLike />);
  assert.match(liked, /aria-pressed="true"/);
  assert.match(liked, /Curtida/);
  assert.match(liked, /aria-label="2 curtidas"/);
  const plain = html(<ReviewCard review={review} />);
  assert.doesNotMatch(plain, /<button/);
  assert.match(plain, /like-static/);
  assert.doesNotMatch(html(<ReviewCard review={{ ...review, like_count: 0 }} />), /like-static/);
});

test("ReviewCard com jogo mostra o título do jogo e o link", () => {
  const markup = html(<ReviewCard review={review} showGame />);
  assert.match(markup, /href="\/jogos\/3-hades"/);
  assert.match(markup, />Hades</);
});

// ----------------------------------------------------------------------------- formulários
test("Field liga rótulo, dica e erro ao campo", () => {
  const markup = html(<Field label="E-mail" hint="Só para entrar." error="Informe um e-mail válido." type="email" />);
  const id = /<input id="([^"]+)"/.exec(markup)[1];
  assert.match(markup, new RegExp(`<label for="${id}"`));
  assert.match(markup, /aria-invalid="true"/);
  const described = /aria-describedby="([^"]+)"/.exec(markup)[1].split(" ");
  assert.equal(described.length, 2);
  for (const target of described) assert.match(markup, new RegExp(`id="${target}"`));
});

test("Field sem erro não marca o campo como inválido", () => {
  const markup = html(<Field label="Nome" />);
  assert.match(markup, /aria-invalid="false"/);
  assert.doesNotMatch(markup, /aria-describedby/);
});

test("Field textarea mostra contador de caracteres", () => {
  const markup = html(<Field label="Bio" as="textarea" maxLength={280} value="olá" readOnly />);
  assert.match(markup, /3\/280/);
});

// ----------------------------------------------------------------------------- navegação
test("Pagination some quando há uma página só e mostra a posição quando há várias", () => {
  assert.equal(html(<Pagination page={1} hasNext={false} onPage={() => {}} />), "");
  const markup = html(<Pagination page={2} hasNext totalPages={5} onPage={() => {}} />);
  assert.match(markup, /Página 2 de 5/);
  assert.equal(count(markup, /disabled=""/g), 0, "no meio, os dois botões ficam ativos");
  const first = html(<Pagination page={1} hasNext onPage={() => {}} />);
  assert.match(first, /<button[^>]*disabled=""[^>]*>[\s\S]*?Anterior/);
  assert.match(first, /Página 1</);
  const last = html(<Pagination page={3} hasNext={false} onPage={() => {}} />);
  assert.match(last, /<button[^>]*disabled=""[^>]*>[\s\S]*?Próxima/);
});

test("Tabs: papéis ARIA, aba selecionada e foco por tabIndex", () => {
  const markup = html(<Tabs label="Seções" value="b" onChange={() => {}} tabs={[{ value: "a", label: "A" }, { value: "b", label: "B", count: 3 }]} />);
  assert.match(markup, /role="tablist"/);
  assert.equal(count(markup, /role="tab"/g), 2);
  assert.equal(count(markup, /aria-selected="true"/g), 1);
  assert.equal(count(markup, /tabindex="-1"/g), 1);
  assert.match(markup, /tab-count">3</);
});

// ----------------------------------------------------------------------------- cartões e capas
test("GameCard mostra ano, status, favorito e nota com texto para leitores de tela", () => {
  const plain = html(<GameCard game={game} />);
  assert.match(plain, /href="\/jogos\/3-hades"/);
  assert.match(plain, />2020</);
  assert.doesNotMatch(plain, /game-card-flags/);

  const logged = html(<GameCard game={game} entry={{ status: "zerado", is_favorite: true }} rating={9} />);
  assert.match(logged, /Zerado/);
  assert.match(logged, /Favorito/);
  assert.match(logged, /Sua nota: <\/span>9/);
});

test("Cover usa a miniatura e, sem imagem, mostra as iniciais", () => {
  assert.match(html(<Cover game={game} />), /src="https:\/\/media\.rawg\.io\/t\.jpg"/);
  assert.match(html(<Cover game={game} />), /referrerPolicy|referrerpolicy="no-referrer"/i);
  const fallback = html(<Cover game={{ name: "Super Metroid" }} />);
  assert.doesNotMatch(fallback, /<img/);
  assert.match(fallback, />SM</);
});

test("Avatar: iniciais quando não há foto e imagem quando há", () => {
  assert.match(html(<Avatar user={user} />), />AS</);
  const withPhoto = html(<Avatar user={{ ...user, avatar_url: "/api/avatars/Zm9vYmFyYmF6cXV4" }} />);
  assert.match(withPhoto, /<img src="\/api\/avatars\/Zm9vYmFyYmF6cXV4"/);
  assert.doesNotMatch(withPhoto, /avatar-initials/);
});

test("Avatar nunca vira <img> para endereços que não são da foto enviada", () => {
  // Nem endereço externo (rastreamento), nem esquemas perigosos: ficam as iniciais.
  for (const bad of [
    "https://example.com/a.png",
    "http://example.com/a.png",
    "javascript:alert(1)",
    "data:image/png;base64,AAAA",
    "/api/avatars/../../x",
    "/api/lists",
  ]) {
    const markup = html(<Avatar user={{ ...user, avatar_url: bad }} />);
    assert.doesNotMatch(markup, /<img/, bad);
    assert.match(markup, />AS</);
  }
});

// ----------------------------------------------------------------------------- atividade
test("ActivityItem narra cada tipo de atividade em português", () => {
  const base = { id: 1, user, created_at: new Date().toISOString(), game };
  assert.match(html(<ul><ActivityItem activity={{ ...base, type: "logged", status: "jogando" }} /></ul>), /começou a jogar/);
  assert.match(html(<ul><ActivityItem activity={{ ...base, type: "logged", status: "zerado" }} /></ul>), /zerou/);
  assert.match(html(<ul><ActivityItem activity={{ ...base, type: "logged", status: "abandonado" }} /></ul>), /abandonou/);
  const reviewed = html(<ul><ActivityItem activity={{ ...base, type: "reviewed", review: { id: 1, rating: 7.5, excerpt: "Bom demais", like_count: 0 } }} /></ul>);
  assert.match(reviewed, /avaliou/);
  assert.match(reviewed, /7,5/);
  assert.match(reviewed, /Bom demais/);
  const list = html(<ul><ActivityItem activity={{ id: 2, type: "list_created", user, created_at: new Date().toISOString(), list: { id: 9, title: "Curtos e bons" } }} /></ul>);
  assert.match(list, /criou a lista/);
  assert.match(list, /href="\/listas\/9"/);
});

test("ActivityItem: recomeço aparece como 'voltou a jogar' e uma mudança comum de status, não", () => {
  const base = { id: 1, user, created_at: new Date().toISOString(), game, type: "logged", status: "jogando" };
  assert.match(html(<ul><ActivityItem activity={{ ...base, replay: true }} /></ul>), /voltou a jogar/);
  const normal = html(<ul><ActivityItem activity={{ ...base, replay: false }} /></ul>);
  assert.match(normal, /começou a jogar/);
  assert.doesNotMatch(normal, /voltou/);
  assert.match(html(<ul><ActivityItem showUser={false} activity={{ ...base, replay: true }} /></ul>), />Voltou a jogar /);
});

test("ActivityItem não mostra trecho de review com spoilers, só o aviso", () => {
  const base = { id: 1, user, created_at: new Date().toISOString(), game, type: "reviewed" };
  const hidden = html(<ul><ActivityItem activity={{ ...base, review: { id: 1, rating: 9, has_spoilers: true, excerpt: null, like_count: 0 } }} /></ul>);
  assert.match(hidden, /Contém spoilers/);
  assert.match(hidden, /9/);
  assert.doesNotMatch(hidden, /activity-excerpt/);
  // Mesmo que um servidor falho mandasse o trecho, a tela não o mostra.
  const leaked = html(<ul><ActivityItem activity={{ ...base, review: { id: 1, rating: 9, has_spoilers: true, excerpt: "O vilão era o mentor", like_count: 0 } }} /></ul>);
  assert.doesNotMatch(leaked, /O vilão era o mentor/);
  const open = html(<ul><ActivityItem activity={{ ...base, review: { id: 1, rating: 9, has_spoilers: false, excerpt: "Trilha linda", like_count: 0 } }} /></ul>);
  assert.match(open, /Trilha linda/);
});

test("ActivityItem sem autor (histórico próprio) começa a frase com maiúscula", () => {
  const markup = html(<ul><ActivityItem showUser={false} activity={{ id: 1, type: "logged", status: "pausado", user, game, created_at: new Date().toISOString() }} /></ul>);
  assert.match(markup, />Pausou /);
  assert.doesNotMatch(markup, /Ana Souza/);
});

// ----------------------------------------------------------------------------- gráficos
test("Histogram traz uma tabela equivalente para leitores de tela", () => {
  const markup = html(<Histogram values={[0, 2, 1]} labels={["0", "1", "2"]} srLabels={["Notas de 0 a 1", "Notas de 1 a 2", "Notas de 2 a 3"]} caption="Notas" />);
  assert.match(markup, /<caption>Notas<\/caption>/);
  assert.match(markup, /<th scope="row">Notas de 1 a 2<\/th><td>2<\/td>/);
  assert.match(markup, /<th scope="row">Total<\/th><td>3<\/td>/);
  assert.match(markup, /aria-hidden="true"/);
  assert.match(html(<Histogram values={[0, 0]} labels={["a", "b"]} caption="x" emptyText="Nada ainda." />), /Nada ainda\./);
  assert.doesNotMatch(markup, /Nada ainda/);
});

// ----------------------------------------------------------------------------- funções puras das telas
test("safeNext só aceita caminhos internos", () => {
  assert.equal(safeNext("/diario"), "/diario");
  assert.equal(safeNext("/jogos?q=a&pagina=2"), "/jogos?q=a&pagina=2");
  assert.equal(safeNext("//evil.example"), "/");
  assert.equal(safeNext("https://evil.example"), "/");
  assert.equal(safeNext("/\\evil.example"), "/");
  assert.equal(safeNext("javascript:alert(1)"), "/");
  assert.equal(safeNext(null), "/");
  assert.equal(safeNext(""), "/");
});

test("buildOptions monta grupos na ordem e termina com 'ver todos'", () => {
  const data = {
    games: { items: [game], error: null },
    users: [user],
    lists: [{ id: 5, title: "Curtos", game_count: 1 }],
    reviews: [{ id: 7, excerpt: "ótimo", user, game }],
  };
  const options = buildOptions(data, "hades");
  assert.deepEqual(options.map((o) => o.group), ["Jogos", "Jogadores", "Listas", "Reviews", null]);
  assert.equal(options[0].to, "/jogos/3-hades");
  assert.equal(options[1].to, "/u/ana");
  assert.equal(options[2].to, "/listas/5");
  assert.equal(options.at(-1).to, "/buscar?q=hades");
  assert.match(options.at(-1).label, /hades/);
  assert.equal(buildOptions(null, "x").length, 0);
  assert.equal(buildOptions({ games: { items: [] }, users: [], lists: [], reviews: [] }, "q").length, 1);
});

test("buildOptions codifica o termo da busca na URL", () => {
  const options = buildOptions({ games: { items: [] }, users: [], lists: [], reviews: [] }, "a&b=c d");
  assert.equal(options[0].to, "/buscar?q=a%26b%3Dc%20d");
});

// ----------------------------------------------------------------------------- foto de perfil
test("checkPhotoFile confere tipo, tamanho e arquivo vazio antes de enviar", () => {
  const file = (type, size) => ({ type, size, name: "foto" });
  for (const type of ["image/jpeg", "image/png", "image/webp"]) assert.equal(checkPhotoFile(file(type, 1000)), null, type);
  assert.equal(checkPhotoFile(file("image/png", PHOTO_MAX_BYTES)), null, "exatamente 5 MB ainda vale");
  assert.match(checkPhotoFile(file("image/png", PHOTO_MAX_BYTES + 1)), /grande demais/);
  assert.match(checkPhotoFile(file("image/png", 0)), /vazio/);
  for (const type of ["image/gif", "image/svg+xml", "application/pdf", "text/html", ""]) {
    assert.match(checkPhotoFile(file(type, 1000)), /JPG, PNG ou WebP/, type);
  }
});
