"""Streamlit 单页装配：只渲染 session 层给的视图，不写判定逻辑。"""
from pathlib import Path

import streamlit as st

from mathcoach.config import content_strict
from mathcoach.content.loader import ContentError, load_content
from mathcoach.domain.models import Phase
from mathcoach.llm import OfflineProvider, build_provider
from mathcoach.session.engine import SessionEngine

CONTENT_ROOT = Path(__file__).parent / "content"

st.set_page_config(page_title="数学陪练", page_icon="📘")


@st.cache_resource
def _load_cards():
    try:
        cards, result = load_content(CONTENT_ROOT, strict=content_strict())
    except ContentError as exc:
        st.error(f"内容加载失败：\n{exc}")
        st.stop()
    for warning in result.warnings:
        st.warning(f"{warning.location}: {warning.message}")
    return cards


cards = _load_cards()
card = cards[0]

if "provider" not in st.session_state:
    st.session_state.provider = build_provider()
if "engine" not in st.session_state:
    st.session_state.engine = SessionEngine(card=card, provider=st.session_state.provider)

provider = st.session_state.provider
engine: SessionEngine = st.session_state.engine
view = engine.view

st.title("数学陪练")
st.caption(f"当前卡片：{card.name} · {card.course}")
if isinstance(provider, OfflineProvider) or getattr(provider, "degraded", False):
    st.caption("离线模板模式：讲解使用确定性模板，判分逻辑不变。")

st.subheader(view.title)
st.write(view.body)
if view.notice:
    st.info(view.notice)


def _render_hint_actions() -> None:
    with st.expander("需要提示？"):
        if st.button("给步骤（最高 L4）", key="hint_step"):
            engine.request_hint("step")
            st.rerun()
        if st.button("直接给答案（最高 L4）", key="hint_answer"):
            engine.request_hint("answer")
            st.rerun()
        if st.button("开放 L5（需先尝试 L1—L4）", key="hint_level5"):
            engine.request_hint("level5")
            st.rerun()


if view.phase is Phase.GOAL_CONFIRM:
    goal = st.text_input("今天想练到什么？", key="goal_input")
    if st.button("确认目标", key="confirm_goal"):
        try:
            engine.confirm_goal(goal)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.rerun()

elif view.phase is Phase.EXPLAIN:
    if st.button("开始小测", key="begin_quiz"):
        engine.begin_quiz()
        st.rerun()

elif view.phase is Phase.QUIZ:
    answer = st.radio(
        "选择答案",
        view.options,
        key=f"answer_{engine.state.exercise_id}_{len(engine.state.attempts)}",
    )
    if st.button("提交答案", key="submit_answer"):
        engine.submit_answer(answer)
        st.rerun()
    _render_hint_actions()

elif view.phase is Phase.DIAGNOSE:
    selected = st.radio(
        "选择更贴近的错因",
        view.options,
        key=f"diagnosis_{engine.state.exercise_id}_{len(engine.state.attempts)}",
    )
    if st.button("确认错因", key="confirm_diagnosis"):
        engine.confirm_diagnosis(selected)
        st.rerun()

elif view.phase is Phase.HINT:
    if st.button("再试一次", key="retry"):
        engine.retry()
        st.rerun()
    _render_hint_actions()

elif view.phase is Phase.RECEIPT:
    if st.button("继续", key="advance"):
        engine.advance()
        st.rerun()

elif view.phase is Phase.WRAPUP:
    if st.button("重新开始", key="restart"):
        st.session_state.engine = SessionEngine(card=card, provider=provider)
        st.rerun()
