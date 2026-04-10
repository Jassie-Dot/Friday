from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FRIDAY"
    host: str = "127.0.0.1"
    port: int = 8000
    workspace_root: Path = Field(default_factory=Path.cwd)
    data_root: Path = Field(default_factory=lambda: Path.cwd() / ".friday")
    log_level: str = "INFO"

    ollama_base_url: str = "http://127.0.0.1:11434"
    primary_model: str = "deepseek-r1:8b"
    fast_model: str = "mistral:7b"
    model_temperature: float = 0.2

    embedding_backend: str = "hash"
    embedding_model_path: str | None = None
    chroma_collection: str = "friday_memory"

    browser_headless: bool = True
    browser_timeout_ms: int = 20_000

    allow_shell: bool = True
    allow_python: bool = True
    allow_app_launch: bool = False
    allow_destructive_shell: bool = False
    max_shell_timeout_seconds: int = 120

    ddg_max_results: int = 5
    comfyui_url: str = "http://127.0.0.1:8188"
    stable_diffusion_model_path: str | None = None
    whisper_model_size: str = "base"
    piper_model_path: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FRIDAY_",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def logs_dir(self) -> Path:
        return self.data_root / "logs"

    @property
    def cache_dir(self) -> Path:
        return self.data_root / "cache"

    @property
    def memory_dir(self) -> Path:
        return self.data_root / "memory"

    @property
    def chroma_dir(self) -> Path:
        return self.memory_dir / "chroma"

    @property
    def generated_dir(self) -> Path:
        return self.data_root / "generated"

    def ensure_directories(self) -> None:
        for path in [
            self.workspace_root,
            self.data_root,
            self.logs_dir,
            self.cache_dir,
            self.memory_dir,
            self.chroma_dir,
            self.generated_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
