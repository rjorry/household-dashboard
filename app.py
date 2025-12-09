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
os.makedirs(config_dir, exist_ok=True)
config_path = config_dir / "config.yaml"

# Create config.yaml with hashed password (only first time)
if not config_path.exists():
    try:
        admin_username = st.secrets["auth"]["username"]
        admin_email    = st.secrets["auth"]["email"]
        admin_password = st.secrets["auth"]["password"]
    except Exception:
        st.error("Missing auth secrets in .streamlit/secrets.toml")
        st.stop()

    credentials = {
        "usernames": {
            admin_username: {
                "name": "Admin User",
                "email": admin_email,
                "password": admin_password
            }
        }
    }

    stauth.Hasher.hash_passwords(credentials)  # hashes in-place

    default_config = {
        "credentials": credentials,
        "cookie": {
            "expiry_days": 30,
            "key": "household_dashboard_auth_key_2025",
            "name": "household_dashboard_cookie"
        },
        "preauthorized": {"emails": [admin_email]}
    }

    with open(config_path, "w") as fh:
        yaml.dump(default_config, fh, sort_keys=False)

# Load config
with open(config_path) as file:
    config = yaml.load(file, Loader=SafeLoader)

# Initialize authenticator
authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
    config.get("preauthorized")
)

# ---- FIXED LOGIN FUNCTION (this is the key change) ----
def show_login():
    st.markdown("<h1 style='text-align:center;'>Household Survey Dashboard</h1>", unsafe_allow_html=True)
    
    # This line works perfectly with streamlit-authenticator 0.4.x in 2025
    name, authentication_status, username, _, _ = authenticator.login(location="main")
    
    if authentication_status is False:
        st.error("Username/password is incorrect")
        return False, None
    if authentication_status is None:
        st.warning("Please enter your username and password")
        return False, None
    
    return True, {"name": name, "username": username}

# ---- Main app ----
def main():
    logged_in, user = show_login()
    if not logged_in:
        return

    with st.sidebar:
        st.markdown(f"### Welcome *{user['name']}*")
        authenticator.logout("Logout", "sidebar")
        st.markdown("---")
        if st.button("Refresh Data"):
            st.rerun()

    try:
        from dashboard import main as dashboard_main
        dashboard_main()
    except ModuleNotFoundError:
        st.error("dashboard.py not found. Create it in the same folder.")
    except Exception as e:
        st.error(f"Error loading dashboard: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
