import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid
import os

# -------------------------
# Google Sheets Setup
# -------------------------
def get_credentials():
    """Get Google API credentials"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    # Use Render secret file path if exists
    creds_path = "/etc/secrets/credentials.json"
    if not os.path.exists(creds_path):
        creds_path = "secrets/credentials.json"  # fallback for local testing
    
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    return creds

def get_sheet():
    """Get Google Sheets client"""
    creds = get_credentials()
    client = gspread.authorize(creds)
    sheet = client.open("Loom Abayas Orders").sheet1
    return sheet

# -------------------------
# Save Order
# -------------------------
def save_order(form_data: dict, payment_screenshot_link: str = ""):
    """
    Save order to Google Sheets
    
    Args:
        form_data: Dictionary containing form data
        payment_screenshot_link: Text note about payment screenshot (e.g., "Payment screenshot attached")
    
    Returns:
        str: Generated order ID
    """
    # Generate fully unique Order ID
    order_id = str(uuid.uuid4()).replace("-", "").upper()[:12]
    
    # Build address
    address_parts = [
        form_data.get("house", ""),
        form_data.get("street_name", ""),
        form_data.get("city", ""),
        form_data.get("district", ""),
        form_data.get("pincode", ""),
        form_data.get("country", "")
    ]
    address = ", ".join([part for part in address_parts if part])
    
    # Get product details (handle multiple products)
    pids = form_data.getlist("pid[]") if hasattr(form_data, 'getlist') else [form_data.get("pid", "")]
    quantities = form_data.getlist("quantity[]") if hasattr(form_data, 'getlist') else [form_data.get("quantity", "1")]
    
    # Combine products into a string
    products_str = "; ".join([f"{pid} (Qty: {qty})" for pid, qty in zip(pids, quantities)])
    
    # Prepare row
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
        payment_screenshot_link  # Note about payment screenshot
    ]
    
    sheet = get_sheet()
    sheet.append_row(row, value_input_option="USER_ENTERED")
    print(f"✅ Order {order_id} saved to Google Sheets")
    
    return order_id