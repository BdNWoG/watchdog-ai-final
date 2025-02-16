from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import requests
import random
import json
import openai
import os
from dotenv import load_dotenv

load_dotenv()  # This loads environment variables from .env

app = Flask(__name__)
CORS(app)

# Set your OpenAI API key from environment variables
openai.api_key = os.environ.get("OPENAI_API_KEY")

# URL of the mempool service (running on port 5000)
MEMPOOL_URL = "http://localhost:5000/transaction"

@app.route('/')
def index():
    return render_template('index.html')

def fetch_all_transactions():
    """Fetch all transactions from the mempool service."""
    try:
        response = requests.get(MEMPOOL_URL)
        if response.ok:
            return response.json()
        else:
            print("Error fetching transactions:", response.status_code, response.text)
            return []
    except Exception as e:
        print("Exception while fetching transactions:", e)
        return []

def simulate_llm_analysis(transactions):
    """
    Use OpenAI's ChatCompletion API to analyze blockchain transaction data and provide a risk score.
    
    The system prompt instructs the model to act as an experienced financial risk analyst with deep knowledge
    of blockchain transaction patterns. The user prompt then provides detailed instructions on how to evaluate the data.
    
    The model is asked to return a JSON object with the keys:
      - "risk_score": a numeric value between 0 (lowest risk) and 100 (highest risk),
      - "risk_level": a categorization ("Low", "Medium", or "High"),
      - "explanation": a detailed explanation of the assessment.
    """
    system_message = (
        "You are an expert financial risk analyst specialized in blockchain transactions. "
        "You have extensive experience in analyzing transaction patterns, liquidity movements, "
        "and trading behaviors in cryptocurrency markets. You understand that high sell volumes, "
        "abnormal trading patterns, and sudden liquidity changes can indicate higher risk. "
        "Your task is to carefully evaluate the provided transaction data and determine an overall risk score."
    )
    
    user_message = (
    "Analyze the following blockchain transaction data and determine the overall risk associated with the token. "
    "Consider factors such as the total volume of transactions, the proportion of sell transactions relative to buy transactions, "
    "any irregularities or abnormal patterns in the data, and liquidity movements if present. "
    "A lot of large size volatile buys and sells in a short period of time relative to the total volume can indicate a potential rug pull. "
    "Based on your analysis, assign a risk score between 0 and 100 (where 0 means extremely low risk and 100 means extremely high risk). "
    "Also, provide a concise risk level categorization ('Low', 'Medium', or 'High') and a brief explanation of your reasoning. "
    "Return your answer as a valid object with exactly three keys: 'risk_score', 'risk_level', and 'explanation', don't return JSON, just return key and value like below. "
    "Do not include any extra text or commentary. "
    "For example, your output should be formatted exactly like this:\n"
    "\n"
    "{\n"
    "  \"risk_score\": 1 to 100,\n"
    "  \"risk_level\": \"High, Medium or Low\",\n"
    "  \"explanation\": \"xxx\"\n"
    "}\n"
    "\n"
    "Transaction data: " + json.dumps(transactions)
)
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.0,
            max_tokens=4000
        )
        result_text = response["choices"][0]["message"]["content"].strip()
        

        print("Analysis result:", result_text)
        analysis = json.loads(result_text)
    except Exception as e:
        print("Error calling OpenAI API:", e)
        analysis = {
            "risk_score": 0,
            "risk_level": "Unknown",
            "explanation": "Failed to analyze transactions."
        }
    return analysis

@app.route('/avs', methods=['GET'])
def avs_analysis():
    """
    AVS endpoint that:
      - Fetches all past transactions from the mempool.
      - Calls ChatGPT (via the OpenAI API) to perform a risk analysis.
    """
    transactions = fetch_all_transactions()
    print("Fetched transactions:", json.dumps(transactions, indent=2))
    
    analysis_result = simulate_llm_analysis(transactions)
    
    return jsonify({
        "message": "AVS analysis complete.",
        "analysis": analysis_result,
        "num_transactions": len(transactions)
    }), 200

if __name__ == '__main__':
    app.run(port=5002, debug=True)
