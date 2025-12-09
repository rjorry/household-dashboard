# app.py
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="Household Survey Dashboard",
    page_icon="key",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Create config directory if it doesn't exist
config_dir = Path("./config")
config_dir.mkdir(exist_ok=True)
config_path = config_dir / "config.yaml"

# ───── Create config.yaml with hashed password (only first time) ─────
if not config_path.exists():
    try:
        admin_username = st.secrets["auth"]["username"]
        admin_email    = st.secrets["auth"]["email"]
        admin_password = st.secrets["auth"]["password"]
    except Exception:
        st.error("Missing auth secrets in Streamlit secrets!")
        st.stop()

    credentials = {
        "usernames": {
            admin_username: {
                "name": "Admin User",
                "email": admin_email,
                "password": admin_password  # plain text here → will be hashed below
            }
        }
    }

    # This is the correct way in v0.3+ / v0.4+
    stauth.Hasher.hash_passwords(credentials)

    config = {
        "credentials": credentials,
        "cookie": {
            "expiry_days": 30,
            "key": "some_signature_key",           # change or randomize
            "name": "household_dashboard_cookie"
        },
        "preauthorized": {"emails": [admin_email]}
    }

    with open(config_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)

# ───── Load config and create authenticator ─────
with open(config_path) as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
    config.get("preauthorized")
)

# ───── Fixed login function (this was broken before) ─────
def show_login():
    st.markdown("<h1 style='text-align:center;'>Household Survey Dashboard</h1>", unsafe_allow_html=True)
    
    name, authentication_status, username = authenticator.login(
        location="main",
        fields={
            "Form name": "Login to Dashboard",
            "Username": "Username",
            "Password": "Password",
            "Login": "Login"
        }
    )

    if authentication_status is False:
        st.error("Username or password is incorrect")
        return False, None
    if authentication_status is None:
        st.warning("Please enter your username and password")
        return False, None
    return True, {"name": name, "username": username}

# ───── Main app ─────
def main():
    logged_in, user = show_login()
    if not logged_in:
        return

    # Sidebar
    with st.sidebar:
        st.success(f"Welcome **{user['name']}**")
        authenticator.logout("Logout", location="sidebar")
        st.markdown("---")
        if st.button("Refresh page"):
            st.rerun()

    # Your actual dashboard
    try:
        from dashboard = __import__("dashboard")
        dashboard.main()
    except ImportError:
        st.error("dashboard.py not found in the project root")
    except Exception as e:
        st.exception(e)

if __name__ == "__main__":
    main()
