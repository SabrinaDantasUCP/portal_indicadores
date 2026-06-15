import os

import streamlit as st

from utils.data_config import DATASETS


DEFAULT_VERSION = "indicadores_v1"
GLOBAL_SCOPE = "global"


def get_current_version():
    return st.session_state.get("data_version", DEFAULT_VERSION)


def set_current_version(version):
    st.session_state.data_version = version


def get_data_path(dataset_name, scope=None):
    scope = scope or get_current_version()
    try:
        return DATASETS[scope][dataset_name]
    except KeyError as exc:
        raise KeyError(f"Dataset no configurado: {scope}.{dataset_name}") from exc


def get_global_data_path(dataset_name):
    return get_data_path(dataset_name, GLOBAL_SCOPE)


def data_file_mtime(dataset_name, scope=None):
    path = get_data_path(dataset_name, scope)
    return os.path.getmtime(path) if os.path.exists(path) else None
