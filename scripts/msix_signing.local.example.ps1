$env:MSIX_SIGN_CERT_PATH = "D:\\path\\to\\your\\certificate.pfx"
$env:MSIX_SIGN_CERT_PASSWORD = "REPLACE_WITH_CERT_PASSWORD"
$env:MSIX_SIGN_TIMESTAMP_URL = "http://timestamp.digicert.com"

# Optional alternative:
# If you prefer not to keep a .pfx file on disk, provide base64 instead of MSIX_SIGN_CERT_PATH.
# $env:MSIX_SIGN_CERT_BASE64 = "REPLACE_WITH_BASE64_PFX"
