# AutoClaimForwardDelegate — EIP-7702 (BSC)

---

## Cara Kerja (Fully Otomatis)

```
Siapapun kirim BNB ke 0xe7FC147...
        │
        │  ← ini trigger-nya. tidak perlu bot, tidak perlu polling.
        ▼
  receive() jalan OTOMATIS (EIP-7702)
        │
        ├─ claim() GUA dari reward contract
        └─ transfer() semua GUA → 0x8575846...  ✅
```

> **Penjelasan:** Setelah `deploy.py` dijalankan sekali, wallet `0xe7FC147...`
> sudah "menjadi" smart contract via EIP-7702. Setiap kali ada BNB masuk
> ke wallet itu — dari siapapun — `receive()` langsung jalan otomatis.
> Tidak ada polling, tidak ada bot, tidak ada cron.
>
> **Satu-satunya yang perlu dilakukan:** pastikan wallet `0xe7FC147...`
> selalu punya cukup BNB untuk gas. Caranya: sesekali top-up BNB ke wallet
> itu. Saat BNB dikirim → `receive()` jalan → claim + forward sekalian.

---

## File

| File | Keterangan |
|---|---|
| `AutoClaimForwardDelegate.sol` | Smart contract (logic claim + forward) |
| `deploy.py` | Deploy contract + setup EIP-7702 delegation (jalankan 1x saja) |
| `.env.example` | Template konfigurasi |
| `requirements.txt` | Dependencies Python |

---

## Setup (1x Saja, Selamanya)

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Buat .env
```bash
cp .env.example .env
# Edit .env — isi semua nilai
```

```env
BSC_RPC=https://bsc-dataseed1.binance.org/
DEPLOYER_PRIVATE_KEY=0xPK_WALLET_0x8575846...
WORKER_PRIVATE_KEY=0xPK_WALLET_0xe7FC147...
RECIPIENT=0x8575846d8fdbcc9e4e346906ad51a65225912345
BYTECODE=0xHASIL_COMPILE_REMIX
```

### 3. Compile di Remix
1. Buka https://remix.ethereum.org/
2. Upload `AutoClaimForwardDelegate.sol`
3. Compile Solidity **≥ 0.8.20**
4. Copy **Compilation Details → Bytecode → object** → paste ke `.env` sebagai `BYTECODE`

### 4. Deploy + Delegate (1x saja)
```bash
python deploy.py
```

Script otomatis:
- **Step 1** → Deploy contract dari `0x8575846...`
- **Step 2** → Wallet `0xe7FC147...` delegate ke contract (EIP-7702)

### 5. Selesai ✅

Mulai sekarang:
```
Kirim BNB ke 0xe7FC147... → claim GUA + kirim ke 0x8575846... (otomatis)
```

---

## Estimasi Gas per Klaim

| | |
|---|---|
| Gas limit | ~150,000 |
| Gas price | 3 Gwei |
| **Total fee** | **~0.00045 BNB (< $0.30)** |
