"""文件接口：上传与列表，按 user_id 实现沙箱隔离。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile

from app.adapters.protocols import StorageProvider
from app.core.container import AppContainer
from app.core.security import try_get_subject
from app.models.database import UserFile, session_scope

router = APIRouter(prefix="/files", tags=["files"])


def get_current_user_id(authorization: str = Header(default="")) -> int:
    """从 Authorization: Bearer <token> 中解析用户 ID。"""

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Bearer Token")
    token = authorization.replace("Bearer ", "", 1).strip()
    subject = try_get_subject(token)
    if not subject or not subject.isdigit():
        raise HTTPException(status_code=401, detail="无效 Token")
    return int(subject)


def get_storage(request: Request) -> StorageProvider:
    """从应用容器中获取存储实现。"""

    container: AppContainer = request.app.state.container
    return container.storage


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    storage: StorageProvider = Depends(get_storage),
):
    content = await file.read()
    relative_path = storage.save_file(user_id, file.filename, content)
    with session_scope() as db:
        db_file = UserFile(user_id=user_id, filename=file.filename, path=relative_path)
        db.add(db_file)
    return {"filename": file.filename, "path": relative_path}


@router.get("")
def list_files(
    user_id: int = Depends(get_current_user_id),
    storage: StorageProvider = Depends(get_storage),
):
    return {"items": storage.list_files(user_id)}
