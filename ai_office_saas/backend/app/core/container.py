"""依赖注入容器：统一装配底层 Provider，避免在 Router 上挂动态属性。"""
from __future__ import annotations

from dataclasses import dataclass

from app.adapters.llm_zhipu import ZhipuLLMProvider
from app.adapters.office_e5 import E5OfficeProvider
from app.adapters.protocols import LLMProvider, OfficeAPIProvider, StorageProvider
from app.adapters.storage_local import LocalStorageProvider
from app.core.config import Settings
from app.agent.engine import AgentEngine


@dataclass
class AppContainer:
    """应用容器，集中管理可替换依赖。"""

    storage: StorageProvider
    llm: LLMProvider
    office: OfficeAPIProvider
    agent_engine: AgentEngine


class ProviderFactory:
    """按配置创建 Provider。"""

    @staticmethod
    def create_storage(settings: Settings) -> StorageProvider:
        if settings.storage.type == "local":
            return LocalStorageProvider(base_path=settings.storage.base_path)
        raise ValueError(f"不支持的 storage provider: {settings.storage.type}")

    @staticmethod
    def create_llm(settings: Settings) -> LLMProvider:
        if settings.llm.provider == "zhipu_mock":
            return ZhipuLLMProvider(api_key=settings.llm.api_key)
        raise ValueError(f"不支持的 llm provider: {settings.llm.provider}")

    @staticmethod
    def create_office(settings: Settings) -> OfficeAPIProvider:
        if settings.office.provider == "e5_mock":
            return E5OfficeProvider()
        raise ValueError(f"不支持的 office provider: {settings.office.provider}")


def build_container(settings: Settings) -> AppContainer:
    """构建完整容器。"""

    storage = ProviderFactory.create_storage(settings)
    llm = ProviderFactory.create_llm(settings)
    office = ProviderFactory.create_office(settings)
    engine = AgentEngine(llm=llm, storage=storage, office=office)
    return AppContainer(storage=storage, llm=llm, office=office, agent_engine=engine)
