import requests
import random
import time
import uuid

# The mempool service's endpoint for adding transactions
MEMPOOL_URL = "http://localhost:5000/transaction"

def random_address():
    """Generate a random Ethereum-style address."""
    return "0x" + "".join(random.choices("0123456789abcdef", k=40))

def create_suspicious_transaction(tx_type):
    """Generate a suspicious transaction payload based on type with large amounts."""
    # For suspicious transactions, we use amounts that are significantly higher.
    if tx_type == "buy":
        # Suspicious buy: amount between 200,000 and 300,000 USD
        amount = round(random.uniform(60000, 100000), 2)
        return {"type": "buy", "amount": amount, "buyer": random_address(), "mev_boost": False}
    elif tx_type == "sell":
        # Suspicious sell: amount between 60000 and 100000 USD
        amount = round(random.uniform(60000, 200000), 2)
        return {"type": "sell", "amount": amount, "seller": random_address(), "mev_boost": False}
    elif tx_type == "add_liquidity":
        # Suspicious add liquidity: amount between 500000 and 600000 USD
        amount = round(random.uniform(110000, 200000), 2)
        return {"type": "add_liquidity", "amount": amount, "provider": random_address(), "mev_boost": False}
    elif tx_type == "remove_liquidity":
        # Suspicious remove liquidity: amount between 110000 and 200000 USD (above typical threshold)
        amount = round(random.uniform(50000, 60000), 2)
        return {"type": "remove_liquidity", "amount": amount, "provider": random_address(), "mev_boost": False}
    else:
        return None

def populate_suspicious_transactions(num_transactions=5):
    tx_types = ["buy", "add_liquidity"]
    for i in range(num_transactions):
        tx_type = random.choice(tx_types)
        payload = create_suspicious_transaction(tx_type)
        if payload is None:
            continue
        # Generate a unique transaction ID for consistency with mempool expectations.
        payload["id"] = str(uuid.uuid4())
        try:
            response = requests.post(MEMPOOL_URL, json=payload)
            if response.ok:
                print(f"Suspicious Transaction {i+1}/{num_transactions} added: {response.json()}")
            else:
                print(f"Error adding suspicious transaction: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Exception adding suspicious transaction: {e}")
        # Small delay between transactions
        time.sleep(0.2)

if __name__ == '__main__':
    print("Populating mempool with suspicious transactions...")
    populate_suspicious_transactions(10)
    print("Done!")
