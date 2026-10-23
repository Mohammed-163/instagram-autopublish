import logging
from database.repositories import (
    settings_repository,
    engine_health_repository,
    model_versions_repository,
    prompt_versions_repository,
    knowledge_versions_repository
)

logger = logging.getLogger("database.seed")

def run():
    logger.info("Starting database seed...")
    
    # 1. System Settings
    settings = [
        ("min_confidence_threshold", 0.6, "Minimum confidence to trust a knowledge rule"),
        ("auto_publish_enabled", False, "Whether auto-publish is active"),
        ("max_posts_per_day", 3, "Maximum posts to publish per day"),
        ("metrics_retention_days", 365, "How long to keep metrics data"),
        ("learning_enabled", False, "Whether the learning loop is active (Phase 2)"),
        ("audit_retention_days", 180, "How long to keep audit logs"),
        ("notification_channels", ["telegram"], "Active notification channels"),
        ("quality_gates_required", ["length_check", "content_quality", "image_quality"], "Required quality gates"),
        ("experiment_max_concurrent", 3, "Max concurrent experiments"),
        ("memory_cleanup_days", 90, "Days before memory entries expire"),
    ]
    for key, value, desc in settings:
        settings_repository.set(key=key, value=value, description=desc)
        logger.info(f"Upserted setting: {key}")

    # 2. Engine Health
    engines = [
        "observation_engine",
        "feature_scoring",
        "performance_evaluation",
        "knowledge_engine",
        "decision_engine",
        "memory_engine",
        "experiment_engine",
        "weekly_planner",
        "strategy_engine",
        "quality_gate_engine",
        "notification_engine",
    ]
    for engine_name in engines:
        engine_health_repository.report_heartbeat(engine_name, "unknown")
        logger.info(f"Reported heartbeat for engine: {engine_name}")

    # 3. Model Versions
    models = [
        ("google", "gemini-3.6-flash", "content_generation"),
        ("google", "gemini-3.5-flash-lite", "image_vetting"),
    ]
    for provider, model_name, purpose in models:
        existing_models = model_versions_repository.list_all()
        if not any(m.provider == provider and m.model_name == model_name and m.purpose == purpose for m in existing_models):
            model_versions_repository.create(provider=provider, model_name=model_name, purpose=purpose)
            logger.info(f"Created model version: {provider}/{model_name} for {purpose}")
        else:
            logger.info(f"Model version already exists: {provider}/{model_name} for {purpose}")

    # 4. Prompt Versions
    prompts = [
        ("post_generation", "v1.0", "Generate an Instagram post about {topic}..."),
        ("topic_selection", "v1.0", "Select the best topic from {topics}..."),
        ("image_vetting", "v1.0", "Evaluate this image for suitability..."),
    ]
    for name, version, template in prompts:
        existing_prompts = prompt_versions_repository.list_all()
        if not any(p.name == name and p.version == version for p in existing_prompts):
            prompt_versions_repository.create(name=name, version=version, template=template)
            logger.info(f"Created prompt version: {name}/{version}")
        else:
            logger.info(f"Prompt version already exists: {name}/{version}")

    # 5. Knowledge Version
    existing_knowledge_versions = knowledge_versions_repository.list_all()
    if not any(kv.version_number == 1 for kv in existing_knowledge_versions):
        knowledge_versions_repository.create(version_number=1, summary="Initial knowledge base - no learned rules yet")
        logger.info("Created initial knowledge version")
    else:
        logger.info("Initial knowledge version already exists")

    logger.info("Database seed completed successfully.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
