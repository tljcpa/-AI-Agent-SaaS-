"""文件接口：上传与列表，按 user_id 实现沙箱隔离。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile

from app.adapters.protocols import StorageProvider
from app.core.container import AppContainer
from app.core.security import try_get_subject
from app.models.database import UserFile, session_scope

router = APIRouter(prefix="/files", tags=["files"])
logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"}
MAGIC_BYTES: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [b"PK\x03\x04"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [b"PK\x03\x04"],
    "application/msword": [b"\xd0\xcf\x11\xe0"],
    "application/vnd.ms-excel": [b"\xd0\xcf\x11\xe0"],
    "text/plain": [],
}


def get_current_user_id(authorization: str = Header(default="")) -> int:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Bearer Token")
    token = authorization.replace("Bearer ", "", 1).strip()
    subject = try_get_subject(token)
    if not subject or not subject.isdigit():
        logger.warning("File API auth failed")
        raise HTTPException(status_code=401, detail="无效 Token")
    return int(subject)


def get_storage(request: Request) -> StorageProvider:
    container: AppContainer = request.app.state.container
    return container.storage


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    storage: StorageProvider = Depends(get_storage),
):
    filename = file.filename or ""
    filename_bytes_len = len(filename.encode("utf-8"))
    if filename_bytes_len < 1 or filename_bytes_len > 255:
        raise HTTPException(status_code=400, detail="文件名长度必须在 1 到 255 字节之间")
    if "\x00" in filename:
        raise HTTPException(status_code=400, detail="文件名不能包含空字节")
    if filename.startswith("."):
        raise HTTPException(status_code=400, detail="文件名不能以 . 开头")
    if re.fullmatch(r"^[a-zA-Z0-9_\-\.]+$", filename) is None:
        raise HTTPException(status_code=400, detail="文件名只能包含英文字母、数字、下划线、短横线和点")
    # 安全加固：显式拦截路径占位名称，避免下游存储适配器误解析。
    if filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="非法文件名")

    file_ext = Path(filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的文件扩展名")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"文件过大，最大支持 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")

    declared_type = file.content_type or ""
    magic_list = MAGIC_BYTES.get(declared_type)
    if magic_list is None:
        raise HTTPException(status_code=400, detail="不支持的文件类型")
    if declared_type == "text/plain":
        try:
            content.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文件内容与声明类型不符")
    elif magic_list and not any(content.startswith(magic) for magic in magic_list):
        raise HTTPException(status_code=400, detail="文件内容与声明类型不符")

    try:
        relative_path = await storage.save_file(user_id, filename, content)
    except (RuntimeError, ValueError) as e:
        logger.error("Storage save failed", exc_info=e)
        raise HTTPException(status_code=503, detail="存储服务暂时不可用，请稍后重试")
    with session_scope() as db:
        db_file = UserFile(user_id=user_id, filename=filename, path=relative_path)
        db.add(db_file)
    logger.info("File uploaded", extra={"user_id": user_id, "filename": filename})
    return {"filename": filename, "path": relative_path}


@router.get("")
async def list_files(
    user_id: int = Depends(get_current_user_id),
    storage: StorageProvider = Depends(get_storage),
):
    try:
        items = await storage.list_files(user_id)
    except (RuntimeError, ValueError) as e:
        logger.error("Storage list failed", exc_info=e)
        raise HTTPException(status_code=503, detail="存储服务暂时不可用，请稍后重试")
    return {"items": items}
