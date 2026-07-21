import sqlite3
from dataclasses import dataclass

from src.config import DEFAULT_ELO
from src.database import database_connection


TOURNAMENT_NAME = "Liga MX"
TOURNAMENT_SEASON = "Apertura 2026"


@dataclass(frozen=True)
class MatchSeed:
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    user_prediction: str


TEAMS = [
    "América",
    "Atlas",
    "Atlante",
    "Cruz Azul",
    "Guadalajara",
    "Juárez",
    "León",
    "Monterrey",
    "Necaxa",
    "Pachuca",
    "Puebla",
    "Pumas",
    "Querétaro",
    "San Luis",
    "Santos",
    "Tigres",
    "Tijuana",
    "Toluca",
]


JORNADA_1 = [
    MatchSeed(
        home_team="Necaxa",
        away_team="Atlante",
        home_goals=2,
        away_goals=1,
        user_prediction="home",
    ),
    MatchSeed(
        home_team="Tijuana",
        away_team="Tigres",
        home_goals=3,
        away_goals=1,
        user_prediction="away",
    ),
    MatchSeed(
        home_team="Cruz Azul",
        away_team="San Luis",
        home_goals=3,
        away_goals=2,
        user_prediction="home",
    ),
    MatchSeed(
        home_team="Atlas",
        away_team="León",
        home_goals=3,
        away_goals=2,
        user_prediction="home",
    ),
    MatchSeed(
        home_team="Puebla",
        away_team="Juárez",
        home_goals=1,
        away_goals=0,
        user_prediction="away",
    ),
    MatchSeed(
        home_team="Pachuca",
        away_team="Pumas",
        home_goals=3,
        away_goals=0,
        user_prediction="away",
    ),
    MatchSeed(
        home_team="Monterrey",
        away_team="Santos",
        home_goals=3,
        away_goals=2,
        user_prediction="away",
    ),
    MatchSeed(
        home_team="Toluca",
        away_team="Guadalajara",
        home_goals=2,
        away_goals=0,
        user_prediction="away",
    ),
    MatchSeed(
        home_team="América",
        away_team="Querétaro",
        home_goals=1,
        away_goals=0,
        user_prediction="home",
    ),
]


def determine_outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"

    if home_goals < away_goals:
        return "away"

    return "draw"


def insert_tournament(connection: sqlite3.Connection) -> int:
    connection.execute(
        """
        INSERT INTO tournaments (
            name,
            season,
            current_round
        )
        VALUES (?, ?, ?)
        ON CONFLICT(name, season)
        DO UPDATE SET current_round = excluded.current_round
        """,
        (
            TOURNAMENT_NAME,
            TOURNAMENT_SEASON,
            1,
        ),
    )

    row = connection.execute(
        """
        SELECT id
        FROM tournaments
        WHERE name = ?
          AND season = ?
        """,
        (
            TOURNAMENT_NAME,
            TOURNAMENT_SEASON,
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError("No fue posible obtener el torneo.")

    return int(row["id"])


def insert_teams(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT INTO teams (
            name,
            current_elo
        )
        VALUES (?, ?)
        ON CONFLICT(name) DO NOTHING
        """,
        [(team, DEFAULT_ELO) for team in TEAMS],
    )


def get_team_ids(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT id, name
        FROM teams
        """
    ).fetchall()

    return {
        str(row["name"]): int(row["id"])
        for row in rows
    }


def insert_match(
    connection: sqlite3.Connection,
    tournament_id: int,
    team_ids: dict[str, int],
    match: MatchSeed,
) -> int:
    home_team_id = team_ids[match.home_team]
    away_team_id = team_ids[match.away_team]

    connection.execute(
        """
        INSERT INTO matches (
            tournament_id,
            round_number,
            home_team_id,
            away_team_id,
            home_goals,
            away_goals,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'completed')
        ON CONFLICT(
            tournament_id,
            round_number,
            home_team_id,
            away_team_id
        )
        DO UPDATE SET
            home_goals = excluded.home_goals,
            away_goals = excluded.away_goals,
            status = excluded.status
        """,
        (
            tournament_id,
            1,
            home_team_id,
            away_team_id,
            match.home_goals,
            match.away_goals,
        ),
    )

    row = connection.execute(
        """
        SELECT id
        FROM matches
        WHERE tournament_id = ?
          AND round_number = 1
          AND home_team_id = ?
          AND away_team_id = ?
        """,
        (
            tournament_id,
            home_team_id,
            away_team_id,
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"No fue posible obtener el partido "
            f"{match.home_team} vs {match.away_team}."
        )

    return int(row["id"])


def insert_prediction(
    connection: sqlite3.Connection,
    match_id: int,
    match: MatchSeed,
) -> None:
    real_outcome = determine_outcome(
        match.home_goals,
        match.away_goals,
    )

    points_awarded = int(
        match.user_prediction == real_outcome
    )

    connection.execute(
        """
        INSERT INTO user_predictions (
            match_id,
            predictor,
            predicted_outcome,
            is_final,
            points_awarded
        )
        VALUES (?, 'Hiram', ?, 1, ?)
        ON CONFLICT(match_id, predictor, is_final)
        DO UPDATE SET
            predicted_outcome = excluded.predicted_outcome,
            points_awarded = excluded.points_awarded
        """,
        (
            match_id,
            match.user_prediction,
            points_awarded,
        ),
    )


def seed_jornada_1() -> None:
    with database_connection() as connection:
        tournament_id = insert_tournament(connection)
        insert_teams(connection)

        team_ids = get_team_ids(connection)

        for match in JORNADA_1:
            match_id = insert_match(
                connection=connection,
                tournament_id=tournament_id,
                team_ids=team_ids,
                match=match,
            )

            insert_prediction(
                connection=connection,
                match_id=match_id,
                match=match,
            )

    print("Jornada 1 cargada correctamente.")
    print("Pronósticos registrados: 9")
    print("Aciertos esperados: 4")
    print("Errores esperados: 5")


if __name__ == "__main__":
    seed_jornada_1()
