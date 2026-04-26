# AutoClaimForwardDelegate — EIP-7702 (BSC)

> Tanpa bot loop. Semua logika di smart contract.
> Cron kirim BNB kecil → `receive()` trigger → claim GUA → forward ke RECIPIENT.

---

## Cara Kerja

```
[Cron setiap X jam]
  trigger.py kirim 0.001 BNB ke 0xe7FC147...
        │
        ▼  (EIP-7702 aktif → EOA jalankan kode contract)
  receive() trigger otomatis
        │
        ├─ pendingReward() → ada?
        ├─ claim() → GUA masuk ke 0xe7FC147...
        └─ transfer() → semua GUA ke RECIPIENT (0x8575846...)  ✅
```

---

## File

| File | Keterangan |
|---|---|
| `AutoClaimForwardDelegate.sol` | Smart contract (logic claim + forward) |
| `deploy.py` | Deploy contract + setup EIP-7702 (jalankan 1x) |
| `trigger.py` | Kirim BNB kecil untuk trigger receive() (cron) |
| `.env.example` | Template konfigurasi |
| `requirements.txt` | Dependencies Python |

---

## Setup

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Buat .env
```bash
cp .env.example .env
# Edit .env — isi semua nilai
```

### 3. Compile di Remix
1. Buka https://remix.ethereum.org/
2. Upload `AutoClaimForwardDelegate.sol`
3. Compile Solidity ≥ 0.8.20
4. Copy **Bytecode → object** → paste ke `.env` sebagai `BYTECODE`

### 4. Deploy + Delegate (1x saja)
```bash
python deploy.py
```

### 5. Setup Cron
```bash
crontab -e
```
Tambahkan (contoh setiap 6 jam):
```
0 */6 * * * /usr/bin/python3 /path/to/guaxxx/trigger.py >> /path/to/trigger.log 2>&1
```

Selesai ✅ — cron jalan → BNB kecil dikirim → claim + forward otomatis.

---

## Konfigurasi .env

| Variable | Keterangan |
|---|---|
| `BSC_RPC` | RPC endpoint BSC |
| `DEPLOYER_PRIVATE_KEY` | PK wallet 0x8575846... (deploy + kirim trigger BNB) |
| `WORKER_PRIVATE_KEY` | PK wallet 0xe7FC147... (yang delegate ke contract) |
| `RECIPIENT` | Alamat penerima GUA (0x8575846...) |
| `BYTECODE` | Bytecode hasil compile Remix |

---

## Estimasi Biaya

| Aksi | Frekuensi | BNB |
|---|---|---|
| Deploy contract | 1x | ~0.0015 BNB |
| Set EIP-7702 delegation | 1x | ~0.00015 BNB |
| Trigger BNB (dikirim ke worker) | Tiap cron | 0.001 BNB |
| Fee receive() claim+forward | Tiap cron | ~0.00045 BNB |

> Trigger BNB 0.001 tidak hilang — sisa setelah fee kembali ke worker untuk trigger berikutnya.
