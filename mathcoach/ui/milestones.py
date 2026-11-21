"""里程碑事件判定：只在明确事件上触发庆祝。"""
from __future__ import annotations

import streamlit as st

from ..domain.models import Consent
from .motion import queue_celebration

FIVE_KEY = "celebration_five_correct"
REVIEW_KEY = "celebration_review_complete"
MISTAKES_KEY = "celebration_mistakes_cleared"


def celebrate_five_correct(engine, consent: Consent) -> bool:
    """连续答对达到 5 题时登记一次庆祝，同一条连对不重复。"""
    attempts = getattr(engine.state, "attempts", [])
    streak = 0
    for attempt in reversed(attempts):
        if attempt.get("correct") is True:
            streak += 1
        else:
            break
    if streak < 5:
        return False
    start = len(attempts) - streak
    key = f"{FIVE_KEY}:{engine.card.id}:{start}"
    if st.session_state.get(key):
        return False
    st.session_state[key] = True
    queue_celebration("five-correct", consent)
    return True


def celebrate_review_complete(state, consent: Consent) -> bool:
    """复习包完成时登记一次庆祝；同一复习会话只触发一次。"""
    if not getattr(state, "finished", False):
        return False
    key = f"{REVIEW_KEY}:{getattr(state, 'date_key', '')}"
    if st.session_state.get(key):
        return False
    st.session_state[key] = True
    queue_celebration("review-complete", consent)
    return True


def celebrate_mistakes_cleared(
    consent: Consent, cleared_mistakes: int
) -> bool:
    """清除学习数据时若确实删除了错题，登记一次庆祝。"""
    if cleared_mistakes <= 0:
        return False
    if st.session_state.get(MISTAKES_KEY):
        return False
    st.session_state[MISTAKES_KEY] = True
    queue_celebration("mistakes-cleared", consent)
    return True
