from collections import Counter
from pathlib import Path

from src.data_sources.manual_source import ManualMatchDataSource
from src.services.data_update_service import DataUpdateService
from tests.test_data_update_service import database


FIXTURE_PATH = Path("examples/apertura_2026_fixtures.json")
EXPECTED_TEAMS = {
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
}
JORNADA_ONE = {
    ("Necaxa", "Atlante"),
    ("Tijuana", "Tigres"),
    ("Cruz Azul", "San Luis"),
    ("Atlas", "León"),
    ("Puebla", "Juárez"),
    ("Pachuca", "Pumas"),
    ("Monterrey", "Santos"),
    ("Toluca", "Guadalajara"),
    ("América", "Querétaro"),
}


def _fixtures():
    return ManualMatchDataSource.from_json_file(
        FIXTURE_PATH, "liga-mx-apertura-2026"
    ).fetch_matches()


def test_apertura_fixture_has_complete_round_robin_schedule() -> None:
    fixtures = _fixtures()

    assert len(fixtures) == 144
    assert {item.round_number for item in fixtures} == set(range(2, 18))
    assert len({item.external_match_id for item in fixtures}) == 144
    assert all(item.match_date is None for item in fixtures)

    by_round = Counter(item.round_number for item in fixtures)
    assert by_round == {round_number: 9 for round_number in range(2, 18)}

    team_rounds = Counter(
        (item.round_number, team)
        for item in fixtures
        for team in (item.home_team_name, item.away_team_name)
    )
    assert set(team for _, team in team_rounds) == EXPECTED_TEAMS
    assert all(count == 1 for count in team_rounds.values())

    pairs = {
        frozenset((item.home_team_name, item.away_team_name))
        for item in fixtures
    }
    pairs.update(frozenset(pair) for pair in JORNADA_ONE)
    assert len(pairs) == 153


def test_apertura_fixture_load_is_idempotent_and_preserves_round_one() -> None:
    connection = database()
    source = ManualMatchDataSource(
        _fixtures(), "liga-mx-apertura-2026"
    )
    tournament_id = connection.execute(
        """
        INSERT INTO tournaments (name, season, current_round)
        VALUES ('Liga MX', 'Apertura 2026', 1)
        """
    ).lastrowid
    team_ids = {}
    for team in sorted(EXPECTED_TEAMS):
        team_ids[team] = connection.execute(
            "INSERT INTO teams (name) VALUES (?)", (team,)
        ).lastrowid
    for home, away in sorted(JORNADA_ONE):
        connection.execute(
            """
            INSERT INTO matches (
                tournament_id, round_number, home_team_id, away_team_id,
                home_goals, away_goals, status
            ) VALUES (?, 1, ?, ?, 1, 0, 'completed')
            """,
            (tournament_id, team_ids[home], team_ids[away]),
        )

    first = DataUpdateService(connection).run(source)
    second = DataUpdateService(connection).run(source)

    assert first.matches_added == 144
    assert second.matches_added == 0
    assert second.matches_updated == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM matches"
    ).fetchone()[0] == 153
    assert connection.execute(
        """
        SELECT COUNT(*) FROM matches
        WHERE round_number = 1 AND status = 'completed'
        """
    ).fetchone()[0] == 9
    assert connection.execute(
        "SELECT current_round FROM tournaments WHERE id = ?",
        (tournament_id,),
    ).fetchone()[0] == 2
