"""
Testing Agent: Automated testing and quality assurance
Handles unit tests, integration tests, performance tests, and quality metrics
"""

import asyncio
import logging
import os
import re
import uuid
from collections import deque
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class TestingAgent(BaseAgent):
    """
    Testing Agent for automated testing and quality assurance
    Handles unit tests, integration tests, performance tests, and quality metrics
    """

    def __init__(self, agent_id: str = "testing_agent", config: dict[str, Any] | None = None):
        super().__init__(agent_id, config or {})

        # Testing configuration
        self.testing_config = {
            "test_types": self.config.get(
                "test_types",
                {
                    "unit_tests": True,
                    "integration_tests": True,
                    "performance_tests": True,
                    "security_tests": True,
                    "accessibility_tests": True,
                    "load_tests": True,
                    "stress_tests": True,
                    "regression_tests": True,
                },
            ),
            "test_frameworks": self.config.get(
                "test_frameworks",
                {
                    "pytest": True,
                    "unittest": True,
                    "selenium": True,
                    "locust": True,
                    "jmeter": True,
                    "cypress": True,
                    "playwright": True,
                },
            ),
            "quality_metrics": self.config.get(
                "quality_metrics",
                {
                    "code_coverage": True,
                    "test_coverage": True,
                    "performance_metrics": True,
                    "security_scan": True,
                    "accessibility_score": True,
                    "maintainability_index": True,
                    "cyclomatic_complexity": True,
                },
            ),
            "ci_cd_integration": self.config.get(
                "ci_cd_integration",
                {
                    "github_actions": True,
                    "gitlab_ci": True,
                    "jenkins": True,
                    "azure_devops": True,
                    "automatic_pr_checks": True,
                    "deployment_gates": True,
                },
            ),
            "test_environments": self.config.get(
                "test_environments",
                {
                    "local": True,
                    "staging": True,
                    "production": True,
                    "docker_containers": True,
                    "kubernetes": True,
                },
            ),
            "reporting": self.config.get(
                "reporting",
                {
                    "test_reports": True,
                    "coverage_reports": True,
                    "performance_reports": True,
                    "quality_dashboards": True,
                    "alerts": True,
                    "notifications": True,
                },
            ),
            "processing": self.config.get(
                "processing",
                {
                    "parallel_test_execution": 4,
                    "test_timeout_seconds": 300,
                    "retry_failed_tests": 3,
                    "max_concurrent_tests": 10,
                },
            ),
        }

        # Test management
        self.test_suites = {}
        self.test_results = deque(maxlen=10000)
        self.quality_metrics = {}
        self.test_environments = {}

        # Background tasks
        self.test_scheduler_task = None
        self.quality_monitor_task = None
        self.test_executor_task = None

        logger.info(f"Testing Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the testing agent
        """
        await super().start()

        # Load test data
        await self._load_test_data()

        # Start background tasks
        self.test_scheduler_task = asyncio.create_task(self._continuous_test_scheduler())
        self.quality_monitor_task = asyncio.create_task(self._continuous_quality_monitor())
        self.test_executor_task = asyncio.create_task(self._continuous_test_executor())

        logger.info("Testing agent started")

    async def stop(self):
        """
        Stop the testing agent
        """
        if self.test_scheduler_task:
            self.test_scheduler_task.cancel()
            try:
                await self.test_scheduler_task
            except asyncio.CancelledError:
                pass

        if self.quality_monitor_task:
            self.quality_monitor_task.cancel()
            try:
                await self.quality_monitor_task
            except asyncio.CancelledError:
                pass

        if self.test_executor_task:
            self.test_executor_task.cancel()
            try:
                await self.test_executor_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Testing agent stopped")

    async def _load_test_data(self):
        """
        Load existing test data and configurations
        """
        try:
            # Load test suites, results, metrics, etc.
            await self._load_test_suites()
            await self._load_test_results()
            await self._load_quality_metrics()
            await self._load_test_environments()

            logger.info("Test data loaded")

        except Exception as e:
            logger.error(f"Test data loading failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process testing requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "run_tests":
                async for response in self._handle_test_execution(message):
                    yield response

            elif message_type == "generate_tests":
                async for response in self._handle_test_generation(message):
                    yield response

            elif message_type == "analyze_quality":
                async for response in self._handle_quality_analysis(message):
                    yield response

            elif message_type == "performance_test":
                async for response in self._handle_performance_test(message):
                    yield response

            elif message_type == "security_test":
                async for response in self._handle_security_test(message):
                    yield response

            elif message_type == "generate_report":
                async for response in self._handle_report_generation(message):
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
            logger.error(f"Testing processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_test_execution(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle test execution request
        """
        try:
            test_type = message.content.get("test_type", "unit")
            test_suite = message.content.get("test_suite")
            environment = message.content.get("environment", "local")
            parallel = message.content.get("parallel", True)

            # Execute tests
            test_result = await self._execute_tests(test_type, test_suite, environment, parallel)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "test_execution_response",
                    "test_result": test_result,
                    "test_type": test_type,
                    "test_suite": test_suite,
                    "environment": environment,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Test execution handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _execute_tests(
        self, test_type: str, test_suite: str | None, environment: str, parallel: bool = True
    ) -> dict[str, Any]:
        """
        Execute tests based on type and configuration
        """
        try:
            execution_start = datetime.now()

            # Determine test files
            test_files = await self._get_test_files(test_type, test_suite)

            # Setup test environment
            await self._setup_test_environment(environment)

            # Execute tests
            if parallel and len(test_files) > 1:
                results = await self._execute_tests_parallel(test_files, test_type, environment)
            else:
                results = await self._execute_tests_sequential(test_files, test_type, environment)

            # Aggregate results
            aggregated_result = await self._aggregate_test_results(results)

            # Store results
            await self._store_test_results(aggregated_result)

            # Calculate execution time
            execution_end = datetime.now()
            execution_time = (execution_end - execution_start).total_seconds()

            return {
                "test_type": test_type,
                "test_suite": test_suite,
                "environment": environment,
                "execution_time": execution_time,
                "results": aggregated_result,
                "parallel_execution": parallel,
                "test_files_count": len(test_files),
                "timestamp": execution_end.isoformat(),
            }

        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return {
                "error": str(e),
                "test_type": test_type,
                "timestamp": datetime.now().isoformat(),
            }

    async def _get_test_files(self, test_type: str, test_suite: str | None) -> list[str]:
        """
        Get test files for execution
        """
        try:
            test_files = []

            if test_type == "unit":
                # Find unit test files
                test_files = await self._find_files("**/test_*.py", ["tests/unit", "tests"])
            elif test_type == "integration":
                # Find integration test files
                test_files = await self._find_files("**/test_*.py", ["tests/integration"])
            elif test_type == "performance":
                # Find performance test files
                test_files = await self._find_files("**/test_*.py", ["tests/performance"])
            elif test_type == "security":
                # Find security test files
                test_files = await self._find_files("**/test_*.py", ["tests/security"])

            # Filter by test suite if specified
            if test_suite:
                test_files = [f for f in test_files if test_suite in f]

            return test_files

        except Exception as e:
            logger.error(f"Test files retrieval failed: {e}")
            return []

    async def _find_files(self, pattern: str, directories: list[str]) -> list[str]:
        """
        Find files matching pattern in directories
        """
        try:
            import glob

            found_files = []
            for directory in directories:
                if os.path.exists(directory):
                    pattern_path = os.path.join(directory, pattern)
                    found_files.extend(glob.glob(pattern_path, recursive=True))

            return found_files

        except Exception as e:
            logger.error(f"File finding failed: {e}")
            return []

    async def _setup_test_environment(self, environment: str) -> dict[str, Any]:
        """
        Setup test environment
        """
        try:
            if environment == "local":
                # Setup local test environment
                return {"type": "local", "status": "ready"}
            elif environment == "docker":
                # Setup Docker test environment
                return {"type": "docker", "status": "ready"}
            elif environment == "kubernetes":
                # Setup Kubernetes test environment
                return {"type": "kubernetes", "status": "ready"}
            else:
                return {"type": environment, "status": "unknown"}

        except Exception as e:
            logger.error(f"Test environment setup failed: {e}")
            return {"error": str(e)}

    async def _execute_tests_parallel(
        self, test_files: list[str], test_type: str, environment: str
    ) -> list[dict[str, Any]]:
        """
        Execute tests in parallel
        """
        try:
            import concurrent.futures

            results = []

            # Execute tests in parallel batches
            batch_size = self.testing_config["processing"]["parallel_test_execution"]

            for i in range(0, len(test_files), batch_size):
                batch = test_files[i : i + batch_size]

                with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
                    futures = [
                        executor.submit(
                            self._execute_single_test, test_file, test_type, environment
                        )
                        for test_file in batch
                    ]

                    for future in concurrent.futures.as_completed(futures):
                        try:
                            result = future.result()
                            results.append(result)
                        except Exception as e:
                            logger.error(f"Test execution error: {e}")
                            results.append({"error": str(e)})

            return results

        except Exception as e:
            logger.error(f"Parallel test execution failed: {e}")
            return [{"error": str(e)}]

    async def _execute_tests_sequential(
        self, test_files: list[str], test_type: str, environment: str
    ) -> list[dict[str, Any]]:
        """
        Execute tests sequentially
        """
        try:
            results = []

            for test_file in test_files:
                result = await self._execute_single_test(test_file, test_type, environment)
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Sequential test execution failed: {e}")
            return [{"error": str(e)}]

    async def _execute_single_test(
        self, test_file: str, test_type: str, environment: str
    ) -> dict[str, Any]:
        """
        Execute a single test file
        """
        try:
            test_start = datetime.now()

            # Determine test command
            if test_type in ["unit", "integration"]:
                cmd = ["python", "-m", "pytest", test_file, "-v", "--tb=short"]
            elif test_type == "performance":
                cmd = ["python", "-m", "pytest", test_file, "-v", "--tb=short", "--durations=10"]
            else:
                cmd = ["python", test_file]

            # Execute test
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd(),
            )

            stdout, stderr = await process.communicate()

            test_end = datetime.now()
            execution_time = (test_end - test_start).total_seconds()

            # Parse results
            result = {
                "test_file": test_file,
                "test_type": test_type,
                "environment": environment,
                "execution_time": execution_time,
                "return_code": process.returncode,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "timestamp": test_end.isoformat(),
            }

            # Parse test output for pass/fail counts
            result.update(self._parse_test_output(result["stdout"]))

            return result

        except Exception as e:
            logger.error(f"Single test execution failed: {e}")
            return {"error": str(e), "test_file": test_file}

    def _parse_test_output(self, output: str) -> dict[str, Any]:
        """
        Parse test output for results
        """
        try:
            # Simple parsing for pytest output
            passed = len(re.findall(r"PASSED|passed", output))
            failed = len(re.findall(r"FAILED|failed", output))
            errors = len(re.findall(r"ERROR|error", output))
            skipped = len(re.findall(r"SKIPPED|skipped", output))

            return {
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
                "total": passed + failed + errors + skipped,
            }

        except Exception as e:
            logger.error(f"Test output parsing failed: {e}")
            return {"parsing_error": str(e)}

    async def _aggregate_test_results(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Aggregate test results
        """
        try:
            total_passed = sum(r.get("passed", 0) for r in results)
            total_failed = sum(r.get("failed", 0) for r in results)
            total_errors = sum(r.get("errors", 0) for r in results)
            total_skipped = sum(r.get("skipped", 0) for r in results)
            total_tests = sum(r.get("total", 0) for r in results)

            total_execution_time = sum(r.get("execution_time", 0) for r in results)

            success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

            return {
                "summary": {
                    "total_tests": total_tests,
                    "passed": total_passed,
                    "failed": total_failed,
                    "errors": total_errors,
                    "skipped": total_skipped,
                    "success_rate": round(success_rate, 2),
                    "total_execution_time": round(total_execution_time, 2),
                },
                "details": results,
                "status": "passed" if total_failed == 0 and total_errors == 0 else "failed",
            }

        except Exception as e:
            logger.error(f"Test results aggregation failed: {e}")
            return {"error": str(e)}

    async def _store_test_results(self, results: dict[str, Any]):
        """
        Store test results
        """
        try:
            # Store in memory for now
            self.test_results.append(
                {"id": str(uuid.uuid4()), "results": results, "timestamp": datetime.now()}
            )

        except Exception as e:
            logger.error(f"Test results storage failed: {e}")

    async def _handle_test_generation(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle test generation request
        """
        try:
            code_file = message.content.get("code_file")
            test_type = message.content.get("test_type", "unit")
            coverage_target = message.content.get("coverage_target", 80)

            # Generate tests
            test_code = await self._generate_tests(code_file, test_type, coverage_target)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "test_generation_response",
                    "test_code": test_code,
                    "code_file": code_file,
                    "test_type": test_type,
                    "coverage_target": coverage_target,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Test generation handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _generate_tests(
        self, code_file: str, test_type: str, coverage_target: int
    ) -> dict[str, Any]:
        """
        Generate tests for code file
        """
        try:
            # Read code file
            with open(code_file) as f:
                code_content = f.read()

            # Analyze code structure
            code_analysis = await self._analyze_code_structure(code_content)

            # Generate test cases
            test_cases = await self._generate_test_cases(code_analysis, test_type)

            # Generate test code
            test_code = await self._generate_test_code(test_cases, code_file, test_type)

            # Estimate coverage
            estimated_coverage = await self._estimate_test_coverage(test_code, code_content)

            return {
                "code_file": code_file,
                "test_type": test_type,
                "test_code": test_code,
                "test_cases_count": len(test_cases),
                "estimated_coverage": estimated_coverage,
                "coverage_target": coverage_target,
                "target_met": estimated_coverage >= coverage_target,
            }

        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            return {"error": str(e), "code_file": code_file}

    async def _analyze_code_structure(self, code_content: str) -> dict[str, Any]:
        """
        Analyze code structure for test generation
        """
        try:
            import ast

            tree = ast.parse(code_content)

            functions = []
            classes = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(
                        {
                            "name": node.name,
                            "args": [arg.arg for arg in node.args.args],
                            "returns": node.returns is not None,
                        }
                    )
                elif isinstance(node, ast.ClassDef):
                    classes.append({"name": node.name, "methods": []})

            return {
                "functions": functions,
                "classes": classes,
                "imports": [],  # Could be analyzed further
                "complexity": "medium",  # Could calculate actual complexity
            }

        except Exception as e:
            logger.error(f"Code structure analysis failed: {e}")
            return {"error": str(e)}

    async def _generate_test_cases(
        self, code_analysis: dict[str, Any], test_type: str
    ) -> list[dict[str, Any]]:
        """
        Generate test cases based on code analysis
        """
        try:
            test_cases = []

            # Generate tests for functions
            for func in code_analysis.get("functions", []):
                test_cases.extend(await self._generate_function_tests(func, test_type))

            # Generate tests for classes
            for cls in code_analysis.get("classes", []):
                test_cases.extend(await self._generate_class_tests(cls, test_type))

            return test_cases

        except Exception as e:
            logger.error(f"Test case generation failed: {e}")
            return []

    async def _generate_function_tests(
        self, func: dict[str, Any], test_type: str
    ) -> list[dict[str, Any]]:
        """
        Generate test cases for a function
        """
        try:
            test_cases = []

            func_name = func["name"]
            args = func["args"]

            # Basic test case
            test_cases.append(
                {
                    "type": "function",
                    "function_name": func_name,
                    "test_name": f"test_{func_name}_basic",
                    "inputs": {arg: "test_value" for arg in args},
                    "expected_output": "expected_result",
                    "description": f"Test basic functionality of {func_name}",
                }
            )

            # Edge case tests
            if args:
                test_cases.append(
                    {
                        "type": "function",
                        "function_name": func_name,
                        "test_name": f"test_{func_name}_edge_cases",
                        "inputs": {arg: None for arg in args},
                        "expected_output": None,
                        "description": f"Test edge cases for {func_name}",
                    }
                )

            return test_cases

        except Exception as e:
            logger.error(f"Function test generation failed: {e}")
            return []

    async def _generate_class_tests(
        self, cls: dict[str, Any], test_type: str
    ) -> list[dict[str, Any]]:
        """
        Generate test cases for a class
        """
        try:
            test_cases = []

            class_name = cls["name"]

            # Constructor test
            test_cases.append(
                {
                    "type": "class",
                    "class_name": class_name,
                    "test_name": f"test_{class_name}_init",
                    "inputs": {},
                    "expected_output": "instance",
                    "description": f"Test {class_name} initialization",
                }
            )

            return test_cases

        except Exception as e:
            logger.error(f"Class test generation failed: {e}")
            return []

    async def _generate_test_code(
        self, test_cases: list[dict[str, Any]], code_file: str, test_type: str
    ) -> str:
        """
        Generate test code from test cases
        """
        try:
            code_lines = []

            # Import statements
            code_lines.append("import pytest")
            code_lines.append("import sys")
            code_lines.append("import os")
            code_lines.append("")

            # Add path for imports
            module_path = os.path.dirname(code_file)
            module_name = os.path.basename(code_file).replace(".py", "")

            code_lines.append(f"sys.path.insert(0, '{module_path}')")
            code_lines.append(f"from {module_name} import *")
            code_lines.append("")

            # Generate test functions
            for test_case in test_cases:
                if test_case["type"] == "function":
                    code_lines.extend(await self._generate_function_test_code(test_case))
                elif test_case["type"] == "class":
                    code_lines.extend(await self._generate_class_test_code(test_case))
                code_lines.append("")

            return "\n".join(code_lines)

        except Exception as e:
            logger.error(f"Test code generation failed: {e}")
            return f"# Error generating test code: {str(e)}"

    async def _generate_function_test_code(self, test_case: dict[str, Any]) -> list[str]:
        """
        Generate test code for function test case
        """
        try:
            lines = []

            func_name = test_case["function_name"]
            test_name = test_case["test_name"]

            lines.append(f"def {test_name}():")
            lines.append(f'    """{test_case["description"]}"""')

            # Setup inputs
            for arg, value in test_case["inputs"].items():
                lines.append(f"    {arg} = {repr(value)}")

            # Call function
            args_str = ", ".join(test_case["inputs"].keys())
            lines.append(f"    result = {func_name}({args_str})")

            # Assert result
            expected = test_case["expected_output"]
            if expected == "expected_result":
                lines.append("    assert result is not None  # Replace with actual assertion")
            else:
                lines.append(f"    assert result == {repr(expected)}")

            return lines

        except Exception as e:
            logger.error(f"Function test code generation failed: {e}")
            return [f"    # Error: {str(e)}"]

    async def _generate_class_test_code(self, test_case: dict[str, Any]) -> list[str]:
        """
        Generate test code for class test case
        """
        try:
            lines = []

            class_name = test_case["class_name"]
            test_name = test_case["test_name"]

            lines.append(f"def {test_name}():")
            lines.append(f'    """{test_case["description"]}"""')

            # Create instance
            lines.append(f"    instance = {class_name}()")
            lines.append("    assert instance is not None")

            return lines

        except Exception as e:
            logger.error(f"Class test code generation failed: {e}")
            return [f"    # Error: {str(e)}"]

    async def _estimate_test_coverage(self, test_code: str, code_content: str) -> float:
        """
        Estimate test coverage
        """
        try:
            # Simple estimation based on code analysis
            # In real implementation, would use coverage tools

            # Count functions in original code
            import ast

            tree = ast.parse(code_content)
            functions_count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))

            # Count test functions
            test_functions_count = test_code.count("def test_")

            # Estimate coverage
            if functions_count > 0:
                coverage = min(100.0, (test_functions_count / functions_count) * 100)
            else:
                coverage = 0.0

            return round(coverage, 2)

        except Exception as e:
            logger.error(f"Coverage estimation failed: {e}")
            return 0.0

    # Background monitoring tasks
    async def _continuous_test_scheduler(self):
        """
        Continuous test scheduling
        """
        try:
            while True:
                try:
                    # Schedule automated tests
                    await self._schedule_automated_tests()

                    # Check for test triggers
                    await self._check_test_triggers()

                except Exception as e:
                    logger.error(f"Test scheduler error: {e}")

                # Schedule every 30 minutes
                await asyncio.sleep(1800)

        except asyncio.CancelledError:
            logger.info("Test scheduler cancelled")
            raise

    async def _continuous_quality_monitor(self):
        """
        Continuous quality monitoring
        """
        try:
            while True:
                try:
                    # Monitor code quality
                    await self._monitor_code_quality()

                    # Generate quality reports
                    await self._generate_quality_reports()

                except Exception as e:
                    logger.error(f"Quality monitor error: {e}")

                # Monitor every 60 minutes
                await asyncio.sleep(3600)

        except asyncio.CancelledError:
            logger.info("Quality monitor cancelled")
            raise

    async def _continuous_test_executor(self):
        """
        Continuous test execution
        """
        try:
            while True:
                try:
                    # Execute scheduled tests
                    await self._execute_scheduled_tests()

                    # Clean up old test results
                    await self._cleanup_old_results()

                except Exception as e:
                    logger.error(f"Test executor error: {e}")

                # Execute every 15 minutes
                await asyncio.sleep(900)

        except asyncio.CancelledError:
            logger.info("Test executor cancelled")
            raise

    # Additional helper methods would continue...

    async def _load_test_suites(self):
        """Load test suites"""
        try:
            # Implementation for loading test suites
            pass
        except Exception as e:
            logger.error(f"Test suites loading failed: {e}")

    async def _load_test_results(self):
        """Load test results"""
        try:
            # Implementation for loading test results
            pass
        except Exception as e:
            logger.error(f"Test results loading failed: {e}")

    async def _load_quality_metrics(self):
        """Load quality metrics"""
        try:
            # Implementation for loading quality metrics
            pass
        except Exception as e:
            logger.error(f"Quality metrics loading failed: {e}")

    async def _load_test_environments(self):
        """Load test environments"""
        try:
            # Implementation for loading test environments
            pass
        except Exception as e:
            logger.error(f"Test environments loading failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_testing_agent():
        # Initialize testing agent
        agent = TestingAgent()
        await agent.start()

        # Test test execution
        test_message = AgentMessage(
            id="test_execution",
            from_agent="test",
            to_agent="testing_agent",
            content={
                "type": "run_tests",
                "test_type": "unit",
                "environment": "local",
                "parallel": False,
            },
            timestamp=datetime.now(),
        )

        print("Testing testing agent...")
        async for response in agent.process_message(test_message):
            print(f"Test response: {response.content.get('type')}")
            test_result = response.content.get("test_result")
            print(f"Tests executed: {test_result.get('test_type')}")

        # Test test generation
        generation_message = AgentMessage(
            id="test_generation",
            from_agent="test",
            to_agent="testing_agent",
            content={
                "type": "generate_tests",
                "code_file": "agents/base_agent.py",
                "test_type": "unit",
                "coverage_target": 80,
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(generation_message):
            print(f"Generation response: {response.content.get('type')}")
            test_code = response.content.get("test_code")
            print(f"Test code generated: {len(test_code) if test_code else 0} characters")

        # Stop agent
        await agent.stop()
        print("Testing agent test completed")

    # Run test
    asyncio.run(test_testing_agent())
