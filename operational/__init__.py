"""
Operational Layer — makes the integrated Autonomous AI System executable.

Modules:
  gemini_rotation  — Multi-key × multi-model rotation engine (free tier only)
  health_monitor   — Pipeline health tracking + Telegram alerts
  logging_config   — Centralized structured logging with rotation
  scheduler        — APScheduler-based job runner (Asia/Baghdad tz)
  backup           — Database + logs + config backup with retention
"""
