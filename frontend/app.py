"""Entry point assembling the modular Streamlit frontend."""
from __future__ import annotations

import streamlit as st

from constants import BUTTON_STYLE, DEFAULT_API_BASE_URL, PAGE_CONFIG
from state import apply_state, initialize_session_state
from ui import render_configuration, render_results, render_utils, sidebar_ui


st.set_page_config(**PAGE_CONFIG)
st.markdown(BUTTON_STYLE, unsafe_allow_html=True)


def main() -> None:
    st.markdown(
        "<h1 style='display:flex;align-items:center;gap:12px;'>🛠️ OSM-K Tester System</h1>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    initialize_session_state()
    apply_state()

    with st.sidebar:
        sidebar_ui()

    api_base = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL)
    tab1, tab2, tab3 = st.tabs(["⚙️ Конфигурация тестирования", "📊 Результаты тестирования", "🔧 Утилиты"])
    with tab1:
        render_configuration(api_base)
    with tab2:
        render_results(api_base)
    with tab3:
        render_utils(api_base)


if __name__ == "__main__":  # pragma: no cover - executed by Streamlit
    main()
