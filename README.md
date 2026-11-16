# Nexprint for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
<a href="https://buymeacoffee.com/peggleg"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="20"></a>

A custom Home Assistant integration for [Nexprint](https://www.nexprint.com/) (Elegoo's 3D model platform), designed for installation via HACS / Home Assistant Marketplace.

## Features

- **Account Authentication**:
  - **Email & Password**: Uses Elegoo's hybrid AES-128-CBC + RSA-PKCS1v15 authentication flow with automatic OAuth token refresh.
  - Set password under `Profile` > `Settings`
  - **Terms Acceptance**: Enforces explicit acceptance of the Nexprint Terms of Use and Privacy Policy during setup.
- **Account Authentication using Google Session Token**:
  - Open your browser and log in to Nexprint using your Google account (or email).
  - Open Developer Tools (Press F12 or right-click anywhere and select Inspect).
  - Click on the Network tab at the top of the DevTools panel.
  - In the Network filter search box (top left of the Network tab), type: /token
  - Refresh the page
  - Look for a request named token (the URL path will end in /gateway/api/v1/account-center-server/token).
  - Click on that request, then select the Response tab on the right side.
  - Look at the JSON output. You will see your tokens right there (`access_token` & `refresh_token`)
  - **Terms Acceptance**: Enforces explicit acceptance of the Nexprint Terms of Use and Privacy Policy during setup.

In the Network filter search box (top left of the Network tab), type:
  - **Terms Acceptance**: Enforces explicit acceptance of the Nexprint Terms of Use and Privacy Policy during setup.
- **Profile, Creator & Points Sensors**:
  - `Profile` (`sensor.nexprint_<user>_profile`): Nickname, User ID, email, country, configured printers, and avatar URL.
  - `Creator points` (`sensor.nexprint_<user>_creator_points`): Live points balance
  - `Published models` (`sensor.nexprint_<user>_published_models`): Total published models (`userPublishedModelCount`).
  - `Followers` (`sensor.nexprint_<user>_followers`): Total followers (`userFollowerCount`) and following count.
  - `Total likes` (`sensor.nexprint_<user>_total_likes`): Total likes (`userGetStarPeopleCount`) and favorites (`userGetFavoritePeopleCount`).
  - `Total downloads` (`sensor.nexprint_<user>_total_downloads`): Total model downloads (`userGetDownloadCount`) and prints (`userGetPrintCount`).
  - `Unread messages` (`sensor.nexprint_<user>_unread_messages`): Total unread notifications with category breakdown (`system`, `comments`, `following`, `activity`, `models`).

## Installation (HACS / Home Assistant Marketplace)

1. Open **HACS / Marketplace** in Home Assistant.
2. Click the three-dots menu in the top right and select **Custom repositories**.
3. Add the GitHub repository [Nexprint](https://github.com/peggleg/ha-nexprint) with category **Integration**, then install **Nexprint**.
4. Restart Home Assistant.
5. Go to **Settings -> Devices & Services -> Add Integration**, search for **Nexprint**, and sign in.