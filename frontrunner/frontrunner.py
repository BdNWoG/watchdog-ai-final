from flask import Flask, request, jsonify, render_template
import requests
import time
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)

# URLs for mempool and token API
MEMPOOL_URL = "http://localhost:5000/transaction"

# Thresholds for suspicious transactions:
FRONT_RUN_THRESHOLD_LIQUIDITY = 150000.0  # For Type 1 attack (liquidity removal)
LARGE_SELL_THRESHOLD = 800000.0            # For Type 2 attack (sell orders)

# URL for trader update endpoint (trader.py)
TRADER_UPDATE_URL = "http://localhost:5004/api/autotrade/update"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/suspicious', methods=['GET'])
def get_suspicious():
    """
    Poll the mempool for transactions and filter for suspicious ones.
    For Type 1: remove_liquidity transactions with an amount >= FRONT_RUN_THRESHOLD_LIQUIDITY.
    For Type 2: sell transactions with an amount >= LARGE_SELL_THRESHOLD.
    """
    try:
        response = requests.get(MEMPOOL_URL)
        if not response.ok:
            return jsonify({"error": "Failed to fetch mempool data"}), 500
        transactions = response.json()
        suspicious = []
        for tx in transactions:
            tx_type = tx.get("type", "").lower()
            try:
                amount = float(tx.get("amount", 0))
            except Exception:
                continue
            if tx_type == "remove_liquidity" and amount >= FRONT_RUN_THRESHOLD_LIQUIDITY:
                suspicious.append(tx)
            elif tx_type == "sell" and amount >= LARGE_SELL_THRESHOLD:
                suspicious.append(tx)
        return jsonify(suspicious), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/frontrun', methods=['POST'])
def execute_frontrun():
    """
    Execute a frontrun attack based on the suspicious transaction.
    For a liquidity removal (Type 1): 
      - Execute a frontrun removal with MEV boost,
      - Wait 15 seconds,
      - Execute a back-run addition.
    For a large sell (Type 2):
      - Execute a frontrun buy with MEV boost,
      - Wait 15 seconds,
      - Execute a back-run sell.
    The request JSON should include:
      - tx_id: ID of the suspicious transaction.
      - type: "remove_liquidity" or "sell"
      - amount: the USD amount in the suspicious transaction.
    """
    data = request.get_json()
    tx_id = data.get("tx_id")
    if not tx_id:
        return jsonify({"error": "No transaction ID provided"}), 400

    # Fetch transaction details from the mempool.
    try:
        tx_response = requests.get(f"{MEMPOOL_URL}/{tx_id}")
        if not tx_response.ok:
            return jsonify({"error": "Transaction not found in mempool"}), 404
        tx = tx_response.json()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    tx_type = tx.get("type", "").lower()
    try:
        amount = float(tx.get("amount", 0))
    except Exception:
        return jsonify({"error": "Invalid amount in transaction"}), 400

    if tx_type == "remove_liquidity" and amount >= FRONT_RUN_THRESHOLD_LIQUIDITY:
        try:
            frontrun_amount = round(amount * 1.1, 2)
            removal_payload = {
                "type": "remove_liquidity",
                "provider": "0x6a038a9481dd46186da3cf63e7e2d85398abc047",
                "amount": str(frontrun_amount),
                "mev_boost": True,
                "status": "executed"
            }
            removal_payload['id'] = str(uuid.uuid4())
            removal_response = requests.post(MEMPOOL_URL, json=removal_payload)
            if not removal_response.ok:
                return jsonify({"error": "Type 1 front-run removal failed", "details": removal_response.text}), 500

            time.sleep(15)

            addition_payload = {
                "type": "add_liquidity",
                "provider": "0x6a038a9481dd46186da3cf63e7e2d85398abc047",
                "amount": str(frontrun_amount),
                "mev_boost": True,
                "status": "executed"
            }
            addition_payload['id'] = str(uuid.uuid4())
            addition_response = requests.post(MEMPOOL_URL, json=addition_payload)
            if not addition_response.ok:
                return jsonify({"error": "Type 1 back-run addition failed", "details": addition_response.text}), 500

            # Update trader's dashboard with autotrade details.
            update_payload = {
                "trade_type": "remove_liquidity",
                "amount": frontrun_amount,
                "details": "Type 1 autotrade: removed liquidity then added liquidity after 15 sec."
            }
            requests.post(TRADER_UPDATE_URL, json=update_payload)
            return jsonify({"message": f"Type 1 autotrade executed: removed liquidity {frontrun_amount} and added liquidity after 15 sec."}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif tx_type == "sell" and amount >= LARGE_SELL_THRESHOLD:
        try:
            frontrun_buy_amount = round(amount * 1.05, 2)
            buy_payload = {
                "type": "buy",
                "buyer": "0x6a038a9481dd46186da3cf63e7e2d85398abc047",
                "amount": str(frontrun_buy_amount),
                "mev_boost": True,
                "status": "executed"
            }
            buy_payload['id'] = str(uuid.uuid4())
            buy_response = requests.post(MEMPOOL_URL, json=buy_payload)
            if not buy_response.ok:
                return jsonify({"error": "Type 2 front-run buy failed", "details": buy_response.text}), 500

            time.sleep(15)

            sell_payload = {
                "type": "sell",
                "seller": "0x6a038a9481dd46186da3cf63e7e2d85398abc047",
                "amount": str(frontrun_buy_amount),
                "mev_boost": True,
                "status": "executed"
            }
            sell_payload['id'] = str(uuid.uuid4())
            sell_response = requests.post(MEMPOOL_URL, json=sell_payload)
            if not sell_response.ok:
                return jsonify({"error": "Type 2 back-run sell failed", "details": sell_response.text}), 500

            # Update trader's dashboard with autotrade details.
            update_payload = {
                "trade_type": "sell",
                "amount": frontrun_buy_amount,
                "details": "Type 2 autotrade: sandwich attack executed."
            }
            requests.post(TRADER_UPDATE_URL, json=update_payload)
            return jsonify({"message": f"Type 2 autotrade executed: sandwich attack bought and sold {frontrun_buy_amount}"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Transaction type does not match any autotrade strategy"}), 400

@app.route('/api/activate_monitoring', methods=['POST'])
def activate_monitoring():
    data = request.get_json() or {}
    token_address = data.get("token_address", "unknown")
    return jsonify({"message": f"Frontrunner monitoring activated for token {token_address}"}), 200

if __name__ == '__main__':
    app.run(port=5003, debug=True)
