"""Constants shared across the Streamlit frontend modules."""
from pathlib import Path

PAGE_CONFIG = {
    "page_title": "OSM-K Tester System",
    "page_icon": "🛠️",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

BUTTON_STYLE = """
 <style>
 div.stButton > button:first-child {background-color: #800000; color: white;font-weight: bold;}
 div.stButton > button:first-child:hover {background-color: #560319;}
 </style>
"""

DEFAULT_API_BASE_URL = "http://localhost:8000"

STATE_FILE = Path(__file__).resolve().parent.parent / "ui_state.json"
