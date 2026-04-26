#!/usr/bin/env python3
"""
trigger.py — Kirim BNB kecil ke worker wallet setiap X jam
Ini yang "mengetuk" contract supaya receive() jalan otomatis.

Jalankan dengan cron:
  crontab -e
  0 */6 * * * /usr/bin/python3 /path/to/guaxxx/trigger.py >> /path/to/trigger.log 2>&1
  (contoh: setiap 6 jam sekali)
"""

import os
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from datetime import datetime

load_dotenv()

BSC_RPC              = os.getenv("BSC_RPC", "https://bsc-dataseed1.binance.org/")
DEPLOYER_PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY")   # yang kirim BNB trigger
WORKER_ADDRESS       = "0xe7FC147DE483D0B0dE439DD0AfdBadf49edD6afD"
GAS_PRICE_GWEI       = 3
TRIGGER_BNB          = 0.001   # BNB yang dikirim sebagai trigger (cukup buat fee receive())

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def main():
    w3 = Web3(Web3.HTTPProvider(BSC_RPC))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    assert w3.is_connected(), "❌ Tidak bisa konek ke BSC RPC!"

    sender  = Account.from_key(DEPLOYER_PRIVATE_KEY)
    gas_price = w3.to_wei(str(GAS_PRICE_GWEI), "gwei")

    sender_bnb = float(w3.from_wei(w3.eth.get_balance(sender.address), "ether"))
    worker_bnb = float(w3.from_wei(w3.eth.get_balance(Web3.to_checksum_address(WORKER_ADDRESS)), "ether"))

    log(f"Sender  : {sender.address}  ({sender_bnb:.6f} BNB)")
    log(f"Worker  : {WORKER_ADDRESS}  ({worker_bnb:.6f} BNB)")

    assert sender_bnb >= TRIGGER_BNB + 0.0001,         f"❌ Saldo sender tidak cukup! Perlu ≥ {TRIGGER_BNB + 0.0001:.4f} BNB"

    nonce = w3.eth.get_transaction_count(sender.address)

    tx = {
        "chainId":  56,
        "nonce":    nonce,
        "to":       Web3.to_checksum_address(WORKER_ADDRESS),
        "value":    w3.to_wei(str(TRIGGER_BNB), "ether"),
        "gas":      21_000,
        "gasPrice": gas_price,
    }

    signed  = sender.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    log(f"✅ Trigger TX → https://bscscan.com/tx/{tx_hash.hex()}")
    log(f"   Mengirim {TRIGGER_BNB} BNB ke worker → receive() akan jalan otomatis")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt["status"] == 1:
        log("✅ TX confirmed — claim + forward GUA selesai!")
    else:
        log("❌ TX gagal!")

if __name__ == "__main__":
    main()
