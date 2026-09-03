import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info(
    "post_published media_id=%s topic_slug=%s hook_line=%s "
    "published_at=%s media_type=%s",
    "test-media-123",
    "test-topic",
    "test hook",
    "2026-09-03T00:00:00",
    "REELS",
)
