"""Async API client for Nexprint."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import hashlib
import os
import secrets
from typing import Any
from urllib.parse import parse_qs, urlparse
import uuid

import aiohttp
from cryptography.hazmat.primitives import padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import (
    BASE_URL,
    CLIENT_ID,
    DEFAULT_PAGE_SIZE,
    ENDPOINT_AUTH_AUTHORIZE,
    ENDPOINT_AUTH_KEY,
    ENDPOINT_AUTH_LOGIN,
    ENDPOINT_AUTH_TOKEN,
    ENDPOINT_MESSAGE_STATE,
    ENDPOINT_POINTS_BALANCE,
    ENDPOINT_SEARCH,
    ENDPOINT_USER_DASHBOARD,
)


class NexprintApiError(Exception):
    """Base exception for Nexprint API errors."""


class NexprintAuthError(NexprintApiError):
    """Raised when login fails or a session token is invalid/expired."""


@dataclass(slots=True)
class NexprintModelSummary:
    """Normalized summary of a Nexprint 3D model."""

    model_id: str
    public_id: str
    title: str
    author: str | None
    url: str | None
    downloads: int
    likes: int


@dataclass(slots=True)
class NexprintSearchResult:
    """Normalized search result payload."""

    keyword: str
    total: int
    models: list[NexprintModelSummary]


@dataclass(slots=True)
class NexprintAccountData:
    """Combined profile, statistics, points, and message state for Nexprint."""

    user_id: str
    nickname: str
    email: str | None
    country_name: str | None
    avatar_url: str | None
    printers: list[str]
    following: int
    followers: int
    published_models: int
    total_likes: int
    total_favorites: int
    total_downloads: int
    total_prints: int
    points_balance: int
    unread_messages_total: int
    unread_system: int
    unread_comments: int
    unread_following: int
    unread_activity: int
    unread_models: int
    raw_user_data: dict[str, Any]


def _encrypt_password(password: str, public_key_b64: str) -> dict[str, str]:
    """Encrypt password using Elegoo's hybrid AES-128-CBC + RSA-PKCS1v15 scheme."""
    der_bytes = base64.b64decode(public_key_b64)
    public_key = serialization.load_der_public_key(der_bytes)

    aes_key = os.urandom(16)
    aes_iv = os.urandom(16)

    padder = padding.PKCS7(128).padder()
    padded_pw = padder.update(password.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv))
    encryptor = cipher.encryptor()
    encrypted_pw = encryptor.update(padded_pw) + encryptor.finalize()

    enc_key = public_key.encrypt(aes_key, asym_padding.PKCS1v15())
    enc_iv = public_key.encrypt(aes_iv, asym_padding.PKCS1v15())

    return {
        "password": base64.b64encode(encrypted_pw).decode("ascii"),
        "aesKey": base64.b64encode(enc_key).decode("ascii"),
        "aesIv": base64.b64encode(enc_iv).decode("ascii"),
    }


def _generate_pkce() -> tuple[str, str]:
    """Generate a PKCE (code_verifier, code_challenge) pair."""
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


class NexprintApiClient:
    """Async client for Nexprint's web gateway API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        self._session = session
        self._email = email.strip() if email else None
        self._password = password
        self._access_token = access_token.strip() if access_token else None
        self._refresh_token = refresh_token.strip() if refresh_token else None

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Return the current refresh token."""
        return self._refresh_token

    def _headers(self, *, json_body: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/json, */*",
            "client-id": CLIENT_ID,
            "user-lang": "en",
            "x-client-request-id": str(uuid.uuid4()),
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
            ),
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def _unwrap(self, payload: Any) -> dict[str, Any]:
        """Validate Nexprint's wrapped JSON status code inside HTTP 200 responses."""
        if not isinstance(payload, dict):
            raise NexprintApiError("Unexpected non-object JSON response from Nexprint")

        code = payload.get("code")
        if code is not None and str(code) not in ("0", "200"):
            msg = str(payload.get("msg") or payload.get("message") or code)
            if (
                str(code) in ("401", "403")
                or "登录" in msg
                or "token" in msg.lower()
                or "auth" in msg.lower()
            ):
                raise NexprintAuthError(f"Nexprint auth error ({code}): {msg}")
            raise NexprintApiError(f"Nexprint gateway error ({code}): {msg}")

        data = payload.get("data")
        return data if isinstance(data, dict) else payload

    async def async_login_with_password(self) -> tuple[str, str | None]:
        """Perform Elegoo's RSA+AES login flow and obtain Nexprint tokens."""
        if not self._email or not self._password:
            raise NexprintAuthError("Email and password are required")

        try:
            async with asyncio.timeout(20):
                # 1. Fetch RSA public key
                async with self._session.post(
                    f"{BASE_URL}{ENDPOINT_AUTH_KEY}",
                    json={"clientId": CLIENT_ID},
                    headers=self._headers(),
                ) as resp:
                    if resp.status >= 400:
                        raise NexprintApiError(f"Auth key HTTP {resp.status}")
                    key_data = self._unwrap(await resp.json(content_type=None))

                public_key = key_data.get("publicKey")
                if not public_key:
                    raise NexprintApiError("Missing publicKey in auth key response")

                # 2. Encrypt password and log in
                encrypted = _encrypt_password(self._password, public_key)
                login_body = {
                    "clientId": CLIENT_ID,
                    "email": self._email,
                    **encrypted,
                }
                async with self._session.post(
                    f"{BASE_URL}{ENDPOINT_AUTH_LOGIN}",
                    json=login_body,
                    headers=self._headers(),
                ) as resp:
                    if resp.status in (401, 403):
                        raise NexprintAuthError("Invalid Nexprint email or password")
                    if resp.status >= 400:
                        raise NexprintApiError(f"Login HTTP {resp.status}")
                    login_data = self._unwrap(await resp.json(content_type=None))

                sso_token = login_data.get("token")
                sso_refresh = login_data.get("refreshToken")
                if not sso_token:
                    raise NexprintAuthError("Login succeeded but returned no token")

                self._access_token = str(sso_token)
                self._refresh_token = str(sso_refresh) if sso_refresh else None

                # 3. Exchange OIDC authorization code for Nexprint gateway session
                verifier, challenge = _generate_pkce()
                redirect_uri = f"{BASE_URL}/en/auth/callback"
                async with self._session.post(
                    f"{BASE_URL}{ENDPOINT_AUTH_AUTHORIZE}",
                    params={
                        "clientId": CLIENT_ID,
                        "responseType": "code",
                        "redirectUri": redirect_uri,
                        "codeChallenge": challenge,
                        "codeChallengeMethod": "S256",
                    },
                    headers=self._headers(json_body=False),
                ) as auth_resp:
                    if auth_resp.status == 200:
                        auth_json = await auth_resp.json(content_type=None)
                        redir = auth_json.get("redirectUri") or (
                            auth_json.get("data") or {}
                        ).get("redirectUri")
                        if redir:
                            code_vals = parse_qs(urlparse(redir).query).get("code")
                            if code_vals:
                                async with self._session.post(
                                    f"{BASE_URL}{ENDPOINT_AUTH_TOKEN}",
                                    data={
                                        "grantType": "authorization_code",
                                        "code": code_vals[0],
                                        "redirectUri": redirect_uri,
                                        "codeVerifier": verifier,
                                        "clientId": CLIENT_ID,
                                    },
                                    headers={
                                        **self._headers(json_body=False),
                                        "Content-Type": "application/x-www-form-urlencoded",
                                    },
                                ) as tok_resp:
                                    if tok_resp.status == 200:
                                        tok_json = await tok_resp.json(
                                            content_type=None
                                        )
                                        if tok_json.get("access_token"):
                                            self._access_token = tok_json[
                                                "access_token"
                                            ]
                                        if tok_json.get("refresh_token"):
                                            self._refresh_token = tok_json[
                                                "refresh_token"
                                            ]

                return self._access_token, self._refresh_token

        except TimeoutError as err:
            raise NexprintApiError("Timed out authenticating with Nexprint") from err
        except (aiohttp.ClientError, ValueError) as err:
            raise NexprintApiError(f"Network/JSON error during login: {err}") from err

    async def async_refresh_access_token(self) -> bool:
        """Attempt to refresh access_token using refresh_token."""
        if not self._refresh_token:
            return False

        try:
            async with asyncio.timeout(15):
                async with self._session.post(
                    f"{BASE_URL}{ENDPOINT_AUTH_TOKEN}",
                    data={
                        "grantType": "refresh_token",
                        "refreshToken": self._refresh_token,
                        "clientId": CLIENT_ID,
                    },
                    headers={
                        **self._headers(json_body=False),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                ) as resp:
                    if resp.status != 200:
                        return False
                    payload = await resp.json(content_type=None)
                    new_access = payload.get("access_token") or (
                        payload.get("data") or {}
                    ).get("access_token")
                    new_refresh = payload.get("refresh_token") or (
                        payload.get("data") or {}
                    ).get("refresh_token")
                    if new_access:
                        self._access_token = str(new_access)
                        if new_refresh:
                            self._refresh_token = str(new_refresh)
                        return True
        except (TimeoutError, aiohttp.ClientError, ValueError):
            return False
        return False

    async def _async_request(
        self, method: str, endpoint: str, *, require_auth: bool = True, **kwargs: Any
    ) -> dict[str, Any]:
        """Make a gateway call with automatic token refresh / re-login."""
        if require_auth and not self._access_token and self._email and self._password:
            await self.async_login_with_password()

        for attempt in range(2):
            try:
                async with asyncio.timeout(15):
                    async with self._session.request(
                        method,
                        f"{BASE_URL}{endpoint}",
                        headers=self._headers(json_body="json" in kwargs),
                        **kwargs,
                    ) as resp:
                        if resp.status in (401, 403):
                            raise NexprintAuthError(f"HTTP {resp.status}")
                        if resp.status >= 400:
                            raise NexprintApiError(f"HTTP {resp.status} on {endpoint}")
                        raw = await resp.json(content_type=None)
                return self._unwrap(raw)
            except NexprintAuthError:
                if attempt == 0 and require_auth:
                    if await self.async_refresh_access_token():
                        continue
                    if self._email and self._password:
                        await self.async_login_with_password()
                        continue
                raise
            except TimeoutError as err:
                raise NexprintApiError(f"Timed out calling {endpoint}") from err
            except (aiohttp.ClientError, ValueError) as err:
                raise NexprintApiError(f"Network/JSON error on {endpoint}: {err}") from err

        raise NexprintAuthError("Unable to authenticate with Nexprint")

    async def async_get_account_data(self) -> NexprintAccountData:
        """Fetch user dashboard stats, points balance, and unread message counts."""
        dashboard_root = await self._async_request("POST", ENDPOINT_USER_DASHBOARD)
        msg_data, points_data = await asyncio.gather(
            self._async_request("GET", ENDPOINT_MESSAGE_STATE),
            self._async_request("GET", ENDPOINT_POINTS_BALANCE),
        )

        user_data = dashboard_root.get("userData") or {}
        stats = dashboard_root.get("userStatistics") or {}
        printers_raw = dashboard_root.get("printerRespVOs") or []
        printers = [
            p.get("printerTypeName")
            for p in printers_raw
            if isinstance(p, dict) and p.get("printerTypeName")
        ]

        # Prefer points-server availableCredits; fall back to dashboard userCreditNow
        available_credits = points_data.get("availableCredits")
        if available_credits is None:
            available_credits = stats.get("userCreditNow") or 0

        sys_unread = int(msg_data.get("systemMessageUnreadNum") or 0)
        fol_unread = int(msg_data.get("followingMessageUnreadNum") or 0)
        com_unread = int(msg_data.get("commentMessageUnreadNum") or 0)
        act_unread = int(msg_data.get("activityMessageUnreadNum") or 0)
        mod_unread = int(msg_data.get("modelMessageUnreadNum") or 0)

        return NexprintAccountData(
            user_id=str(user_data.get("userId") or "unknown"),
            nickname=str(
                user_data.get("nickname")
                or user_data.get("userName")
                or self._email
                or "Nexprint User"
            ),
            email=user_data.get("email"),
            country_name=user_data.get("countryName"),
            avatar_url=user_data.get("avatarUrl"),
            printers=printers,
            following=int(stats.get("userFollowCount") or 0),
            followers=int(stats.get("userFollowerCount") or 0),
            published_models=int(stats.get("userPublishedModelCount") or 0),
            total_likes=int(stats.get("userGetStarPeopleCount") or 0),
            total_favorites=int(stats.get("userGetFavoritePeopleCount") or 0),
            total_downloads=int(stats.get("userGetDownloadCount") or 0),
            total_prints=int(stats.get("userGetPrintCount") or 0),
            points_balance=int(available_credits),
            unread_messages_total=(
                sys_unread + fol_unread + com_unread + act_unread + mod_unread
            ),
            unread_system=sys_unread,
            unread_comments=com_unread,
            unread_following=fol_unread,
            unread_activity=act_unread,
            unread_models=mod_unread,
            raw_user_data=dashboard_root,
        )

    async def async_search_models(
        self, keyword: str, page_no: int = 1, page_size: int = DEFAULT_PAGE_SIZE
    ) -> NexprintSearchResult:
        """Query the Nexprint model search gateway."""
        data = await self._async_request(
            "GET",
            ENDPOINT_SEARCH,
            require_auth=False,
            params={
                "keyword": keyword,
                "pageNo": str(page_no),
                "pageSize": str(page_size),
            },
        )
        raw_list = data.get("list") or data.get("records") or []
        total = int(data.get("total") or len(raw_list))
        models: list[NexprintModelSummary] = []

        for entry in raw_list:
            if not isinstance(entry, dict):
                continue
            item = entry.get("model") if isinstance(entry.get("model"), dict) else entry
            public_id = str(item.get("modelId") or item.get("id") or "")
            internal_id = str(item.get("id") or public_id)
            title = str(item.get("modelName") or item.get("name") or "Unknown Model")
            author_obj = (
                item.get("author") if isinstance(item.get("author"), dict) else {}
            )
            author = (
                item.get("authorName")
                or author_obj.get("nickname")
                or item.get("authorUserId")
            )
            stats = (
                item.get("statistics")
                if isinstance(item.get("statistics"), dict)
                else {}
            )
            models.append(
                NexprintModelSummary(
                    model_id=internal_id,
                    public_id=public_id,
                    title=title,
                    author=str(author) if author else None,
                    url=f"{BASE_URL}/en/models/{public_id}" if public_id else None,
                    downloads=int(stats.get("staticsModelDownloadCount") or 0),
                    likes=int(stats.get("staticsModelStarPeoPleCount") or 0),
                )
            )

        return NexprintSearchResult(keyword=keyword, total=total, models=models)
