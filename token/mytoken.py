from flask import Flask, request, jsonify, render_template
import requests
import datetime
import time
import threading
from flask_cors import CORS
import uuid
import re

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

# URL of the mempool service (running on port 5000)
MEMPOOL_URL = "http://localhost:5000"

# A simulated starting liquidity value
INITIAL_LIQUIDITY = 1000000

# Total token circulation (for trading impact calculation)
TOTAL_CIRCULATION = 1000000

# Global list to store computed prices over time.
price_history = []

def fetch_mempool_transactions():
    """Helper function to fetch all transactions from the mempool."""
    try:
        response = requests.get(f"{MEMPOOL_URL}/transaction")
        if response.ok:
            return response.json()
        else:
            return []
    except Exception as e:
        print("Error fetching mempool transactions:", e)
        return []

def compute_liquidity(transactions):
    """
    Compute current liquidity as:
      INITIAL_LIQUIDITY + (sum of all 'add_liquidity' amounts) - (sum of all 'remove_liquidity' amounts)
    Only consider transactions with status "executed".
    """
    add_liq = sum(float(tx.get("amount", 0)) for tx in transactions 
                  if tx.get("type") == "add_liquidity" and tx.get("status") == "executed")
    remove_liq = sum(float(tx.get("amount", 0)) for tx in transactions 
                     if tx.get("type") == "remove_liquidity" and tx.get("status") == "executed")
    return INITIAL_LIQUIDITY + add_liq - remove_liq

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """
    Returns dashboard data:
      - volume: total buy + sell amount (sum of absolute amounts from executed buy/sell transactions)
      - liquidity: computed from executed liquidity transactions
      - current_price: computed price based on liquidity and trading impact from executed transactions
      - history: a list of {timestamp, price} entries (the price history)
    """
    transactions = fetch_mempool_transactions()

    # Only include executed transactions in calculations.
    executed_tx = [tx for tx in transactions if tx.get("status") == "executed"]

    # Compute volume for display (only for executed buy and sell transactions)
    volume = sum(abs(float(tx.get("amount", 0))) for tx in executed_tx if tx.get("type") in ["buy", "sell"])
    
    # Compute liquidity and factors.
    liquidity = compute_liquidity(executed_tx)
    liquidity_factor = liquidity / INITIAL_LIQUIDITY

    # Calculate trading impact from executed buy and sell transactions.
    trading_factor = 1.0
    for tx in executed_tx:
        tx_type = tx.get("type")
        amt = float(tx.get("amount", 0))
        if tx_type == "buy":
            trading_factor *= (1 + 0.01 * (amt / TOTAL_CIRCULATION))
        elif tx_type == "sell":
            trading_factor *= (1 - 0.01 * (amt / TOTAL_CIRCULATION))
    
    base_price = 1.0
    new_price = base_price * liquidity_factor * trading_factor

    # Append the new computed price to the global price history.
    current_time = datetime.datetime.now()
    price_history.append({
        "timestamp": current_time.strftime("%H:%M:%S"),
        "price": round(new_price, 4)
    })
    # Limit history to the last 50 data points.
    if len(price_history) > 50:
        del price_history[0]

    return jsonify({
        "volume": round(volume, 2),
        "liquidity": liquidity,
        "current_price": round(new_price, 4),
        "history": price_history
    })

def forward_transaction(payload):
    """
    Helper to forward a transaction payload to the mempool.
    The mempool endpoint is assumed to be POST /transaction.
    If the payload does NOT include "mev_boost": true, a 10-second delay is scheduled before
    marking the transaction as executed.
    """
    try:
        response = requests.post(f"{MEMPOOL_URL}/transaction", json=payload)
        if not payload.get("mev_boost", False):
            tx_id = payload.get("id")
            if tx_id:
                threading.Timer(10, execute_transaction, args=(tx_id,)).start()
        return response.json(), response.status_code
    except Exception as e:
        return {"error": str(e)}, 500

def execute_transaction(tx_id):
    """
    Update the transaction's status from "pending" to "executed" in the mempool.
    """
    try:
        response = requests.get(f"{MEMPOOL_URL}/transaction/{tx_id}")
        if response.ok:
            tx = response.json()
            if tx.get("status") == "pending":
                tx["status"] = "executed"
                requests.delete(f"{MEMPOOL_URL}/transaction/{tx_id}")
                requests.post(f"{MEMPOOL_URL}/transaction", json=tx)
                print(f"Transaction {tx_id} status updated to executed after delay.")
    except Exception as e:
        print("Error executing transaction:", e)

@app.route('/buy', methods=['POST'])
def buy_tokens():
    data = request.get_json()
    buyer = data.get('buyer')
    amount = data.get('amount')
    if not buyer or not amount:
        return jsonify({'error': 'Missing buyer or amount'}), 400

    payload = {
        'type': 'buy',
        'buyer': buyer,
        'amount': amount,
        'mev_boost': data.get('mev_boost', False),
        'status': "executed" if data.get('mev_boost', False) else "pending"
    }
    payload['id'] = str(uuid.uuid4())
    resp, status = forward_transaction(payload)
    return jsonify(resp), status

@app.route('/sell', methods=['POST'])
def sell_tokens():
    data = request.get_json()
    seller = data.get('seller')
    amount = data.get('amount')
    if not seller or not amount:
        return jsonify({'error': 'Missing seller or amount'}), 400

    payload = {
        'type': 'sell',
        'seller': seller,
        'amount': amount,
        'mev_boost': data.get('mev_boost', False),
        'status': "executed" if data.get('mev_boost', False) else "pending"
    }
    payload['id'] = str(uuid.uuid4())
    resp, status = forward_transaction(payload)
    return jsonify(resp), status

@app.route('/add_liquidity', methods=['POST'])
def add_liquidity():
    data = request.get_json()
    provider = data.get('provider')
    amount = data.get('amount')
    if not provider or not amount:
        return jsonify({'error': 'Missing provider or amount'}), 400

    payload = {
        'type': 'add_liquidity',
        'provider': provider,
        'amount': amount,
        'mev_boost': data.get('mev_boost', False),
        'status': "executed" if data.get('mev_boost', False) else "pending"
    }
    payload['id'] = str(uuid.uuid4())
    resp, status = forward_transaction(payload)
    return jsonify(resp), status

@app.route('/remove_liquidity', methods=['POST'])
def remove_liquidity():
    data = request.get_json()
    provider = data.get('provider')
    amount = data.get('amount')
    if not provider or not amount:
        return jsonify({'error': 'Missing provider or amount'}), 400

    try:
        removal_amt = float(amount)
    except Exception:
        return jsonify({'error': 'Invalid amount'}), 400

    # Check current liquidity to avoid over-removal.
    transactions = fetch_mempool_transactions()
    current_liquidity = compute_liquidity(transactions)

    payload = {
        'type': 'remove_liquidity',
        'provider': provider,
        'amount': amount,
        'mev_boost': data.get('mev_boost', False),
        'status': "executed" if data.get('mev_boost', False) else "pending"
    }
    payload['id'] = str(uuid.uuid4())
    resp, status = forward_transaction(payload)
    return jsonify(resp), status

if __name__ == '__main__':
    app.run(port=5001, debug=True)
