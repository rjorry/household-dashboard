# app.py
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from pathlib import Path
import os

# ---- PAGE CONFIG ----
st.set_page_config(
    page_title="Household Survey Dashboard",
    page_icon="🔐",
    layout="wide"
)

# ---- CONFIG FOLDER ----
config_dir = Path("./config")
config_dir.mkdir(exist_ok=True)

config_path = config_dir / "config.yaml"

# ---- READ SECRETS (Required) ----
try:
    admin_username = st.secrets["auth"]["username"]
    admin_email = st.secrets["auth"]["email"]
    admin_password = st.secrets["auth"]["password"]
except:
    st.error("❌ Missing secrets! Add them in Streamlit Cloud → Settings → Secrets")
    st.stop()

# ---- ALWAYS RECREATE CONFIG ----
# (Prevents corrupted YAML on Streamlit Cloud)
hashed_pw = stauth.Hasher([admin_password]).generate()[0]

credentials = {
    "usernames": {
        admin_username: {
            "email": admin_email,
            "name": "Admin",
            "password": hashed_pw
        }
    }
}

config_data = {
    "credentials": credentials,
    "cookie": {
        "expiry_days": 1,
        "key": "some_signature_key",
        "name": "auth_cookie"
    },
    "preauthorized": {
        "emails": [admin_email]
    }
}

with open(config_path, "w") as f:
    yaml.dump(config_data, f, sort_keys=False)

# ---- LOAD CLEAN CONFIG ----
with open(config_path) as f:
    config = yaml.load(f, Loader=SafeLoader)

# ---- AUTHENTICATOR ----
authenticator = stauth.Authenticate(
    credentials=config["credentials"],
    cookie_name=config["cookie"]["name"],
    key=config["cookie"]["key"],
    cookie_expiry_days=config["cookie"]["expiry_days"],
    preauthorized=config["preauthorized"]
)

# ---- LOGIN UI ----
def login_screen():
    st.title("🔐 Household Survey Dashboard")

    name, auth_status, username = authenticator.login("Login", "main")

    if auth_status is False:
        st.error("❌ Incorrect username or password")
        return None

    if auth_status is None:
        st.warning("Enter login credentials")
        return None

    return name, username


# ---- MAIN ----
def main():
    auth = login_screen()
    if not auth:
        return

    name, username = auth

    # SIDEBAR
    with st.sidebar:
        st.success(f"Logged in as {name}")
        authenticator.logout("Logout", "sidebar")

    # DASHBOARD
    try:
        from dashboard import main as dashboard_main
        dashboard_main()
    except Exception as e:
        st.error(f"Dashboard Error: {e}")
        st.exception(e)


if __name__ == "__main__":
    main()
