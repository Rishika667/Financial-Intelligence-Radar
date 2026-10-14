"""Configuration helper for environment variables and Streamlit secrets."""
import os
import sys


def get_sec_user_agent() -> str:
    """
    Retrieve SEC_USER_AGENT from OS environment or Streamlit secrets.
    Does not crash if Streamlit secrets store is absent or unconfigured.
    Never exposes or logs secret values.
    """
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if ua:
        return ua
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "SEC_USER_AGENT" in st.secrets:
            val = str(st.secrets["SEC_USER_AGENT"]).strip()
            if val:
                return val
    except Exception:
        pass
    return ""


def is_public_demo_mode() -> bool:
    """
    Check if PUBLIC_DEMO_MODE is enabled via OS environment or Streamlit secrets.
    When enabled, visitor-specific portfolio holdings, notes, and watchlist
    customizations are session-scoped to prevent multi-visitor shared-state leaks.
    """
    env_val = os.environ.get("PUBLIC_DEMO_MODE", "").strip().lower()
    if env_val in ("1", "true", "yes", "on"):
        return True
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "PUBLIC_DEMO_MODE" in st.secrets:
            val = str(st.secrets["PUBLIC_DEMO_MODE"]).strip().lower()
            return val in ("1", "true", "yes", "on")
    except Exception:
        pass
    return False


def validate_user_agent(ua: str) -> bool:
    """
    Validate that User-Agent identifies an operator and contact email.
    """
    if not ua or len(ua.strip()) < 5 or "@" not in ua:
        return False
    return True
