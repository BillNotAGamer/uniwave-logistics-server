from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_content_editor
from app.core.exceptions import AppException
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.blog_repository import BlogRepository
from app.schemas.blog import (
    BlogAdminDetailRead,
    BlogAdminListItemRead,
    BlogCreateRequest,
    BlogUpdateRequest,
    BlogUploadResponse,
    normalize_blog_status,
)
from app.services.blog_service import BlogService
from app.services.cloudinary import CloudinaryService, get_cloudinary_service

router = APIRouter(prefix="/api/admin/blogs", tags=["BlogsAdmin"])

MAX_THUMBNAIL_FILE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


def get_blog_service(
    session: AsyncSession = Depends(get_db_session),
) -> BlogService:
    return BlogService(
        session=session,
        repository=BlogRepository(session),
    )


@router.get(
    "",
    response_model=list[BlogAdminListItemRead],
    status_code=status.HTTP_200_OK,
)
async def list_blog_posts_admin(
    response: Response,
    status_filter: int | str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    page: int = Query(default=1),
    pageSize: int = Query(default=10),
    _: User = Depends(require_content_editor),
    service: BlogService = Depends(get_blog_service),
) -> list[BlogAdminListItemRead]:
    normalized_status: int | None = None
    if status_filter is not None:
        try:
            normalized_status = normalize_blog_status(status_filter)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Invalid blog status."},
            )

    rows, total = await service.list_admin_posts(
        page=page,
        page_size=pageSize,
        status_filter=normalized_status,
        search=search,
    )

    response.headers["X-Total-Count"] = str(total)
    return [BlogAdminListItemRead.from_model(row) for row in rows]


@router.get(
    "/{id}",
    response_model=BlogAdminDetailRead,
    status_code=status.HTTP_200_OK,
)
async def get_blog_post_admin(
    id: int,
    _: User = Depends(require_content_editor),
    service: BlogService = Depends(get_blog_service),
) -> BlogAdminDetailRead | JSONResponse:
    post = await service.get_admin_post_by_id(blog_post_id=id)
    if post is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Blog not found."})
    return BlogAdminDetailRead.from_model(post)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create_blog_post_admin(
    request: BlogCreateRequest,
    current_editor: User = Depends(require_content_editor),
    service: BlogService = Depends(get_blog_service),
) -> JSONResponse:
    try:
        post = await service.create_post(
            request=request,
            current_user_id=current_editor.id,
        )
    except AppException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            return JSONResponse(status_code=exc.status_code, content={"message": exc.message})
        raise

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"id": post.id},
        headers={"Location": f"/api/admin/blogs/{post.id}"},
    )


@router.put(
    "/{id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_blog_post_admin(
    id: int,
    request: BlogUpdateRequest,
    _: User = Depends(require_content_editor),
    service: BlogService = Depends(get_blog_service),
) -> Response | JSONResponse:
    try:
        post = await service.update_post(
            blog_post_id=id,
            request=request,
        )
    except AppException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            return JSONResponse(status_code=exc.status_code, content={"message": exc.message})
        raise

    if post is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Blog not found."})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_blog_post_admin(
    id: int,
    _: User = Depends(require_content_editor),
    service: BlogService = Depends(get_blog_service),
) -> Response | JSONResponse:
    deleted = await service.delete_post(blog_post_id=id)
    if not deleted:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Blog not found."})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/upload",
    response_model=BlogUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_blog_thumbnail(
    file: UploadFile = File(...),
    _: User = Depends(require_content_editor),
    service: BlogService = Depends(get_blog_service),
    cloudinary_service: CloudinaryService = Depends(get_cloudinary_service),
) -> BlogUploadResponse | JSONResponse:
    if file is None:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "No file uploaded."})

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES and not content_type.startswith("image/"):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "Only image files are allowed."})

    file_bytes = await file.read()
    await file.close()

    if not file_bytes:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "No file uploaded."})

    if len(file_bytes) > MAX_THUMBNAIL_FILE_SIZE_BYTES:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Uploaded image exceeds the 5MB size limit."},
        )

    secure_url = await service.upload_standalone(
        file_bytes=file_bytes,
        filename=file.filename,
        cloudinary_service=cloudinary_service,
    )
    return BlogUploadResponse(url=secure_url, path=secure_url)


@router.post(
    "/{blog_post_id}/thumbnail",
    response_model=BlogAdminDetailRead,
    status_code=status.HTTP_200_OK,
)
async def upload_blog_thumbnail_admin(
    blog_post_id: int,
    file: UploadFile = File(...),
    _: User = Depends(require_content_editor),
    service: BlogService = Depends(get_blog_service),
    cloudinary_service: CloudinaryService = Depends(get_cloudinary_service),
) -> BlogAdminDetailRead | JSONResponse:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Only image files are allowed."},
        )

    file_bytes = await file.read()
    await file.close()

    if not file_bytes:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "No file uploaded."},
        )

    if len(file_bytes) > MAX_THUMBNAIL_FILE_SIZE_BYTES:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Uploaded image exceeds the 5MB size limit."},
        )

    post = await service.upload_thumbnail(
        blog_post_id=blog_post_id,
        file_bytes=file_bytes,
        filename=file.filename,
        cloudinary_service=cloudinary_service,
    )
    if post is None:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Blog not found."})
    return BlogAdminDetailRead.from_model(post)
