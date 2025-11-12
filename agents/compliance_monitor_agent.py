"""
Compliance Monitor Agent: Regulatory compliance monitoring and reporting
Monitors regulatory requirements, compliance status, and generates compliance reports
"""

import asyncio
import logging
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

import lightgbm as lgb
import numpy as np
import xgboost as xgb
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sqlalchemy.ext.declarative import declarative_base

from ..agents.base_agent import AgentMessage, BaseAgent
from ..api.database import get_db_session

logger = logging.getLogger(__name__)

Base = declarative_base()


class ComplianceMonitorAgent(BaseAgent):
    """
    Compliance Monitor Agent for regulatory compliance monitoring and reporting
    Uses ML models and rule-based systems to monitor compliance status and generate reports
    """

    def __init__(
        self, agent_id: str = "compliance_monitor_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Compliance configuration
        self.compliance_config = {
            "regulatory_frameworks": self.config.get(
                "regulatory_frameworks",
                [
                    "GDPR",
                    "CCPA",
                    "HIPAA",
                    "SOX",
                    "PCI_DSS",
                    "ISO_27001",
                    "NIST",
                    "FedRAMP",
                    "CIS_Controls",
                    "MITRE_ATT&CK",
                ],
            ),
            "compliance_domains": self.config.get(
                "compliance_domains",
                [
                    "data_privacy",
                    "data_security",
                    "financial_reporting",
                    "risk_management",
                    "access_control",
                    "audit_logging",
                    "incident_response",
                    "business_continuity",
                ],
            ),
            "risk_levels": self.config.get("risk_levels", ["low", "medium", "high", "critical"]),
            "compliance_statuses": self.config.get(
                "compliance_statuses",
                ["compliant", "non_compliant", "partially_compliant", "not_applicable"],
            ),
            "monitoring_frequency": self.config.get(
                "monitoring_frequency",
                {
                    "high_risk": 3600,  # 1 hour
                    "medium_risk": 86400,  # 24 hours
                    "low_risk": 604800,  # 7 days
                },
            ),
            "alert_thresholds": self.config.get(
                "alert_thresholds",
                {"critical_violations": 1, "high_violations": 5, "medium_violations": 10},
            ),
        }

        # ML models for compliance prediction
        self.compliance_models = {}
        self.risk_assessment_models = {}
        self.violation_detection_models = {}

        # Compliance knowledge base
        self.regulatory_requirements = {}
        self.compliance_rules = {}
        self.risk_scoring_rules = {}

        # Monitoring state
        self.monitoring_state = {
            "active_checks": {},
            "compliance_status": {},
            "violation_history": defaultdict(list),
            "audit_trail": deque(maxlen=10000),
            "alert_queue": deque(),
        }

        # Background tasks
        self.monitoring_task = None
        self.reporting_task = None
        self.audit_task = None

        logger.info(f"Compliance Monitor Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the compliance monitor agent
        """
        await super().start()

        # Initialize compliance knowledge base
        await self._initialize_compliance_knowledge()

        # Initialize ML models
        await self._initialize_compliance_models()

        # Start background tasks
        self.monitoring_task = asyncio.create_task(self._continuous_monitoring())
        self.reporting_task = asyncio.create_task(self._scheduled_reporting())
        self.audit_task = asyncio.create_task(self._audit_logging())

        logger.info("Compliance monitoring started")

    async def stop(self):
        """
        Stop the compliance monitor agent
        """
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        if self.reporting_task:
            self.reporting_task.cancel()
            try:
                await self.reporting_task
            except asyncio.CancelledError:
                pass

        if self.audit_task:
            self.audit_task.cancel()
            try:
                await self.audit_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Compliance monitor agent stopped")

    async def _initialize_compliance_knowledge(self):
        """
        Initialize compliance knowledge base with regulatory requirements
        """
        try:
            # GDPR requirements
            self.regulatory_requirements["GDPR"] = {
                "data_privacy": {
                    "lawful_processing": "Personal data must be processed lawfully, fairly and transparently",
                    "purpose_limitation": "Collected for specified, explicit and legitimate purposes",
                    "data_minimization": "Adequate, relevant and limited to what is necessary",
                    "accuracy": "Accurate and kept up to date",
                    "storage_limitation": "Kept in a form which permits identification for no longer than necessary",
                    "integrity_security": "Processed securely with appropriate protection",
                    "accountability": "Controller responsible for compliance and can demonstrate compliance",
                },
                "data_subject_rights": {
                    "right_to_information": "Information about processing activities",
                    "right_of_access": "Access to personal data",
                    "right_to_rectification": "Correction of inaccurate data",
                    "right_to_erasure": "Right to be forgotten",
                    "right_to_restriction": "Restriction of processing",
                    "right_to_data_portability": "Receive and transmit data",
                    "right_to_object": "Object to processing",
                    "rights_automated_decisions": "Not subject to automated decisions",
                },
            }

            # HIPAA requirements
            self.regulatory_requirements["HIPAA"] = {
                "privacy_rule": {
                    "uses_disclosures": "Permitted uses and disclosures of protected health information",
                    "minimum_necessary": "Minimum necessary information for permitted uses",
                    "individual_rights": "Individual rights regarding their health information",
                    "administrative_requirements": "Administrative requirements for covered entities",
                },
                "security_rule": {
                    "administrative_safeguards": "Administrative actions and policies",
                    "physical_safeguards": "Physical protections for PHI",
                    "technical_safeguards": "Technology protections for PHI",
                },
            }

            # SOX requirements
            self.regulatory_requirements["SOX"] = {
                "financial_reporting": {
                    "accurate_financials": "Financial statements must be accurate and complete",
                    "internal_controls": "Effective internal controls over financial reporting",
                    "ceo_cfo_certification": "CEO and CFO must certify financial statements",
                    "audit_committee": "Independent audit committee oversight",
                    "whistleblower_protection": "Protection for whistleblowers",
                }
            }

            # PCI DSS requirements
            self.regulatory_requirements["PCI_DSS"] = {
                "build_maintain_network": {
                    "firewall_configuration": "Install and maintain firewall configuration",
                    "system_passwords": "Do not use vendor-supplied defaults",
                    "protect_stored_data": "Protect stored cardholder data",
                    "encrypt_transmissions": "Encrypt transmission of cardholder data",
                    "antivirus_software": "Use and regularly update antivirus software",
                    "develop_maintain_systems": "Develop and maintain secure systems and applications",
                },
                "implement_access_control": {
                    "restrict_access": "Restrict access to cardholder data by business need to know",
                    "unique_ids": "Assign unique ID to each person with computer access",
                    "remote_access": "Restrict physical access to cardholder data",
                },
            }

            # Initialize compliance rules
            await self._initialize_compliance_rules()

            logger.info("Compliance knowledge base initialized")

        except Exception as e:
            logger.error(f"Compliance knowledge initialization failed: {e}")

    async def _initialize_compliance_rules(self):
        """
        Initialize compliance rules and risk scoring
        """
        try:
            # Data privacy rules
            self.compliance_rules["data_privacy"] = {
                "retention_check": {
                    "rule": "Data retention periods must be defined and enforced",
                    "check_type": "automated",
                    "severity": "high",
                },
                "consent_management": {
                    "rule": "User consent must be obtained and tracked",
                    "check_type": "automated",
                    "severity": "critical",
                },
                "data_encryption": {
                    "rule": "Sensitive data must be encrypted at rest and in transit",
                    "check_type": "automated",
                    "severity": "high",
                },
                "access_logging": {
                    "rule": "All data access must be logged and monitored",
                    "check_type": "automated",
                    "severity": "medium",
                },
            }

            # Security rules
            self.compliance_rules["data_security"] = {
                "password_policy": {
                    "rule": "Passwords must meet complexity requirements",
                    "check_type": "automated",
                    "severity": "medium",
                },
                "multi_factor_auth": {
                    "rule": "Multi-factor authentication required for privileged access",
                    "check_type": "automated",
                    "severity": "high",
                },
                "patch_management": {
                    "rule": "Security patches must be applied within defined timeframes",
                    "check_type": "automated",
                    "severity": "high",
                },
                "vulnerability_scanning": {
                    "rule": "Regular vulnerability scanning must be performed",
                    "check_type": "automated",
                    "severity": "medium",
                },
            }

            # Risk scoring rules
            self.risk_scoring_rules = {
                "data_breach": {"base_score": 9.0, "factors": ["data_volume", "data_sensitivity"]},
                "unauthorized_access": {
                    "base_score": 7.0,
                    "factors": ["access_level", "data_sensitivity"],
                },
                "policy_violation": {"base_score": 5.0, "factors": ["violation_type", "frequency"]},
                "configuration_error": {
                    "base_score": 4.0,
                    "factors": ["system_criticality", "exposure_level"],
                },
            }

            logger.info("Compliance rules initialized")

        except Exception as e:
            logger.error(f"Compliance rules initialization failed: {e}")

    async def _initialize_compliance_models(self):
        """
        Initialize ML models for compliance monitoring
        """
        try:
            # Compliance prediction models
            self.compliance_models = {
                "violation_predictor": RandomForestClassifier(n_estimators=100, random_state=42),
                "risk_assessor": GradientBoostingClassifier(n_estimators=100, random_state=42),
                "anomaly_detector": xgb.XGBClassifier(n_estimators=100, random_state=42),
            }

            # Risk assessment models
            self.risk_assessment_models = {
                "impact_predictor": RandomForestClassifier(n_estimators=100, random_state=42),
                "severity_classifier": lgb.LGBMClassifier(n_estimators=100, random_state=42),
            }

            # Violation detection models
            self.violation_detection_models = {
                "pattern_detector": xgb.XGBClassifier(n_estimators=100, random_state=42),
                "behavior_analyzer": RandomForestClassifier(n_estimators=100, random_state=42),
            }

            logger.info("Compliance models initialized")

        except Exception as e:
            logger.error(f"Compliance models initialization failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process compliance monitoring requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "check_compliance":
                async for response in self._handle_compliance_check(message):
                    yield response

            elif message_type == "generate_compliance_report":
                async for response in self._handle_compliance_report(message):
                    yield response

            elif message_type == "assess_risk":
                async for response in self._handle_risk_assessment(message):
                    yield response

            elif message_type == "audit_log":
                async for response in self._handle_audit_log(message):
                    yield response

            elif message_type == "monitor_regulation":
                async for response in self._handle_regulation_monitoring(message):
                    yield response

            elif message_type == "compliance_alert":
                async for response in self._handle_compliance_alert(message):
                    yield response

            else:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": f"Unknown message type: {message_type}"},
                    timestamp=datetime.now(),
                )

        except Exception as e:
            logger.error(f"Compliance monitoring processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _continuous_monitoring(self):
        """
        Continuous compliance monitoring loop
        """
        try:
            while True:
                try:
                    # Perform automated compliance checks
                    await self._perform_automated_checks()

                    # Monitor for violations
                    await self._monitor_violations()

                    # Update compliance status
                    await self._update_compliance_status()

                except Exception as e:
                    logger.error(f"Continuous monitoring error: {e}")

                # Wait for next monitoring cycle
                await asyncio.sleep(300)  # Check every 5 minutes

        except asyncio.CancelledError:
            logger.info("Continuous monitoring cancelled")
            raise

    async def _scheduled_reporting(self):
        """
        Scheduled compliance reporting
        """
        try:
            while True:
                try:
                    # Generate periodic reports
                    await self._generate_periodic_reports()

                    # Send alerts if needed
                    await self._process_alerts()

                except Exception as e:
                    logger.error(f"Scheduled reporting error: {e}")

                # Wait for next reporting cycle (daily)
                await asyncio.sleep(86400)

        except asyncio.CancelledError:
            logger.info("Scheduled reporting cancelled")
            raise

    async def _audit_logging(self):
        """
        Continuous audit logging
        """
        try:
            while True:
                try:
                    # Log compliance events
                    await self._log_compliance_events()

                    # Archive old logs
                    await self._archive_audit_logs()

                except Exception as e:
                    logger.error(f"Audit logging error: {e}")

                # Wait for next audit cycle
                await asyncio.sleep(3600)  # Log every hour

        except asyncio.CancelledError:
            logger.info("Audit logging cancelled")
            raise

    async def _handle_compliance_check(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle compliance check request
        """
        try:
            framework = message.content.get("framework", "GDPR")
            domain = message.content.get("domain", "data_privacy")
            scope = message.content.get("scope", "full")

            # Perform compliance check
            check_result = await self._perform_compliance_check(framework, domain, scope)

            # Log the check
            await self._log_compliance_check(check_result)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "compliance_check_response",
                    "framework": framework,
                    "domain": domain,
                    "scope": scope,
                    "result": check_result,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Compliance check handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _perform_compliance_check(
        self, framework: str, domain: str, scope: str
    ) -> dict[str, Any]:
        """
        Perform compliance check for specified framework and domain
        """
        try:
            check_results = {
                "framework": framework,
                "domain": domain,
                "scope": scope,
                "timestamp": datetime.now(),
                "checks_performed": [],
                "violations_found": [],
                "compliance_score": 0.0,
                "overall_status": "unknown",
            }

            # Get relevant rules
            rules = self.compliance_rules.get(domain, {})

            for rule_name, rule_config in rules.items():
                check_result = await self._execute_compliance_rule(rule_name, rule_config)
                check_results["checks_performed"].append(check_result)

                if not check_result["compliant"]:
                    check_results["violations_found"].append(
                        {
                            "rule": rule_name,
                            "severity": rule_config["severity"],
                            "details": check_result["details"],
                        }
                    )

            # Calculate compliance score
            total_checks = len(check_results["checks_performed"])
            compliant_checks = sum(
                1 for check in check_results["checks_performed"] if check["compliant"]
            )

            if total_checks > 0:
                check_results["compliance_score"] = compliant_checks / total_checks

                # Determine overall status
                if check_results["compliance_score"] >= 0.95:
                    check_results["overall_status"] = "compliant"
                elif check_results["compliance_score"] >= 0.8:
                    check_results["overall_status"] = "partially_compliant"
                else:
                    check_results["overall_status"] = "non_compliant"

            # Add risk assessment
            check_results["risk_assessment"] = await self._assess_compliance_risk(check_results)

            return check_results

        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            return {"error": str(e), "status": "check_failed"}

    async def _execute_compliance_rule(
        self, rule_name: str, rule_config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a specific compliance rule
        """
        try:
            rule_type = rule_config.get("check_type", "automated")

            if rule_type == "automated":
                # Automated rule checking
                return await self._execute_automated_rule(rule_name, rule_config)
            else:
                # Manual rule checking (would require human intervention)
                return {
                    "rule": rule_name,
                    "compliant": None,  # Requires manual review
                    "check_type": "manual",
                    "details": "Manual review required",
                    "executed_at": datetime.now(),
                }

        except Exception as e:
            logger.error(f"Rule execution failed for {rule_name}: {e}")
            return {
                "rule": rule_name,
                "compliant": False,
                "error": str(e),
                "executed_at": datetime.now(),
            }

    async def _execute_automated_rule(
        self, rule_name: str, rule_config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute automated compliance rule
        """
        try:
            compliant = True
            details = []

            # Rule-specific checks
            if rule_name == "retention_check":
                compliant, rule_details = await self._check_data_retention()
                details.extend(rule_details)

            elif rule_name == "consent_management":
                compliant, rule_details = await self._check_consent_management()
                details.extend(rule_details)

            elif rule_name == "data_encryption":
                compliant, rule_details = await self._check_data_encryption()
                details.extend(rule_details)

            elif rule_name == "access_logging":
                compliant, rule_details = await self._check_access_logging()
                details.extend(rule_details)

            elif rule_name == "password_policy":
                compliant, rule_details = await self._check_password_policy()
                details.extend(rule_details)

            elif rule_name == "multi_factor_auth":
                compliant, rule_details = await self._check_mfa()
                details.extend(rule_details)

            elif rule_name == "patch_management":
                compliant, rule_details = await self._check_patch_management()
                details.extend(rule_details)

            elif rule_name == "vulnerability_scanning":
                compliant, rule_details = await self._check_vulnerability_scanning()
                details.extend(rule_details)

            return {
                "rule": rule_name,
                "compliant": compliant,
                "check_type": "automated",
                "details": details,
                "executed_at": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Automated rule execution failed for {rule_name}: {e}")
            return {
                "rule": rule_name,
                "compliant": False,
                "error": str(e),
                "executed_at": datetime.now(),
            }

    async def _check_data_retention(self) -> tuple[bool, list[str]]:
        """Check data retention compliance"""
        try:
            # Query database for data retention status
            async with get_db_session():
                # Check for data older than retention policies
                # This is a simplified check - in practice would query actual data tables
                retention_violations = []

                # Example checks (would be replaced with actual database queries)
                retention_violations.append("Found 5 records older than retention policy")

                compliant = len(retention_violations) == 0
                return compliant, retention_violations

        except Exception as e:
            return False, [f"Retention check failed: {str(e)}"]

    async def _check_consent_management(self) -> tuple[bool, list[str]]:
        """Check consent management compliance"""
        try:
            consent_issues = []

            # Check for users without consent records
            async with get_db_session():
                # Example check - would query actual consent tables
                consent_issues.append("Found 3 users without valid consent records")

            compliant = len(consent_issues) == 0
            return compliant, consent_issues

        except Exception as e:
            return False, [f"Consent check failed: {str(e)}"]

    async def _check_data_encryption(self) -> tuple[bool, list[str]]:
        """Check data encryption compliance"""
        try:
            encryption_issues = []

            # Check database encryption status
            async with get_db_session():
                # Example checks - would query actual encryption status
                encryption_issues.append("Database not fully encrypted")
                encryption_issues.append("API keys not encrypted")

            compliant = len(encryption_issues) == 0
            return compliant, encryption_issues

        except Exception as e:
            return False, [f"Encryption check failed: {str(e)}"]

    async def _check_access_logging(self) -> tuple[bool, list[str]]:
        """Check access logging compliance"""
        try:
            logging_issues = []

            # Check if access logging is enabled
            async with get_db_session():
                # Example checks - would verify logging configuration
                logging_issues.append("Audit logging not configured for all tables")

            compliant = len(logging_issues) == 0
            return compliant, logging_issues

        except Exception as e:
            return False, [f"Access logging check failed: {str(e)}"]

    async def _check_password_policy(self) -> tuple[bool, list[str]]:
        """Check password policy compliance"""
        try:
            policy_issues = []

            # Check password complexity requirements
            async with get_db_session():
                # Example checks - would verify password policies
                policy_issues.append("Weak password policy detected")

            compliant = len(policy_issues) == 0
            return compliant, policy_issues

        except Exception as e:
            return False, [f"Password policy check failed: {str(e)}"]

    async def _check_mfa(self) -> tuple[bool, list[str]]:
        """Check multi-factor authentication compliance"""
        try:
            mfa_issues = []

            # Check MFA configuration
            async with get_db_session():
                # Example checks - would verify MFA settings
                mfa_issues.append("MFA not enabled for admin accounts")

            compliant = len(mfa_issues) == 0
            return compliant, mfa_issues

        except Exception as e:
            return False, [f"MFA check failed: {str(e)}"]

    async def _check_patch_management(self) -> tuple[bool, list[str]]:
        """Check patch management compliance"""
        try:
            patch_issues = []

            # Check for outdated software versions
            async with get_db_session():
                # Example checks - would verify patch status
                patch_issues.append("Security patches pending for 3 systems")

            compliant = len(patch_issues) == 0
            return compliant, patch_issues

        except Exception as e:
            return False, [f"Patch management check failed: {str(e)}"]

    async def _check_vulnerability_scanning(self) -> tuple[bool, list[str]]:
        """Check vulnerability scanning compliance"""
        try:
            scan_issues = []

            # Check vulnerability scan schedule
            async with get_db_session():
                # Example checks - would verify scan schedules
                scan_issues.append("Vulnerability scans not performed this month")

            compliant = len(scan_issues) == 0
            return compliant, scan_issues

        except Exception as e:
            return False, [f"Vulnerability scanning check failed: {str(e)}"]

    async def _assess_compliance_risk(self, check_results: dict[str, Any]) -> dict[str, Any]:
        """
        Assess risk based on compliance check results
        """
        try:
            violations = check_results.get("violations_found", [])

            if not violations:
                return {
                    "risk_level": "low",
                    "risk_score": 0.0,
                    "recommendations": ["Continue monitoring compliance"],
                }

            # Calculate risk score based on violations
            risk_score = 0.0
            critical_count = sum(1 for v in violations if v["severity"] == "critical")
            high_count = sum(1 for v in violations if v["severity"] == "high")
            medium_count = sum(1 for v in violations if v["severity"] == "medium")

            risk_score = (critical_count * 10) + (high_count * 5) + (medium_count * 2)

            # Determine risk level
            if risk_score >= 20:
                risk_level = "critical"
            elif risk_score >= 10:
                risk_level = "high"
            elif risk_score >= 5:
                risk_level = "medium"
            else:
                risk_level = "low"

            # Generate recommendations
            recommendations = []
            if critical_count > 0:
                recommendations.append("Immediate remediation required for critical violations")
            if high_count > 0:
                recommendations.append("Address high-severity violations within 24 hours")
            if risk_level != "low":
                recommendations.append("Schedule compliance review meeting")

            return {
                "risk_level": risk_level,
                "risk_score": float(risk_score),
                "violation_breakdown": {
                    "critical": critical_count,
                    "high": high_count,
                    "medium": medium_count,
                },
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return {"error": str(e)}

    async def _handle_compliance_report(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle compliance report generation request
        """
        try:
            report_type = message.content.get("report_type", "summary")
            time_period = message.content.get("time_period", "monthly")
            frameworks = message.content.get("frameworks", ["GDPR", "HIPAA"])

            # Generate compliance report
            report = await self._generate_compliance_report(report_type, time_period, frameworks)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "compliance_report_response",
                    "report_type": report_type,
                    "time_period": time_period,
                    "frameworks": frameworks,
                    "report": report,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Compliance report handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _generate_compliance_report(
        self, report_type: str, time_period: str, frameworks: list[str]
    ) -> dict[str, Any]:
        """
        Generate compliance report
        """
        try:
            report = {
                "report_type": report_type,
                "time_period": time_period,
                "frameworks": frameworks,
                "generated_at": datetime.now(),
                "executive_summary": {},
                "detailed_findings": {},
                "recommendations": [],
                "compliance_trends": {},
            }

            # Calculate date range
            end_date = datetime.now()
            if time_period == "weekly":
                start_date = end_date - timedelta(days=7)
            elif time_period == "monthly":
                start_date = end_date - timedelta(days=30)
            elif time_period == "quarterly":
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=365)

            # Gather compliance data
            for framework in frameworks:
                framework_data = await self._gather_framework_data(framework, start_date, end_date)
                report["detailed_findings"][framework] = framework_data

                # Update executive summary
                if framework_data.get("overall_status") == "non_compliant":
                    report["executive_summary"]["critical_issues"] = (
                        report["executive_summary"].get("critical_issues", 0) + 1
                    )

            # Generate recommendations
            report["recommendations"] = await self._generate_report_recommendations(report)

            # Add compliance trends
            report["compliance_trends"] = await self._calculate_compliance_trends(time_period)

            return report

        except Exception as e:
            logger.error(f"Compliance report generation failed: {e}")
            return {"error": str(e)}

    async def _gather_framework_data(
        self, framework: str, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """
        Gather compliance data for a specific framework
        """
        try:
            # Query compliance checks for the framework
            async with get_db_session():
                # Example data gathering - would query actual compliance tables
                framework_data = {
                    "framework": framework,
                    "checks_performed": 25,
                    "compliant_checks": 22,
                    "violations_found": 3,
                    "compliance_score": 0.88,
                    "overall_status": "partially_compliant",
                    "critical_violations": 1,
                    "high_violations": 2,
                    "medium_violations": 0,
                    "violation_details": [
                        {
                            "rule": "data_encryption",
                            "severity": "high",
                            "description": "Database encryption not fully implemented",
                        }
                    ],
                }

                return framework_data

        except Exception as e:
            logger.error(f"Framework data gathering failed for {framework}: {e}")
            return {"error": str(e)}

    async def _generate_report_recommendations(self, report: dict[str, Any]) -> list[str]:
        """
        Generate recommendations based on report findings
        """
        try:
            recommendations = []

            # Analyze findings and generate recommendations
            critical_issues = report.get("executive_summary", {}).get("critical_issues", 0)

            if critical_issues > 0:
                recommendations.append(
                    "Immediate action required for critical compliance violations"
                )
                recommendations.append("Schedule emergency compliance review meeting")

            # Framework-specific recommendations
            for framework, data in report.get("detailed_findings", {}).items():
                if data.get("compliance_score", 1.0) < 0.8:
                    recommendations.append(
                        f"Improve {framework} compliance - current score: {data.get('compliance_score', 0):.2f}"
                    )

                if data.get("critical_violations", 0) > 0:
                    recommendations.append(f"Address critical {framework} violations immediately")

            # General recommendations
            recommendations.extend(
                [
                    "Implement automated compliance monitoring",
                    "Conduct regular compliance training for staff",
                    "Establish compliance review board",
                    "Develop incident response plan for compliance violations",
                ]
            )

            return recommendations

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return ["Review compliance findings with legal team"]

    async def _calculate_compliance_trends(self, time_period: str) -> dict[str, Any]:
        """
        Calculate compliance trends over time
        """
        try:
            # Example trend data - would be calculated from historical data
            trends = {
                "overall_trend": "improving",
                "compliance_score_change": 0.05,
                "violation_trend": "decreasing",
                "critical_issues_change": -2,
                "monthly_scores": [
                    {"month": "Jan", "score": 0.85},
                    {"month": "Feb", "score": 0.87},
                    {"month": "Mar", "score": 0.90},
                ],
            }

            return trends

        except Exception as e:
            logger.error(f"Trend calculation failed: {e}")
            return {"error": str(e)}

    async def _handle_risk_assessment(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle risk assessment request
        """
        try:
            assessment_type = message.content.get("assessment_type", "compliance")
            scope = message.content.get("scope", "organization")
            factors = message.content.get("factors", {})

            # Perform risk assessment
            risk_assessment = await self._perform_risk_assessment(assessment_type, scope, factors)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "risk_assessment_response",
                    "assessment_type": assessment_type,
                    "scope": scope,
                    "assessment": risk_assessment,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Risk assessment handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _perform_risk_assessment(
        self, assessment_type: str, scope: str, factors: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Perform comprehensive risk assessment
        """
        try:
            assessment = {
                "assessment_type": assessment_type,
                "scope": scope,
                "factors": factors,
                "timestamp": datetime.now(),
                "risk_score": 0.0,
                "risk_level": "low",
                "risk_factors": {},
                "mitigation_strategies": [],
                "recommendations": [],
            }

            # Calculate risk score based on factors
            risk_score = await self._calculate_risk_score(factors)
            assessment["risk_score"] = risk_score

            # Determine risk level
            if risk_score >= 8.0:
                assessment["risk_level"] = "critical"
            elif risk_score >= 6.0:
                assessment["risk_level"] = "high"
            elif risk_score >= 4.0:
                assessment["risk_level"] = "medium"
            else:
                assessment["risk_level"] = "low"

            # Identify risk factors
            assessment["risk_factors"] = await self._identify_risk_factors(factors)

            # Generate mitigation strategies
            assessment["mitigation_strategies"] = await self._generate_mitigation_strategies(
                assessment["risk_level"]
            )

            # Generate recommendations
            assessment["recommendations"] = await self._generate_risk_recommendations(assessment)

            return assessment

        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return {"error": str(e)}

    async def _calculate_risk_score(self, factors: dict[str, Any]) -> float:
        """
        Calculate risk score based on factors
        """
        try:
            base_score = 0.0

            # Factor weights
            weights = {
                "data_sensitivity": 0.3,
                "exposure_level": 0.25,
                "threat_level": 0.2,
                "vulnerability_count": 0.15,
                "compliance_gaps": 0.1,
            }

            # Calculate weighted score
            for factor, weight in weights.items():
                factor_value = factors.get(factor, 0)
                if isinstance(factor_value, (int, float)):
                    base_score += factor_value * weight

            # Apply risk multipliers
            if factors.get("regulatory_impact", False):
                base_score *= 1.5
            if factors.get("financial_impact", False):
                base_score *= 1.3
            if factors.get("reputational_impact", False):
                base_score *= 1.2

            return min(10.0, base_score)

        except Exception as e:
            logger.error(f"Risk score calculation failed: {e}")
            return 5.0

    async def _identify_risk_factors(self, factors: dict[str, Any]) -> dict[str, Any]:
        """
        Identify specific risk factors
        """
        try:
            risk_factors = {}

            # Analyze each factor
            for factor_name, factor_value in factors.items():
                if factor_name == "data_sensitivity" and factor_value > 7:
                    risk_factors["high_data_sensitivity"] = (
                        "Highly sensitive data increases breach impact"
                    )
                elif factor_name == "exposure_level" and factor_value > 5:
                    risk_factors["high_exposure"] = "High system exposure increases attack surface"
                elif factor_name == "vulnerability_count" and factor_value > 10:
                    risk_factors["multiple_vulnerabilities"] = "Multiple vulnerabilities present"

            return risk_factors

        except Exception as e:
            logger.error(f"Risk factor identification failed: {e}")
            return {}

    async def _generate_mitigation_strategies(self, risk_level: str) -> list[str]:
        """
        Generate mitigation strategies based on risk level
        """
        try:
            strategies = {
                "critical": [
                    "Immediate security assessment and remediation",
                    "Implement emergency incident response procedures",
                    "Engage external security experts",
                    "Temporary suspension of high-risk operations",
                    "Enhanced monitoring and alerting",
                ],
                "high": [
                    "Priority remediation of high-risk vulnerabilities",
                    "Implement additional security controls",
                    "Conduct security awareness training",
                    "Regular security assessments",
                    "Establish incident response team",
                ],
                "medium": [
                    "Address identified vulnerabilities within defined timeframe",
                    "Implement security best practices",
                    "Regular security monitoring",
                    "Staff training on security procedures",
                    "Periodic security reviews",
                ],
                "low": [
                    "Maintain current security posture",
                    "Regular security updates and patches",
                    "Periodic security assessments",
                    "Security awareness reminders",
                    "Monitor security trends",
                ],
            }

            return strategies.get(risk_level, strategies["low"])

        except Exception as e:
            logger.error(f"Mitigation strategy generation failed: {e}")
            return ["Conduct comprehensive security assessment"]

    async def _generate_risk_recommendations(self, assessment: dict[str, Any]) -> list[str]:
        """
        Generate risk management recommendations
        """
        try:
            recommendations = []
            risk_level = assessment.get("risk_level", "low")
            risk_factors = assessment.get("risk_factors", {})

            # Base recommendations by risk level
            if risk_level == "critical":
                recommendations.extend(
                    [
                        "Immediate executive review required",
                        "Consider business continuity planning activation",
                        "Notify regulatory authorities if required",
                        "Implement crisis communication plan",
                    ]
                )
            elif risk_level == "high":
                recommendations.extend(
                    [
                        "Senior management review within 24 hours",
                        "Develop detailed remediation plan",
                        "Increase monitoring frequency",
                        "Prepare contingency plans",
                    ]
                )

            # Factor-specific recommendations
            for factor in risk_factors.keys():
                if "data_sensitivity" in factor:
                    recommendations.append("Implement enhanced data protection measures")
                elif "exposure" in factor:
                    recommendations.append("Reduce system exposure and attack surface")
                elif "vulnerabilities" in factor:
                    recommendations.append("Prioritize vulnerability remediation")

            return recommendations

        except Exception as e:
            logger.error(f"Risk recommendation generation failed: {e}")
            return ["Consult with security experts for detailed assessment"]

    async def _handle_audit_log(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle audit log request
        """
        try:
            log_type = message.content.get("log_type", "compliance_events")
            time_range = message.content.get("time_range", "24h")
            filters = message.content.get("filters", {})

            # Retrieve audit logs
            audit_logs = await self._retrieve_audit_logs(log_type, time_range, filters)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "audit_log_response",
                    "log_type": log_type,
                    "time_range": time_range,
                    "filters": filters,
                    "logs": audit_logs,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Audit log handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _retrieve_audit_logs(
        self, log_type: str, time_range: str, filters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Retrieve audit logs based on criteria
        """
        try:
            # Calculate time range
            end_time = datetime.now()
            if time_range == "1h":
                start_time = end_time - timedelta(hours=1)
            elif time_range == "24h":
                start_time = end_time - timedelta(hours=24)
            elif time_range == "7d":
                start_time = end_time - timedelta(days=7)
            elif time_range == "30d":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=24)

            # Filter audit trail
            filtered_logs = []
            for log_entry in self.monitoring_state["audit_trail"]:
                if start_time <= log_entry.get("timestamp", datetime.min) <= end_time:
                    # Apply filters
                    if self._matches_filters(log_entry, filters):
                        filtered_logs.append(log_entry)

            return {
                "log_type": log_type,
                "time_range": f"{start_time.isoformat()} to {end_time.isoformat()}",
                "total_entries": len(filtered_logs),
                "entries": filtered_logs[-100:],  # Return last 100 entries
                "filters_applied": filters,
            }

        except Exception as e:
            logger.error(f"Audit log retrieval failed: {e}")
            return {"error": str(e)}

    def _matches_filters(self, log_entry: dict[str, Any], filters: dict[str, Any]) -> bool:
        """
        Check if log entry matches filters
        """
        try:
            for filter_key, filter_value in filters.items():
                if filter_key not in log_entry:
                    return False
                if log_entry[filter_key] != filter_value:
                    return False
            return True

        except Exception as e:
            logger.error(f"Filter matching failed: {e}")
            return False

    async def _handle_regulation_monitoring(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle regulation monitoring request
        """
        try:
            regulations = message.content.get("regulations", ["GDPR", "CCPA"])
            monitoring_type = message.content.get("monitoring_type", "changes")

            # Monitor regulations
            monitoring_results = await self._monitor_regulations(regulations, monitoring_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "regulation_monitoring_response",
                    "regulations": regulations,
                    "monitoring_type": monitoring_type,
                    "results": monitoring_results,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Regulation monitoring handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _monitor_regulations(
        self, regulations: list[str], monitoring_type: str
    ) -> dict[str, Any]:
        """
        Monitor regulatory changes and updates
        """
        try:
            results = {
                "monitoring_type": monitoring_type,
                "regulations_monitored": regulations,
                "updates_found": [],
                "compliance_impacts": {},
                "recommendations": [],
            }

            # Check for regulatory updates (simplified - would integrate with regulatory APIs)
            for regulation in regulations:
                updates = await self._check_regulatory_updates(regulation)
                results["updates_found"].extend(updates)

                if updates:
                    # Assess compliance impact
                    impact = await self._assess_regulatory_impact(regulation, updates)
                    results["compliance_impacts"][regulation] = impact

            # Generate recommendations
            if results["updates_found"]:
                results["recommendations"].extend(
                    [
                        "Review regulatory updates with legal team",
                        "Assess impact on current compliance posture",
                        "Update compliance procedures if necessary",
                        "Conduct gap analysis for new requirements",
                    ]
                )

            return results

        except Exception as e:
            logger.error(f"Regulation monitoring failed: {e}")
            return {"error": str(e)}

    async def _check_regulatory_updates(self, regulation: str) -> list[dict[str, Any]]:
        """
        Check for regulatory updates (placeholder - would integrate with real APIs)
        """
        try:
            # Placeholder - in real implementation would check official regulatory sources
            updates = []

            # Example updates (would be fetched from APIs)
            if regulation == "GDPR":
                updates.append(
                    {
                        "regulation": "GDPR",
                        "update_type": "guidance",
                        "title": "New guidance on AI and data protection",
                        "date": datetime.now() - timedelta(days=30),
                        "impact": "medium",
                    }
                )

            return updates

        except Exception as e:
            logger.error(f"Regulatory update check failed for {regulation}: {e}")
            return []

    async def _assess_regulatory_impact(
        self, regulation: str, updates: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Assess impact of regulatory updates on compliance
        """
        try:
            impact = {
                "regulation": regulation,
                "overall_impact": "low",
                "affected_areas": [],
                "required_actions": [],
                "timeline": "90_days",
            }

            # Analyze updates for impact
            high_impact_updates = [u for u in updates if u.get("impact") == "high"]

            if high_impact_updates:
                impact["overall_impact"] = "high"
                impact["required_actions"].extend(
                    [
                        "Immediate compliance review",
                        "Legal consultation required",
                        "System updates may be needed",
                    ]
                )
                impact["timeline"] = "30_days"

            return impact

        except Exception as e:
            logger.error(f"Regulatory impact assessment failed: {e}")
            return {"error": str(e)}

    async def _handle_compliance_alert(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle compliance alert request
        """
        try:
            alert_type = message.content.get("alert_type", "violation")
            severity = message.content.get("severity", "high")
            details = message.content.get("details", {})

            # Process compliance alert
            alert_result = await self._process_compliance_alert(alert_type, severity, details)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "compliance_alert_response",
                    "alert_type": alert_type,
                    "severity": severity,
                    "result": alert_result,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Compliance alert handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _process_compliance_alert(
        self, alert_type: str, severity: str, details: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process and escalate compliance alert
        """
        try:
            alert = {
                "alert_type": alert_type,
                "severity": severity,
                "details": details,
                "timestamp": datetime.now(),
                "alert_id": str(uuid.uuid4()),
                "status": "active",
                "escalation_level": self._determine_escalation_level(severity),
                "recommended_actions": [],
                "assigned_to": None,
            }

            # Determine recommended actions based on alert type and severity
            alert["recommended_actions"] = self._get_alert_actions(alert_type, severity)

            # Add to alert queue
            self.monitoring_state["alert_queue"].append(alert)

            # Log alert
            await self._log_compliance_event("alert_generated", alert)

            return {
                "alert_id": alert["alert_id"],
                "status": "queued",
                "escalation_level": alert["escalation_level"],
                "estimated_response_time": self._get_response_time(severity),
            }

        except Exception as e:
            logger.error(f"Compliance alert processing failed: {e}")
            return {"error": str(e)}

    def _determine_escalation_level(self, severity: str) -> str:
        """Determine alert escalation level"""
        escalation_map = {
            "critical": "executive",
            "high": "management",
            "medium": "supervisor",
            "low": "team",
        }
        return escalation_map.get(severity, "team")

    def _get_alert_actions(self, alert_type: str, severity: str) -> list[str]:
        """Get recommended actions for alert"""
        actions = {
            "violation": {
                "critical": [
                    "Immediate investigation",
                    "Executive notification",
                    "Legal consultation",
                ],
                "high": [
                    "Priority investigation",
                    "Management notification",
                    "Remediation planning",
                ],
                "medium": [
                    "Investigation within 24h",
                    "Supervisor notification",
                    "Document findings",
                ],
                "low": ["Log and monitor", "Weekly review", "Track trends"],
            },
            "breach": {
                "critical": [
                    "Activate incident response",
                    "Notify authorities",
                    "Customer communication",
                ],
                "high": ["Breach assessment", "Containment procedures", "Impact analysis"],
                "medium": ["Initial assessment", "Stakeholder notification", "Recovery planning"],
                "low": ["Monitor situation", "Document incident", "Review procedures"],
            },
        }

        return actions.get(alert_type, {}).get(severity, ["Review and document"])

    def _get_response_time(self, severity: str) -> str:
        """Get expected response time for alert severity"""
        response_times = {
            "critical": "1_hour",
            "high": "4_hours",
            "medium": "24_hours",
            "low": "7_days",
        }
        return response_times.get(severity, "24_hours")

    async def _perform_automated_checks(self):
        """
        Perform automated compliance checks
        """
        try:
            # Run checks for all configured domains
            for domain in self.compliance_config["compliance_domains"]:
                for framework in self.compliance_config["regulatory_frameworks"]:
                    check_result = await self._perform_compliance_check(
                        framework, domain, "automated"
                    )

                    # Update monitoring state
                    self.monitoring_state["compliance_status"][
                        f"{framework}_{domain}"
                    ] = check_result

                    # Check for violations that need alerts
                    violations = check_result.get("violations_found", [])
                    critical_violations = [v for v in violations if v["severity"] == "critical"]

                    if (
                        len(critical_violations)
                        >= self.compliance_config["alert_thresholds"]["critical_violations"]
                    ):
                        await self._process_compliance_alert(
                            "violation",
                            "critical",
                            {
                                "framework": framework,
                                "domain": domain,
                                "violations": critical_violations,
                            },
                        )

        except Exception as e:
            logger.error(f"Automated checks failed: {e}")

    async def _monitor_violations(self):
        """
        Monitor for ongoing violations and patterns
        """
        try:
            # Analyze violation patterns
            recent_violations = []
            cutoff_time = datetime.now() - timedelta(hours=24)

            for violation_list in self.monitoring_state["violation_history"].values():
                recent_violations.extend(
                    [v for v in violation_list if v.get("timestamp", datetime.min) > cutoff_time]
                )

            # Check for violation patterns
            if (
                len(recent_violations)
                > self.compliance_config["alert_thresholds"]["high_violations"]
            ):
                await self._process_compliance_alert(
                    "pattern",
                    "high",
                    {
                        "violation_count": len(recent_violations),
                        "time_period": "24_hours",
                        "pattern_type": "high_frequency",
                    },
                )

        except Exception as e:
            logger.error(f"Violation monitoring failed: {e}")

    async def _update_compliance_status(self):
        """
        Update overall compliance status
        """
        try:
            # Calculate overall compliance score
            all_checks = list(self.monitoring_state["compliance_status"].values())

            if all_checks:
                compliance_scores = [check.get("compliance_score", 0) for check in all_checks]
                avg_score = np.mean(compliance_scores)

                self.monitoring_state["compliance_status"]["overall"] = {
                    "compliance_score": float(avg_score),
                    "last_updated": datetime.now(),
                    "total_checks": len(all_checks),
                }

        except Exception as e:
            logger.error(f"Compliance status update failed: {e}")

    async def _generate_periodic_reports(self):
        """
        Generate periodic compliance reports
        """
        try:
            # Generate weekly summary report
            report = await self._generate_compliance_report(
                "summary", "weekly", self.compliance_config["regulatory_frameworks"]
            )

            # Store report (would typically save to database or file)
            logger.info(f"Generated periodic compliance report: {report.get('generated_at')}")

        except Exception as e:
            logger.error(f"Periodic report generation failed: {e}")

    async def _process_alerts(self):
        """
        Process queued alerts
        """
        try:
            # Process alerts in queue
            alerts_to_process = list(self.monitoring_state["alert_queue"])
            self.monitoring_state["alert_queue"].clear()

            for alert in alerts_to_process:
                # In real implementation, would send notifications, create tickets, etc.
                logger.warning(
                    f"Processing compliance alert: {alert['alert_id']} - {alert['alert_type']}"
                )

                # Log alert processing
                await self._log_compliance_event("alert_processed", alert)

        except Exception as e:
            logger.error(f"Alert processing failed: {e}")

    async def _log_compliance_event(self, event_type: str, event_data: dict[str, Any]):
        """
        Log compliance event to audit trail
        """
        try:
            log_entry = {
                "event_type": event_type,
                "event_data": event_data,
                "timestamp": datetime.now(),
                "agent_id": self.agent_id,
            }

            self.monitoring_state["audit_trail"].append(log_entry)

        except Exception as e:
            logger.error(f"Compliance event logging failed: {e}")

    async def _log_compliance_check(self, check_result: dict[str, Any]):
        """
        Log compliance check result
        """
        try:
            await self._log_compliance_event("compliance_check", check_result)

            # Update violation history
            violations = check_result.get("violations_found", [])
            for violation in violations:
                rule_name = violation.get("rule", "unknown")
                if rule_name not in self.monitoring_state["violation_history"]:
                    self.monitoring_state["violation_history"][rule_name] = []

                self.monitoring_state["violation_history"][rule_name].append(
                    {
                        "timestamp": datetime.now(),
                        "severity": violation.get("severity"),
                        "details": violation.get("details"),
                    }
                )

        except Exception as e:
            logger.error(f"Compliance check logging failed: {e}")

    async def _log_compliance_events(self):
        """
        Log ongoing compliance events
        """
        try:
            # Log system status, user activities, etc.
            # This would integrate with actual system monitoring
            event = {
                "event_type": "system_status",
                "status": "operational",
                "checks_running": len(self.monitoring_state["active_checks"]),
                "alerts_pending": len(self.monitoring_state["alert_queue"]),
            }

            await self._log_compliance_event("periodic_status", event)

        except Exception as e:
            logger.error(f"Compliance events logging failed: {e}")

    async def _archive_audit_logs(self):
        """
        Archive old audit logs
        """
        try:
            # Archive logs older than 90 days
            cutoff_date = datetime.now() - timedelta(days=90)

            archived_count = 0
            remaining_logs = []

            for log_entry in self.monitoring_state["audit_trail"]:
                if log_entry.get("timestamp", datetime.min) < cutoff_date:
                    archived_count += 1
                    # In real implementation, would save to archive storage
                else:
                    remaining_logs.append(log_entry)

            self.monitoring_state["audit_trail"] = deque(remaining_logs, maxlen=10000)

            if archived_count > 0:
                logger.info(f"Archived {archived_count} old audit log entries")

        except Exception as e:
            logger.error(f"Audit log archiving failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_compliance_monitor_agent():
        # Initialize compliance monitor agent
        agent = ComplianceMonitorAgent()
        await agent.start()

        # Test compliance check
        check_message = AgentMessage(
            id="test_check",
            from_agent="test",
            to_agent="compliance_monitor_agent",
            content={
                "type": "check_compliance",
                "framework": "GDPR",
                "domain": "data_privacy",
                "scope": "full",
            },
            timestamp=datetime.now(),
        )

        print("Testing compliance monitor agent...")
        async for response in agent.process_message(check_message):
            print(f"Compliance check response: {response.content.get('type')}")
            if response.content.get("type") == "compliance_check_response":
                result = response.content.get("result", {})
                print(f"Compliance score: {result.get('compliance_score', 'N/A'):.2f}")
                print(f"Overall status: {result.get('overall_status', 'N/A')}")

        # Test compliance report
        report_message = AgentMessage(
            id="test_report",
            from_agent="test",
            to_agent="compliance_monitor_agent",
            content={
                "type": "generate_compliance_report",
                "report_type": "summary",
                "time_period": "monthly",
                "frameworks": ["GDPR", "HIPAA"],
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(report_message):
            print(f"Compliance report response: {response.content.get('type')}")

        # Test risk assessment
        risk_message = AgentMessage(
            id="test_risk",
            from_agent="test",
            to_agent="compliance_monitor_agent",
            content={
                "type": "assess_risk",
                "assessment_type": "compliance",
                "scope": "organization",
                "factors": {
                    "data_sensitivity": 8,
                    "exposure_level": 6,
                    "threat_level": 7,
                    "regulatory_impact": True,
                },
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(risk_message):
            print(f"Risk assessment response: {response.content.get('type')}")
            if response.content.get("type") == "risk_assessment_response":
                assessment = response.content.get("assessment", {})
                print(f"Risk level: {assessment.get('risk_level', 'N/A')}")
                print(f"Risk score: {assessment.get('risk_score', 'N/A'):.1f}")

        # Stop agent
        await agent.stop()
        print("Compliance monitor agent test completed")

    # Run test
    asyncio.run(test_compliance_monitor_agent())
