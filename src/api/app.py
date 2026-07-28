import sqlite3
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware

from src.config import FRONTEND_ORIGINS
from src.api.schemas import (
    QueryRequest,
    QueryResponse,
    NextRoundResponse,
    PersonalModelComparisonResponse,
    PersonalPerformanceResponse,
    RoundResultsResponse,
    UpdateRequest,
    UpdateResponse,
    UserPicksRequest,
    UserPickUpdateRequest,
)
from src.data_sources.manual_source import ManualMatchDataSource
from src.database import database_connection
from src.query.interpreter import UnsupportedQueryError
from src.services.conversation_service import ConversationService
from src.services.data_update_service import DataUpdateService
from src.services.query_service import QueryService
from src.models.prediction import PredictedResult
from src.models.user_prediction import UserPickSelection
from src.repositories.user_prediction_repository import (
    UserPredictionRoundStateError,
)
from src.services.personal_prediction_service import (
    PersonalPredictionService,
    PredictionRoundNotFoundError,
    UserPredictionNotFoundError,
)


ConnectionProvider = Callable[
    [], AbstractContextManager[sqlite3.Connection]
]
READINESS_TABLES = {
    "matches",
    "predictions",
    "tournaments",
    "user_prediction_rounds",
    "user_predictions",
}


def create_app(
    connection_provider: ConnectionProvider = database_connection,
) -> FastAPI:
    app = FastAPI(title="PitchProphet", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(FRONTEND_ORIGINS),
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    def connection_dependency() -> Generator[sqlite3.Connection]:
        with connection_provider() as connection:
            yield connection

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readiness")
    def readiness(
        response: Response,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> dict[str, object]:
        try:
            connection.execute("SELECT 1").fetchone()
            tables = {
                str(row["name"])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            missing = sorted(READINESS_TABLES - tables)
        except sqlite3.DatabaseError:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready", "missing_tables": []}
        if missing:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready", "missing_tables": missing}
        return {"status": "ready", "missing_tables": []}

    @app.get(
        "/tournaments/{tournament_id}/rounds/next",
        response_model=NextRoundResponse,
    )
    def next_round(
        tournament_id: int,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        result = QueryService(connection).get_next_round(tournament_id)
        if result is None:
            raise HTTPException(404, "Next scheduled round was not found")
        return result

    @app.get("/tournaments/{tournament_id}/rounds/{round_number}/predictions")
    def round_predictions(
        tournament_id: int,
        round_number: int,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        return QueryService(connection).get_predictions_for_round(
            tournament_id, round_number
        )

    @app.get("/matches/{match_id}/predictions")
    def match_predictions(
        match_id: int,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        comparison = QueryService(connection).compare_models_for_match(match_id)
        if comparison is None:
            raise HTTPException(404, "Predictions were not found")
        return comparison

    @app.get("/matches/{match_id}/explanation")
    def match_explanation(
        match_id: int,
        model_name: str = Query(default="ensemble"),
        model_version: str = Query(default="1.0.0"),
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        explanation = QueryService(connection).get_prediction_explanation(
            match_id, model_name, model_version
        )
        if explanation is None:
            raise HTTPException(404, "Explanation was not found")
        return explanation

    @app.get("/models/performance")
    def model_performance(
        tournament_id: int = Query(gt=0),
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        return QueryService(connection).get_model_performance(tournament_id)

    @app.get(
        "/tournaments/{tournament_id}/rounds/{round_number}/results",
        response_model=RoundResultsResponse,
    )
    def round_results(
        tournament_id: int,
        round_number: int,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        result = QueryService(connection).get_round_results(
            tournament_id, round_number
        )
        if result is None:
            raise HTTPException(404, "Tournament round was not found")
        return result

    @app.get(
        "/tournaments/{tournament_id}/performance/personal",
        response_model=PersonalPerformanceResponse,
    )
    def personal_performance(
        tournament_id: int,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        return QueryService(connection).get_personal_performance(
            tournament_id
        )

    @app.get(
        "/tournaments/{tournament_id}/performance/comparison",
        response_model=PersonalModelComparisonResponse,
    )
    def personal_model_comparison(
        tournament_id: int,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        return QueryService(connection).compare_personal_performance(
            tournament_id
        )

    @app.post("/updates/run", response_model=UpdateResponse)
    def run_update(
        request: UpdateRequest,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> UpdateResponse:
        result = DataUpdateService(connection).run(
            ManualMatchDataSource(request.matches, request.source_name)
        )
        return UpdateResponse(
            run_id=result.run_id,
            matches_added=result.matches_added,
            matches_updated=result.matches_updated,
            predictions_generated=result.predictions_generated,
        )

    @app.post("/queries", response_model=QueryResponse)
    def answer_query(
        request: QueryRequest,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> QueryResponse:
        try:
            answer = ConversationService(QueryService(connection)).answer(
                request.question,
                request.tournament_id,
                request.match_id,
            )
        except UnsupportedQueryError as error:
            raise HTTPException(422, str(error)) from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        return QueryResponse(
            intent=answer.intent.value,
            message=answer.message,
            data=answer.data,
        )

    @app.post(
        "/tournaments/{tournament_id}/rounds/{round_number}/journal"
    )
    def open_personal_journal(
        tournament_id: int,
        round_number: int,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        try:
            journal = PersonalPredictionService(connection).open_round(
                tournament_id, round_number
            )
        except PredictionRoundNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        return {"journal": journal, "picks": []}

    @app.put(
        "/tournaments/{tournament_id}/rounds/{round_number}/picks"
    )
    def save_personal_picks(
        tournament_id: int,
        round_number: int,
        request: UserPicksRequest,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        try:
            service = PersonalPredictionService(connection)
            picks = service.save_picks(
                tournament_id,
                round_number,
                [
                    UserPickSelection(
                        match_id=item.match_id,
                        predicted_result=PredictedResult(
                            item.predicted_outcome.upper()
                        ),
                    )
                    for item in request.picks
                ],
            )
        except PredictionRoundNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except UserPredictionRoundStateError as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        journal = QueryService(
            connection
        ).get_personal_prediction_round(tournament_id, round_number)
        return {"journal": journal, "picks": picks}

    @app.patch("/picks/{prediction_id}")
    def update_personal_pick(
        prediction_id: int,
        request: UserPickUpdateRequest,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        try:
            return PersonalPredictionService(connection).update_pick(
                prediction_id,
                PredictedResult(request.predicted_outcome.upper()),
            )
        except UserPredictionNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except UserPredictionRoundStateError as error:
            raise HTTPException(409, str(error)) from error

    @app.post(
        "/tournaments/{tournament_id}/rounds/{round_number}/finalize"
    )
    def finalize_personal_journal(
        tournament_id: int,
        round_number: int,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        try:
            journal = PersonalPredictionService(connection).finalize_round(
                tournament_id, round_number
            )
        except PredictionRoundNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except UserPredictionRoundStateError as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        picks = QueryService(
            connection
        ).get_personal_predictions_for_round(tournament_id, round_number)
        return {"journal": journal, "picks": picks}

    @app.get(
        "/tournaments/{tournament_id}/rounds/{round_number}/picks"
    )
    def get_personal_picks(
        tournament_id: int,
        round_number: int,
        connection: sqlite3.Connection = Depends(connection_dependency),
    ) -> object:
        query = QueryService(connection)
        journal = query.get_personal_prediction_round(
            tournament_id, round_number
        )
        if journal is None:
            raise HTTPException(404, "Personal prediction round was not found")
        return {
            "journal": journal,
            "picks": query.get_personal_predictions_for_round(
                tournament_id, round_number
            ),
        }

    return app


app = create_app()
