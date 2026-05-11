from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import Settings
from app.schemas.slack import SlackChannelPrefs

logger = logging.getLogger(__name__)

BUNDLED_DEFAULT = Path(__file__).resolve().parents[1] / "automation" / "config" / "default_slack_channels.json"


def _user_prefs_path(settings: Settings) -> Path:
    return settings.data_dir / "slack" / "slack_channels.json"


def load_slack_channel_prefs(settings: Settings) -> SlackChannelPrefs:
    base: dict = {}
    if BUNDLED_DEFAULT.exists():
        try:
            base = json.loads(BUNDLED_DEFAULT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("default slack channel prefs unreadable: %s", e)
            base = {}

    user_path = _user_prefs_path(settings)
    merged = dict(base)
    if user_path.exists():
        try:
            user_obj = json.loads(user_path.read_text(encoding="utf-8"))
            if isinstance(user_obj, dict):
                merged.update(user_obj)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("user slack channel prefs unreadable: %s", e)

    try:
        return SlackChannelPrefs.model_validate(merged)
    except Exception:
        return SlackChannelPrefs()
