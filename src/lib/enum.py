from enum import Enum
import streamlit as st
from typing import Any

class StateKey(str, Enum):
    ACTIVE_PAGE = "active_page"
    UPLOAD_KEY = "upload_key"


class StageKey(str, Enum):
    STAGE_1 = "stage_1"
    STAGE_1_DATASET = "stage_1_dataset"
    STAGE_1_SLANG = "stage_1_slang"
    STAGE_2 = "stage_2"
    STAGE_3 = "stage_3"
    STAGE_4 = "stage_4"
    STAGE_5 = "stage_5"
    STAGE_6 = "stage_6"
    STAGE_7 = "stage_7"
    STAGE_8 = "stage_8"


class StageCollect(str, Enum):
    DATASET_COUNT = "dataset_count"
    MODEL_READY = "model_ready"

DEFAULT_SESSION_STATE = {
    # State global
    StateKey.ACTIVE_PAGE: None,
    StateKey.UPLOAD_KEY: 0,

    # Stage modeling
    StageKey.STAGE_1: False,
    StageKey.STAGE_1_DATASET: False,
    StageKey.STAGE_1_SLANG: False,
    StageKey.STAGE_2: False,
    StageKey.STAGE_3: False,
    StageKey.STAGE_4: False,
    StageKey.STAGE_5: False,
    StageKey.STAGE_6: False,
    StageKey.STAGE_7: False,
    StageKey.STAGE_8: False,

    # Stage Collect
    StageCollect.DATASET_COUNT: 0,
    StageCollect.MODEL_READY: False
}


def load_session_state() -> None:
    for key, value in DEFAULT_SESSION_STATE.items():
        st.session_state.setdefault(key, value)
        
def get_session_state(key: str | Enum, default: Any = None) -> Any:
    session_key: str = key.value if isinstance(key, Enum) else key
    return st.session_state.get(session_key, default)

def set_session_state(key: str | Enum, value: Any) -> None:
    session_key = key.value if isinstance(key, Enum) else key
    st.session_state[session_key] = value