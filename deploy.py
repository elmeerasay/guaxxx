#!/usr/bin/env python3
"""
deploy.py — Deploy AutoClaimForwardDelegate ke BSC
───────────────────────────────────────────────────
Step 1: Deploy contract dari wallet DEPLOYER (0x8575846...)
Step 2: Sign EIP-7702 delegation dari wallet WORKER (0xe7FC147...)
"""

import os
from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
import rlp
from eth_utils import keccak, decode_hex

load_dotenv()

BSC_RPC              = os.getenv("BSC_RPC", "https://bsc-dataseed1.binance.org/")
DEPLOYER_PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY")
WORKER_PRIVATE_KEY   = os.getenv("WORKER_PRIVATE_KEY")
RECIPIENT            = os.getenv("RECIPIENT")
BYTECODE             = os.getenv("BYTECODE")
BSC_CHAIN_ID         = 56
GAS_PRICE_GWEI       = 3

assert DEPLOYER_PRIVATE_KEY, "❌ DEPLOYER_PRIVATE_KEY tidak ada di .env"
assert WORKER_PRIVATE_KEY,   "❌ WORKER_PRIVATE_KEY tidak ada di .env"
assert RECIPIENT,            "❌ RECIPIENT tidak ada di .env"
assert BYTECODE and BYTECODE != "0xPASTE_COMPILED_BYTECODE_HERE",     "❌ BYTECODE belum diisi di .env"

DEPLOYER_ADDRESS = "0x8575846d8fdbcc9e4e346906ad51a65225912345"
WORKER_ADDRESS   = "0xe7FC147DE483D0B0dE439DD0AfdBadf49edD6afD"

def sign_eip7702_authorization(pk_hex, chain_id, delegate_addr, nonce):
    pk_bytes  = bytes.fromhex(pk_hex.replace("0x", ""))
    addr_b    = decode_hex(delegate_addr)
    encoded   = rlp.encode([chain_id, addr_b, nonce])
    auth_hash = keccak(b"\x05" + encoded)
    from eth_keys import keys
    pk  = keys.PrivateKey(pk_bytes)
    sig = pk.sign_msg_hash(auth_hash)
    return {"chainId": chain_id, "address": delegate_addr, "nonce": nonce,
            "yParity": sig.v, "r": sig.r, "s": sig.s}

def main():
    w3 = Web3(Web3.HTTPProvider(BSC_RPC))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    assert w3.is_connected(), "❌ Tidak bisa konek ke BSC RPC!"

    deployer = Account.from_key(DEPLOYER_PRIVATE_KEY)
    worker   = Account.from_key(WORKER_PRIVATE_KEY)

    assert deployer.address.lower() == DEPLOYER_ADDRESS.lower(), "⛔ PK deployer tidak cocok!"
    assert worker.address.lower()   == WORKER_ADDRESS.lower(),   "⛔ PK worker tidak cocok!"

    gas_price = w3.to_wei(str(GAS_PRICE_GWEI), "gwei")

    # ── STEP 1: Deploy contract ───────────────
    print("=" * 56)
    print("STEP 1 — Deploy AutoClaimForwardDelegate")
    print(f"  Deployer : {deployer.address}")
    print(f"  Recipient: {RECIPIENT}")
    print(f"  RPC      : {BSC_RPC}")
    print("=" * 56)

    nonce_d = w3.eth.get_transaction_count(deployer.address)
    bnb_d   = float(w3.from_wei(w3.eth.get_balance(deployer.address), "ether"))
    print(f"  BNB saldo deployer: {bnb_d:.6f} BNB")

    deploy_tx = {
        "chainId":  BSC_CHAIN_ID,
        "nonce":    nonce_d,
        "gas":      600_000,
        "gasPrice": gas_price,
        "data":     BYTECODE,
        "value":    0,
    }
    signed_d  = deployer.sign_transaction(deploy_tx)
    tx_hash_d = w3.eth.send_raw_transaction(signed_d.raw_transaction)
    print(f"  TX → https://bscscan.com/tx/{tx_hash_d.hex()}")
    print("  Menunggu konfirmasi...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash_d, timeout=120)
    assert receipt["status"] == 1, f"❌ Deploy gagal!"

    DELEGATE_ADDRESS = receipt.contractAddress
    print(f"  ✅ Deploy sukses!")
    print(f"  DELEGATE_ADDRESS = {DELEGATE_ADDRESS}")

    # ── STEP 2: EIP-7702 Delegation dari worker ─
    print()
    print("=" * 56)
    print("STEP 2 — EIP-7702 Delegate dari Worker")
    print(f"  Worker   : {worker.address}")
    print(f"  Delegate : {DELEGATE_ADDRESS}")
    print("=" * 56)

    nonce_w = w3.eth.get_transaction_count(worker.address)
    bnb_w   = float(w3.from_wei(w3.eth.get_balance(worker.address), "ether"))
    print(f"  BNB saldo worker: {bnb_w:.6f} BNB")

    pk_bytes = bytes.fromhex(WORKER_PRIVATE_KEY.replace("0x", ""))
    auth = sign_eip7702_authorization(WORKER_PRIVATE_KEY, BSC_CHAIN_ID, DELEGATE_ADDRESS, nonce_w)

    addr_b = decode_hex(worker.address)
    auth_entry = [
        auth["chainId"],
        decode_hex(auth["address"]),
        auth["nonce"],
        auth["yParity"],
        auth["r"].to_bytes(32, "big"),
        auth["s"].to_bytes(32, "big"),
    ]
    unsigned = [
        BSC_CHAIN_ID, nonce_w,
        gas_price, gas_price,
        50_000, addr_b, 0, b"", [], [auth_entry],
    ]
    tx_hash_raw = keccak(b"\x04" + rlp.encode(unsigned))
    from eth_keys import keys as ekeys
    sig = ekeys.PrivateKey(pk_bytes).sign_msg_hash(tx_hash_raw)
    signed_fields = unsigned + [sig.v, sig.r.to_bytes(32,"big"), sig.s.to_bytes(32,"big")]
    raw_tx = b"\x04" + rlp.encode(signed_fields)

    tx_hash_w = w3.eth.send_raw_transaction(raw_tx)
    print(f"  TX → https://bscscan.com/tx/{tx_hash_w.hex()}")
    print("  Menunggu konfirmasi...")

    receipt_w = w3.eth.wait_for_transaction_receipt(tx_hash_w, timeout=120)
    assert receipt_w["status"] == 1, "❌ Delegate gagal!"

    print(f"  ✅ Delegate sukses!")
    print()
    print("=" * 56)
    print("🎉 SELESAI! Fully otomatis.")
    print()
    print(f"  Kirim BNB ke : {worker.address}")
    print(f"  GUA dikirim  : {RECIPIENT}")
    print(f"  Monitor      : https://bscscan.com/address/{worker.address}")
    print("=" * 56)

if __name__ == "__main__":
    main()
