#!/usr/bin/env python3
"""
deploy.py — Deploy AutoClaimForwardDelegate ke BSC
──────────────────────────────────────────────────────
Step 1 : Deploy contract dari wallet DEPLOYER (0x8575846...)
Step 2a: WORKER (0xe7FC147...) sign EIP-7702 authorization OFF-CHAIN (gratis, no gas)
Step 2b: DEPLOYER embed signature WORKER ke Type-4 tx → DEPLOYER yang bayar gas delegation
         → WORKER tidak perlu keluar gas sepeserpun untuk delegation
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
assert BYTECODE and BYTECODE != "0xPASTE_COMPILED_BYTECODE_HERE", "❌ BYTECODE belum diisi di .env"

DEPLOYER_ADDRESS = "0x8575846d8fdbcc9e4e346906ad51a65225912345"
WORKER_ADDRESS   = "0xe7FC147DE483D0B0dE439DD0AfdBadf49edD6afD"


# ──────────────────────────────────────────────────────────────
#  sign_eip7702_authorization
#  Pure off-chain — tidak butuh koneksi RPC, tidak bayar gas.
#  WORKER hanya perlu private key-nya, hasilkan {chainId, address,
#  nonce, yParity, r, s} yang bisa diberikan ke siapapun sebagai
#  "kuasa" untuk mengaktifkan delegation via Type-4 tx.
# ──────────────────────────────────────────────────────────────
def sign_eip7702_authorization(pk_hex, chain_id, delegate_addr, nonce):
    """
    Buat EIP-7702 authorization signature secara off-chain.

    Parameter:
        pk_hex        : private key WORKER dalam hex (0x...)
        chain_id      : chain ID BSC = 56
        delegate_addr : alamat contract yang akan jadi code WORKER
        nonce         : nonce WORKER saat ini (harus fresh)

    Return:
        dict {chainId, address, nonce, yParity, r, s}
        → siap dimasukkan ke authorizationList milik tx SIAPAPUN
    """
    from eth_keys import keys
    pk_bytes  = bytes.fromhex(pk_hex.replace("0x", ""))
    addr_b    = decode_hex(delegate_addr)
    encoded   = rlp.encode([chain_id, addr_b, nonce])
    auth_hash = keccak(b"\x05" + encoded)   # 0x05 = EIP-7702 magic prefix
    pk_obj    = keys.PrivateKey(pk_bytes)
    sig       = pk_obj.sign_msg_hash(auth_hash)
    return {
        "chainId" : chain_id,
        "address" : delegate_addr,
        "nonce"   : nonce,
        "yParity" : sig.v,
        "r"       : sig.r,
        "s"       : sig.s,
    }


# ──────────────────────────────────────────────────────────────
#  build_and_send_delegation_tx
#  DEPLOYER embed authorization WORKER ke Type-4 tx (0x04).
#  DEPLOYER yang bayar gas — WORKER tidak keluar gas sama sekali.
# ──────────────────────────────────────────────────────────────
def build_and_send_delegation_tx(w3, deployer_pk, auth, gas_price):
    """
    Kirim Type-4 (EIP-7702 SET_CODE) tx dari DEPLOYER.
    auth = hasil sign_eip7702_authorization() dari WORKER.
    """
    from eth_keys import keys as ekeys

    deployer      = Account.from_key(deployer_pk)
    deployer_addr = decode_hex(deployer.address)
    nonce_d       = w3.eth.get_transaction_count(deployer.address)

    auth_entry = [
        auth["chainId"],
        decode_hex(auth["address"]),
        auth["nonce"],
        auth["yParity"],
        auth["r"].to_bytes(32, "big"),
        auth["s"].to_bytes(32, "big"),
    ]

    # Type-4 tx fields (EIP-7702):
    # [chain_id, nonce, max_priority_fee, max_fee, gas_limit,
    #  to, value, data, access_list, authorization_list]
    unsigned = [
        BSC_CHAIN_ID,
        nonce_d,
        gas_price,   # max_priority_fee_per_gas
        gas_price,   # max_fee_per_gas
        80_000,      # gas limit (delegation only, no data execution)
        deployer_addr,
        0,
        b"",
        [],
        [auth_entry],
    ]

    tx_hash_raw = keccak(b"\x04" + rlp.encode(unsigned))
    pk_bytes    = bytes.fromhex(deployer_pk.replace("0x", ""))
    sig         = ekeys.PrivateKey(pk_bytes).sign_msg_hash(tx_hash_raw)

    signed_fields = unsigned + [
        sig.v,
        sig.r.to_bytes(32, "big"),
        sig.s.to_bytes(32, "big"),
    ]
    raw_tx = b"\x04" + rlp.encode(signed_fields)
    return w3.eth.send_raw_transaction(raw_tx)


def main():
    w3 = Web3(Web3.HTTPProvider(BSC_RPC))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    assert w3.is_connected(), "❌ Tidak bisa konek ke BSC RPC!"

    deployer = Account.from_key(DEPLOYER_PRIVATE_KEY)
    worker   = Account.from_key(WORKER_PRIVATE_KEY)

    assert deployer.address.lower() == DEPLOYER_ADDRESS.lower(), "⛔ PK deployer tidak cocok!"
    assert worker.address.lower()   == WORKER_ADDRESS.lower(),   "⛔ PK worker tidak cocok!"

    gas_price = w3.to_wei(str(GAS_PRICE_GWEI), "gwei")

    # ── STEP 1: Deploy contract dari DEPLOYER ──────────────────
    print("=" * 60)
    print("STEP 1 — Deploy AutoClaimForwardDelegate")
    print(f"  Deployer : {deployer.address}")
    print(f"  Recipient: {RECIPIENT}")
    print(f"  RPC      : {BSC_RPC}")
    print("=" * 60)

    nonce_d = w3.eth.get_transaction_count(deployer.address)
    bnb_d   = float(w3.from_wei(w3.eth.get_balance(deployer.address), "ether"))
    print(f"  BNB saldo deployer: {bnb_d:.6f} BNB")

    deploy_tx = {
        "chainId" : BSC_CHAIN_ID,
        "nonce"   : nonce_d,
        "gas"     : 600_000,
        "gasPrice": gas_price,
        "data"    : BYTECODE,
        "value"   : 0,
    }
    signed_d  = deployer.sign_transaction(deploy_tx)
    tx_hash_d = w3.eth.send_raw_transaction(signed_d.raw_transaction)
    print(f"  TX → https://bscscan.com/tx/{tx_hash_d.hex()}")
    print("  Menunggu konfirmasi...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash_d, timeout=120)
    assert receipt["status"] == 1, "❌ Deploy gagal!"

    DELEGATE_ADDRESS = receipt.contractAddress
    print(f"  ✅ Deploy sukses!")
    print(f"  DELEGATE_ADDRESS = {DELEGATE_ADDRESS}")

    # ── STEP 2a: WORKER sign off-chain (GRATIS, zero gas) ──────
    print()
    print("=" * 60)
    print("STEP 2a — WORKER sign EIP-7702 authorization (OFF-CHAIN, no gas)")
    print(f"  Worker   : {worker.address}")
    print(f"  Delegate : {DELEGATE_ADDRESS}")
    print("  ℹ️  Ini pure off-chain — WORKER tidak butuh BNB untuk ini")
    print("=" * 60)

    # Ambil nonce WORKER sekarang — harus fresh saat tx delegation dikirim
    nonce_w = w3.eth.get_transaction_count(worker.address)
    bnb_w   = float(w3.from_wei(w3.eth.get_balance(worker.address), "ether"))
    print(f"  BNB saldo worker  : {bnb_w:.6f} BNB (tidak akan berkurang)")
    print(f"  Nonce worker      : {nonce_w}")

    # Sign off-chain — tidak ada tx, tidak ada gas
    auth = sign_eip7702_authorization(
        pk_hex        = WORKER_PRIVATE_KEY,
        chain_id      = BSC_CHAIN_ID,
        delegate_addr = DELEGATE_ADDRESS,
        nonce         = nonce_w,
    )
    print(f"  ✅ Signature dibuat off-chain:")
    print(f"     yParity = {auth['yParity']}")
    print(f"     r       = {hex(auth['r'])[:18]}...")
    print(f"     s       = {hex(auth['s'])[:18]}...")

    # ── STEP 2b: DEPLOYER kirim Type-4 tx, embed signature WORKER
    print()
    print("=" * 60)
    print("STEP 2b — DEPLOYER kirim Type-4 tx (DEPLOYER yang bayar gas)")
    print(f"  Sender (bayar gas): {deployer.address}")
    print(f"  Authorization dari: {worker.address}")
    print("  ℹ️  WORKER tidak keluar gas sama sekali")
    print("=" * 60)

    bnb_d2 = float(w3.from_wei(w3.eth.get_balance(deployer.address), "ether"))
    print(f"  BNB saldo deployer: {bnb_d2:.6f} BNB")

    tx_hash_w = build_and_send_delegation_tx(w3, DEPLOYER_PRIVATE_KEY, auth, gas_price)
    print(f"  TX → https://bscscan.com/tx/{tx_hash_w.hex()}")
    print("  Menunggu konfirmasi...")

    receipt_w = w3.eth.wait_for_transaction_receipt(tx_hash_w, timeout=120)
    assert receipt_w["status"] == 1, "❌ Delegate gagal!"

    print(f"  ✅ Delegate sukses!")

    # ── Verifikasi delegation aktif ────────────────────────────
    print()
    print("=" * 60)
    print("VERIFIKASI — Cek delegation aktif di BSC")
    code = w3.eth.get_code(worker.address)
    expected_prefix = bytes.fromhex("ef0100")
    if code[:3] == expected_prefix:
        delegated_to = "0x" + code[3:].hex()
        print(f"  ✅ Delegation AKTIF!")
        print(f"     0x{worker.address} sekarang menjalankan code dari:")
        print(f"     {delegated_to}")
    else:
        print(f"  ⚠️  Code: {code.hex() or '(kosong)'}")
        print("  Delegation mungkin belum aktif — cek manual di BscScan")

    print()
    print("=" * 60)
    print("🎉 SELESAI! Fully otomatis.")
    print()
    print(f"  Kirim BNB ke : {worker.address}")
    print(f"  GUA dikirim  : {RECIPIENT}")
    print(f"  Monitor      : https://bscscan.com/address/{worker.address}")
    print()
    print("  Gas breakdown:")
    print("    Step 1 (deploy)     : dibayar DEPLOYER ✅")
    print("    Step 2a (sign)      : GRATIS (off-chain) ✅")
    print("    Step 2b (delegation): dibayar DEPLOYER ✅")
    print("    WORKER total gas    : 0 BNB ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
