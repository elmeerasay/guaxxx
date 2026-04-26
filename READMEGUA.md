# AutoClaimForwardDelegate — EIP-7702 (BSC)

> **Tanpa bot, tanpa loop** — semua logika ada di dalam smart contract.
> Cukup kirim BNB ke wallet → otomatis claim GUA + forward ke RECIPIENT.

---

## Cara Kerja

```
Kirim BNB ke 0xe7FC147...
        │
        ▼  (EIP-7702: EOA bertindak sebagai contract)
  receive() trigger otomatis
        │
        ├─ cek pendingReward() → ada?
        │
        ├─ claim() → GUA masuk ke 0xe7FC147...
        │
        └─ transfer() → semua GUA ke 0x8575846...  ✅
```

---

## File

| File | Keterangan |
|---|---|
| `AutoClaimForwardDelegate.sol` | Smart contract utama |
| `deploy.py` | Deploy contract + setup EIP-7702 delegation (1x jalan) |
| `requirements.txt` | Dependencies Python untuk deploy.py |

> `bot.py` sudah tidak diperlukan — logika ada di contract.

---

## Setup (1 Kali Saja)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Compile Contract di Remix
1. Buka https://remix.ethereum.org/
2. Upload / paste isi `AutoClaimForwardDelegate.sol`
3. Compile dengan Solidity **≥ 0.8.20**
4. Copy **Compilation Details → Bytecode → object** (string hex)

### 3. Isi deploy.py
```python
DEPLOYER_PRIVATE_KEY = "0xPK_WALLET_0x8575846"   # deployer & penerima GUA
WORKER_PRIVATE_KEY   = "0xPK_WALLET_0xe7FC147"   # worker yang delegate
BYTECODE             = "0xHASIL_COMPILE_REMIX"
```

### 4. Jalankan deploy.py (satu kali)
```bash
python deploy.py
```

Script ini otomatis melakukan **2 hal sekaligus**:
- **Step 1** — Deploy `AutoClaimForwardDelegate` dari wallet `0x8575846...`
- **Step 2** — Sign EIP-7702 authorization dari wallet `0xe7FC147...` (delegate ke contract)

### 5. Selesai ✅
Kirim BNB ke `0xe7FC147...` → claim + forward berjalan otomatis.

---

## Estimasi Fee
| Aksi | Gas | BNB |
|---|---|---|
| Deploy contract | ~500,000 | ~0.0015 BNB |
| Set delegation | ~50,000 | ~0.00015 BNB |
| Tiap claim+forward | ~150,000 | ~0.00045 BNB |

> Harga BNB asumsi 3 Gwei gas price.

---

## Keamanan
- `RECIPIENT` hardcoded di contract → tidak bisa diubah siapapun setelah deploy
- `CLAIM_CONTRACT` dan `GUA_TOKEN` hardcoded → tidak ada fungsi admin/owner
- Tidak ada `selfdestruct`, tidak ada `withdraw`, tidak ada backdoor
