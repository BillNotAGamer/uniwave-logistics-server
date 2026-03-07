from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.blog_repository import BlogRepository
from app.schemas.blog import BlogPublicDetailRead, BlogPublicListItemRead
from app.services.blog_service import BlogService

router = APIRouter(prefix="/api/blogs/public", tags=["BlogsPublic"])


def get_blog_service(
    session: AsyncSession = Depends(get_db_session),
) -> BlogService:
    return BlogService(
        session=session,
        repository=BlogRepository(session),
    )


@router.get(
    "",
    response_model=list[BlogPublicListItemRead],
    status_code=status.HTTP_200_OK,
)
async def list_public_blog_posts(
    response: Response,
    page: int = Query(default=1),
    pageSize: int = Query(default=10),
    service: BlogService = Depends(get_blog_service),
) -> list[BlogPublicListItemRead]:
    rows, total = await service.list_public_posts(
        page=page,
        page_size=pageSize,
    )
    response.headers["X-Total-Count"] = str(total)
    return [BlogPublicListItemRead.from_model(row) for row in rows]


@router.get(
    "/{slug}",
    response_model=BlogPublicDetailRead,
    status_code=status.HTTP_200_OK,
)
async def get_public_blog_post_detail(
    slug: str,
    service: BlogService = Depends(get_blog_service),
) -> BlogPublicDetailRead | JSONResponse:
    post = await service.get_public_post_by_slug(slug=slug)
    if post is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Bài viết không tồn tại hoặc chưa được xuất bản."},
        )
    return BlogPublicDetailRead.from_model(post)
