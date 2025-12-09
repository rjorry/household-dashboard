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
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Create config directory if it doesn't exist
config_dir = Path("./config")
os.makedirs(config_dir, exist_ok=True)

# Path to config file (will store hashed password)
config_path = config_dir / "config.yaml"

# If config doesn't exist, create it using secrets (secrets hold the plain password locally)
if not config_path.exists():
    # Read credentials from Streamlit secrets (keep secrets.toml local and ignored by git)
    try:
        admin_username = st.secrets["auth"]["username"]
        admin_email = st.secrets["auth"]["email"]
        admin_password = st.secrets["auth"]["password"]
    except Exception as e:
        st.error("Missing auth secrets. Create .streamlit/secrets.toml with [auth] username, email, password.")
        st.stop()

    # Hash the password using streamlit_authenticator Hasher
    # Hasher takes a list of plain passwords and returns a list of hashed passwords
    hashed_list = stauth.Hasher([str(admin_password)]).generate()
    hashed_pw = hashed_list[0]

    credentials = {
        "usernames": {
            admin_username: {
                "name": "Admin User",
                "email": admin_email,
                "password": hashed_pw
            }
        }
    }

    default_config = {
        "credentials": credentials,
        "cookie": {
            "expiry_days": 1,
            "key": "household_dashboard_auth_key",  # you can change this to any random string
            "name": "household_dashboard_cookie"
        },
        "preauthorized": {
            "emails": [admin_email]
        }
    }

    # Save hashed credentials to config.yaml (this file contains only hashed password)
    with open(config_path, "w") as fh:
        yaml.dump(default_config, fh, sort_keys=False)

# Load configuration (the file contains hashed password)
with open(config_path) as file:
    config = yaml.load(file, Loader=SafeLoader)

# Initialize authenticator
authenticator = stauth.Authenticate(
    credentials=config["credentials"],
    cookie_name=config["cookie"]["name"],
    key=config["cookie"]["key"],
    cookie_expiry_days=config["cookie"]["expiry_days"],
    preauthorized=config.get("preauthorized")
)

# ---- UI / Login ----
def show_login():
    st.markdown("<h1 style='text-align:center;'>🔐 Household Survey Dashboard</h1>", unsafe_allow_html=True)
    name, auth_status, username = authenticator.login("Login", "main")

    if auth_status is False:
        st.error("Username/password is incorrect")
        return False, None
    if auth_status is None:
        st.warning("Please enter your username and password")
        return False, None

    # auth_status == True
    return True, {"name": name, "username": username}

# ---- Main app ----
def main():
    # If logged in show dashboard, else show login
    logged_in, user = show_login()

    if not logged_in:
        return

    # Sidebar with logout and info
    with st.sidebar:
        st.markdown(f"### Welcome *{user['name']}*")
        authenticator.logout("Logout", "sidebar")
        st.markdown("---")
        if st.button("Refresh Data"):
            st.experimental_rerun()

    # Run the dashboard (imported from dashboard.py)
    try:
        from dashboard import main as dashboard_main
        dashboard_main()
    except ModuleNotFoundError:
        st.error("dashboard.py not found. Create dashboard.py in the same folder.")
    except Exception as e:
        st.error(f"Error while loading dashboard: {e}")
        st.exception(e)

if __name__ == "__main__":
    main()
