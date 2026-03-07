from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.models.blog_post import BlogPost
from app.schemas.base import APIModel
from app.utils.slug import slugify

BLOG_STATUS_DRAFT = 0
BLOG_STATUS_PUBLISHED = 1
BLOG_STATUS_DELETED = 2

BLOG_STATUS_CODE_TO_NAME: dict[int, str] = {
    BLOG_STATUS_DRAFT: "draft",
    BLOG_STATUS_PUBLISHED: "published",
    BLOG_STATUS_DELETED: "deleted",
}
BLOG_STATUS_NAME_TO_CODE: dict[str, int] = {
    value: key for key, value in BLOG_STATUS_CODE_TO_NAME.items()
}


def normalize_blog_status(value: int | str) -> int:
    if isinstance(value, int):
        if value not in BLOG_STATUS_CODE_TO_NAME:
            raise ValueError("Invalid blog status.")
        return value

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in BLOG_STATUS_NAME_TO_CODE:
        raise ValueError("Invalid blog status.")
    return BLOG_STATUS_NAME_TO_CODE[normalized]


def _normalize_required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")
    return normalized


class BlogCreateRequest(APIModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    content_html: str = Field(alias="contentHtml", min_length=1)
    thumbnail_url: str | None = Field(alias="thumbnailUrl", default=None, max_length=500)
    status: int = BLOG_STATUS_DRAFT

    @field_validator("title", "content_html")
    @classmethod
    def normalize_required_fields(cls, value: str, info) -> str:
        return _normalize_required_text(value, field_name=info.field_name)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        raw = value.strip()
        if not raw:
            return None
        normalized = slugify(raw)
        if normalized == "post" and not any(char.isalnum() for char in raw):
            raise ValueError("Slug must include at least one letter or number.")
        return normalized

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> int:
        if isinstance(value, (int, str)):
            return normalize_blog_status(value)
        raise ValueError("Invalid blog status.")


class BlogUpdateRequest(APIModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    content_html: str = Field(alias="contentHtml", min_length=1)
    thumbnail_url: str | None = Field(alias="thumbnailUrl", default=None, max_length=500)
    status: int

    @field_validator("title", "content_html")
    @classmethod
    def normalize_required_fields(cls, value: str, info) -> str:
        return _normalize_required_text(value, field_name=info.field_name)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return None
        raw = value.strip()
        if not raw:
            return None
        normalized = slugify(raw)
        if normalized == "post" and not any(char.isalnum() for char in raw):
            raise ValueError("Slug must include at least one letter or number.")
        return normalized

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: Any) -> int:
        if isinstance(value, (int, str)):
            return normalize_blog_status(value)
        raise ValueError("Invalid blog status.")


class BlogAdminListItemRead(APIModel):
    id: int
    slug: str
    title: str
    status: int
    created_at: datetime
    updated_at: datetime | None = None
    published_at: datetime | None = None
    author_name: str | None = None

    @classmethod
    def from_model(cls, post: BlogPost) -> "BlogAdminListItemRead":
        author_name: str | None = None
        if post.author is not None:
            author_name = post.author.full_name or post.author.email

        return cls(
            id=post.id,
            slug=post.slug,
            title=post.title,
            status=post.status,
            created_at=post.created_at,
            updated_at=post.updated_at,
            published_at=post.published_at,
            author_name=author_name,
        )


class BlogAdminDetailRead(APIModel):
    id: int
    slug: str
    title: str
    summary: str | None = None
    content_html: str = Field(alias="contentHtml")
    thumbnail_url: str | None = Field(alias="thumbnailUrl", default=None)
    status: int
    created_at: datetime
    updated_at: datetime | None = None
    published_at: datetime | None = None
    author_name: str | None = None

    @classmethod
    def from_model(cls, post: BlogPost) -> "BlogAdminDetailRead":
        author_name: str | None = None
        if post.author is not None:
            author_name = post.author.full_name or post.author.email

        return cls(
            id=post.id,
            slug=post.slug,
            title=post.title,
            summary=post.excerpt,
            content_html=post.content,
            thumbnail_url=post.thumbnail_url,
            status=post.status,
            created_at=post.created_at,
            updated_at=post.updated_at,
            published_at=post.published_at,
            author_name=author_name,
        )


class BlogPublicListItemRead(APIModel):
    id: int
    slug: str
    title: str
    summary: str | None = None
    thumbnail_url: str | None = Field(alias="thumbnailUrl", default=None)
    published_at: datetime | None = None
    author_name: str | None = None

    @classmethod
    def from_model(cls, post: BlogPost) -> "BlogPublicListItemRead":
        author_name: str | None = None
        if post.author is not None:
            author_name = post.author.full_name or post.author.email

        return cls(
            id=post.id,
            slug=post.slug,
            title=post.title,
            summary=post.excerpt,
            thumbnail_url=post.thumbnail_url,
            published_at=post.published_at,
            author_name=author_name,
        )


class BlogPublicDetailRead(APIModel):
    id: int
    slug: str
    title: str
    summary: str | None = None
    content_html: str = Field(alias="contentHtml")
    thumbnail_url: str | None = Field(alias="thumbnailUrl", default=None)
    published_at: datetime | None = None
    author_name: str | None = None

    @classmethod
    def from_model(cls, post: BlogPost) -> "BlogPublicDetailRead":
        author_name: str | None = None
        if post.author is not None:
            author_name = post.author.full_name or post.author.email

        return cls(
            id=post.id,
            slug=post.slug,
            title=post.title,
            summary=post.excerpt,
            content_html=post.content,
            thumbnail_url=post.thumbnail_url,
            published_at=post.published_at,
            author_name=author_name,
        )


class BlogUploadResponse(APIModel):
    url: str
    path: str
