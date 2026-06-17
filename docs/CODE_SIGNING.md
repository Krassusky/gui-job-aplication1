# Code signing guide (Windows + macOS)

Unsigned builds work, but the OS shows security warnings on first launch:

| Platform | What users see (unsigned) | Workaround without signing |
|----------|---------------------------|----------------------------|
| **Windows** | SmartScreen: "Windows protected your PC" | More info → Run anyway |
| **macOS** | "cannot be opened because the developer cannot be verified" | Right-click → Open → Open |

Signing removes (or greatly reduces) these warnings for normal users.

---

## macOS — Developer ID + notarization

**Cost:** Apple Developer Program — about **$99 USD/year**  
**Required for:** Smooth installs on MacBooks (especially Apple Silicon)

### 1. Enroll and create certificates

1. Join https://developer.apple.com/programs/
2. Open **Xcode → Settings → Accounts → Manage Certificates**
3. Create **Developer ID Application** (for distribution outside the App Store)

### 2. Export a `.p12` for CI

1. Keychain Access → export the **Developer ID Application** cert as `.p12`
2. Set a strong password

### 3. Sign and notarize locally (on a Mac)

After `pyinstaller autoapply.spec` and `bash scripts/ci_package.sh`:

```bash
export APPLE_SIGNING_IDENTITY="Developer ID Application: Your Name (TEAMID)"
codesign --deep --force --options runtime --timestamp \
  --sign "$APPLE_SIGNING_IDENTITY" dist/JobApplyAssistant.app

xcrun notarytool submit dist/JobApplyAssistant-1.0.1-mac-arm64.zip \
  --apple-id "you@email.com" \
  --password "app-specific-password" \
  --team-id "TEAMID" \
  --wait
```

Create an **app-specific password** at https://appleid.apple.com (Security → App-Specific Passwords).

### 4. Automate in GitHub Actions (optional)

Add these **repository secrets**:

| Secret | Value |
|--------|--------|
| `APPLE_CERTIFICATE` | Base64-encoded `.p12` file |
| `APPLE_CERTIFICATE_PASSWORD` | `.p12` export password |
| `APPLE_SIGNING_IDENTITY` | e.g. `Developer ID Application: Your Name (ABC123XYZ)` |
| `APPLE_ID` | Apple ID email |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password |
| `APPLE_TEAM_ID` | 10-character Team ID |

The Release workflow imports the certificate when these secrets exist, then `scripts/ci_package.sh` signs and notarizes the zip.

**Note:** Notarization requires running on `macos-latest` (real Apple hardware). Self-signed certs do **not** satisfy Gatekeeper.

---

## Windows — Authenticode

**Cost:** Code signing certificate — roughly **$200–400 USD/year** (DigiCert, Sectigo, SSL.com, etc.)  
**Required for:** Avoiding SmartScreen warnings for unknown publishers

### 1. Buy an OV or EV certificate

- **EV (Extended Validation)** — SmartScreen trust builds faster (recommended for public downloads)
- **OV (Organization Validation)** — cheaper; reputation builds slowly over time

### 2. Sign the executable

With `signtool` (Windows SDK) or `osslsigncode` on Linux CI:

```powershell
signtool sign /fd SHA256 /f certificate.pfx /p "password" `
  /tr http://timestamp.digicert.com /td SHA256 `
  dist\JobApplyAssistant\JobApplyAssistant.exe
```

### 3. Automate in GitHub Actions (optional)

| Secret | Value |
|--------|--------|
| `WINDOWS_CERTIFICATE_BASE64` | Base64-encoded `.pfx` |
| `WINDOWS_CERTIFICATE_PASSWORD` | `.pfx` password |

`scripts/ci_package.sh` signs `JobApplyAssistant.exe` before zipping when these secrets are set.

---

## What signing does **not** fix

- **Virus scanners** flagging automation tools — unrelated to code signing
- **LinkedIn ToS** — signing does not make automation allowed
- **Free self-signed certs** — Windows and macOS still warn users

---

## Recommended path for this project

| Stage | Approach |
|-------|----------|
| **Friend testing (now)** | Unsigned zip + LEIA-ME instructions (Open anyway / Right-click Open) |
| **Wider Mac distribution** | Apple Developer + notarization |
| **Wider Windows distribution** | EV Authenticode certificate |

For a single friend on a MacBook, unsigned `mac-arm64` build with the right-click **Open** instructions is usually enough.
