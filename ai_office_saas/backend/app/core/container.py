"""依赖注入容器：统一装配底层 Provider，避免在 Router 上挂动态属性。"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.adapters.llm_openai_compat import OpenAICompatLLMProvider
from app.adapters.llm_zhipu import ZhipuLLMProvider
from app.adapters.ms_auth import MSAuthService
from app.adapters.office_e5 import E5OfficeProvider
from app.adapters.office_graph import GraphOfficeProvider
from app.adapters.protocols import LLMProvider, OfficeAPIProvider, StorageProvider, ToolSchema
from app.adapters.storage_local import LocalStorageProvider
from app.adapters.storage_onedrive import OneDriveStorageProvider
from app.agent.engine import AgentEngine
from app.agent.tool_registry import ToolRegistry
from app.core.config import Settings


@dataclass
class AppContainer:
    storage: StorageProvider
    llm: LLMProvider
    office: OfficeAPIProvider
    auth_service: MSAuthService
    agent_engine: AgentEngine
    tool_registry: ToolRegistry


class ProviderFactory:
    @staticmethod
    def create_storage(settings: Settings, auth_service: MSAuthService) -> StorageProvider:
        if settings.storage.type == "local":
            return LocalStorageProvider(base_path=settings.storage.base_path)
        if settings.storage.type == "onedrive":
            return OneDriveStorageProvider(auth_service=auth_service, http_client=auth_service.http_client, root_path=settings.storage.onedrive_root)
        raise ValueError(f"不支持的 storage provider: {settings.storage.type}")

    @staticmethod
    def create_llm(settings: Settings) -> LLMProvider:
        if settings.llm.provider == "zhipu_mock":
            return ZhipuLLMProvider(api_key=settings.llm.api_key)
        if settings.llm.provider == "openai_compat":
            return OpenAICompatLLMProvider(
                base_url=settings.llm.base_url,
                api_key=settings.llm.api_key,
                model=settings.llm.model,
            )
        raise ValueError(f"不支持的 llm provider: {settings.llm.provider}")

    @staticmethod
    def create_office(settings: Settings, auth_service: MSAuthService) -> OfficeAPIProvider:
        if settings.office.provider == "e5_mock":
            return E5OfficeProvider()
        if settings.office.provider == "graph":
            return GraphOfficeProvider(auth_service=auth_service, http_client=auth_service.http_client)
        raise ValueError(f"不支持的 office provider: {settings.office.provider}")


def build_container(settings: Settings, http_client: httpx.AsyncClient) -> AppContainer:
    auth_service = MSAuthService(settings.ms_graph, http_client=http_client)
    storage = ProviderFactory.create_storage(settings, auth_service)
    llm = ProviderFactory.create_llm(settings)
    office = ProviderFactory.create_office(settings, auth_service)
    tool_registry = ToolRegistry()

    tool_registry.register(
        ToolSchema(
            name="read_word_content",
            description="读取 Word 文本内容",
            parameters={"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]},
        ),
        lambda *, user_id, file_id: office.read_word_content(user_id, file_id),
    )
    tool_registry.register(
        ToolSchema(
            name="read_excel_data",
            description="读取 Excel sheet 数据",
            parameters={
                "type": "object",
                "properties": {"file_id": {"type": "string"}, "sheet_name": {"type": "string"}},
                "required": ["file_id", "sheet_name"],
            },
        ),
        lambda *, user_id, file_id, sheet_name: office.read_excel_data(user_id, file_id, sheet_name),
    )
    tool_registry.register(
        ToolSchema(
            name="format_word_document",
            description="按指令格式化 Word 文档",
            parameters={
                "type": "object",
                "properties": {"file_id": {"type": "string"}, "style_instructions": {"type": "string"}},
                "required": ["file_id", "style_instructions"],
            },
        ),
        lambda *, user_id, file_id, style_instructions: office.format_word_document(user_id, file_id, style_instructions),
    )
    tool_registry.register(
        ToolSchema(
            name="write_excel_data",
            description="写入 Excel 数据",
            parameters={
                "type": "object",
                "properties": {
                    "file_id": {"type": "string"},
                    "sheet_name": {"type": "string"},
                    "data": {"type": "array"},
                },
                "required": ["file_id", "sheet_name", "data"],
            },
        ),
        lambda *, user_id, file_id, sheet_name, data: office.write_excel_data(user_id, file_id, sheet_name, data),
    )

    engine = AgentEngine(llm=llm, storage=storage, office=office, tool_registry=tool_registry)
    return AppContainer(
        storage=storage,
        llm=llm,
        office=office,
        auth_service=auth_service,
        agent_engine=engine,
        tool_registry=tool_registry,
    )
