from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración global de Pocket Option Analyzer.

    Todos los valores pueden sobrescribirse mediante variables
    de entorno o un archivo .env.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    app_name: str = "Pocket Option Analyzer"

    app_version: str = "0.1.0-dev"

    debug: bool = False

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------

    target_fps: int = Field(
        default=10,
        ge=1,
        le=120,
    )

    capture_interval_ms: int = Field(
        default=100,
        ge=10,
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    log_level: str = "INFO"

    log_directory: str = "logs"

    log_max_bytes: int = Field(
        default=2 * 1024 * 1024,
        ge=1024,
    )

    log_backup_count: int = Field(
        default=5,
        ge=0,
        le=100,
    )

    log_compression: str | None = "zip"

    visual_evidence_directory: Path | None = None

    visual_identity_evidence_enabled: bool = False

    visual_identity_evidence_ring_buffer_size: int = Field(
        default=30,
        ge=1,
        le=3600,
    )

    visual_identity_evidence_pre_event_trace_count: int = Field(
        default=5,
        ge=0,
        le=3600,
    )

    visual_identity_evidence_intensive_png: bool = False

    visual_identity_evidence_checkpoint_interval_frames: int | None = Field(
        default=None,
        ge=1,
    )

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    monitor_index: int = Field(
        default=1,
        ge=1,
    )

    window_title: str = "Pocket Option"

    # ------------------------------------------------------------------
    # Vision
    # ------------------------------------------------------------------

    max_candle_history: int = Field(
        default=1000,
        ge=100,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Devuelve una única instancia de Settings.

    Utiliza caché para evitar recrear el objeto durante
    toda la vida de la aplicación.
    """

    return Settings()
