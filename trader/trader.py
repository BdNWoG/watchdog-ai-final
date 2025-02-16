from flask import Flask, jsonify, render_template, request
import requests
import random
import time
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)

# Simulated trader portfolio.
portfolio = {
    "liquidity": 100000.0,      # Cash in USD
    "assets": { "TOKEN": 5000 }, # Quantity of TOKEN owned
    "initial_value": 100000.0    # Initial portfolio value (USD)
}

# Global variable to track WatchdogAI status.
watchdog_activated = True

# For simulation, record portfolio total value history.
portfolio_history = []

trade_log = []

# URL of the memecoin dashboard (running on port 5001)
MEMECOIN_DASHBOARD_URL = "http://localhost:5001/dashboard"

def fetch_asset_price():
    """
    Pull the current asset price from the memecoin dashboard.
    If any error occurs, default to 1.0.
    """
    try:
        response = requests.get(MEMECOIN_DASHBOARD_URL)
        if response.ok:
            data = response.json()
            return float(data.get("current_price", 1.0))
        else:
            return 1.0
    except Exception as e:
        print("Error fetching asset price:", e)
        return 1.0

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    asset_price = fetch_asset_price()
    asset_value = portfolio['assets'].get("TOKEN", 0) * asset_price
    total_value = portfolio["liquidity"] + asset_value
    pnl = total_value - portfolio["initial_value"]

    data = {
        "liquidity": round(portfolio["liquidity"], 2),
        "assets": portfolio["assets"],
        "asset_price": asset_price,
        "total_value": round(total_value, 2),
        "pnl": round(pnl, 2),
        "trade_log": trade_log
    }
    # Record the total value with a timestamp.
    portfolio_history.append({"timestamp": time.strftime("%H:%M:%S"), "total_value": data["total_value"]})
    # Limit history to the last 50 points.
    if len(portfolio_history) > 50:
        del portfolio_history[0]
    data["history"] = portfolio_history
    return jsonify(data)

@app.route('/api/trade', methods=['POST'])
def trade():
    """
    Simulate a normal trade (unboosted). Request JSON must include:
    - type: "buy" or "sell"
    - amount: the USD amount to trade.
    For a buy: subtract liquidity, add TOKEN at the current price.
    For a sell: subtract TOKEN, add liquidity.
    """
    data = request.get_json()
    trade_type = data.get("type")
    try:
        amount = float(data.get("amount", 0))
    except Exception:
        return jsonify({"error": "Invalid amount"}), 400

    asset_price = fetch_asset_price()

    if trade_type == "buy":
        tokens_bought = amount / asset_price
        if amount > portfolio["liquidity"]:
            return jsonify({"error": "Not enough liquidity to buy"}), 400
        portfolio["liquidity"] -= amount
        portfolio["assets"]["TOKEN"] = portfolio["assets"].get("TOKEN", 0) + tokens_bought
        message = f"Bought {round(tokens_bought,2)} TOKEN at ${asset_price}"
    elif trade_type == "sell":
        tokens_to_sell = amount / asset_price
        if tokens_to_sell > portfolio["assets"].get("TOKEN", 0):
            return jsonify({"error": "Not enough TOKEN to sell"}), 400
        portfolio["assets"]["TOKEN"] -= tokens_to_sell
        portfolio["liquidity"] += amount
        message = f"Sold {round(tokens_to_sell,2)} TOKEN at ${asset_price}"
    else:
        return jsonify({"error": "Invalid trade type"}), 400

    # Log the trade.
    trade_log.insert(0, {
        "id": str(uuid.uuid4()),
        "trade_type": trade_type,
        "amount": amount,
        "source": "User",
        "timestamp": time.strftime("%H:%M:%S")
    })

    return jsonify({"message": message, "portfolio": portfolio, "mev_boost": False})

@app.route('/api/autotrade', methods=['POST'])
def autotrade():
    """
    Execute an autotrade triggered by WatchdogAI.
    Request JSON must include:
      - type: "buy" or "sell" (for simplicity, we assume a buy in our example)
      - amount: USD amount to execute.
    This endpoint updates the portfolio and records the trade in the log.
    """
    data = request.get_json()
    trade_type = data.get("type")
    try:
        amount = float(data.get("amount", 0))
    except Exception:
        return jsonify({"error": "Invalid amount"}), 400

    asset_price = fetch_asset_price()

    if trade_type == "buy":
        tokens_bought = amount / asset_price
        if amount > portfolio["liquidity"]:
            return jsonify({"error": "Not enough liquidity for autotrade"}), 400
        portfolio["liquidity"] -= amount
        portfolio["assets"]["TOKEN"] = portfolio["assets"].get("TOKEN", 0) + tokens_bought
        message = f"Auto-bought {round(tokens_bought,2)} TOKEN at ${asset_price}"
    elif trade_type == "sell":
        tokens_to_sell = amount / asset_price
        if tokens_to_sell > portfolio["assets"].get("TOKEN", 0):
            return jsonify({"error": "Not enough TOKEN for autotrade"}), 400
        portfolio["assets"]["TOKEN"] -= tokens_to_sell
        portfolio["liquidity"] += amount
        message = f"Auto-sold {round(tokens_to_sell,2)} TOKEN at ${asset_price}"
    else:
        return jsonify({"error": "Invalid trade type for autotrade"}), 400

    # Record the autotrade in the trade log.
    log_entry = {
        "id": str(uuid.uuid4()),
        "trade_type": trade_type,
        "amount": amount,
        "source": "Auto",
        "timestamp": time.strftime("%H:%M:%S")
    }
    trade_log.insert(0, log_entry)

    return jsonify({"message": message, "portfolio": portfolio, "log": log_entry})

@app.route('/api/watchdog', methods=['GET'])
def watchdog_status():
    # Return the current status of WatchdogAI.
    return jsonify({"activated": watchdog_activated})

@app.route('/api/toggle_watchdog', methods=['POST'])
def toggle_watchdog():
    global watchdog_activated
    # Toggle the WatchdogAI status.
    watchdog_activated = not watchdog_activated
    status = "Activated" if watchdog_activated else "Deactivated"
    return jsonify({"message": f"WatchdogAI is now {status}", "activated": watchdog_activated})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # Run on port 5004.
    app.run(port=5004, debug=True)
