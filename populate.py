import requests
import random
import time

# The mempool service's endpoint for adding transactions
MEMPOOL_URL = "http://localhost:5000/transaction"

# Define possible transaction types
transaction_types = ["buy", "sell", "add_liquidity"]

def random_address():
    """Generate a random Ethereum-style address."""
    return "0x" + "".join(random.choices("0123456789abcdef", k=40))

def create_transaction(tx_type):
    """Generate a random transaction payload based on the type with mev_boost set to False."""
    amount = round(random.uniform(1000, 100000), 2)
    payload = {"type": tx_type, "amount": amount, "mev_boost": False}
    if tx_type == "buy":
        payload["buyer"] = random_address()
    elif tx_type == "sell":
        payload["seller"] = random_address()
    elif tx_type == "add_liquidity":
        payload["provider"] = random_address()
    return payload

def populate_transactions(num_transactions=20):
    """Post a number of random, unboosted transactions to the mempool service."""
    for i in range(num_transactions):
        tx_type = random.choice(transaction_types)
        payload = create_transaction(tx_type)
        try:
            response = requests.post(MEMPOOL_URL, json=payload)
            if response.ok:
                print(f"Transaction {i+1}/{num_transactions} added: {response.json()}")
            else:
                print(f"Error adding transaction: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Exception adding transaction: {e}")
        # Small delay between transactions
        time.sleep(0.2)

if __name__ == '__main__':
    print("Populating mempool with random unboosted transactions...")
    populate_transactions(20)
    print("Done!")
