import sqlite3
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager

from fastapi import Depends, FastAPI, HTTPException, Query

from src.api.schemas import (
    QueryRequest,
    QueryResponse,
    UpdateRequest,
    UpdateResponse,
)
from src.data_sources.manual_source import ManualMatchDataSource
from src.database import database_connection
from src.query.interpreter import UnsupportedQueryError
from src.services.conversation_service import ConversationService
from src.services.data_update_service import DataUpdateService
from src.services.query_service import QueryService


ConnectionProvider = Callable[
    [], AbstractContextManager[sqlite3.Connection]
]


def create_app(
    connection_provider: ConnectionProvider = database_connection,
) -> FastAPI:
    app = FastAPI(title="PitchProphet", version="1.0.0")

    def connection_dependency() -> Generator[sqlite3.Connection]:
        with connection_provider() as connection:
            yield connection

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

    return app


app = create_app()
