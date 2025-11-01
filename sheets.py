import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid
import os
import json

# -------------------------
# Google Sheets Setup
# -------------------------
def get_credentials():
    """Load Google API credentials from Render environment or local file"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    # 1️⃣ Check if credentials are provided as environment variable (Render)
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return creds

    # 2️⃣ Fallback to local file for local testing
    creds_path = "secrets/credentials.json"
    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            "Google credentials not found. Set GOOGLE_CREDENTIALS_JSON in Render or place credentials.json in secrets/."
        )
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    return creds


def get_sheet():
    """Authorize and return the Google Sheet"""
    creds = get_credentials()
    client = gspread.authorize(creds)
    sheet = client.open("Loom Abayas Orders").sheet1
    return sheet


# -------------------------
# Save Order
# -------------------------
def save_order(form_data: dict, payment_screenshot_link: str = ""):
    """
    Save order details to Google Sheets

    Args:
        form_data: Dictionary containing the form submission data
        payment_screenshot_link: Text note about payment screenshot
    Returns:
        str: Generated order ID
    """
    order_id = str(uuid.uuid4()).replace("-", "").upper()[:12]

    # Build address string
    address_parts = [
        form_data.get("house", ""),
        form_data.get("street_name", ""),
        form_data.get("city", ""),
        form_data.get("district", ""),
        form_data.get("pincode", ""),
        form_data.get("country", "")
    ]
    address = ", ".join([part for part in address_parts if part])

    # Extract product details
    pids = form_data.getlist("pid[]") if hasattr(form_data, "getlist") else [form_data.get("pid", "")]
    quantities = form_data.getlist("quantity[]") if hasattr(form_data, "getlist") else [form_data.get("quantity", "1")]

    # Combine into readable string
    products_str = "; ".join([f"{pid} (Qty: {qty})" for pid, qty in zip(pids, quantities)])

    # Prepare the row to insert
    row = [
        order_id,
        form_data.get("full_name", ""),
        form_data.get("email", ""),
        form_data.get("insta_username", ""),
        products_str,
        form_data.get("abaya_size", ""),
        form_data.get("custom_size", ""),
        form_data.get("Additional_Requirements", ""),
        form_data.get("additional_sheila", ""),
        form_data.get("sheila_meter", ""),
        address,
        form_data.get("contact_number", ""),
        form_data.get("queries", ""),
        payment_screenshot_link
    ]

    # Append to Google Sheet
    sheet = get_sheet()
    sheet.append_row(row, value_input_option="USER_ENTERED")
    print(f"✅ Order {order_id} saved to Google Sheets")

    return order_id
