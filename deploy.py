#!/usr/bin/env python3
"""
deploy.py — Deploy AutoClaimForwardDelegate ke BSC
───────────────────────────────────────────────────
Jalankan SEKALI dari wallet deployer (0x8575846...)
Setelah dapat DELEGATE_ADDRESS → sign EIP-7702 dari 0xe7FC147...
"""

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
import rlp
from eth_utils import keccak, decode_hex

# ─────────────────────────────────────────────
#  KONFIGURASI — EDIT BAGIAN INI
# ─────────────────────────────────────────────
DEPLOYER_PRIVATE_KEY = "0xYOUR_DEPLOYER_PK"          # PK wallet 0x8575846...
DEPLOYER_ADDRESS     = "0x8575846d8fdbcc9e4e346906ad51a65225912345"

WORKER_PRIVATE_KEY   = "0xYOUR_WORKER_PK"            # PK wallet 0xe7FC147... (untuk delegate)
WORKER_ADDRESS       = "0xe7FC147DE483D0B0dE439DD0AfdBadf49edD6afD"

BSC_RPC              = "https://bsc-dataseed1.binance.org/"
BSC_CHAIN_ID         = 56
GAS_PRICE_GWEI       = 3
# ─────────────────────────────────────────────

# Paste bytecode hasil compile AutoClaimForwardDelegate.sol di Remix:
# Compile → Bytecode → "object"
BYTECODE = "0xPASTE_COMPILED_BYTECODE_HERE"

# ── EIP-7702 Authorization Signer ────────────
def sign_eip7702_authorization(pk_hex: str, chain_id: int, delegate_addr: str, nonce: int):
    """Sign EIP-7702 authorization: worker EOA delegate ke contract."""
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

    assert BYTECODE != "0xPASTE_COMPILED_BYTECODE_HERE", \
        "⛔ Isi BYTECODE dulu! Compile AutoClaimForwardDelegate.sol di Remix."

    deployer = Account.from_key(DEPLOYER_PRIVATE_KEY)
    worker   = Account.from_key(WORKER_PRIVATE_KEY)

    assert deployer.address.lower() == DEPLOYER_ADDRESS.lower(), "⛔ PK deployer tidak cocok!"
    assert worker.address.lower()   == WORKER_ADDRESS.lower(),   "⛔ PK worker tidak cocok!"

    # ── STEP 1: Deploy contract dari deployer (0x8575846...) ──
    print("=" * 56)
    print("STEP 1 — Deploy AutoClaimForwardDelegate")
    print(f"  Deployer : {DEPLOYER_ADDRESS}")
    print("=" * 56)

    nonce_d    = w3.eth.get_transaction_count(deployer.address)
    gas_price  = w3.to_wei(str(GAS_PRICE_GWEI), "gwei")
    bnb_d      = float(w3.from_wei(w3.eth.get_balance(deployer.address), "ether"))
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
    print(f"  TX deploy → https://bscscan.com/tx/{tx_hash_d.hex()}")
    print("  Menunggu konfirmasi...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash_d, timeout=120)
    assert receipt["status"] == 1, f"❌ Deploy gagal! TX: {tx_hash_d.hex()}"

    DELEGATE_ADDRESS = receipt.contractAddress
    print(f"  ✅ Contract berhasil di-deploy!")
    print(f"  DELEGATE_ADDRESS = {DELEGATE_ADDRESS}")

    # ── STEP 2: Sign EIP-7702 Authorization dari worker (0xe7FC147...) ──
    print()
    print("=" * 56)
    print("STEP 2 — EIP-7702 Delegate dari Worker")
    print(f"  Worker   : {WORKER_ADDRESS}")
    print(f"  Delegate : {DELEGATE_ADDRESS}")
    print("=" * 56)

    nonce_w   = w3.eth.get_transaction_count(worker.address)
    bnb_w     = float(w3.from_wei(w3.eth.get_balance(worker.address), "ether"))
    print(f"  BNB saldo worker  : {bnb_w:.6f} BNB")

    # Build EIP-7702 set-delegation tx (type 0x04, calldata kosong = hanya set delegation)
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
        w3.to_wei(str(GAS_PRICE_GWEI), "gwei"),
        w3.to_wei(str(GAS_PRICE_GWEI), "gwei"),
        50_000,         # gas cukup untuk set delegation saja
        addr_b,         # to = worker EOA sendiri
        0, b"", [],     # value=0, calldata kosong, access_list kosong
        [auth_entry],
    ]

    tx_hash_raw = keccak(b"\x04" + rlp.encode(unsigned))
    from eth_keys import keys as ekeys
    pk_obj = ekeys.PrivateKey(pk_bytes)
    sig    = pk_obj.sign_msg_hash(tx_hash_raw)
    signed_fields = unsigned + [sig.v, sig.r.to_bytes(32,"big"), sig.s.to_bytes(32,"big")]
    raw_tx = b"\x04" + rlp.encode(signed_fields)

    tx_hash_w = w3.eth.send_raw_transaction(raw_tx)
    print(f"  TX delegate → https://bscscan.com/tx/{tx_hash_w.hex()}")
    print("  Menunggu konfirmasi...")

    receipt_w = w3.eth.wait_for_transaction_receipt(tx_hash_w, timeout=120)
    assert receipt_w["status"] == 1, f"❌ Delegate gagal! TX: {tx_hash_w.hex()}"

    print(f"  ✅ Delegate berhasil!")
    print()
    print("=" * 56)
    print("🎉 SELESAI! Bot sudah aktif sepenuhnya.")
    print()
    print("  Cara pakai:")
    print(f"  → Kirim BNB ke: {WORKER_ADDRESS}")
    print(f"  → Otomatis: claim GUA + kirim ke {receipt.contractAddress[:10]}...{RECIPIENT[-6:]}")
    print()
    print(f"  Monitor wallet : https://bscscan.com/address/{WORKER_ADDRESS}")
    print("=" * 56)

RECIPIENT = "0x8575846d8fdbcc9e4e346906ad51a65225912345"

if __name__ == "__main__":
    main()
