# app.py
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os
from pathlib import Path
# Import dashboard here to make it available for the main function
try:
    from dashboard import main as dashboard_main
except ModuleNotFoundError:
    # If dashboard.py doesn't exist yet, this will catch it later in main()
    dashboard_main = None


# Page configuration
st.set_page_config(
    page_title="Household Survey Dashboard",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Configuration Setup (No changes needed here) ---

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
    preauthorized=config["preauthorized"]["emails"]
)

# --- CORRECTED Login and Main Functions using Session State ---

def show_login():
    """Handles the login form display and state update via session_state."""
    st.markdown("<h1 style='text-align:center;'>🔐 Household Survey Dashboard</h1>", unsafe_allow_html=True)
    
    # Call the login function. This displays the form and updates st.session_state
    # with keys: 'authentication_status', 'name', and 'username'.
    authenticator.login(location="main")
    
    # Check the status written to session_state
    if st.session_state["authentication_status"] is False:
        st.error("Username/password is incorrect")
    elif st.session_state["authentication_status"] is None:
        st.warning("Please enter your username and password")
    
    # Note: We don't return anything here. The main function will check st.session_state directly.

# ---- Main app ----
def main():
    # 1. Run the login process to display the form and update session state
    show_login()
    
    # 2. Check the authentication status in session state
    if st.session_state.get("authentication_status"):
        # This block runs ONLY if login was successful (authentication_status is True)
        
        # Sidebar with logout and info
        with st.sidebar:
            # Access user info directly from session state
            st.markdown(f"### Welcome *{st.session_state['name']}*")
            # Log out button (will set authentication_status to False and RERUN)
            authenticator.logout(button_name="Logout", location="sidebar")
            st.markdown("---")
            if st.button("Refresh Data"):
                st.rerun()
        
        # Run the dashboard (imported from dashboard.py)
        if dashboard_main:
            try:
                dashboard_main()
            except Exception as e:
                st.error(f"Error while loading dashboard: {e}")
                st.exception(e)
        else:
            st.error("dashboard.py not found. Create dashboard.py in the same folder.")

    # else: If authentication_status is False or None, the dashboard part is skipped, 
    # and only the login form (displayed in show_login) is shown.

if __name__ == "__main__":
    main()
