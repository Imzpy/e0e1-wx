"""摘要：集中生成 MCP 服务地址、启动命令、CLI 添加命令和子进程环境。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

DEFAULT_MCP_HOST = "127.0.0.1"
DEFAULT_MCP_PORT = 49999
DEFAULT_MCP_TOKEN = "eeeeeeeecode-e0e1-wx-gui"
DEFAULT_MCP_PYTHON = "python11"


def default_mcp_project_root() -> Path:
    """返回参考 MCP 项目目录，允许环境变量覆盖。"""
    raw_root = str(os.getenv("MCP_PROJECT_ROOT", "")).strip()
    if raw_root:
        return Path(raw_root).expanduser()
    project_root = Path(__file__).resolve().parents[2]
    return project_root.parent / "mcp"


@dataclass(slots=True)
class McpServerConfig:
    """描述本地 MCP HTTP 服务所需的固定配置。"""

    host: str = DEFAULT_MCP_HOST
    port: int = DEFAULT_MCP_PORT
    token: str = DEFAULT_MCP_TOKEN
    project_root: Path | None = None
    python_executable: str = DEFAULT_MCP_PYTHON

    def resolved_project_root(self) -> Path:
        """返回已经补齐默认值的 MCP 项目目录。"""
        return Path(self.project_root).expanduser() if self.project_root is not None else default_mcp_project_root()

    def endpoint_url(self) -> str:
        """生成带 /mcp 路径和 token 的 Streamable HTTP 地址。"""
        query = urlencode({"token": self.token})
        return f"http://{self.host}:{int(self.port)}/mcp?{query}"

    def http_server_command(self) -> list[str]:
        """生成手动启动参考 MCP HTTP 服务的 python11 命令。"""
        return [self.python_executable, str(self.resolved_project_root() / "main.py"), "--mode", "http"]

    def install_commands(self) -> dict[str, str]:
        """生成 Claude Code 和 Codex CLI 添加 MCP 的命令。"""
        url = self.endpoint_url()
        return {
            "claude": f"claude mcp add wxcdp --tool-mode full --transport http --scope user {url}",
            "codex": f"codex mcp add wxcdp --url {url}",
        }

    def delete_commands(self) -> dict[str, str]:
        """生成 Claude Code 和 Codex CLI 删除 wxcdp MCP 的命令。"""
        return {
            "claude": "claude mcp remove --scope user wxcdp",
            "codex": "codex mcp remove wxcdp",
        }

    def child_environment(self, base_env: dict[str, str] | None = None) -> dict[str, str]:
        """生成 MCP 子进程环境变量，确保 UTF-8 和参考 src 路径可用。"""
        env = dict(os.environ if base_env is None else base_env)
        root = self.resolved_project_root()
        src_path = str(root / "src")
        old_pythonpath = str(env.get("PYTHONPATH", "")).strip()
        env["PYTHONPATH"] = src_path if not old_pythonpath else os.pathsep.join([src_path, old_pythonpath])
        env["PYTHONIOENCODING"] = "utf-8"
        env["MCP_HOST"] = str(self.host)
        env["MCP_PORT"] = str(int(self.port))
        env["MCP_TOKEN"] = str(self.token)
        return env

    def to_payload(self) -> dict[str, str | int]:
        """转成可安全传入 multiprocessing 的普通字典。"""
        return {
            "host": str(self.host),
            "port": int(self.port),
            "token": str(self.token),
            "project_root": str(self.resolved_project_root()),
            "python_executable": str(self.python_executable),
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "McpServerConfig":
        """从 worker 收到的普通字典恢复配置对象。"""
        return cls(
            host=str(payload.get("host") or DEFAULT_MCP_HOST),
            port=int(payload.get("port") or DEFAULT_MCP_PORT),
            token=str(payload.get("token") or DEFAULT_MCP_TOKEN),
            project_root=Path(str(payload.get("project_root") or default_mcp_project_root())),
            python_executable=str(payload.get("python_executable") or DEFAULT_MCP_PYTHON),
        )

    def state_payload(self, *, status: str, message: str, pid: int | None = None, last_error: str = "") -> dict:
        """生成 UI 可直接消费的 MCP 状态快照。"""
        return {
            "status": str(status),
            "message": str(message),
            "running": str(status) == "running",
            "pid": pid,
            "url": self.endpoint_url(),
            "commands": self.install_commands(),
            "delete_commands": self.delete_commands(),
            "project_root": str(self.resolved_project_root()),
            "python_executable": str(self.python_executable),
            "last_error": str(last_error or ""),
        }
