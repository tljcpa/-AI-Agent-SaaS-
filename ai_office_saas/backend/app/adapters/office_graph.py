"""Office Graph 适配器：操作 OneDrive 中的 Word/Excel。"""
from __future__ import annotations

from io import BytesIO

import httpx
from docx import Document

from app.adapters.ms_auth import MSAuthService


class GraphOfficeProvider:
    def __init__(self, auth_service: MSAuthService) -> None:
        self.auth_service = auth_service

    def _headers(self, user_id: int) -> dict[str, str]:
        token = self.auth_service.get_valid_access_token(user_id)
        return {"Authorization": f"Bearer {token}"}

    def read_word_content(self, user_id: int, file_id: str) -> str:
        url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
        with httpx.Client(timeout=60) as client:
            resp = client.get(url, headers=self._headers(user_id))
            resp.raise_for_status()
        doc = Document(BytesIO(resp.content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    def format_word_document(self, user_id: int, file_id: str, style_instructions: str) -> str:
        url = f"https://graph.microsoft.com/v1.0/me/drive/items/{file_id}/content"
        with httpx.Client(timeout=60) as client:
            download = client.get(url, headers=self._headers(user_id))
            download.raise_for_status()

            doc = Document(BytesIO(download.content))
            for para in doc.paragraphs:
                if para.text.strip().startswith("#"):
                    para.style = "Heading 1"
                elif "标题" in style_instructions:
                    para.style = "Heading 2" if len(para.text) < 24 else para.style
                for run in para.runs:
                    if "字体" in style_instructions:
                        run.font.name = "Calibri"

            out = BytesIO()
            doc.save(out)
            out.seek(0)

            upload = client.put(url, headers=self._headers(user_id), content=out.read())
            upload.raise_for_status()
        return f"Word 文档 {file_id} 已完成样式更新"

    def read_excel_data(self, user_id: int, file_id: str, sheet_name: str) -> str:
        url = (
            "https://graph.microsoft.com/v1.0/me/drive/items/"
            f"{file_id}/workbook/worksheets/{sheet_name}/usedRange"
        )
        with httpx.Client(timeout=60) as client:
            resp = client.get(url, headers=self._headers(user_id))
            resp.raise_for_status()
            data = resp.json()
        values = data.get("values", [])
        return "\n".join([", ".join(map(str, row)) for row in values])

    def write_excel_data(self, user_id: int, file_id: str, sheet_name: str, data: list[list]) -> str:
        range_url = (
            "https://graph.microsoft.com/v1.0/me/drive/items/"
            f"{file_id}/workbook/worksheets/{sheet_name}/range(address='A1')"
        )
        chart_url = (
            "https://graph.microsoft.com/v1.0/me/drive/items/"
            f"{file_id}/workbook/worksheets/{sheet_name}/charts/add"
        )
        with httpx.Client(timeout=60) as client:
            range_resp = client.patch(range_url, headers=self._headers(user_id), json={"values": data})
            range_resp.raise_for_status()
            chart_resp = client.post(
                chart_url,
                headers=self._headers(user_id),
                json={
                    "type": "ColumnClustered",
                    "sourceData": f"{sheet_name}!A1:C{max(2, len(data))}",
                    "seriesBy": "Auto",
                },
            )
            if chart_resp.status_code >= 400 and chart_resp.status_code != 409:
                chart_resp.raise_for_status()
        return f"Excel {sheet_name} 写入 {len(data)} 行并尝试更新图表"

    async def format_document(self, user_id: int, file_path: str, style: str) -> str:
        return self.format_word_document(user_id, file_path, style)

    async def analyze_report(self, user_id: int, file_path: str) -> str:
        sheet = "Sheet1"
        data = self.read_excel_data(user_id, file_path, sheet)
        return f"报表读取成功（{sheet}）：\n{data[:1000]}"

    async def export_pdf(self, user_id: int, file_id: str) -> str:
        return f"PDF 导出暂未接入（mock）：{file_id}"
