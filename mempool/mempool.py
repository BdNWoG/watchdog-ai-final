from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import uuid
import re
import threading
import time

app = Flask(__name__)
CORS(app)

# A simple in-memory mempool where keys are transaction IDs.
mempool = {}

# Simple address validation (Ethereum-style address: starts with "0x" followed by 40 hex digits)
def is_valid_address(address):
    return isinstance(address, str) and re.fullmatch(r"0x[a-fA-F0-9]{40}", address)

@app.route('/')
def index():
    return render_template('index.html')

def execute_transaction(tx_id):
    """Function to update the status of a pending transaction to 'executed'."""
    if tx_id in mempool:
        mempool[tx_id]["status"] = "executed"
        print(f"Transaction {tx_id} executed after delay.")

@app.route('/transaction', methods=['GET', 'POST'])
def transactions():
    if request.method == 'GET':
        # List all transactions
        return jsonify(list(mempool.values())), 200
    elif request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No transaction data provided'}), 400

        tx_type = data.get("type")
        # Validate addresses based on transaction type
        if tx_type in ["buy", "sell"]:
            # For buy, require a valid buyer address; for sell, require a valid seller address.
            address_field = "buyer" if tx_type == "buy" else "seller"
            if not is_valid_address(data.get(address_field, "")):
                return jsonify({'error': f'Invalid {address_field} address'}), 400
        elif tx_type in ["add_liquidity", "remove_liquidity"]:
            # For liquidity transactions, require a valid provider address.
            if not is_valid_address(data.get("provider", "")):
                return jsonify({'error': 'Invalid provider address'}), 400
        else:
            # Optionally validate generic "from" and "to" addresses if provided.
            if "from" in data and not is_valid_address(data.get("from", "")):
                return jsonify({'error': 'Invalid from address'}), 400
            if "to" in data and not is_valid_address(data.get("to", "")):
                return jsonify({'error': 'Invalid to address'}), 400

        # Generate a unique transaction ID and store the transaction.
        tx_id = str(uuid.uuid4())
        data['id'] = tx_id

        # Check for MEV boost flag. If True, execute immediately; if False, delay execution.
        mev_boost = data.get("mev_boost", False)
        if mev_boost:
            data["status"] = "executed"
        else:
            data["status"] = "pending"
            # Schedule status update after 10 seconds.
            threading.Timer(10, execute_transaction, args=(tx_id,)).start()

        mempool[tx_id] = data
        return jsonify({'message': 'Transaction added', 'transaction': data}), 201

@app.route('/transaction/<tx_id>', methods=['GET'])
def fetch_transaction(tx_id):
    transaction = mempool.get(tx_id)
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    return jsonify(transaction), 200

@app.route('/transaction/<tx_id>', methods=['DELETE'])
def remove_transaction(tx_id):
    if tx_id in mempool:
        del mempool[tx_id]
        return jsonify({'message': 'Transaction removed'}), 200
    return jsonify({'error': 'Transaction not found'}), 404

if __name__ == '__main__':
    app.run(port=5000, debug=True)
