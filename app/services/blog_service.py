from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.blog_post import BlogPost
from app.models.mixins import utc_now
from app.repositories.blog_repository import BlogRepository
from app.schemas.blog import (
    BLOG_STATUS_PUBLISHED,
    BlogCreateRequest,
    BlogUpdateRequest,
)
from app.services.cloudinary import CloudinaryService
from app.utils.slug import build_slug_candidate, slugify


class BlogService:
    def __init__(self, *, session: AsyncSession, repository: BlogRepository) -> None:
        self._session = session
        self._repository = repository

    @staticmethod
    def normalize_legacy_paging(*, page: int, page_size: int) -> tuple[int, int]:
        normalized_page = page if page > 0 else 1
        normalized_page_size = page_size if 0 < page_size <= 50 else 10
        return normalized_page, normalized_page_size

    async def list_public_posts(
        self,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[BlogPost], int]:
        normalized_page, normalized_page_size = self.normalize_legacy_paging(
            page=page,
            page_size=page_size,
        )
        offset = (normalized_page - 1) * normalized_page_size

        as_of = utc_now()
        rows = await self._repository.list_public(
            as_of=as_of,
            offset=offset,
            limit=normalized_page_size,
        )
        total = await self._repository.count_public(as_of=as_of)
        return rows, total

    async def get_public_post_by_slug(self, *, slug: str) -> BlogPost | None:
        return await self._repository.get_public_by_slug(slug=slug, as_of=utc_now())

    async def list_admin_posts(
        self,
        *,
        page: int,
        page_size: int,
        status_filter: int | None,
        search: str | None,
    ) -> tuple[list[BlogPost], int]:
        normalized_page, normalized_page_size = self.normalize_legacy_paging(
            page=page,
            page_size=page_size,
        )
        offset = (normalized_page - 1) * normalized_page_size

        rows = await self._repository.list_admin(
            offset=offset,
            limit=normalized_page_size,
            status_filter=status_filter,
            search=search,
        )
        total = await self._repository.count_admin(
            status_filter=status_filter,
            search=search,
        )
        return rows, total

    async def get_admin_post_by_id(self, *, blog_post_id: int) -> BlogPost | None:
        return await self._repository.get_by_id(blog_post_id)

    async def create_post(
        self,
        *,
        request: BlogCreateRequest,
        current_user_id: int | None,
    ) -> BlogPost:
        author_id = current_user_id
        if author_id is not None and not await self._repository.author_exists(author_id=author_id):
            author_id = None

        slug = await self._resolve_slug(
            requested_slug=request.slug,
            title=request.title,
            exclude_post_id=None,
        )
        published_at = self._resolve_create_published_at(
            status=request.status,
            published_at=None,
        )

        try:
            created = await self._repository.create(
                author_id=author_id,
                slug=slug,
                title=request.title,
                summary=request.summary,
                content_html=request.content_html,
                thumbnail_url=request.thumbnail_url,
                status=request.status,
                published_at=published_at,
            )
            await self._repository.save()
        except IntegrityError:
            await self._repository.rollback()
            raise AppException(
                code="blog_slug_conflict",
                message="Slug đã tồn tại, vui lòng chọn slug khác.",
                status_code=409,
            ) from None

        persisted = await self._repository.get_by_id(created.id, include_deleted=True)
        if persisted is None:
            raise AppException(
                code="blog_post_not_found",
                message="Blog not found.",
                status_code=404,
            )
        return persisted

    async def update_post(
        self,
        *,
        blog_post_id: int,
        request: BlogUpdateRequest,
    ) -> BlogPost | None:
        post = await self._repository.get_by_id(blog_post_id)
        if post is None:
            return None

        slug = await self._resolve_slug(
            requested_slug=request.slug,
            title=request.title,
            exclude_post_id=post.id,
        )

        was_published = post.status == BLOG_STATUS_PUBLISHED
        will_be_published = request.status == BLOG_STATUS_PUBLISHED

        post.title = request.title
        post.slug = slug
        post.excerpt = request.summary
        post.content = request.content_html
        post.thumbnail_url = request.thumbnail_url
        post.status = request.status
        post.is_published = will_be_published

        if not was_published and will_be_published and post.published_at is None:
            post.published_at = utc_now()
        elif post.published_at is not None and post.published_at.tzinfo is None:
            post.published_at = post.published_at.replace(tzinfo=timezone.utc)

        post.updated_at = utc_now()

        try:
            await self._repository.save()
        except IntegrityError:
            await self._repository.rollback()
            raise AppException(
                code="blog_slug_conflict",
                message="Slug đã tồn tại ở bài viết khác.",
                status_code=409,
            ) from None

        return post

    async def delete_post(self, *, blog_post_id: int) -> bool:
        post = await self._repository.get_by_id(blog_post_id)
        if post is None:
            return False

        await self._repository.soft_delete(post)
        post.updated_at = utc_now()
        await self._repository.save()
        return True

    async def upload_thumbnail(
        self,
        *,
        blog_post_id: int,
        file_bytes: bytes,
        filename: str | None,
        cloudinary_service: CloudinaryService,
    ) -> BlogPost | None:
        post = await self._repository.get_by_id(blog_post_id)
        if post is None:
            return None

        secure_url = await cloudinary_service.upload_image(file_bytes=file_bytes, filename=filename)
        post.thumbnail_url = secure_url
        post.updated_at = utc_now()
        await self._repository.save()
        return post

    async def upload_standalone(
        self,
        *,
        file_bytes: bytes,
        filename: str | None,
        cloudinary_service: CloudinaryService,
    ) -> str:
        return await cloudinary_service.upload_image(file_bytes=file_bytes, filename=filename)

    async def _resolve_slug(
        self,
        *,
        requested_slug: str | None,
        title: str,
        exclude_post_id: int | None,
    ) -> str:
        if requested_slug:
            normalized_requested = slugify(requested_slug)
            if await self._repository.slug_exists(
                slug=normalized_requested,
                exclude_post_id=exclude_post_id,
            ):
                raise AppException(
                    code="blog_slug_conflict",
                    message="Slug đã tồn tại ở bài viết khác." if exclude_post_id else "Slug đã tồn tại, vui lòng chọn slug khác.",
                    status_code=409,
                )
            return normalized_requested

        base_slug = slugify(title)
        for sequence in range(1, 101):
            candidate = build_slug_candidate(base_slug, sequence)
            if not await self._repository.slug_exists(
                slug=candidate,
                exclude_post_id=exclude_post_id,
            ):
                return candidate

        raise AppException(
            code="slug_generation_failed",
            message="Unable to generate a unique slug.",
            status_code=500,
        )

    @staticmethod
    def _resolve_create_published_at(*, status: int, published_at: datetime | None) -> datetime | None:
        if status != BLOG_STATUS_PUBLISHED:
            return None

        if published_at is None:
            return utc_now()

        if published_at.tzinfo is None:
            return published_at.replace(tzinfo=timezone.utc)

        return published_at.astimezone(timezone.utc)
