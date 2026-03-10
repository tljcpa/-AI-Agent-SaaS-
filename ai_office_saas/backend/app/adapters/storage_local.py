"""本地文件存储实现：严格限制在 user 沙箱目录中。"""
from __future__ import annotations

from pathlib import Path


class LocalStorageProvider:
    """本地磁盘存储实现。"""

    def __init__(self, base_path: str) -> None:
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _user_root(self, user_id: int) -> Path:
        """获取用户根目录，并确保目录存在。"""

        user_root = self.base_path / f"user_{user_id}"
        user_root.mkdir(parents=True, exist_ok=True)
        return user_root

    def _assert_in_sandbox(self, user_root: Path, target: Path) -> None:
        """确保目标路径在用户沙箱内，防止目录穿越攻击。"""

        resolved_target = target.resolve()
        if user_root.resolve() not in resolved_target.parents and resolved_target != user_root.resolve():
            raise ValueError("非法路径：超出用户沙箱范围")

    def save_file(self, user_id: int, filename: str, content: bytes) -> str:
        """保存文件并返回相对路径。"""

        safe_name = Path(filename).name
        user_root = self._user_root(user_id)
        target = user_root / safe_name
        self._assert_in_sandbox(user_root, target)
        target.write_bytes(content)
        return safe_name

    def list_files(self, user_id: int) -> list[str]:
        """列出用户沙箱内文件。"""

        user_root = self._user_root(user_id)
        return [item.name for item in user_root.iterdir() if item.is_file()]

    def read_text(self, user_id: int, relative_path: str) -> str:
        """读取用户沙箱内文本文件。"""

        user_root = self._user_root(user_id)
        target = user_root / relative_path
        self._assert_in_sandbox(user_root, target)
        return target.read_text(encoding="utf-8")
