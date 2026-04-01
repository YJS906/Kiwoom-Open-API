"""Account related services backed by Kiwoom REST API."""

from __future__ import annotations

import logging
import re

from app.client import KiwoomRESTClient
from app.exceptions import KiwoomSafetyError
from app.models import AccountSnapshot, CashBalance, Holding
from app.utils import safe_abs_int, safe_float, safe_int


class AccountService:
    """Read account numbers, deposits, and holdings."""

    ACCOUNT_PATH = "/api/dostk/acnt"

    def __init__(self, client: KiwoomRESTClient, logger: logging.Logger) -> None:
        self.client = client
        self.logger = logger.getChild("account")

    def get_accounts(self) -> list[str]:
        """Fetch account numbers tied to the current token using ka00001."""

        result = self.client.post(path=self.ACCOUNT_PATH, api_id="ka00001", body={})
        value = result.body.get("acctNo")
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [item.strip() for item in re.split(r"[;,]", str(value)) if item.strip()]

    def verify_expected_account(self, expected_account_no: str) -> None:
        """Stop early if the token does not belong to the configured mock account."""

        available_accounts = self.get_accounts()
        if expected_account_no not in available_accounts:
            raise KiwoomSafetyError(
                "The configured KIWOOM_ACCOUNT_NO was not returned by ka00001. "
                "Stop here and verify you are using the correct mock account."
            )
        self.logger.info("Mock account validation succeeded.")

    def get_cash_balance(self, query_type: str = "2") -> CashBalance:
        """Fetch deposit summary using kt00001."""

        result = self.client.post(
            path=self.ACCOUNT_PATH,
            api_id="kt00001",
            body={"qry_tp": query_type},
        )
        return CashBalance(
            deposit_krw=safe_abs_int(result.body.get("entr")),
            raw=result.body,
        )

    def get_account_snapshot(self, exchange: str, query_type: str = "1") -> AccountSnapshot:
        """Fetch holdings and summary using kt00018."""

        result = self.client.post(
            path=self.ACCOUNT_PATH,
            api_id="kt00018",
            body={"qry_tp": query_type, "dmst_stex_tp": exchange},
        )
        rows = result.body.get("acnt_evlt_remn_indv_tot", []) or []
        holdings = [
            Holding(
                symbol=str(row.get("stk_cd", "")),
                name=str(row.get("stk_nm", "")),
                quantity=safe_abs_int(row.get("rmnd_qty")),
                available_quantity=safe_abs_int(row.get("trde_able_qty")),
                current_price=safe_abs_int(row.get("cur_prc")),
                purchase_price=safe_abs_int(row.get("pur_pric")),
                evaluation_profit_loss=safe_int(row.get("evltv_prft")),
                profit_rate=safe_float(row.get("prft_rt")),
                raw=row,
            )
            for row in rows
            if safe_abs_int(row.get("rmnd_qty")) > 0
        ]
        return AccountSnapshot(
            total_purchase_amount_krw=safe_abs_int(result.body.get("tot_pur_amt")),
            total_evaluation_amount_krw=safe_abs_int(result.body.get("tot_evlt_amt")),
            total_profit_loss_krw=safe_int(result.body.get("tot_evlt_pl")),
            total_profit_rate=safe_float(result.body.get("tot_prft_rt")),
            estimated_assets_krw=safe_abs_int(result.body.get("prsm_dpst_aset_amt")),
            holdings=holdings,
            raw=result.body,
        )
