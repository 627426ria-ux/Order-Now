from flask import Flask, render_template_string, request, redirect, url_for
from sheets import save_order
import os
import requests
from werkzeug.utils import secure_filename
from uuid import uuid4

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Telegram Bot credentials
TELEGRAM_BOT_TOKEN = "8487239244:AAGNZeh9CyzGiAQyqrjRCvWfhGmkh4qxKew"
TELEGRAM_CHAT_ID = "7923516574"

# Product prices (same as frontend)
PRICES = {
    "UAE": {
        "P01": 110, "P02": 110, "P03": 110, "P04": 130,
        "P05": 200, "P06": 190, "P07": 260, "P08": 170,
        "P09": 190, "P10": 190
    },
    "India": {
        "P01": 2650, "P02": 2650, "P03": 2650, "P04": 3130,
        "P05": 4800, "P06": 4630, "P07": 6240, "P08": 4090,
        "P09": 4570, "P10": 4570
    }
}

# Read HTML templates (embedded as strings for reliability)
INDEX_HTML = open('templates/index.html', 'r', encoding='utf-8').read()
ORDER_HTML = open('templates/order-form.html', 'r', encoding='utf-8').read()
SUCCESS_HTML = open('templates/success.html', 'r', encoding='utf-8').read()

# -------------------------
# Helper Functions
# -------------------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_order_total(form_data):
    """Calculate order totals just like the frontend does"""
    country = form_data.get("country", "India")
    pids = form_data.getlist("pid[]")
    quantities = form_data.getlist("quantity[]")
    
    subtotal = 0
    product_count = 0
    products_detail = []
    
    # Calculate product subtotal
    for pid, qty_str in zip(pids, quantities):
        if pid and qty_str:
            qty = int(qty_str)
            if qty > 0:
                product_count += 1
                price = PRICES.get(country, {}).get(pid, 0)
                row_total = price * qty
                subtotal += row_total
                products_detail.append({
                    "pid": pid,
                    "qty": qty,
                    "price": price,
                    "total": row_total
                })
    
    # Add additional sheila cost
    additional_sheila = form_data.get("additional_sheila")
    if additional_sheila == "YES":
        sheila_meter = float(form_data.get("sheila_meter", 0))
        if sheila_meter > 2:
            extra_length = sheila_meter - 2
            rate_per_025m = 5 if country == "UAE" else 120
            extra_units = extra_length / 0.25
            sheila_cost = int(extra_units) * rate_per_025m
            subtotal += sheila_cost
            products_detail.append({
                "pid": f"Additional Sheila ({sheila_meter}m)",
                "qty": 1,
                "price": sheila_cost,
                "total": sheila_cost
            })
    
    # Apply discount
    discount = 0
    discount_percentage = 0
    if product_count > 4:
        discount_percentage = 15
        discount = int(subtotal * 0.15)
    elif product_count > 2:
        discount_percentage = 10
        discount = int(subtotal * 0.10)
    
    total = subtotal - discount
    
    # Calculate shipping
    shipping = 0
    free_shipping = False
    if country == "UAE":
        if total >= 330:
            free_shipping = True
        else:
            shipping = 30
    elif country == "India":
        if total >= 8000:
            free_shipping = True
        else:
            fast_delivery = form_data.get("fast_delivery", "NO")
            shipping = 550 if fast_delivery == "YES" else 450
    
    total += shipping
    
    currency = "AED" if country == "UAE" else "₹"
    
    return {
        "products": products_detail,
        "subtotal": subtotal,
        "discount": discount,
        "discount_percentage": discount_percentage,
        "shipping": shipping,
        "free_shipping": free_shipping,
        "total": total,
        "currency": currency,
        "country": country
    }

# -------------------------
# Send Order Notification via Telegram
# -------------------------
def send_confirmation_telegram(form_data, order_id, file_path=""):
    """Send order confirmation with bill to Telegram"""
    
    # Calculate order totals
    bill = calculate_order_total(form_data)
    
    # Build products list
    products_str = ""
    for product in bill["products"]:
        products_str += f"   • {product['pid']} - Qty: {product['qty']} @ {bill['currency']} {product['price']} = {bill['currency']} {product['total']}\n"
    
    # Build bill summary
    bill_str = f"""
💰 **Order Bill:**
{products_str}
━━━━━━━━━━━━━━━━━━━━
Subtotal: {bill['currency']} {bill['subtotal']}
"""
    
    if bill['discount'] > 0:
        bill_str += f"Discount ({bill['discount_percentage']}%): -{bill['currency']} {bill['discount']}\n"
    
    if bill['free_shipping']:
        bill_str += "Shipping: FREE ✓\n"
    else:
        bill_str += f"Shipping: {bill['currency']} {bill['shipping']}\n"
    
    bill_str += f"━━━━━━━━━━━━━━━━━━━━\n"
    bill_str += f"💵 **GRAND TOTAL: {bill['currency']} {bill['total']}**\n"
    
    # Get address info based on country
    if bill['country'] == "UAE":
        address_str = f"""
📍 **Delivery Address (UAE):**
   {form_data.get('apartment_number')}, {form_data.get('house_name')}
   {form_data.get('street_name_uae')}
   {form_data.get('area_name')}, {form_data.get('emirate')}
   Landmark: {form_data.get('landmark')}
"""
    else:
        address_str = f"""
📍 **Delivery Address (India):**
   {form_data.get('house')}
   {form_data.get('street_name')}
   {form_data.get('city')}, {form_data.get('district')}
   Pincode: {form_data.get('pincode')}
"""
    
    body = f"""
🆕 **NEW ORDER RECEIVED**
━━━━━━━━━━━━━━━━━━━━

📌 **Order ID:** {order_id}

👤 **Customer Details:**
   • Name: {form_data.get('full_name')}
   • Email: {form_data.get('email')}
   • Contact: {form_data.get('contact_number')}
   • Instagram: {form_data.get('insta_username')}

📦 **Product Details:**
{products_str}

   • Additional Requirements: {form_data.get('Additional_Requirements', 'None')}
   • Additional Sheila: {form_data.get('additional_sheila', 'NO')}

{bill_str}

{address_str}

📝 **Queries:** {form_data.get('queries', 'None')}

━━━━━━━━━━━━━━━━━━━━
✓ Payment screenshot attached below
"""
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": body,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Telegram message sent successfully")
            
            if file_path and os.path.exists(file_path):
                send_telegram_photo(file_path, order_id)
        else:
            print("❌ Failed to send Telegram message:", response.text)
    except Exception as e:
        print("❌ Exception while sending Telegram message:", e)

def send_telegram_photo(file_path, order_id):
    """Send payment screenshot to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    
    try:
        with open(file_path, 'rb') as photo:
            files = {'photo': photo}
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': f"💳 Payment Screenshot - Order {order_id}"
            }
            response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                print("✅ Payment screenshot sent to Telegram")
            else:
                print("❌ Failed to send photo:", response.text)
    except Exception as e:
        print(f"❌ Error sending photo to Telegram: {e}")

# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    """Landing page"""
    return render_template_string(INDEX_HTML)

@app.route("/order-form", methods=["GET", "POST"])
def order_form():
    """Order form page"""
    if request.method == "POST":
        try:
            form_data = request.form
            print("📝 Received form data")
            
            temp_order_id = str(uuid4()).replace("-", "").upper()[:12]
            
            # Handle file upload
            saved_file_path = ""
            if 'payment_screenshot' in request.files:
                file = request.files['payment_screenshot']
                
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    saved_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{temp_order_id}_{filename}")
                    file.save(saved_file_path)
                    print(f"📁 File saved: {saved_file_path}")
            
            # Save order to Google Sheets
            order_id = save_order(form_data, "Payment screenshot attached" if saved_file_path else "")
            print(f"📦 Order saved: {order_id}")
            
            # Send Telegram notification with bill
            send_confirmation_telegram(form_data, order_id, saved_file_path)
            
            # Important: Use _external=True for redirect
            return redirect(url_for("success", order_id=order_id, _external=False))
            
        except Exception as e:
            print(f"❌ Error processing order: {e}")
            import traceback
            traceback.print_exc()
            return f"<h1>Error processing order</h1><p>{str(e)}</p><a href='/order'>Go back</a>", 500
    
    # Render order form
    return render_template_string(ORDER_HTML)

@app.route("/success")
def success():
    """Order success page"""
    order_id = request.args.get("order_id", "UNKNOWN")
    
    # Replace the placeholder in the success HTML
    success_page = SUCCESS_HTML.replace("'{{ order_id }}'", f"'{order_id}'")
    success_page = success_page.replace("{{ order_id }}", order_id)
    
    return render_template_string(success_page)

@app.route("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "message": "Server is running"}, 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5009))
    app.run(debug=True, host="0.0.0.0", port=port)