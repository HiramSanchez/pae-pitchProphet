import sqlite3
from dataclasses import dataclass

from src.config import DEFAULT_ELO
from src.models.match import CompletedMatch, ExternalMatch, ScheduledMatch


@dataclass(frozen=True)
class MatchSyncResult:
    added: int
    updated: int
    tournament_ids: frozenset[int]


class MatchRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_scheduled_by_round(
        self,
        tournament_id: int,
        round_number: int,
    ) -> list[ScheduledMatch]:
        rows = self.connection.execute(
            """
            SELECT
                m.id AS match_id,
                m.tournament_id,
                m.round_number,
                m.home_team_id,
                home_team.name AS home_team_name,
                m.away_team_id,
                away_team.name AS away_team_name
            FROM matches m
            INNER JOIN teams home_team
                ON home_team.id = m.home_team_id
            INNER JOIN teams away_team
                ON away_team.id = m.away_team_id
            WHERE m.tournament_id = ?
              AND m.round_number = ?
              AND m.status = 'scheduled'
            ORDER BY m.id
            """,
            (
                tournament_id,
                round_number,
            ),
        ).fetchall()

        return [
            ScheduledMatch(
                match_id=int(row["match_id"]),
                tournament_id=int(row["tournament_id"]),
                round_number=int(row["round_number"]),
                home_team_id=int(row["home_team_id"]),
                home_team_name=str(row["home_team_name"]),
                away_team_id=int(row["away_team_id"]),
                away_team_name=str(row["away_team_name"]),
            )
            for row in rows
        ]

    def find_completed_matches(
        self,
    ) -> list[sqlite3.Row]:
        date_column = (
            "match_date" if self._has_match_date() else "NULL AS match_date"
        )
        date_order = (
            "CASE WHEN match_date IS NULL THEN 1 ELSE 0 END, match_date,"
            if self._has_match_date()
            else ""
        )
        return self.connection.execute(
            f"""
            SELECT
                id,
                tournament_id,
                round_number,
                home_team_id,
                away_team_id,
                home_goals,
                away_goals,
                {date_column}
            FROM matches
            WHERE status = 'completed'
              AND home_goals IS NOT NULL
              AND away_goals IS NOT NULL
            ORDER BY
                {date_order}
                round_number ASC,
                home_team_id,
                away_team_id,
                id ASC
            """
        ).fetchall()

    def find_completed_by_tournament(
        self,
        tournament_id: int,
    ) -> list[CompletedMatch]:
        date_column = (
            "m.match_date" if self._has_match_date() else "NULL AS match_date"
        )
        date_order = (
            "CASE WHEN m.match_date IS NULL THEN 1 ELSE 0 END, m.match_date,"
            if self._has_match_date()
            else ""
        )
        rows = self.connection.execute(
            f"""
            SELECT
                m.id AS match_id,
                m.tournament_id,
                m.round_number,
                m.home_team_id,
                home.name AS home_team_name,
                m.away_team_id,
                away.name AS away_team_name,
                m.home_goals,
                m.away_goals,
                {date_column}
            FROM matches m
            INNER JOIN teams home
                ON home.id = m.home_team_id
            INNER JOIN teams away
                ON away.id = m.away_team_id
            WHERE m.tournament_id = ?
              AND m.status = 'completed'
              AND m.home_goals IS NOT NULL
              AND m.away_goals IS NOT NULL
            ORDER BY
                {date_order}
                m.round_number,
                m.home_team_id,
                m.away_team_id,
                m.id
            """,
            (tournament_id,),
        ).fetchall()

        return [
            CompletedMatch(
                match_id=int(row["match_id"]),
                tournament_id=int(row["tournament_id"]),
                round_number=int(row["round_number"]),
                home_team_id=int(row["home_team_id"]),
                home_team_name=str(row["home_team_name"]),
                away_team_id=int(row["away_team_id"]),
                away_team_name=str(row["away_team_name"]),
                home_goals=int(row["home_goals"]),
                away_goals=int(row["away_goals"]),
                match_date=(
                    str(row["match_date"])
                    if row["match_date"] is not None
                    else None
                ),
            )
            for row in rows
        ]

    def _has_match_date(self) -> bool:
        return any(
            str(row[1]) == "match_date"
            for row in self.connection.execute("PRAGMA table_info(matches)")
        )

    def synchronize(
        self,
        source_name: str,
        matches: list[ExternalMatch],
    ) -> MatchSyncResult:
        added = 0
        updated = 0
        tournament_ids: set[int] = set()
        for external in matches:
            tournament_id = self._tournament_id(external)
            home_id = self._team_id(external.home_team_name)
            away_id = self._team_id(external.away_team_name)
            tournament_ids.add(tournament_id)
            row = self.connection.execute(
                """
                SELECT match_id FROM match_sources
                WHERE source_name = ? AND external_match_id = ?
                """,
                (source_name, external.external_match_id),
            ).fetchone()
            if row is None:
                natural = self.connection.execute(
                    """
                    SELECT id FROM matches
                    WHERE tournament_id = ? AND round_number = ?
                      AND home_team_id = ? AND away_team_id = ?
                    """,
                    (tournament_id, external.round_number, home_id, away_id),
                ).fetchone()
                if natural is None:
                    cursor = self.connection.execute(
                        """
                        INSERT INTO matches (
                            tournament_id, round_number, home_team_id,
                            away_team_id, match_date, home_goals,
                            away_goals, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        self._match_values(
                            external, tournament_id, home_id, away_id
                        ),
                    )
                    match_id = int(cursor.lastrowid)
                    added += 1
                else:
                    match_id = int(natural["id"])
                    updated += self._update_match_if_changed(
                        match_id, external, tournament_id, home_id, away_id
                    )
                self.connection.execute(
                    """
                    INSERT INTO match_sources
                    (source_name, external_match_id, match_id)
                    VALUES (?, ?, ?)
                    """,
                    (source_name, external.external_match_id, match_id),
                )
            else:
                match_id = int(row["match_id"])
                updated += self._update_match_if_changed(
                    match_id, external, tournament_id, home_id, away_id
                )
        for tournament_id in tournament_ids:
            self._refresh_current_round(tournament_id)
        return MatchSyncResult(added, updated, frozenset(tournament_ids))

    def _update_match_if_changed(
        self,
        match_id: int,
        external: ExternalMatch,
        tournament_id: int,
        home_id: int,
        away_id: int,
    ) -> int:
        current = self.connection.execute(
            "SELECT * FROM matches WHERE id = ?", (match_id,)
        ).fetchone()
        desired = self._match_values(
            external, tournament_id, home_id, away_id
        )
        columns = (
            "tournament_id", "round_number", "home_team_id",
            "away_team_id", "match_date", "home_goals",
            "away_goals", "status",
        )
        if tuple(current[name] for name in columns) == desired:
            return 0
        self.connection.execute(
            """
            UPDATE matches SET tournament_id = ?, round_number = ?,
                home_team_id = ?, away_team_id = ?, match_date = ?,
                home_goals = ?, away_goals = ?, status = ?
            WHERE id = ?
            """,
            (*desired, match_id),
        )
        return 1

    def find_next_scheduled_round(self, tournament_id: int) -> int | None:
        row = self.connection.execute(
            """
            SELECT MIN(round_number) AS round_number FROM matches
            WHERE tournament_id = ? AND status = 'scheduled'
            """,
            (tournament_id,),
        ).fetchone()
        return (
            int(row["round_number"])
            if row["round_number"] is not None
            else None
        )

    def _tournament_id(self, match: ExternalMatch) -> int:
        name = self._normalize(match.tournament_name)
        season = self._normalize(match.season)
        row = self.connection.execute(
            """
            SELECT id FROM tournaments
            WHERE name = ? COLLATE NOCASE
              AND season = ? COLLATE NOCASE
            """,
            (name, season),
        ).fetchone()
        if row is None:
            cursor = self.connection.execute(
                """
                INSERT INTO tournaments (name, season, current_round)
                VALUES (?, ?, ?)
                """,
                (name, season, match.round_number),
            )
            return int(cursor.lastrowid)
        return int(row["id"])

    def _refresh_current_round(self, tournament_id: int) -> None:
        self.connection.execute(
            """
            UPDATE tournaments
            SET current_round = COALESCE(
                (
                    SELECT MIN(round_number)
                    FROM matches
                    WHERE tournament_id = tournaments.id
                      AND status = 'scheduled'
                ),
                (
                    SELECT MAX(round_number)
                    FROM matches
                    WHERE tournament_id = tournaments.id
                      AND status = 'completed'
                ),
                1
            )
            WHERE id = ?
            """,
            (tournament_id,),
        )

    def _team_id(self, raw_name: str) -> int:
        name = self._normalize(raw_name)
        row = self.connection.execute(
            "SELECT id FROM teams WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if row is None:
            cursor = self.connection.execute(
                "INSERT INTO teams (name, current_elo) VALUES (?, ?)",
                (name, DEFAULT_ELO),
            )
            return int(cursor.lastrowid)
        return int(row["id"])

    @staticmethod
    def _normalize(value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Names cannot be empty")
        return normalized

    @staticmethod
    def _match_values(
        match: ExternalMatch,
        tournament_id: int,
        home_id: int,
        away_id: int,
    ) -> tuple[object, ...]:
        return (
            tournament_id, match.round_number, home_id, away_id,
            match.match_date, match.home_goals, match.away_goals, match.status,
        )
