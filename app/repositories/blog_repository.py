from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.blog_post import BlogPost
from app.models.user import User
from app.schemas.blog import BLOG_STATUS_DELETED, BLOG_STATUS_PUBLISHED


class BlogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _is_sqlite(self) -> bool:
        bind = self._session.get_bind()
        return bool(bind is not None and bind.dialect.name == "sqlite")

    async def _next_id(self) -> int:
        statement = select(func.coalesce(func.max(BlogPost.id), 0) + 1)
        value = await self._session.scalar(statement)
        return int(value or 1)

    @staticmethod
    def _public_filter(as_of: datetime):
        return and_(
            BlogPost.status == BLOG_STATUS_PUBLISHED,
            or_(BlogPost.published_at.is_(None), BlogPost.published_at <= as_of),
        )

    @staticmethod
    def _apply_search(statement, search: str | None):
        if not search:
            return statement

        normalized = search.strip()
        if not normalized:
            return statement

        like_pattern = f"%{normalized}%"
        return statement.where(
            or_(
                BlogPost.title.ilike(like_pattern),
                BlogPost.slug.ilike(like_pattern),
                BlogPost.excerpt.ilike(like_pattern),
            )
        )

    async def count_public(self, *, as_of: datetime) -> int:
        statement = select(func.count(BlogPost.id)).where(self._public_filter(as_of))
        total = await self._session.scalar(statement)
        return int(total or 0)

    async def list_public(
        self,
        *,
        as_of: datetime,
        offset: int,
        limit: int,
    ) -> list[BlogPost]:
        statement = (
            select(BlogPost)
            .options(selectinload(BlogPost.author))
            .where(self._public_filter(as_of))
            .order_by(func.coalesce(BlogPost.published_at, BlogPost.created_at).desc())
            .offset(offset)
            .limit(limit)
        )
        rows = await self._session.scalars(statement)
        return list(rows)

    async def get_public_by_slug(self, *, slug: str, as_of: datetime) -> BlogPost | None:
        statement = (
            select(BlogPost)
            .options(selectinload(BlogPost.author))
            .where(
                self._public_filter(as_of),
                BlogPost.slug == slug,
            )
        )
        return await self._session.scalar(statement)

    async def count_admin(self, *, status_filter: int | None = None, search: str | None = None) -> int:
        statement = select(func.count(BlogPost.id))
        statement = self._apply_admin_visibility_filter(statement, status_filter=status_filter)
        statement = self._apply_search(statement, search)
        total = await self._session.scalar(statement)
        return int(total or 0)

    async def list_admin(
        self,
        *,
        offset: int,
        limit: int,
        status_filter: int | None = None,
        search: str | None = None,
    ) -> list[BlogPost]:
        statement = (
            select(BlogPost)
            .options(selectinload(BlogPost.author))
            .order_by(BlogPost.created_at.desc())
        )
        statement = self._apply_admin_visibility_filter(statement, status_filter=status_filter)
        statement = self._apply_search(statement, search)
        statement = statement.offset(offset).limit(limit)

        rows = await self._session.scalars(statement)
        return list(rows)

    @staticmethod
    def _apply_admin_visibility_filter(statement, *, status_filter: int | None):
        if status_filter is None:
            return statement.where(BlogPost.status != BLOG_STATUS_DELETED)
        if status_filter == BLOG_STATUS_DELETED:
            return statement.where(false())
        return statement.where(BlogPost.status == status_filter)

    async def get_by_id(self, blog_post_id: int, *, include_deleted: bool = False) -> BlogPost | None:
        statement = (
            select(BlogPost)
            .options(selectinload(BlogPost.author))
            .where(BlogPost.id == blog_post_id)
        )
        if not include_deleted:
            statement = statement.where(BlogPost.status != BLOG_STATUS_DELETED)
        return await self._session.scalar(statement)

    async def slug_exists(self, *, slug: str, exclude_post_id: int | None = None) -> bool:
        statement = select(BlogPost.id).where(BlogPost.slug == slug)
        if exclude_post_id is not None:
            statement = statement.where(BlogPost.id != exclude_post_id)

        existing_id = await self._session.scalar(statement)
        return existing_id is not None

    async def author_exists(self, *, author_id: int) -> bool:
        statement = select(User.id).where(User.id == author_id)
        return await self._session.scalar(statement) is not None

    async def create(
        self,
        *,
        author_id: int | None,
        slug: str,
        title: str,
        summary: str | None,
        content_html: str,
        thumbnail_url: str | None,
        status: int,
        published_at: datetime | None,
    ) -> BlogPost:
        blog_id: int | None = None
        if self._is_sqlite():
            blog_id = await self._next_id()

        entity = BlogPost(
            id=blog_id,
            author_id=author_id,
            slug=slug,
            title=title,
            excerpt=summary,
            content=content_html,
            thumbnail_url=thumbnail_url,
            status=status,
            is_published=(status == BLOG_STATUS_PUBLISHED),
            published_at=published_at,
        )
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def save(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def soft_delete(self, entity: BlogPost) -> None:
        entity.status = BLOG_STATUS_DELETED
        entity.is_published = False
