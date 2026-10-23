import uuid
from typing import Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy import text
from database.client import get_session

def get_best_posts_last_n_days(days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT p.id, p.category, p.status, p.published_at, 
                   m.views, m.reach, m.likes, m.comments, m.saves, m.engagement_rate
            FROM posts p
            LEFT JOIN metrics m ON p.id = m.post_id AND m.snapshot_period = '24h'
            WHERE p.published_at >= NOW() - INTERVAL ':days days'
            ORDER BY m.engagement_rate DESC NULLS LAST
            LIMIT :limit
        """)
        results = session.execute(query, {"days": days, "limit": limit}).mappings().all()
        return [dict(r) for r in results]

def get_weekly_category_stats(weeks: int = 4) -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT p.category, 
                   COUNT(p.id) as post_count,
                   AVG(m.reach) as avg_reach,
                   AVG(m.engagement_rate) as avg_engagement
            FROM posts p
            LEFT JOIN metrics m ON p.id = m.post_id AND m.snapshot_period = '24h'
            WHERE p.published_at >= NOW() - INTERVAL ':weeks weeks'
            GROUP BY p.category
            ORDER BY avg_engagement DESC NULLS LAST
        """)
        results = session.execute(query, {"weeks": weeks}).mappings().all()
        return [dict(r) for r in results]

def get_top_performing_designs(limit: int = 10) -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT d.background_type, d.dominant_color, d.font_family,
                   AVG(m.engagement_rate) as avg_engagement,
                   COUNT(p.id) as usage_count
            FROM designs d
            JOIN posts p ON d.post_id = p.id
            LEFT JOIN metrics m ON p.id = m.post_id AND m.snapshot_period = '24h'
            GROUP BY d.background_type, d.dominant_color, d.font_family
            HAVING COUNT(p.id) > 1
            ORDER BY avg_engagement DESC NULLS LAST
            LIMIT :limit
        """)
        results = session.execute(query, {"limit": limit}).mappings().all()
        return [dict(r) for r in results]

def get_failed_posts_with_details(limit: int = 50) -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT p.id, p.status, p.created_at, f.error_message, f.created_at as failed_at
            FROM posts p
            LEFT JOIN publishing_history f ON p.id = f.post_id AND f.result = 'failure'
            WHERE p.status = 'failed'
            ORDER BY p.created_at DESC
            LIMIT :limit
        """)
        results = session.execute(query, {"limit": limit}).mappings().all()
        return [dict(r) for r in results]

def get_experiment_results_summary() -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT status, COUNT(*) as count, AVG(
                CASE WHEN status = 'completed' THEN 1 ELSE 0 END
            ) as completion_rate
            FROM experiments
            GROUP BY status
        """)
        results = session.execute(query).mappings().all()
        return [dict(r) for r in results]

def get_knowledge_rule_effectiveness() -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT lifecycle_state, COUNT(*) as count, AVG(confidence) as avg_confidence, AVG(evidence_count) as avg_evidence
            FROM knowledge_rules
            GROUP BY lifecycle_state
        """)
        results = session.execute(query).mappings().all()
        return [dict(r) for r in results]

def get_decision_outcome_analysis(days: int = 30) -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT decision_type, outcome, COUNT(*) as count
            FROM decision_logs
            WHERE created_at >= NOW() - INTERVAL ':days days'
            GROUP BY decision_type, outcome
            ORDER BY decision_type, count DESC
        """)
        results = session.execute(query, {"days": days}).mappings().all()
        return [dict(r) for r in results]

def get_engine_health_history(engine_name: str, days: int = 7) -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT status, last_heartbeat, error_message
            FROM engine_health
            WHERE engine_name = :engine_name
            ORDER BY last_heartbeat DESC
        """)
        results = session.execute(query, {"engine_name": engine_name}).mappings().all()
        return [dict(r) for r in results]

def get_post_lifecycle_timeline(post_id: uuid.UUID) -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT 'created' as event_type, created_at as event_time, status as details FROM posts WHERE id = :post_id
            UNION ALL
            SELECT 'published', published_at, final_text FROM posts WHERE id = :post_id AND published_at IS NOT NULL
            UNION ALL
            SELECT 'failed', created_at, error_message FROM publishing_history WHERE post_id = :post_id AND result = 'failure'
            ORDER BY event_time ASC
        """)
        results = session.execute(query, {"post_id": str(post_id)}).mappings().all()
        return [dict(r) for r in results]

def get_system_dashboard_data() -> Dict[str, Any]:
    with get_session() as session:
        active_posts = session.execute(text("SELECT COUNT(*) FROM posts WHERE status IN ('draft', 'ready', 'scheduled')")).scalar()
        failed_posts = session.execute(text("SELECT COUNT(*) FROM posts WHERE status = 'failed'")).scalar()
        active_rules = session.execute(text("SELECT COUNT(*) FROM knowledge_rules WHERE lifecycle_state = 'active'")).scalar()
        return {
            "active_posts": active_posts,
            "failed_posts": failed_posts,
            "active_rules": active_rules,
        }

def get_content_performance_trend(days: int = 90) -> List[Dict[str, Any]]:
    with get_session() as session:
        query = text("""
            SELECT DATE(p.published_at) as pub_date, COUNT(p.id) as post_count, AVG(m.engagement_rate) as avg_engagement
            FROM posts p
            LEFT JOIN metrics m ON p.id = m.post_id AND m.snapshot_period = '24h'
            WHERE p.published_at >= NOW() - INTERVAL ':days days'
            GROUP BY DATE(p.published_at)
            ORDER BY pub_date ASC
        """)
        results = session.execute(query, {"days": days}).mappings().all()
        return [dict(r) for r in results]

def get_quality_gate_pass_rates(days: int = 30) -> Dict[str, Any]:
    with get_session() as session:
        query = text("""
            SELECT gate_name,
                   SUM(CASE WHEN passed = TRUE THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as pass_rate
            FROM quality_results
            WHERE created_at >= NOW() - INTERVAL ':days days'
            GROUP BY gate_name
        """)
        results = session.execute(query, {"days": days}).mappings().all()
        return {r["gate_name"]: r["pass_rate"] for r in results}

def get_memory_usage_stats() -> Dict[str, Any]:
    with get_session() as session:
        total_entries = session.execute(text("SELECT COUNT(*) FROM memory_entries")).scalar()
        avg_importance = session.execute(text("SELECT AVG(importance) FROM memory_entries")).scalar()
        return {
            "total_entries": total_entries,
            "avg_importance": avg_importance
        }

def get_notification_summary(days: int = 7) -> Dict[str, Any]:
    with get_session() as session:
        query = text("""
            SELECT channel, status, COUNT(*) as count
            FROM notifications
            WHERE created_at >= NOW() - INTERVAL ':days days'
            GROUP BY channel, status
        """)
        results = session.execute(query, {"days": days}).mappings().all()
        
        summary = {}
        for r in results:
            channel = r["channel"]
            status = r["status"]
            if channel not in summary:
                summary[channel] = {}
            summary[channel][status] = r["count"]
        return summary
