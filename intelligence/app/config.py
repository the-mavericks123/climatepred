"""
Configuration settings for the Climate Eye View S2 Intelligence Service.
Uses pydantic-settings to validate environment variables cleanly.
"""

from typing import List, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Service Network Settings
    host: str = Field(default="127.0.0.1", description="Service bind host")
    port: int = Field(default=8000, description="Service bind port")
    environment: str = Field(default="development", description="Runtime environment (development, staging, production)")
    log_level: str = Field(default="INFO", description="Logging verbosity level")
    json_logging: bool = Field(default=False, description="Format logs as single-line JSON")
    api_prefix: str = Field(default="/api/v1", description="Prefix for API routes")

    # Security & RBAC
    secret_key: str = Field(
        default="development-insecure-secret-key-32-chars-min",
        description="Secret key for service signature/session verification",
    )
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:4173", "http://127.0.0.1:4173", "http://localhost:5173"],
        description="Allowed CORS origins for S1 GEV frontend",
    )
    api_auth_enabled: bool = Field(default=False, description="Enable API key / token authentication on protected endpoints")
    admin_api_key: Optional[str] = Field(default=None, description="Pre-shared administrative API key")
    operator_api_key: Optional[str] = Field(default=None, description="Pre-shared operator API key")

    # Resource Protection & Rate Limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting on compute-heavy routes")
    rate_limit_requests_per_minute: int = Field(default=60, description="Permitted requests per minute per client")
    rate_limit_burst: int = Field(default=10, description="Burst bucket capacity")
    max_request_body_bytes: int = Field(default=10_485_760, description="Max request payload size in bytes (10MB default)")

    # Timeouts & Circuit Breakers
    external_service_timeout_sec: float = Field(default=5.0, description="External request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry count for idempotent calls")
    retry_backoff_factor: float = Field(default=1.5, description="Exponential backoff multiplier")
    circuit_breaker_failure_threshold: int = Field(default=5, description="Consecutive errors to trip circuit breaker")
    circuit_breaker_recovery_timeout_sec: float = Field(default=30.0, description="Recovery cooldown before retry")

    # Data Processing & Freshness Thresholds
    data_freshness_threshold_sec: int = Field(
        default=300,
        description="Seconds after which incoming telemetry is marked STALE (default 5 minutes)",
    )
    model_config_dir: str = Field(
        default="intelligence/models",
        description="Filesystem path to model configurations and metadata",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforces fail-fast production security constraints."""
        if self.environment.lower() == "production":
            sec = self.secret_key.lower()
            if len(self.secret_key) < 32:
                raise ValueError("Production secret_key must be at least 32 characters long.")
            if "insecure" in sec or "development" in sec or "change-me" in sec or "dev-secret" in sec:
                raise ValueError("Insecure default secret_key cannot be used in production environment.")
            if any("*" in origin for origin in self.allowed_origins):
                raise ValueError("Wildcard origins '*' are strictly prohibited in production environment.")
            if "api_auth_enabled" in self.model_fields_set and not self.api_auth_enabled:
                raise ValueError("api_auth_enabled cannot be explicitly set to False in production environment.")
            if self.admin_api_key and len(self.admin_api_key) < 16:
                raise ValueError("admin_api_key must be configured with at least 16 characters in production environment.")
        return self

    # Feature Flags
    enable_detailed_provenance: bool = Field(
        default=True,
        description="Compute and attach cryptographic provenance hashes to telemetry",
    )
    enable_ingestion_validation: bool = Field(
        default=True,
        description="Strictly validate incoming telemetry against physical range gates",
    )
    enable_simulation_stubs: bool = Field(
        default=False,
        description="Enable simulation stubs for offline testing",
    )

    # Evacuation & Routing Parameters (Phase 6)
    evacuation_human_impact_threshold: float = Field(
        default=0.50,
        description="Minimum Phase 5 human impact required to qualify a zone for evacuation",
    )
    evacuation_hazard_risk_threshold: float = Field(
        default=0.70,
        description="Minimum hazard severity triggering mandatory evacuation need",
    )
    shelter_safety_threshold: float = Field(
        default=0.60,
        description="Maximum local hazard severity allowed for an emergency shelter to be considered safe",
    )
    max_route_hazard_limit: float = Field(
        default=0.95,
        description="Maximum road segment hazard severity beyond which an edge is considered impassable",
    )
    edge_accessibility_threshold: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Minimum road edge accessibility score required for routing traversal eligibility; edges below this threshold are impassable",
    )

    # Simulation & Digital Twin Parameters (Phase 7 / 8)
    enable_scenario_simulation: bool = Field(
        default=True,
        description="Enable deterministic scenario simulation engine",
    )
    simulation_max_telemetry_history: int = Field(
        default=24,
        description="Maximum historical telemetry records to retain for simulation",
    )
    simulation_cache_size: int = Field(
        default=100,
        description="Number of recent simulation results retained in memory",
    )

    # Response Planner Parameters (Phase 9)
    enable_response_planner: bool = Field(
        default=True,
        description="Enable Phase 9 AI Response Planner engine",
    )
    response_rule_version: str = Field(
        default="response-rules-v1",
        description="Version string for deterministic response rule set",
    )
    response_model_version: str = Field(
        default="response-v1",
        description="Version string for AI Response Planner architecture",
    )
    response_priority_formula_version: str = Field(
        default="priority-v1",
        description="Version string for priority scoring algorithm",
    )
    response_confidence_formula_version: str = Field(
        default="confidence-v1",
        description="Version string for confidence aggregation model",
    )
    response_freshness_threshold_sec: int = Field(
        default=300,
        description="Seconds after which incoming evidence is penalized for staleness",
    )
    response_stale_confidence_penalty: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Multiplicative confidence penalty applied when telemetry is stale",
    )
    response_missing_evidence_penalty: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Confidence penalty applied when critical upstream evidence is missing",
    )
    # Alert Level Thresholds
    alert_level_green_max_hazard: float = Field(
        default=0.40,
        description="Upper hazard threshold for GREEN alert level",
    )
    alert_level_yellow_max_hazard: float = Field(
        default=0.70,
        description="Upper hazard threshold for YELLOW alert level",
    )
    alert_level_orange_hazard_threshold: float = Field(
        default=0.70,
        description="Minimum hazard severity contributing to ORANGE alert level",
    )
    alert_level_orange_impact_threshold: float = Field(
        default=0.50,
        description="Minimum human impact contributing to ORANGE alert level",
    )
    alert_level_red_hazard_threshold: float = Field(
        default=0.85,
        description="Minimum hazard severity triggering RED alert level",
    )
    alert_level_red_impact_threshold: float = Field(
        default=0.70,
        description="Minimum human impact contributing to RED alert level",
    )

    # Phase 10: Explainability, Evaluation & Calibration Parameters
    calibration_min_samples: int = Field(
        default=50,
        ge=10,
        description="Minimum sample size required to perform probability calibration",
    )
    drift_psi_threshold: float = Field(
        default=0.20,
        ge=0.0,
        description="PSI threshold indicating significant distribution drift",
    )
    drift_ks_alpha_threshold: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="KS test significance level alpha",
    )
    regression_f1_tolerance: float = Field(
        default=0.05,
        ge=0.0,
        description="Maximum allowable F1 score degradation before regression is flagged",
    )
    regression_mae_tolerance: float = Field(
        default=0.05,
        ge=0.0,
        description="Maximum allowable MAE increase before regression is flagged",
    )

    # Optional External Service URLs
    database_url: str | None = Field(default=None, description="Optional PostGIS/TimescaleDB connection string")
    mqtt_broker_url: str | None = Field(default=None, description="Optional MQTT broker address for ingestion bridge")

    # MQTT Ingestion Bridge Configuration (Phase 11 Remediation)
    mqtt_broker_host: str = Field(default="localhost", description="MQTT broker hostname or IP")
    mqtt_broker_port: int = Field(default=1883, description="MQTT broker TCP port")
    mqtt_username: Optional[str] = Field(default=None, description="MQTT authentication username")
    mqtt_password: Optional[str] = Field(default=None, description="MQTT authentication password")
    mqtt_client_id: str = Field(default="climate-eye-backend", description="MQTT client ID")
    mqtt_tls_enabled: bool = Field(default=False, description="Enable TLS/SSL for MQTT broker connection")
    mqtt_topic_telemetry: str = Field(default="climate/nodes/+/telemetry", description="MQTT topic pattern for telemetry")
    mqtt_keepalive: int = Field(default=60, description="MQTT keepalive interval in seconds")
    mqtt_reconnect_min_delay_sec: float = Field(default=1.0, description="Minimum reconnect backoff delay in seconds")
    mqtt_reconnect_max_delay_sec: float = Field(default=30.0, description="Maximum reconnect backoff delay in seconds")

    # Database & PostGIS Persistence Configuration (Phase 11 Remediation)
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_db: str = Field(default="climate_eye", description="PostgreSQL database name")
    postgres_user: str = Field(default="climate_user", description="PostgreSQL username")
    postgres_password: str = Field(default="climate_secure_pass_2026", description="PostgreSQL password")


settings = Settings()

