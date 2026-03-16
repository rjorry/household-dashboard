import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os
from pathlib import Path

# ────────────────────────────────────────────────
# Page configuration
# ────────────────────────────────────────────────
st.set_page_config(
    page_title="Household Survey Dashboard",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ────────────────────────────────────────────────
# Helper – local CSS (if you still use it)
# ────────────────────────────────────────────────
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except:
        pass

# ────────────────────────────────────────────────
# Config & Auth setup
# ────────────────────────────────────────────────
config_dir = Path("./config")
os.makedirs(config_dir, exist_ok=True)

config_path = config_dir / "config.yaml"

if not config_path.exists():
    # Create default config with hashed password
    credentials = {
        "usernames": {
            "admin": {
                "email": "admin@example.com",
                "name": "Admin User",
                "password": "admin123"
            }
        }
    }

    hashed_pw = stauth.Hasher(['admin123']).generate()[0]
    credentials['usernames']['admin']['password'] = hashed_pw

    default_config = {
        "credentials": credentials,
        "cookie": {
            "expiry_days": 1,
            "key": "household_dashboard_auth",
            "name": "household_dashboard_cookie"
        },
        "preauthorized": {
            "emails": ["admin@example.com"]
        }
    }

    with open(config_path, 'w') as file:
        yaml.dump(default_config, file, default_flow_style=False, sort_keys=False)

# Load config
with open(config_path) as file:
    config = yaml.load(file, Loader=SafeLoader)

# Initialize authenticator
authenticator = stauth.Authenticate(
    credentials=config['credentials'],
    cookie_name=config['cookie']['name'],
    key=config['cookie']['key'],
    cookie_expiry_days=config['cookie']['expiry_days'],
    preauthorized=config['preauthorized']
)

# ────────────────────────────────────────────────
# Login page
# ────────────────────────────────────────────────
def login_page():
    st.markdown("<h2 style='text-align: center;'>🔐 Household Survey Dashboard</h2>", unsafe_allow_html=True)
    
    st.subheader("Login")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == "admin" and password == "admin123":
            # For hardcoded check (you can remove this later if using proper auth)
            st.session_state['authentication_status'] = True
            st.session_state['name'] = "Admin User"
            st.session_state['username'] = "admin"
            st.rerun()
        else:
            st.error("Incorrect username or password")

# ────────────────────────────────────────────────
# Main app logic
# ────────────────────────────────────────────────
def main_app():
    # Sidebar welcome & logout
    st.sidebar.write(f"Welcome **{st.session_state['name']}** 👋")
    
    if st.sidebar.button("Logout"):
        st.session_state['authentication_status'] = False
        authenticator.logout("Logout", "sidebar")
        st.rerun()

    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()

    # ── Load dashboard only after login ──
    with st.spinner("Loading dashboard..."):
        try:
            from dashboard import main as dashboard_main
            dashboard_main()
        except ModuleNotFoundError:
            st.error("File **dashboard.py** was not found in the same folder.")
            st.info("Make sure the dashboard code is saved in a file named exactly `dashboard.py`")
        except ImportError as e:
            st.error(f"Import error: {e}")
            st.info("Check that dashboard.py has no syntax errors and all imports work.")
        except Exception as e:
            st.error("The dashboard failed to run.")
            with st.expander("Show detailed error"):
                st.exception(e)

# ────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = False

if not st.session_state['authentication_status']:
    login_page()
else:
    main_app()

# Optional footer
st.markdown(
    """
    <hr style='margin-top: 40px;'>
    <small>Household Survey Dashboard • Support: ronnyjorry@gmail.com</small>
    """,
    unsafe_allow_html=True
)
