#!/usr/bin/env python3
"""
deploy.py — Deploy ClaimAndForwardDelegate ke BSC
Jalankan SEKALI untuk dapat DELEGATE_ADDRESS
"""
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account

PRIVATE_KEY = "0xYOUR_PRIVATE_KEY_HERE"
BSC_RPC     = "https://bsc-dataseed1.binance.org/"

# Bytecode hasil compile ClaimAndForwardDelegate.sol
# Compile di: https://remix.ethereum.org/
BYTECODE = "0xPASTE_COMPILED_BYTECODE_HERE"

w3 = Web3(Web3.HTTPProvider(BSC_RPC))
w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
account = Account.from_key(PRIVATE_KEY)

nonce    = w3.eth.get_transaction_count(account.address)
gas_price = w3.to_wei("3", "gwei")

tx = {
    "chainId": 56,
    "nonce":   nonce,
    "gas":     500_000,
    "gasPrice": gas_price,
    "data":    BYTECODE,
    "value":   0,
}

signed = account.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print(f"TX: https://bscscan.com/tx/{tx_hash.hex()}")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
print(f"✅ DELEGATE_ADDRESS = {receipt.contractAddress}")
print(f"   Salin address ini ke bot.py -> DELEGATE_ADDRESS")
