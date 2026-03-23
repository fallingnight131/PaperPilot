from abc import ABC, abstractmethod


class BaseTool(ABC):
    """工具基类"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, input_data: dict) -> dict:
        """执行工具逻辑"""
        raise NotImplementedError

    def get_schema(self) -> dict:
        """获取工具元信息"""
        return {"name": self.name, "description": self.description}
