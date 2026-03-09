"""GraphQL router with graceful fallback when strawberry is unavailable."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user_sync

try:
    from strawberry.fastapi import GraphQLRouter

    from app.api.graphql.schema import schema

    async def get_graphql_context(
        current_user: dict = Depends(get_current_user_sync),
    ) -> dict:
        return {"current_user": current_user}

    router = GraphQLRouter(
        schema=schema,
        context_getter=get_graphql_context,
        graphiql=True,
    )
except Exception:
    router = APIRouter(prefix="/graphql", tags=["GraphQL"])

    @router.get("")
    @router.post("")
    async def graphql_unavailable():
        raise HTTPException(
            status_code=503,
            detail="GraphQL is unavailable. Install 'strawberry-graphql[fastapi]' and restart.",
        )
