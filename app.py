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
    
    # Build credentials with PLAIN password first
    credentials = {
        "usernames": {
            admin_username: {
                "name": "Admin User",
                "email": admin_email,
                "password": admin_password  # ← Plain text here (safe, since it's local/secrets only)
            }
        }
    }
    
    # NOW hash the password in-place using the full credentials dict
    stauth.Hasher.hash_passwords(credentials)
    # → Hashes credentials["usernames"][admin_username]["password"] securely
    
    default_config = {
        "credentials": credentials,  # ← Now contains the HASHED password
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
    preauthorized=config["preauthorized"]["emails"]  # ← Flat list for new API
)

# ---- UI / Login ----
def show_login():
    st.markdown("<h1 style='text-align:center;'>🔐 Household Survey Dashboard</h1>", unsafe_allow_html=True)
    
    # Initialize variables for the try/except block
    name = None
    authentication_status = None
    username = None

    # Use a try/except block to handle the TypeError when the login function
    # only returns 2 values (on initial load or failed login in some versions)
    try:
        # Tries to unpack 3 values (Success or certain failed states)
        name, authentication_status, username = authenticator.login(location="main")
    except TypeError:
        # If the library returns only 2 values (common on initial load),
        # we catch the error, and the variables remain as None, which is fine
        # because the logic below handles the None status.
        # Rerun the login call to ensure the UI is displayed, but only unpack 2 values
        # NOTE: This approach is slightly cleaner than relying on global state/st.session_state
        # for a simple login screen.
        pass

    # The login widget is displayed if authentication_status is None
    if authentication_status is False:
        st.error("Username/password is incorrect")
        return False, None
    if authentication_status is None:
        # This state occurs on initial load or if the user hasn't interacted yet.
        # The login form is visible.
        return False, None
    
    # If authentication_status is True (Success)
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
        # FIXED: Keyword args for new API
        authenticator.logout(button_name="Logout", location="sidebar")
        st.markdown("---")
        if st.button("Refresh Data"):
            st.rerun()  # FIXED: experimental_rerun() → rerun()
    
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
