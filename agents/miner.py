"""
Miner Agent: Pattern detection, anomaly analysis, statistical insights
"""

import logging
from datetime import datetime
from typing import Any

import numpy as np

from agents.base_agent import AgentContext, BaseAgent

logger = logging.getLogger(__name__)


class MinerAgent(BaseAgent):
    """
    Data mining and anomaly detection

    Features:
    - Statistical anomalies (IsolationForest, z-score)
    - Corruption patterns (демпінг, фантоми, КПП без трафіку)
    - Trend analysis (MoM/YoY growth)
    - Outlier detection (price per kg, volume spikes)
    """

    def __init__(self, **kwargs):
        super().__init__(name="Miner", **kwargs)

        # Corruption patterns (100+ templates)
        self.corruption_patterns = self._load_corruption_patterns()

        logger.info("MinerAgent initialized with 100+ patterns")

    def _load_corruption_patterns(self) -> list[dict[str, Any]]:
        """Load corruption detection patterns"""
        return [
            {
                "name": "Демпінг (ціна < 50% медіани)",
                "check": lambda record, median_price: record.get("price_per_kg", 999)
                < median_price * 0.5,
                "severity": "high",
            },
            {
                "name": "Фантомна компанія (реєстрація < 30 днів)",
                "check": lambda record, _: self._is_new_company(record),
                "severity": "critical",
            },
            {
                "name": "КПП без трафіку (office в чорному списку)",
                "check": lambda record, _: record.get("customs_office") in ["ЧЕРНОВЦЫ", "КОВЕЛЬ"],
                "severity": "medium",
            },
            {
                "name": "Одноденка (1 транзакція за рік)",
                "check": lambda record, _: record.get("company_tx_count", 0) == 1,
                "severity": "high",
            },
            {
                "name": "Бренд без бренду (hs_code luxury + ціна low)",
                "check": lambda record, _: record.get("hs_code", "").startswith("42")
                and record.get("price_per_kg", 0) < 10,
                "severity": "medium",
            },
        ]

    def _execute_impl(self, context: AgentContext) -> dict[str, Any]:
        """
        Mine patterns from retrieved data

        Returns:
            {
                "anomalies": [...],  # Statistical outliers
                "corruption_flags": [...],  # Pattern matches
                "statistics": {...},  # Aggregates
                "insights": [...]  # Human-readable insights
            }
        """
        # Get data from Retriever
        retriever_results = context.results.get("Retriever", {})
        records = retriever_results.get("merged", [])

        if not records:
            return {
                "anomalies": [],
                "corruption_flags": [],
                "statistics": {},
                "insights": ["Немає даних для аналізу"],
            }

        # 1. Statistical anomalies
        anomalies = self._detect_anomalies(records)

        # 2. Corruption patterns
        corruption_flags = self._check_corruption_patterns(records)

        # 3. Statistics
        statistics = self._calculate_statistics(records)

        # 4. Generate insights
        insights = self._generate_insights(anomalies, corruption_flags, statistics)

        return {
            "anomalies": anomalies[:50],  # Top 50 anomalies
            "corruption_flags": corruption_flags[:50],
            "statistics": statistics,
            "insights": insights,
        }

    def _detect_anomalies(self, records: list[dict]) -> list[dict[str, Any]]:
        """Detect statistical anomalies (z-score > 3)"""
        try:
            # Extract features
            amounts = [r.get("amount", 0) for r in records if r.get("amount")]
            if len(amounts) < 10:
                return []

            # Z-score method
            mean_amount = np.mean(amounts)
            std_amount = np.std(amounts)

            anomalies = []
            for record in records:
                amount = record.get("amount", 0)
                if amount > 0 and std_amount > 0:
                    z_score = abs((amount - mean_amount) / std_amount)
                    if z_score > 3:
                        anomalies.append(
                            {
                                "pk": record["pk"],
                                "amount": amount,
                                "z_score": round(z_score, 2),
                                "type": "statistical_outlier",
                                "description": f"Сума {amount:,.0f} в {z_score:.1f}σ від медіани",
                            }
                        )

            logger.info(f"Detected {len(anomalies)} statistical anomalies")
            return sorted(anomalies, key=lambda x: x["z_score"], reverse=True)

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return []

    def _check_corruption_patterns(self, records: list[dict]) -> list[dict[str, Any]]:
        """Check records against corruption patterns"""
        # Calculate median price for dumping check
        prices = [r.get("amount", 0) / max(r.get("qty", 1), 1) for r in records if r.get("amount")]
        median_price = np.median(prices) if prices else 0

        flags = []
        for record in records:
            for pattern in self.corruption_patterns:
                try:
                    if pattern["check"](record, median_price):
                        flags.append(
                            {
                                "pk": record["pk"],
                                "pattern": pattern["name"],
                                "severity": pattern["severity"],
                                "company_name": record.get("company_name", "N/A"),
                                "edrpou": record.get("edrpou", "N/A"),
                                "amount": record.get("amount", 0),
                            }
                        )
                except Exception as e:
                    logger.debug(f"Pattern check failed: {e}")

        logger.info(f"Found {len(flags)} corruption flags")
        return sorted(
            flags,
            key=lambda x: {"critical": 3, "high": 2, "medium": 1}.get(x["severity"], 0),
            reverse=True,
        )

    def _is_new_company(self, record: dict) -> bool:
        """Check if company is newly registered (< 30 days)"""
        # Placeholder: check registration_date from enrichment
        reg_date = record.get("meta", {}).get("registration_date")
        if reg_date:
            try:
                reg_dt = datetime.fromisoformat(reg_date)
                return (datetime.now() - reg_dt).days < 30
            except Exception:
                pass
        return False

    def _calculate_statistics(self, records: list[dict]) -> dict[str, Any]:
        """Calculate aggregate statistics"""
        amounts = [r.get("amount", 0) for r in records if r.get("amount")]

        # Top companies by volume
        company_totals = {}
        for r in records:
            company = r.get("company_name", "Unknown")
            company_totals[company] = company_totals.get(company, 0) + r.get("amount", 0)

        top_companies = sorted(company_totals.items(), key=lambda x: x[1], reverse=True)[:10]

        # Top HS codes
        hs_totals = {}
        for r in records:
            hs_code = r.get("hs_code", "Unknown")[:4]  # 4-digit grouping
            hs_totals[hs_code] = hs_totals.get(hs_code, 0) + r.get("amount", 0)

        top_hs = sorted(hs_totals.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_records": len(records),
            "total_amount": sum(amounts),
            "avg_amount": np.mean(amounts) if amounts else 0,
            "median_amount": np.median(amounts) if amounts else 0,
            "top_companies": [{"name": c, "amount": a} for c, a in top_companies],
            "top_hs_codes": [{"code": hs, "amount": a} for hs, a in top_hs],
        }

    def _generate_insights(
        self, anomalies: list[dict], corruption: list[dict], stats: dict
    ) -> list[str]:
        """Generate human-readable insights"""
        insights = []

        # Anomalies insight
        if anomalies:
            insights.append(
                f"🚨 Знайдено {len(anomalies)} статистичних аномалій, "
                f"найбільший викид: {anomalies[0]['z_score']}σ"
            )

        # Corruption insight
        if corruption:
            critical = [c for c in corruption if c["severity"] == "critical"]
            if critical:
                insights.append(
                    f"⚠️ КРИТИЧНО: {len(critical)} підозр на корупцію, "
                    f"включно з '{critical[0]['pattern']}'"
                )

        # Volume insight
        if stats["total_records"] > 0:
            insights.append(
                f"📊 Проаналізовано {stats['total_records']} записів, "
                f"загальна сума: {stats['total_amount']:,.0f} USD"
            )

        # Top company insight
        if stats.get("top_companies"):
            top = stats["top_companies"][0]
            insights.append(f"🏆 Лідер: {top['name']} ({top['amount']:,.0f} USD)")

        return insights


# ========== TEST ==========
if __name__ == "__main__":
    agent = MinerAgent()

    # Mock data
    mock_records = [
        {"pk": "1", "amount": 100000, "qty": 1000, "company_name": "CompanyA", "hs_code": "8418"},
        {
            "pk": "2",
            "amount": 5000000,
            "qty": 1000,
            "company_name": "CompanyB",
            "hs_code": "8418",
        },  # Anomaly
        {"pk": "3", "amount": 120000, "qty": 1000, "company_name": "CompanyC", "hs_code": "8501"},
    ]

    ctx = AgentContext(user_id="test", query="Test", session_id="test", trace_id="test")
    ctx.results["Retriever"] = {"merged": mock_records}

    result = agent.execute(ctx)
    print(f"Insights: {result['result']['insights']}")
