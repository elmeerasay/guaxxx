// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * ╔══════════════════════════════════════════════════════════╗
 * ║       AutoClaimForwardDelegate — EIP-7702                ║
 * ║                                                          ║
 * ║  Deploy sekali → delegate dari EOA 0xe7FC147...          ║
 * ║                                                          ║
 * ║  Cara kerja (otomatis, tanpa bot):                       ║
 * ║  1. Kirim BNB (berapapun) ke wallet 0xe7FC147...         ║
 * ║  2. receive() trigger otomatis                           ║
 * ║  3. claim() GUA dari reward contract                     ║
 * ║  4. transfer() semua GUA ke RECIPIENT                    ║
 * ╚══════════════════════════════════════════════════════════╝
 *
 * Deploy dari: 0x8575846d8fdbcc9e4e346906ad51a65225912345
 * Delegate  di: 0xe7FC147DE483D0B0dE439DD0AfdBadf49edD6afD
 */

interface IERC20 {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
}

interface IClaimContract {
    function claim() external;
    function pendingReward(address account) external view returns (uint256);
}

contract AutoClaimForwardDelegate {

    // ── Konfigurasi (hardcoded, tidak bisa diubah siapapun) ──
    address public constant CLAIM_CONTRACT = 0x70ae7D3DECfB4C3aE996fb1c07092566F73D5c15;
    address public constant GUA_TOKEN      = 0xa5c8e1513b6a08334b479fe4d71f1253259469be;
    address public constant RECIPIENT      = 0x8575846d8fdbcc9e4e346906ad51a65225912345;

    // ── Events ───────────────────────────────────────────────
    event Claimed(address indexed wallet, uint256 guaAmount, address recipient);
    event BNBReceived(address indexed sender, uint256 amount);
    event NothingToClaim(address indexed wallet);

    // ─────────────────────────────────────────────────────────
    //  receive() — Trigger otomatis ketika BNB masuk ke wallet
    //  (berlaku karena EOA delegate ke contract ini via EIP-7702)
    // ─────────────────────────────────────────────────────────
    receive() external payable {
        emit BNBReceived(msg.sender, msg.value);
        _claimAndForward();
    }

    // ─────────────────────────────────────────────────────────
    //  claimAndForward() — Bisa dipanggil manual juga
    // ─────────────────────────────────────────────────────────
    function claimAndForward() external {
        _claimAndForward();
    }

    // ─────────────────────────────────────────────────────────
    //  Internal logic
    // ─────────────────────────────────────────────────────────
    function _claimAndForward() internal {
        // Cek ada pending reward dulu (hemat gas jika kosong)
        uint256 pending = _safePendingReward();

        if (pending == 0) {
            emit NothingToClaim(address(this));
            return;
        }

        // Claim dari reward contract
        IClaimContract(CLAIM_CONTRACT).claim();

        // Ambil seluruh saldo GUA (termasuk sisa sebelumnya jika ada)
        IERC20 token   = IERC20(GUA_TOKEN);
        uint256 balance = token.balanceOf(address(this));

        if (balance > 0) {
            bool ok = token.transfer(RECIPIENT, balance);
            require(ok, "GUA transfer failed");
            emit Claimed(address(this), balance, RECIPIENT);
        }
    }

    // ─────────────────────────────────────────────────────────
    //  safePendingReward — try/catch supaya tidak revert
    //  jika claim contract tidak support pendingReward()
    // ─────────────────────────────────────────────────────────
    function _safePendingReward() internal view returns (uint256) {
        try IClaimContract(CLAIM_CONTRACT).pendingReward(address(this)) returns (uint256 p) {
            return p;
        } catch {
            return 1; // asumsikan ada reward jika tidak bisa cek
        }
    }

    // ─────────────────────────────────────────────────────────
    //  View helpers
    // ─────────────────────────────────────────────────────────
    function pendingGUA() external view returns (uint256) {
        try IClaimContract(CLAIM_CONTRACT).pendingReward(address(this)) returns (uint256 p) {
            return p;
        } catch {
            return 0;
        }
    }

    function guaBalance() external view returns (uint256) {
        return IERC20(GUA_TOKEN).balanceOf(address(this));
    }
}
