#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║         BSC Auto Claim + Forward Bot (EIP-7702)          ║
║                                                          ║
║  Cara kerja:                                             ║
║  1. Monitor wallet → deteksi BNB masuk                   ║
║  2. Jika BNB cukup bayar fee → execute 1 tx EIP-7702     ║
║     • claim() GUA dari reward contract                   ║
║     • forward() semua GUA ke RECIPIENT                   ║
║  3. Kembali monitor (loop terus)                         ║
╚══════════════════════════════════════════════════════════╝

Setup:
  1. pip install -r requirements.txt
  2. Deploy ClaimAndForwardDelegate.sol → isi DELEGATE_ADDRESS
  3. Isi PRIVATE_KEY dan RECIPIENT di bawah
  4. python bot.py
"""

import time
import logging
import rlp
from rlp.sedes import big_endian_int, Binary, CountableList, List as RLPList
from eth_utils import keccak, to_bytes, decode_hex
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from eth_account._utils.signing import sign_message_hash
import colorlog

# ─────────────────────────────────────────────
#  KONFIGURASI — EDIT BAGIAN INI
# ─────────────────────────────────────────────
PRIVATE_KEY       = "0xYOUR_PRIVATE_KEY_HERE"
WALLET_ADDRESS    = "0xe7FC147DE483D0B0dE439DD0AfdBadf49edD6afD"
RECIPIENT         = "0x8575846d8fdbcc9e4e346906ad51a65225912345"

DELEGATE_ADDRESS  = "0xYOUR_DELEGATE_CONTRACT"   # hasil deploy.py
CLAIM_CONTRACT    = "0x70ae7D3DECfB4C3aE996fb1c07092566F73D5c15"
GUA_TOKEN         = "0xa5c8e1513b6a08334b479fe4d71f1253259469be"

BSC_RPC           = "https://bsc-dataseed1.binance.org/"
BSC_CHAIN_ID      = 56
GAS_LIMIT         = 260_000
GAS_PRICE_GWEI    = 3            # naikkan ke 5 kalau sering pending
POLL_INTERVAL_SEC = 3            # cek setiap N detik
MIN_BNB_BUFFER    = 0.0003       # BNB minimum sisa setelah fee (safety)
# ─────────────────────────────────────────────


# ── Logger berwarna ───────────────────────────
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s [%(levelname)s]%(reset)s %(message)s",
    datefmt="%H:%M:%S",
    log_colors={"DEBUG":"cyan","INFO":"green","WARNING":"yellow","ERROR":"red","CRITICAL":"bold_red"},
))
log = colorlog.getLogger("ClaimBot")
log.addHandler(handler)
log.setLevel(logging.INFO)


# ── ABI minimal ──────────────────────────────
DELEGATE_ABI = [{
    "name": "claimAndForward",
    "type": "function",
    "stateMutability": "nonpayable",
    "inputs": [
        {"name": "claimContract", "type": "address"},
        {"name": "tokenAddress",  "type": "address"},
        {"name": "recipient",     "type": "address"},
    ],
    "outputs": [],
}]

ERC20_ABI = [{
    "name": "balanceOf",
    "type": "function",
    "stateMutability": "view",
    "inputs": [{"name": "account", "type": "address"}],
    "outputs": [{"name": "", "type": "uint256"}],
}]


# ── EIP-7702 TX Builder ───────────────────────
def _to_addr_bytes(addr: str) -> bytes:
    return decode_hex(addr) if addr.startswith("0x") else bytes.fromhex(addr)


def sign_authorization(private_key_bytes: bytes, chain_id: int, delegate_addr: str, auth_nonce: int):
    """
    Sign EIP-7702 authorization tuple.
    Hash = keccak256(0x05 || rlp([chain_id, address, nonce]))
    """
    addr_bytes = _to_addr_bytes(delegate_addr)
    encoded = rlp.encode([chain_id, addr_bytes, auth_nonce])
    auth_hash = keccak(b"\x05" + encoded)
    from eth_account._utils.signing import sign_message_hash
    from eth_keys import keys
    pk = keys.PrivateKey(private_key_bytes)
    sig = pk.sign_msg_hash(auth_hash)
    return {
        "chainId":   chain_id,
        "address":   delegate_addr,
        "nonce":     auth_nonce,
        "yParity":   sig.v,
        "r":         sig.r,
        "s":         sig.s,
    }


def build_and_sign_eip7702_tx(
    w3: Web3,
    private_key_bytes: bytes,
    from_addr: str,
    calldata: bytes,
    nonce: int,
    gas_price_wei: int,
):
    """
    Build EIP-7702 (type 0x04) transaction, sign, return raw bytes.

    TX = 0x04 || rlp([
        chain_id, nonce, max_priority_fee, max_fee, gas,
        to, value, data, access_list,
        authorization_list,           ← daftar [chain_id, addr, nonce, yParity, r, s]
        sig_y_parity, sig_r, sig_s
    ])
    """
    from eth_keys import keys

    auth = sign_authorization(private_key_bytes, BSC_CHAIN_ID, DELEGATE_ADDRESS, nonce)
    to_bytes_addr = _to_addr_bytes(from_addr)   # to = EOA kamu sendiri

    # authorization_list element: [chain_id, address, nonce, yParity, r, s]
    auth_entry = [
        auth["chainId"],
        _to_addr_bytes(auth["address"]),
        auth["nonce"],
        auth["yParity"],
        auth["r"].to_bytes(32, "big"),
        auth["s"].to_bytes(32, "big"),
    ]

    # Unsigned payload (tanpa signature fields)
    unsigned_fields = [
        BSC_CHAIN_ID,
        nonce,
        gas_price_wei,      # max_priority_fee_per_gas
        gas_price_wei,      # max_fee_per_gas
        GAS_LIMIT,
        to_bytes_addr,
        0,                  # value (BNB yg dikirim ke kontrak = 0)
        calldata,
        [],                 # access_list
        [auth_entry],       # authorization_list
    ]

    unsigned_encoded = b"\x04" + rlp.encode(unsigned_fields)
    tx_hash = keccak(unsigned_encoded)

    pk = keys.PrivateKey(private_key_bytes)
    sig = pk.sign_msg_hash(tx_hash)

    signed_fields = unsigned_fields + [sig.v, sig.r.to_bytes(32,"big"), sig.s.to_bytes(32,"big")]
    return b"\x04" + rlp.encode(signed_fields)


# ── Helpers ───────────────────────────────────
def bnb_balance(w3, addr):
    return float(w3.from_wei(w3.eth.get_balance(Web3.to_checksum_address(addr)), "ether"))


def gua_balance(w3, addr):
    tok = w3.eth.contract(address=Web3.to_checksum_address(GUA_TOKEN), abi=ERC20_ABI)
    return tok.functions.balanceOf(Web3.to_checksum_address(addr)).call() / 1e18


def fee_bnb(w3):
    gp = w3.to_wei(GAS_PRICE_GWEI, "gwei")
    return float(w3.from_wei(GAS_LIMIT * gp, "ether"))


# ── Execute Bundle ────────────────────────────
def execute_bundle(w3, account, pk_bytes):
    nonce = w3.eth.get_transaction_count(account.address)
    gas_price_wei = w3.to_wei(GAS_PRICE_GWEI, "gwei")

    # Encode calldata → claimAndForward(CLAIM_CONTRACT, GUA_TOKEN, RECIPIENT)
    iface = w3.eth.contract(
        address=Web3.to_checksum_address(account.address),
        abi=DELEGATE_ABI,
    )
    calldata = bytes.fromhex(
        iface.encodeABI(
            fn_name="claimAndForward",
            args=[
                Web3.to_checksum_address(CLAIM_CONTRACT),
                Web3.to_checksum_address(GUA_TOKEN),
                Web3.to_checksum_address(RECIPIENT),
            ]
        )[2:]  # strip 0x
    )

    raw_tx = build_and_sign_eip7702_tx(w3, pk_bytes, account.address, calldata, nonce, gas_price_wei)
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    log.info(f"  📡 TX sent  → https://bscscan.com/tx/{tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    if receipt["status"] == 1:
        log.info(f"  ✅ Berhasil! GUA dikirim ke {RECIPIENT}")
    else:
        log.error(f"  ❌ TX revert! Cek: https://bscscan.com/tx/{tx_hash.hex()}")
    return receipt


# ── Main Loop ─────────────────────────────────
def main():
    w3 = Web3(Web3.HTTPProvider(BSC_RPC))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    assert w3.is_connected(), "❌ Tidak bisa konek ke BSC RPC!"

    pk_bytes = bytes.fromhex(PRIVATE_KEY.replace("0x", ""))
    account  = Account.from_key(PRIVATE_KEY)
    assert account.address.lower() == WALLET_ADDRESS.lower(), \
        "⛔ Private key tidak cocok dengan WALLET_ADDRESS!"

    estimated_fee = fee_bnb(w3)
    min_bnb_needed = estimated_fee + MIN_BNB_BUFFER

    log.info("━" * 56)
    log.info("  BSC Auto Claim + Forward Bot  ⚡ EIP-7702")
    log.info("━" * 56)
    log.info(f"  Wallet    : {WALLET_ADDRESS}")
    log.info(f"  Recipient : {RECIPIENT}")
    log.info(f"  Delegate  : {DELEGATE_ADDRESS}")
    log.info(f"  Est. Fee  : {estimated_fee:.6f} BNB")
    log.info(f"  Min BNB   : {min_bnb_needed:.6f} BNB")
    log.info("━" * 56)

    prev_bnb = bnb_balance(w3, WALLET_ADDRESS)
    log.info(f"▶ Monitoring... BNB saat ini: {prev_bnb:.6f}")

    while True:
        try:
            curr_bnb = bnb_balance(w3, WALLET_ADDRESS)

            if curr_bnb > prev_bnb + 1e-9:   # ada BNB masuk (threshold kecil untuk float noise)
                delta = curr_bnb - prev_bnb
                log.info(f"💰 BNB MASUK: +{delta:.6f} BNB  (total: {curr_bnb:.6f} BNB)")

                if curr_bnb >= min_bnb_needed:
                    gua = gua_balance(w3, WALLET_ADDRESS)
                    log.info(f"  GUA claimable: ~{gua:.4f} GUA")
                    log.info(f"  Menjalankan bundle tx (1 tx: claim + transfer)...")
                    execute_bundle(w3, account, pk_bytes)
                    curr_bnb = bnb_balance(w3, WALLET_ADDRESS)
                    log.info(f"  BNB sisa  : {curr_bnb:.6f} BNB")
                else:
                    log.warning(
                        f"  ⚠ BNB tidak cukup. "
                        f"Perlu ≥ {min_bnb_needed:.6f}, ada {curr_bnb:.6f} BNB"
                    )

            prev_bnb = curr_bnb
            time.sleep(POLL_INTERVAL_SEC)

        except KeyboardInterrupt:
            log.info("\n⛔ Bot dihentikan (Ctrl+C)")
            break
        except Exception as exc:
            log.error(f"Error: {exc}")
            time.sleep(POLL_INTERVAL_SEC * 3)


if __name__ == "__main__":
    main()
