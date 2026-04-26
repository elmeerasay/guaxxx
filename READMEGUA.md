# BSC Auto Claim + Forward Bot

## Cara Pakai (3 Langkah)

### Langkah 1 — Install Dependencies
```bash
pip install -r requirements.txt
```

### Langkah 2 — Deploy Delegate Contract (SEKALI SAJA)
1. Buka https://remix.ethereum.org/
2. Upload `ClaimAndForwardDelegate.sol`
3. Compile → Deploy ke **BSC Mainnet** (pakai MetaMask)
4. Salin contract address yang muncul setelah deploy
5. Atau jalankan `deploy.py` (isi PRIVATE_KEY dulu)

### Langkah 3 — Konfigurasi & Jalankan Bot
Edit `bot.py` bagian KONFIGURASI:
```python
PRIVATE_KEY      = "0xISI_PRIVATE_KEY_KAMU"
DELEGATE_ADDRESS = "0xALAMAT_HASIL_DEPLOY"
RECIPIENT        = "0x8575846d8fdbcc9e4e346906ad51a65225912345"
```

Jalankan:
```bash
python bot.py
```

---

## Cara Kerja (Flow)

```
Kamu kirim BNB berapapun ke wallet 0xe7FC...
           │
           ▼ (bot deteksi dalam ~3 detik)
    Cek BNB ≥ fee (≈ 0.0008 BNB)?
           │ Ya
           ▼
    Kirim 1 TX EIP-7702 ──────────────────────────────┐
    ├── Authorization: EOA delegate ke contract        │
    ├── claim() → GUA masuk ke wallet kamu             │ 1 TX atomik
    └── transfer() → GUA langsung ke RECIPIENT ────────┘
           │
           ▼
    Kembali monitor...
```

## Penjelasan EIP-7702

| Tanpa EIP-7702 | Dengan EIP-7702 |
|---|---|
| claim() → 1 TX | ✅ claim + transfer → 1 TX |
| transfer() → 1 TX | msg.sender = EOA asli kamu |
| Total 2 TX + 2x fee | Fee hanya 1x |

EIP-7702 sudah aktif di BSC sejak **Pascal Hardfork 20 Maret 2025**.

---

## Konfigurasi

| Variable | Nilai Default | Keterangan |
|---|---|---|
| `GAS_PRICE_GWEI` | 3 | Naikkan ke 5 jika sering pending |
| `GAS_LIMIT` | 260,000 | Cukup untuk claim + transfer |
| `POLL_INTERVAL_SEC` | 3 | Cek setiap 3 detik |
| `MIN_BNB_BUFFER` | 0.0003 | BNB sisa setelah bayar fee |

## Estimasi Fee
- Gas limit: 260,000
- Gas price: 3 Gwei
- **Total fee: ≈ 0.00078 BNB (< $0.50)**
