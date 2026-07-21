from src.config import DATABASE_PATH
from src.database import database_connection
from src.repositories.team_repository import TeamRepository

def show_teams() -> None:
    with database_connection() as connection:
        teams = connection.execute(
            """
            SELECT name, current_elo
            FROM teams
            ORDER BY current_elo DESC, name
            """
        ).fetchall()

    print("\nEQUIPOS")
    print("-" * 35)

    for team in teams:
        print(
            f"{team['name']:<20} "
            f"{team['current_elo']:>8.2f}"
        )

    total_elo = sum(
        float(team["current_elo"])
        for team in teams
    )

    print("-" * 35)
    print(f"{'Elo total':<20} {total_elo:>8.2f}")


def show_user_summary() -> None:
    with database_connection() as connection:
        summary = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(points_awarded), 0) AS correct
            FROM predictions
            WHERE predictor = 'Hiram'
              AND is_final = 1
              AND points_awarded IS NOT NULL
            """
        ).fetchone()

    total = int(summary["total"])
    correct = int(summary["correct"])
    incorrect = total - correct
    accuracy = correct / total * 100 if total else 0.0

    print("\nQUINIELA DE HIRAM")
    print("-" * 35)
    print(f"Pronósticos: {total}")
    print(f"Aciertos:    {correct}")
    print(f"Errores:     {incorrect}")
    print(f"Efectividad: {accuracy:.1f}%")
    
def show_standings() -> None:
    with database_connection() as connection:
        repository = TeamRepository(connection)
        teams = repository.find_all_ordered_by_standings()

    print("\nCLASIFICACIÓN")
    print("-" * 79)
    print(
        f"{'#':<3}"
        f"{'Equipo':<18}"
        f"{'PJ':>4}"
        f"{'G':>4}"
        f"{'E':>4}"
        f"{'P':>4}"
        f"{'GF':>5}"
        f"{'GC':>5}"
        f"{'DG':>5}"
        f"{'PTS':>6}"
        f"{'Elo':>9}"
    )
    print("-" * 79)

    for position, team in enumerate(teams, start=1):
        print(
            f"{position:<3}"
            f"{team['name']:<18}"
            f"{team['matches_played']:>4}"
            f"{team['wins']:>4}"
            f"{team['draws']:>4}"
            f"{team['losses']:>4}"
            f"{team['goals_for']:>5}"
            f"{team['goals_against']:>5}"
            f"{team['goal_difference']:>+5}"
            f"{team['points']:>6}"
            f"{team['current_elo']:>9.2f}"
        )


def main() -> None:
    print("PITCH PROPHET")
    print(f"Base de datos: {DATABASE_PATH}")

    show_standings()
    show_user_summary()


if __name__ == "__main__":
    main()