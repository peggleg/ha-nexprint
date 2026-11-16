"""Constants for the Nexprint integration."""

from __future__ import annotations

DOMAIN = "nexprint"

BASE_URL = "https://www.nexprint.com"
CLIENT_ID = "Nexprint"

# Verified Nexprint web gateway endpoints
ENDPOINT_AUTH_KEY = "/gateway/api/v1/account-center-server/account-auth/key"
ENDPOINT_AUTH_LOGIN = (
    "/gateway/api/v1/account-center-server/account-auth/login/email/password"
)
ENDPOINT_AUTH_AUTHORIZE = "/gateway/api/v1/account-center-server/authorize/code"
ENDPOINT_AUTH_TOKEN = "/gateway/api/v1/account-center-server/token"
ENDPOINT_USER_DATA = "/gateway/api/v1/model-user-server/member/user_data"
ENDPOINT_USER_DASHBOARD = "/gateway/api/v1/model-user-server/member/user_dashboard"
ENDPOINT_POINTS_BALANCE = "/gateway/api/v1/points-server/credits/balance"
ENDPOINT_MESSAGE_STATE = "/gateway/api/v1/message-server/state"
ENDPOINT_SEARCH = "/gateway/api/v1/model-library-server/model-base-info/search"

CONF_AUTH_MODE = "auth_mode"
AUTH_MODE_PASSWORD = "password"
AUTH_MODE_TOKEN = "token"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_ACCEPT_TERMS = "accept_terms"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_KEYWORD = "keyword"
CONF_PAGE_SIZE = "page_size"

DEFAULT_PAGE_SIZE = 30
DEFAULT_SCAN_INTERVAL_MINUTES = 30

SERVICE_SEARCH = "search"
EVENT_SEARCH_RESULTS = "nexprint_search_results"
