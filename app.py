from flask import Flask, request, jsonify, render_template, redirect, session, url_for
import requests
import random
import string
import os

app = Flask(__name__)
# Secret key is required for secure admin login sessions
app.secret_key = "super_secret_key_change_this_in_production" 

# --- SDK Implementations ---
class KhilaadiXProSDK:
    def __init__(self):
        self.base_url = "https://niyope.com/api/"
    
    def create_order(self, customer_mobile, user_token, amount, order_id, redirect_url, remark1, remark2):
        endpoint = self.base_url + "create-order"
        payload = {
            "customer_mobile": customer_mobile,
            "user_token": user_token,
            "amount": amount,
            "order_id": order_id,
            "redirect_url": redirect_url,
            "remark1": remark1,
            "remark2": remark2
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        try:
            response = requests.post(endpoint, data=payload, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": False, "message": "Error in API call"}
        except requests.exceptions.RequestException as e:
            return {"status": False, "message": str(e)}

class OrderStatusSDK:
    def __init__(self):
        self.base_url = "https://niyope.com"

    def check_order_status(self, user_token, order_id):
        url = f"{self.base_url}/api/check-order-status"
        payload = {
            "user_token": user_token,
            "order_id": order_id
        }
        try:
            response = requests.post(url, data=payload)
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "ERROR", "message": "API request failed"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

# --- App Configuration & Mock Database ---
USER_TOKEN = "e8d2a2f1ac98d41d3b7422fd11ab98fa" 

# In-memory database to store orders
orders_db = {}

# Store Configuration (Managed via Admin Panel)
store_config = {
    "product_name": "Premium Web Development eBook",
    "product_price": "199",
    "product_link": "https://example.com/download/ebook.pdf",
    "admin_password": "admin" # Change this password!
}

# --- Customer Facing Routes ---

@app.route('/')
def index():
    return render_template('index.html', 
                           product_name=store_config['product_name'], 
                           price=store_config['product_price'])

@app.route('/checkout', methods=['POST'])
def checkout():
    customer_mobile = request.form.get('mobile')
    order_id = ''.join(random.choices(string.digits, k=10))
    redirect_url = request.host_url + f"success?order_id={order_id}"
    
    orders_db[order_id] = {
        "mobile": customer_mobile,
        "amount": store_config['product_price'],
        "status": "PENDING",
        "product_link": None
    }
    
    sdk = KhilaadiXProSDK()
    result = sdk.create_order(
        customer_mobile=customer_mobile,
        user_token=USER_TOKEN,
        amount=store_config['product_price'],
        order_id=order_id,
        redirect_url=redirect_url,
        remark1="digital_ebook_purchase",
        remark2="web_store"
    )
    
    if result.get("status") == True and "payment_url" in result:
        return redirect(result["payment_url"])
    else:
        return jsonify({"error": "Failed to initialize payment gateway", "details": result}), 400

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.form
    status = data.get('status')
    order_id = data.get('order_id')

    if status == 'SUCCESS':
        if order_id in orders_db:
            orders_db[order_id]['status'] = 'SUCCESS'
            orders_db[order_id]['product_link'] = store_config['product_link']
        return "Webhook received successfully", 200
    else:
        if order_id in orders_db:
            orders_db[order_id]['status'] = 'FAILED'
        return jsonify({"error": f"Invalid status: {status}"}), 400

@app.route('/success')
def success():
    order_id = request.args.get('order_id')
    status_sdk = OrderStatusSDK()
    api_status = status_sdk.check_order_status(USER_TOKEN, order_id)
    order = orders_db.get(order_id)
    
    if order and (order['status'] == 'SUCCESS' or api_status.get('status') == 'SUCCESS'):
        # Ensure order status is updated if SDK catches it before webhook
        orders_db[order_id]['status'] = 'SUCCESS' 
        download_link = store_config['product_link']
        return f"""
        <div style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h1 style="color: green;">Payment Successful! 🎉</h1>
            <p>Thank you for purchasing {store_config['product_name']}.</p>
            <a href="{download_link}" style="padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">Download Your Product</a>
        </div>
        """
    else:
        return """
        <div style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h1 style="color: orange;">Payment Pending</h1>
            <p>We are waiting for the payment gateway confirmation. Please check back in a few minutes.</p>
        </div>
        """

# --- Admin Panel Routes ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == store_config['admin_password']:
            session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid password")
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    # Protect Route
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    
    # Handle Product Updates
    if request.method == 'POST':
        store_config['product_name'] = request.form.get('product_name')
        store_config['product_price'] = request.form.get('product_price')
        store_config['product_link'] = request.form.get('product_link')
        return redirect(url_for('admin_dashboard'))
        
    return render_template('admin.html', config=store_config, orders=orders_db)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
