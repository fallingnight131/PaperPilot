from ..tools.base_tool import BaseTool


class ToolRegistry:
    """工具插件注册表（全局单例）"""

    def __init__(self):
        self._tools: dict = {}

    def register(self, tool: BaseTool):
        """注册工具"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """获取指定名称的工具"""
        return self._tools.get(name)

    def list_tools(self) -> list:
        """列出所有已注册工具的元信息"""
        return [t.get_schema() for t in self._tools.values()]

    def run_tool(self, name: str, input_data: dict) -> dict:
        """执行指定工具"""
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        return tool.run(input_data)


# 全局单例
tool_registry = ToolRegistry()
