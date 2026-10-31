"""Perfis de exemplo: contas fictícias com diário, reviews, listas e seguidores.

Servem para mostrar como o site fica com atividade (a página inicial, o ranking, os perfis), por exemplo num
portfólio ainda sem comunidade. Nada acontece sozinho: só o comando abaixo cria ou remove esses perfis.

    python -m app.demo seed      cria os perfis de exemplo (não faz nada se eles já existem)
    python -m app.demo remove    remove todos de uma vez, com diário, notas, listas e curtidas
    python -m app.demo status    mostra se existem e quantos

Cuidados de projeto:
  * Cada conta fica marcada (`users.is_demo = 1`) e as telas mostram "Perfil de exemplo" ao lado do nome.
  * As contas não fazem login: a senha é aleatória e ninguém a conhece (e o login ainda recusa contas de exemplo).
  * Tudo passa pelas mesmas regras do diário de uma pessoa real: só avalia quem começou o jogo, "Quero jogar" não tem
    datas, e assim por diante. Só as datas de criação são recuadas, para a atividade não nascer toda no mesmo minuto.
  * Os jogos vêm da RAWG (busca pelo nome, na hora do seed): nenhum identificador ou capa é inventado. Um jogo que a
    RAWG não encontrar é pulado, junto com o que dependia dele.
  * Em produção o comando pede `--sim`, para ninguém criar perfis de exemplo num site de verdade sem querer.
"""
from __future__ import annotations

import argparse
import secrets
import sys
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from . import db as database
from .auth import hash_password
from .db import execute, fetch_all, fetch_one, transaction
from .services import games as games_service
from .services import library, lists as lists_service, rawg
from .services import reviews as reviews_service
from .utils.dates import today_utc, utcnow_iso


class DemoError(Exception):
    """Algo impede o comando; a mensagem diz o que fazer."""


@dataclass(frozen=True)
class Play:
    """Um jogo no diário de uma pessoa de exemplo.

    `ago`: há quantos dias o status foi registrado (para "zerado", é o dia em que terminou) e `start`: há quantos dias
    começou. `rating`/`review`: a nota (e o texto) dada depois.
    """

    game: str
    status: str
    ago: int
    start: int | None = None
    rating: float | None = None
    review: str | None = None
    spoilers: bool = False
    favorite: bool = False


@dataclass(frozen=True)
class Person:
    username: str
    display_name: str
    bio: str
    joined: int  # há quantos dias entrou
    plays: tuple[Play, ...] = ()
    follows: tuple[str, ...] = ()
    lists: tuple[tuple[str, str, tuple[str, ...]], ...] = field(default_factory=tuple)


CAST: tuple[Person, ...] = (
    Person(
        "marina_rpg",
        "Marina Lopes",
        "RPG longo, café frio e anotação no caderno. Se tem calendário no jogo, eu planejo a semana inteira.",
        joined=150,
        follows=("tiago_indie", "bia_souls", "renato_turnos"),
        plays=(
            Play(
                "Persona 5 Royal", "zerado", ago=41, start=112, rating=9.5, favorite=True,
                review="Cem horas e eu ainda queria mais um semestre. O calendário transforma cada dia numa pequena "
                "decisão, e a trilha faz o resto: até o menu me deixa de bom humor. A reta final cansa um pouco, mas o "
                "elenco segura.",
            ),
            Play(
                "Disco Elysium", "zerado", ago=74, start=96, rating=10,
                review="Li mais do que joguei, e foi perfeito. Cada habilidade vira uma voz na sua cabeça brigando por "
                "espaço, e algumas são péssimas conselheiras. Joguei sem pressa e recomendo o mesmo.",
            ),
            Play(
                "Hades", "zerado", ago=62, start=80, rating=8,
                review="Ótimo, mas não é um jogo para todo dia. Gosto de como a história avança a cada fuga; só não tenho "
                "a paciência de quem quer fechar todas as armas.",
            ),
            Play(
                "Chrono Trigger", "zerado", ago=21, start=30, rating=9,
                review="Curto para um RPG, sem gordura. Cada viagem no tempo muda a conversa, e a música ajuda em cada cena.",
            ),
            Play(
                "Baldur's Gate 3", "pausado", ago=9, start=35, rating=9,
                review="Pausei porque cada cena pede uma tarde inteira, e eu só tinha uma hora. Volto no fim de semana.",
            ),
            Play("The Witcher 3: Wild Hunt", "jogando", ago=12, start=12),
            Play("Elden Ring", "quero_jogar", ago=6),
        ),
        lists=(),
    ),
    Person(
        "tiago_indie",
        "Tiago Nogueira",
        "Indies curtos, de preferência os que cabem numa noite de semana. Anoto tudo aqui para não repetir jogo.",
        joined=140,
        follows=("marina_rpg", "luiza_cozy", "caio_retro"),
        plays=(
            Play(
                "Celeste", "zerado", ago=15, start=18, rating=9.5, favorite=True,
                review="Uma escalada que cabe em três noites. Morri centenas de vezes e nunca fiquei com raiva, porque o "
                "jogo reinicia na hora e me trata bem quando falho. O modo assistido é uma ideia tão boa que devia virar "
                "padrão.",
            ),
            Play(
                "Hollow Knight", "zerado", ago=33, start=70, rating=9,
                review="Me perdi no mapa de propósito e achei que valeu. Os chefes são justos, o silêncio é bonito e a "
                "trilha acompanha sem pedir atenção.",
            ),
            Play(
                "Outer Wilds", "zerado", ago=52, start=60, rating=10, spoilers=True,
                review="A hora em que o ciclo finalmente fez sentido me fez largar o controle. O final me deixou sem fala. "
                "Jogue sem ler nada antes e depois volte aqui para a gente conversar.",
            ),
            Play(
                "Return of the Obra Dinn", "abandonado", ago=70, start=80, rating=7,
                review="Admiro mais do que gosto. A ideia de deduzir quem morreu e como é brilhante, mas travei no meio do "
                "livro e perdi a paciência.",
            ),
            Play(
                "Balatro", "jogando", ago=6, start=6, rating=8.5,
                review="Era para ser só uma rodada. Já se passaram seis dias.",
            ),
            Play("Slay the Spire", "quero_jogar", ago=3),
        ),
        lists=(
            (
                "Indies para uma noite",
                "Jogos que terminam antes de a semana acabar.",
                ("Celeste", "Outer Wilds", "Balatro", "Return of the Obra Dinn"),
            ),
        ),
    ),
    Person(
        "bia_souls",
        "Bia Carvalho",
        "Morro, aprendo, morro de novo. Souls e parentes, sem guia aberto na outra tela.",
        joined=135,
        follows=("tiago_indie", "renato_turnos", "caio_retro"),
        plays=(
            Play(
                "Elden Ring", "zerado", ago=28, start=75, rating=9,
                review="O mundo aberto não segura a sua mão, e isso é o ponto. Fiquei três dias presa num chefe, trocando "
                "de estratégia, e a vitória valeu cada um. Só tenho ressalva com a câmera em lugares apertados.",
            ),
            Play(
                "Sekiro: Shadows Die Twice", "zerado", ago=61, start=110, rating=9.5,
                review="Aqui não dá para construir personagem para fugir do problema: é você e o ritmo do combate. "
                "Quando clicou, foi uma das sensações mais satisfatórias que já tive com um controle na mão.",
            ),
            Play(
                "Celeste", "zerado", ago=10, start=20, rating=9,
                review="Um respiro depois de tanto chefe. Mesma lógica de tentar de novo, só que sem castigo.",
            ),
            Play(
                "Hollow Knight", "pausado", ago=24, start=50, rating=8,
                review="Pausei no meio e volto quando eu me sentir corajosa. Lindo, mas me perco fácil nesse mapa.",
            ),
            Play(
                "Cyberpunk 2077", "abandonado", ago=90, start=140, rating=6,
                review="A cidade é de encher os olhos, mas larguei no meio. Talvez eu volte depois de tantos remendos.",
            ),
            Play("Hades", "jogando", ago=4, start=4),
        ),
        lists=(
            (
                "Morrer mais um pouco",
                "Para quem acha que ainda não apanhou o bastante.",
                ("Elden Ring", "Sekiro: Shadows Die Twice", "Hollow Knight"),
            ),
        ),
    ),
    Person(
        "caio_retro",
        "Caio Mendes",
        "Coleciono cartuchos e opinião sobre jogos de 1994. Se tem pixel, eu jogo.",
        joined=130,
        follows=("tiago_indie", "luiza_cozy", "marina_rpg"),
        plays=(
            Play(
                "Super Metroid", "zerado", ago=22, start=30, rating=10, favorite=True,
                review="1994 e ainda é aula de como se constrói um mapa. Você nunca recebe um tutorial, só um corredor "
                "estreito e a vontade de voltar com a habilidade nova.",
            ),
            Play(
                "Chrono Trigger", "zerado", ago=47, start=60, rating=9.5,
                review="Cada final novo faz você querer um pouco mais de tudo. É raro um RPG tão enxuto.",
            ),
            Play(
                "Half-Life 2", "zerado", ago=85, start=100, rating=9,
                review="A física na sua mão ainda impressiona. O ritmo é de cinema sem tirar o controle de você.",
            ),
            Play(
                "Shadow of the Colossus", "zerado", ago=18, start=25, rating=9,
                review="Poucas palavras, dezesseis gigantes e um silêncio que dói. A caminhada entre eles faz parte da obra.",
            ),
            Play(
                "Portal 2", "zerado", ago=130, start=140, rating=9.5,
                review="Tão engraçado quanto inteligente. O cooperativo é a melhor desculpa para chamar alguém para jogar.",
            ),
            Play(
                "Outer Wilds", "zerado", ago=37, start=44, rating=9.5,
                review="Um mistério de vinte e dois minutos que me deixou pensando por duas semanas.",
            ),
            Play("Undertale", "quero_jogar", ago=2),
        ),
        lists=(
            (
                "Aulas de design de 1994 a 2007",
                "Jogos antigos que ainda ensinam como se faz.",
                ("Super Metroid", "Chrono Trigger", "Half-Life 2", "Shadow of the Colossus", "Portal 2"),
            ),
        ),
    ),
    Person(
        "luiza_cozy",
        "Luíza Prado",
        "Jogos tranquilos, trilhas boas e nenhum chefe final. Se der para jogar de pijama, melhor.",
        joined=120,
        follows=("tiago_indie", "caio_retro"),
        plays=(
            Play(
                "Stardew Valley", "jogando", ago=20, start=20, rating=9, favorite=True,
                review="Era para ser só uma plantação. Agora tenho uma rotina, um vizinho que me adora e vontade de "
                "acordar cedo. Não sei como isso aconteceu.",
            ),
            Play(
                "Celeste", "zerado", ago=38, start=45, rating=8.5,
                review="Mais difícil do que eu esperava para um jogo fofo, mas o modo assistido me deixou terminar no meu ritmo.",
            ),
            Play(
                "Undertale", "zerado", ago=66, start=72, rating=9,
                review="Chorei com bichinho de pixel e não me arrependo. Faça tudo do jeito gentil na primeira vez.",
            ),
            Play(
                "Outer Wilds", "zerado", ago=50, start=55, rating=9,
                review="Um mistério que pede curiosidade, não habilidade. Joguei de pijama, com a luz apagada, e foi uma "
                "das melhores noites do ano.",
            ),
            Play(
                "Hades", "zerado", ago=26, start=40, rating=8.5,
                review="Não sou de jogos de ação, mas a cada tentativa a história avança um pouco, então perder nunca é "
                "tempo jogado fora.",
            ),
            Play("Return of the Obra Dinn", "quero_jogar", ago=5),
        ),
        lists=(
            (
                "Aconchego com trilha boa",
                "Para jogar de pijama.",
                ("Stardew Valley", "Undertale", "Celeste"),
            ),
        ),
    ),
    Person(
        "renato_turnos",
        "Renato Alves",
        "Mais um turno. Só mais um. Estratégia, cartas e planilhas que ninguém pediu.",
        joined=110,
        follows=("marina_rpg", "bia_souls", "tiago_indie"),
        plays=(
            Play(
                "Baldur's Gate 3", "zerado", ago=35, start=70, rating=10,
                review="Joguei uma vez e já quero outra só para ver o que acontece se eu for cruel. É o RPG com mais "
                "respeito pelas suas escolhas que já joguei.",
            ),
            Play(
                "Hades", "zerado", ago=44, start=60, rating=9,
                review="Cada fuga do inferno rende uma conversa nova. Raro ver um roguelike em que dá vontade de perder só "
                "para ouvir o que vem depois.",
            ),
            Play(
                "Hollow Knight", "zerado", ago=58, start=90, rating=8.5,
                review="Bonito e longo. Só achei os caminhos de volta cansativos.",
            ),
            Play(
                "Cyberpunk 2077", "zerado", ago=70, start=120, rating=7.5,
                review="Terminei e gostei do final que escolhi. No caminho, tropecei em mais bug do que merecia. A cidade "
                "compensa.",
            ),
            Play(
                "Slay the Spire", "jogando", ago=9, start=9, rating=8.5,
                review="Cada corrida é uma pequena história de risco. Perdi as primeiras todas, e foi aí que entendi o jogo.",
            ),
            Play(
                "Balatro", "jogando", ago=25, start=25, rating=9,
                review="Pôquer com regras quebradas de propósito. Perigoso para a noite de segunda.",
            ),
            Play("Disco Elysium", "quero_jogar", ago=8),
        ),
    ),
)

# (quem curte, quem escreveu, jogo)
LIKES: tuple[tuple[str, str, str], ...] = (
    ("marina_rpg", "tiago_indie", "Outer Wilds"),
    ("bia_souls", "tiago_indie", "Celeste"),
    ("luiza_cozy", "tiago_indie", "Celeste"),
    ("caio_retro", "marina_rpg", "Disco Elysium"),
    ("renato_turnos", "marina_rpg", "Persona 5 Royal"),
    ("tiago_indie", "bia_souls", "Sekiro: Shadows Die Twice"),
    ("marina_rpg", "bia_souls", "Elden Ring"),
    ("luiza_cozy", "caio_retro", "Super Metroid"),
    ("tiago_indie", "caio_retro", "Super Metroid"),
    ("bia_souls", "renato_turnos", "Baldur's Gate 3"),
    ("marina_rpg", "renato_turnos", "Baldur's Gate 3"),
    ("caio_retro", "luiza_cozy", "Undertale"),
    ("tiago_indie", "luiza_cozy", "Outer Wilds"),
    ("renato_turnos", "caio_retro", "Half-Life 2"),
)


# ---------------------------------------------------------------------------------------------- tempo
def _stamp(today: date, days_ago: int, key: str, *, later: int = 0) -> str:
    """Um instante (UTC) `days_ago` dias atrás, com hora e minuto estáveis para a mesma chave."""
    hour = min(9 + zlib.crc32(key.encode()) % 12 + later, 23)
    minute = zlib.crc32((key + "/min").encode()) % 60
    day = today - timedelta(days=days_ago)
    return datetime(day.year, day.month, day.day, hour, minute).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day(today: date, days_ago: int) -> str:
    return (today - timedelta(days=days_ago)).isoformat()


# ---------------------------------------------------------------------------------------------- jogos
def _names_needed() -> list[str]:
    names: list[str] = []
    for person in CAST:
        for play in person.plays:
            names.append(play.game)
        for _title, _description, games in person.lists:
            names.extend(games)
    return list(dict.fromkeys(names))


def _norm(text: str) -> str:
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def _find_on_rawg(name: str) -> int | None:
    """O id do jogo na RAWG: o resultado com o mesmo nome; na falta dele, o primeiro cujo nome contém o procurado."""
    found = rawg.search_games(search=name, page_size=10)["results"]
    wanted = _norm(name)
    for item in found:
        if _norm(item["name"]) == wanted:
            return item["rawg_id"]
    for item in found:
        if wanted in _norm(item["name"]):
            return item["rawg_id"]
    return None


def _resolve_games() -> tuple[dict[str, dict], list[str]]:
    """Procura cada jogo na RAWG e guarda a cópia local. Devolve (nome -> jogo, nomes não encontrados)."""
    resolved: dict[str, dict] = {}
    missing: list[str] = []
    for name in _names_needed():
        rawg_id = _find_on_rawg(name)
        if rawg_id is None:
            missing.append(name)
            continue
        resolved[name] = games_service.ensure_game(rawg_id)
    return resolved, missing


# ---------------------------------------------------------------------------------------------- comandos
def count() -> int:
    return fetch_one("SELECT COUNT(*) AS n FROM users WHERE is_demo = 1")["n"]


def seed() -> dict:
    """Cria os perfis de exemplo. Se já existem, não mexe em nada (use `remove` antes para refazer)."""
    if count():
        return {"created": False, "users": count()}
    taken = [p.username for p in CAST if fetch_one("SELECT 1 FROM users WHERE username = ?", (p.username,))]
    if taken:
        raise DemoError(
            "Estes nomes de usuário já pertencem a contas reais, então os perfis de exemplo não foram criados: "
            + ", ".join(taken)
            + "."
        )
    try:
        games, missing = _resolve_games()
    except rawg.RawgError as exc:
        raise DemoError(f"Não consegui falar com a RAWG para escolher os jogos ({exc.message}). Nada foi criado.") from exc
    if len(games) < len(_names_needed()) * 0.7:
        raise DemoError("A RAWG não encontrou jogos suficientes para montar os perfis de exemplo. Nada foi criado.")

    today = today_utc()
    today_iso = today.isoformat()
    ids: dict[str, int] = {}
    stats = {"users": 0, "entries": 0, "reviews": 0, "likes": 0, "follows": 0, "lists": 0}
    reviews: dict[tuple[str, str], int] = {}

    with transaction():
        for person in CAST:
            ids[person.username] = execute(
                "INSERT INTO users (username, display_name, email, password_hash, bio, session_key, created_at, is_demo)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    person.username,
                    person.display_name,
                    f"{person.username}@exemplo.invalid",  # .invalid nunca existe: ninguém recebe e-mail
                    hash_password(secrets.token_urlsafe(32)),  # senha aleatória, descartada
                    person.bio,
                    secrets.token_hex(16),
                    _stamp(today, person.joined, person.username),
                ),
            ).lastrowid
            stats["users"] += 1

        for person in CAST:
            user_id = ids[person.username]
            for play in person.plays:
                game = games.get(play.game)
                if game is None:
                    continue
                dates: dict = {}
                if play.status != "quero_jogar" and play.start is not None:
                    dates["started_at"] = _day(today, play.start)
                if play.status == "zerado":
                    dates["completed_at"] = _day(today, play.ago)
                if play.favorite:
                    dates["is_favorite"] = True
                library.upsert_entry(user_id, game, status=play.status, today=today_iso, **dates)
                key = f"{person.username}/{play.game}"
                changed = _stamp(today, play.ago, key)
                execute(
                    "UPDATE library_entries SET created_at = ?, updated_at = ?, status_changed_at = ?"
                    " WHERE user_id = ? AND game_id = ?",
                    (changed, changed, changed, user_id, game["id"]),
                )
                execute(
                    "UPDATE activities SET created_at = ? WHERE user_id = ? AND game_id = ? AND type = 'logged'",
                    (changed, user_id, game["id"]),
                )
                stats["entries"] += 1
                if play.rating is None:
                    continue
                review_id = reviews_service.create_review(
                    user_id, game, play.rating, play.review, play.spoilers, today=today_iso
                )
                said = _stamp(today, play.ago, key, later=1)
                execute("UPDATE reviews SET created_at = ? WHERE id = ?", (said, review_id))
                execute("UPDATE activities SET created_at = ? WHERE review_id = ?", (said, review_id))
                reviews[(person.username, play.game)] = review_id
                stats["reviews"] += 1

            for title, description, names in person.lists:
                list_id = lists_service.create_list(user_id, title, description, True)
                for name in names:
                    if name in games:
                        lists_service.add_game(list_id, games[name]["id"])
                made = _stamp(today, max(person.joined // 4, 5), f"{person.username}/lista/{title}")
                execute("UPDATE lists SET created_at = ?, updated_at = ? WHERE id = ?", (made, made, list_id))
                execute("UPDATE list_games SET added_at = ? WHERE list_id = ?", (made, list_id))
                execute("UPDATE activities SET created_at = ? WHERE list_id = ?", (made, list_id))
                stats["lists"] += 1

        for person in CAST:
            for followed in person.follows:
                execute(
                    "INSERT OR IGNORE INTO follows (follower_id, followed_id, created_at) VALUES (?, ?, ?)",
                    (ids[person.username], ids[followed], _stamp(today, max(person.joined - 10, 3), person.username + followed)),
                )
                stats["follows"] += 1

        for liker, author, game_name in LIKES:
            review_id = reviews.get((author, game_name))
            if review_id is None:
                continue
            reviews_service.set_like(ids[liker], review_id, True)
            execute(
                "UPDATE review_likes SET created_at = (SELECT created_at FROM reviews WHERE id = ?) WHERE user_id = ? AND review_id = ?",
                (review_id, ids[liker], review_id),
            )
            stats["likes"] += 1

    return {"created": True, "missing": missing, **stats}


def remove() -> int:
    """Remove todas as contas de exemplo e o que é delas (diário, notas, listas, curtidas, seguidores). Devolve quantas."""
    with transaction():
        total = count()
        execute("DELETE FROM users WHERE is_demo = 1")
    return total


# ---------------------------------------------------------------------------------------------- linha de comando
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.demo", description="Perfis de exemplo do DiscPlayer.")
    parser.add_argument("action", choices=["seed", "remove", "status"])
    parser.add_argument("--sim", action="store_true", help="confirma a ação quando o site está em produção")
    args = parser.parse_args(argv)

    from . import create_app

    app = create_app()
    with app.app_context():
        if args.action != "status" and app.config["IS_PRODUCTION"] and not args.sim:
            print(
                "Este banco é o de produção. Se é isso mesmo que você quer, repita o comando com --sim.",
                file=sys.stderr,
            )
            return 2
        database.migrate()
        try:
            if args.action == "status":
                total = count()
                print(f"{total} perfil(is) de exemplo." if total else "Não há perfis de exemplo.")
            elif args.action == "seed":
                result = seed()
                if not result["created"]:
                    print(f"Os {result['users']} perfis de exemplo já existem. Para refazer: remove e depois seed.")
                else:
                    print(
                        f"Criados {result['users']} perfis, {result['entries']} jogos no diário, {result['reviews']} reviews, "
                        f"{result['lists']} listas, {result['follows']} seguidas e {result['likes']} curtidas."
                    )
                    if result["missing"]:
                        print("Jogos que a RAWG não achou e foram pulados: " + ", ".join(result["missing"]) + ".")
            else:
                print(f"Removidos {remove()} perfil(is) de exemplo.")
        except DemoError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
