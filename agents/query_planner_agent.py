"""
Query Planner Agent: Intelligent query planning and orchestration
Uses LangGraph to coordinate multi-agent workflows for complex queries
"""
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import asyncio
import json
from datetime import datetime, timedelta
from collections import defaultdict
import uuid

from langgraph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import CustomsData, Company, HSCode

logger = logging.getLogger(__name__)


class QueryPlannerAgent(BaseAgent):
    """
    Query Planner Agent for intelligent query planning and orchestration
    Uses LangGraph to coordinate complex multi-agent workflows
    """
    
    def __init__(
        self,
        agent_id: str = "query_planner_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # LangGraph setup
        self.workflow = self._build_query_workflow()
        
        # Agent capabilities registry
        self.agent_capabilities = self._load_agent_capabilities()
        
        # Query complexity thresholds
        self.complexity_thresholds = {
            "simple": 1,
            "medium": 3,
            "complex": 5,
            "very_complex": 10
        }
        
        # Performance tracking
        self.query_history = []
        self.agent_performance = defaultdict(dict)
        
        logger.info(f"Query Planner Agent initialized: {agent_id}")
    
    def _build_query_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow for query processing
        """
        try:
            # Define workflow state
            class QueryState:
                def __init__(self):
                    self.query = ""
                    self.query_type = ""
                    self.complexity = "simple"
                    self.required_agents = []
                    self.execution_plan = []
                    self.results = {}
                    self.metadata = {}
                    self.errors = []
            
            # Create workflow
            workflow = StateGraph(QueryState)
            
            # Add nodes
            workflow.add_node("analyze_query", self._analyze_query_node)
            workflow.add_node("plan_execution", self._plan_execution_node)
            workflow.add_node("coordinate_agents", self._coordinate_agents_node)
            workflow.add_node("aggregate_results", self._aggregate_results_node)
            workflow.add_node("validate_results", self._validate_results_node)
            
            # Add edges
            workflow.add_edge("analyze_query", "plan_execution")
            workflow.add_edge("plan_execution", "coordinate_agents")
            workflow.add_edge("coordinate_agents", "aggregate_results")
            workflow.add_edge("aggregate_results", "validate_results")
            workflow.add_edge("validate_results", END)
            
            # Set entry point
            workflow.set_entry_point("analyze_query")
            
            return workflow.compile()
            
        except Exception as e:
            logger.error(f"Workflow building failed: {e}")
            return None
    
    def _load_agent_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """
        Load capabilities of available agents
        """
        return {
            "retriever_agent": {
                "capabilities": ["search", "retrieve", "filter"],
                "specialties": ["document_search", "data_retrieval", "similarity_search"],
                "performance_score": 0.9,
                "cost_per_query": 0.1
            },
            "miner_agent": {
                "capabilities": ["analyze", "extract", "correlate"],
                "specialties": ["pattern_mining", "anomaly_detection", "correlation_analysis"],
                "performance_score": 0.85,
                "cost_per_query": 0.2
            },
            "arbiter_agent": {
                "capabilities": ["validate", "consolidate", "decide"],
                "specialties": ["result_validation", "consensus_building", "final_decision"],
                "performance_score": 0.95,
                "cost_per_query": 0.05
            },
            "forecast_agent": {
                "capabilities": ["predict", "forecast", "trend_analysis"],
                "specialties": ["time_series_forecasting", "trend_prediction", "scenario_planning"],
                "performance_score": 0.8,
                "cost_per_query": 0.3
            },
            "corruption_detector_agent": {
                "capabilities": ["detect", "investigate", "alert"],
                "specialties": ["fraud_detection", "corruption_analysis", "risk_assessment"],
                "performance_score": 0.88,
                "cost_per_query": 0.25
            },
            "lobby_map_agent": {
                "capabilities": ["network_analysis", "relationship_mapping", "influence_detection"],
                "specialties": ["company_networks", "influence_mapping", "lobby_detection"],
                "performance_score": 0.82,
                "cost_per_query": 0.2
            }
        }
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process query planning requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "plan_query":
                async for response in self._handle_query_planning(message):
                    yield response
                    
            elif message_type == "execute_query":
                async for response in self._handle_query_execution(message):
                    yield response
                    
            elif message_type == "optimize_plan":
                async for response in self._handle_plan_optimization(message):
                    yield response
                    
            elif message_type == "get_performance":
                async for response in self._handle_performance_request(message):
                    yield response
                    
            else:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": f"Unknown message type: {message_type}"
                    },
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Query planning failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _handle_query_planning(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle query planning request
        """
        try:
            query = message.content.get("query", "")
            context = message.content.get("context", {})
            
            if not query:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Query required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Analyze query and create plan
            query_analysis = await self._analyze_query(query, context)
            execution_plan = await self._create_execution_plan(query_analysis)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "query_plan_response",
                    "query": query,
                    "analysis": query_analysis,
                    "execution_plan": execution_plan
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Query planning failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _analyze_query(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze query to determine requirements and complexity
        """
        try:
            analysis = {
                "query_type": "unknown",
                "complexity": "simple",
                "required_capabilities": [],
                "data_requirements": [],
                "estimated_cost": 0.0,
                "estimated_time": 0.0,
                "confidence_score": 0.0
            }
            
            # Use LLM to analyze query
            analysis_prompt = f"""
            Analyze this query and determine its requirements:
            
            Query: {query}
            Context: {json.dumps(context, indent=2)}
            
            Return a JSON with:
            - query_type: (search/retrieval/analysis/forecast/detection/network/investigation)
            - complexity: (simple/medium/complex/very_complex)
            - required_capabilities: list of needed capabilities
            - data_requirements: types of data needed
            - reasoning: brief explanation
            """
            
            # Get LLM response for analysis
            llm_response = await self._call_llm_for_analysis(analysis_prompt)
            
            if llm_response:
                analysis.update(llm_response)
            
            # Calculate complexity score
            complexity_score = self._calculate_complexity_score(query, analysis)
            analysis["complexity_score"] = complexity_score
            
            # Determine required agents
            required_agents = self._determine_required_agents(analysis)
            analysis["required_agents"] = required_agents
            
            # Estimate cost and time
            cost_estimate = self._estimate_execution_cost(required_agents)
            time_estimate = self._estimate_execution_time(required_agents, complexity_score)
            
            analysis["estimated_cost"] = cost_estimate
            analysis["estimated_time"] = time_estimate
            
            return analysis
            
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            return {"error": str(e)}
    
    async def _call_llm_for_analysis(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Call LLM for query analysis
        """
        try:
            # Use model registry to get appropriate LLM
            from ..agents.model_registry import get_model_for_task
            
            llm = get_model_for_task("analysis", "query_analysis")
            
            if not llm:
                return None
            
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            
            # Parse JSON response
            try:
                result = json.loads(response.content)
                return result
            except json.JSONDecodeError:
                # Try to extract JSON from response
                content = response.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                
                return json.loads(content.strip())
                
        except Exception as e:
            logger.error(f"LLM analysis call failed: {e}")
            return None
    
    def _calculate_complexity_score(self, query: str, analysis: Dict[str, Any]) -> float:
        """
        Calculate query complexity score
        """
        try:
            score = 0.0
            
            # Length-based complexity
            query_length = len(query.split())
            score += min(query_length / 50, 2.0)  # Max 2 points for length
            
            # Keyword-based complexity
            complex_keywords = [
                "correlation", "predict", "forecast", "anomaly", "network",
                "influence", "lobby", "fraud", "corruption", "trend",
                "optimization", "comparison", "aggregation", "clustering"
            ]
            
            query_lower = query.lower()
            keyword_count = sum(1 for keyword in complex_keywords if keyword in query_lower)
            score += keyword_count * 0.5
            
            # Capability-based complexity
            capability_count = len(analysis.get("required_capabilities", []))
            score += capability_count * 0.3
            
            # Data requirement complexity
            data_req_count = len(analysis.get("data_requirements", []))
            score += data_req_count * 0.2
            
            return min(score, 10.0)  # Cap at 10
            
        except Exception as e:
            logger.error(f"Complexity calculation failed: {e}")
            return 1.0
    
    def _determine_required_agents(self, analysis: Dict[str, Any]) -> List[str]:
        """
        Determine which agents are required for the query
        """
        try:
            required_agents = []
            capabilities = analysis.get("required_capabilities", [])
            query_type = analysis.get("query_type", "")
            
            # Map capabilities to agents
            capability_agent_map = {
                "search": "retriever_agent",
                "retrieve": "retriever_agent",
                "filter": "retriever_agent",
                "analyze": "miner_agent",
                "extract": "miner_agent",
                "correlate": "miner_agent",
                "validate": "arbiter_agent",
                "consolidate": "arbiter_agent",
                "decide": "arbiter_agent",
                "predict": "forecast_agent",
                "forecast": "forecast_agent",
                "trend_analysis": "forecast_agent",
                "detect": "corruption_detector_agent",
                "investigate": "corruption_detector_agent",
                "alert": "corruption_detector_agent",
                "network_analysis": "lobby_map_agent",
                "relationship_mapping": "lobby_map_agent",
                "influence_detection": "lobby_map_agent"
            }
            
            # Add agents based on capabilities
            for capability in capabilities:
                agent = capability_agent_map.get(capability)
                if agent and agent not in required_agents:
                    required_agents.append(agent)
            
            # Add agents based on query type
            query_type_agent_map = {
                "search": ["retriever_agent"],
                "retrieval": ["retriever_agent"],
                "analysis": ["miner_agent", "arbiter_agent"],
                "forecast": ["forecast_agent", "arbiter_agent"],
                "detection": ["corruption_detector_agent", "arbiter_agent"],
                "network": ["lobby_map_agent", "arbiter_agent"],
                "investigation": ["corruption_detector_agent", "lobby_map_agent", "arbiter_agent"]
            }
            
            type_agents = query_type_agent_map.get(query_type, [])
            for agent in type_agents:
                if agent not in required_agents:
                    required_agents.append(agent)
            
            # Always include arbiter for complex queries
            complexity = analysis.get("complexity", "simple")
            if complexity in ["complex", "very_complex"] and "arbiter_agent" not in required_agents:
                required_agents.append("arbiter_agent")
            
            return required_agents
            
        except Exception as e:
            logger.error(f"Agent determination failed: {e}")
            return ["retriever_agent", "arbiter_agent"]
    
    def _estimate_execution_cost(self, agents: List[str]) -> float:
        """
        Estimate execution cost based on required agents
        """
        try:
            total_cost = 0.0
            
            for agent in agents:
                agent_info = self.agent_capabilities.get(agent, {})
                cost_per_query = agent_info.get("cost_per_query", 0.1)
                total_cost += cost_per_query
            
            return total_cost
            
        except Exception as e:
            return 1.0
    
    def _estimate_execution_time(self, agents: List[str], complexity_score: float) -> float:
        """
        Estimate execution time in seconds
        """
        try:
            base_time = 5.0  # Base 5 seconds
            agent_time = len(agents) * 2.0  # 2 seconds per agent
            complexity_time = complexity_score * 1.0  # 1 second per complexity point
            
            return base_time + agent_time + complexity_time
            
        except Exception as e:
            return 10.0
    
    async def _create_execution_plan(
        self,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create detailed execution plan
        """
        try:
            required_agents = analysis.get("required_agents", [])
            complexity = analysis.get("complexity", "simple")
            
            execution_plan = {
                "stages": [],
                "parallel_execution": [],
                "sequential_execution": [],
                "fallback_agents": [],
                "timeout_seconds": 300,
                "max_retries": 3,
                "cost_budget": 10.0
            }
            
            # Define execution stages based on complexity
            if complexity == "simple":
                execution_plan["stages"] = [
                    {
                        "stage": "data_retrieval",
                        "agents": ["retriever_agent"],
                        "parallel": False,
                        "timeout": 60
                    },
                    {
                        "stage": "result_validation",
                        "agents": ["arbiter_agent"],
                        "parallel": False,
                        "timeout": 30
                    }
                ]
                
            elif complexity == "medium":
                execution_plan["stages"] = [
                    {
                        "stage": "data_retrieval",
                        "agents": ["retriever_agent"],
                        "parallel": False,
                        "timeout": 90
                    },
                    {
                        "stage": "analysis",
                        "agents": ["miner_agent"],
                        "parallel": True,
                        "timeout": 120
                    },
                    {
                        "stage": "consolidation",
                        "agents": ["arbiter_agent"],
                        "parallel": False,
                        "timeout": 60
                    }
                ]
                
            elif complexity in ["complex", "very_complex"]:
                execution_plan["stages"] = [
                    {
                        "stage": "initial_retrieval",
                        "agents": ["retriever_agent"],
                        "parallel": False,
                        "timeout": 120
                    },
                    {
                        "stage": "parallel_analysis",
                        "agents": required_agents[:-1],  # All except arbiter
                        "parallel": True,
                        "timeout": 180
                    },
                    {
                        "stage": "coordination",
                        "agents": ["arbiter_agent"],
                        "parallel": False,
                        "timeout": 90
                    },
                    {
                        "stage": "final_validation",
                        "agents": ["arbiter_agent"],
                        "parallel": False,
                        "timeout": 60
                    }
                ]
            
            # Set timeout based on complexity
            if complexity == "very_complex":
                execution_plan["timeout_seconds"] = 600
            elif complexity == "complex":
                execution_plan["timeout_seconds"] = 450
            elif complexity == "medium":
                execution_plan["timeout_seconds"] = 300
            
            # Set cost budget
            estimated_cost = analysis.get("estimated_cost", 1.0)
            execution_plan["cost_budget"] = estimated_cost * 2.0  # 2x buffer
            
            return execution_plan
            
        except Exception as e:
            logger.error(f"Execution plan creation failed: {e}")
            return {"error": str(e)}
    
    async def _handle_query_execution(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle query execution request
        """
        try:
            query = message.content.get("query", "")
            execution_plan = message.content.get("execution_plan", {})
            
            if not query or not execution_plan:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Query and execution plan required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Execute query using LangGraph workflow
            execution_result = await self._execute_query_workflow(query, execution_plan)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "query_execution_response",
                    "query": query,
                    "execution_result": execution_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _execute_query_workflow(
        self,
        query: str,
        execution_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute query using LangGraph workflow
        """
        try:
            # Initialize workflow state
            initial_state = {
                "query": query,
                "execution_plan": execution_plan,
                "results": {},
                "metadata": {
                    "start_time": datetime.now(),
                    "stages_completed": [],
                    "agent_calls": []
                },
                "errors": []
            }
            
            # Execute workflow
            if self.workflow:
                final_state = await self.workflow.ainvoke(initial_state)
                
                # Add completion metadata
                final_state["metadata"]["end_time"] = datetime.now()
                final_state["metadata"]["total_time"] = (
                    final_state["metadata"]["end_time"] - final_state["metadata"]["start_time"]
                ).total_seconds()
                
                # Track performance
                self._track_query_performance(query, final_state)
                
                return final_state
            else:
                return {"error": "Workflow not available"}
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {"error": str(e)}
    
    # LangGraph node functions
    async def _analyze_query_node(self, state):
        """Analyze query node"""
        try:
            analysis = await self._analyze_query(state["query"], {})
            state["query_type"] = analysis.get("query_type", "unknown")
            state["complexity"] = analysis.get("complexity", "simple")
            state["required_agents"] = analysis.get("required_agents", [])
            state["metadata"]["analysis"] = analysis
            return state
        except Exception as e:
            state["errors"].append(f"Analysis failed: {e}")
            return state
    
    async def _plan_execution_node(self, state):
        """Plan execution node"""
        try:
            analysis = state["metadata"]["analysis"]
            execution_plan = await self._create_execution_plan(analysis)
            state["execution_plan"] = execution_plan
            return state
        except Exception as e:
            state["errors"].append(f"Planning failed: {e}")
            return state
    
    async def _coordinate_agents_node(self, state):
        """Coordinate agents node"""
        try:
            execution_plan = state["execution_plan"]
            stages = execution_plan.get("stages", [])
            
            for stage in stages:
                stage_name = stage["stage"]
                agents = stage["agents"]
                parallel = stage.get("parallel", False)
                timeout = stage.get("timeout", 60)
                
                # Execute stage
                stage_results = await self._execute_stage(
                    stage_name, agents, state["query"], parallel, timeout
                )
                
                state["results"][stage_name] = stage_results
                state["metadata"]["stages_completed"].append(stage_name)
                
                # Check for errors
                if "error" in stage_results:
                    state["errors"].append(f"Stage {stage_name} failed: {stage_results['error']}")
                    break
            
            return state
        except Exception as e:
            state["errors"].append(f"Coordination failed: {e}")
            return state
    
    async def _execute_stage(
        self,
        stage_name: str,
        agents: List[str],
        query: str,
        parallel: bool,
        timeout: int
    ) -> Dict[str, Any]:
        """
        Execute a workflow stage
        """
        try:
            stage_results = {}
            
            if parallel:
                # Execute agents in parallel
                tasks = []
                for agent_id in agents:
                    task = self._call_agent(agent_id, query, stage_name, timeout)
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    agent_id = agents[i]
                    if isinstance(result, Exception):
                        stage_results[agent_id] = {"error": str(result)}
                    else:
                        stage_results[agent_id] = result
            else:
                # Execute agents sequentially
                for agent_id in agents:
                    result = await self._call_agent(agent_id, query, stage_name, timeout)
                    stage_results[agent_id] = result
                    
                    # Stop on first error in sequential execution
                    if "error" in result:
                        break
            
            return stage_results
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _call_agent(
        self,
        agent_id: str,
        query: str,
        context: str,
        timeout: int
    ) -> Dict[str, Any]:
        """
        Call an agent with timeout
        """
        try:
            # Create agent message
            message = AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=agent_id,
                content={
                    "type": "process_query",
                    "query": query,
                    "context": context
                },
                timestamp=datetime.now()
            )
            
            # Call agent (simplified - in real implementation, use agent registry)
            # For now, return mock response
            await asyncio.sleep(0.1)  # Simulate processing time
            
            return {
                "status": "completed",
                "response": f"Mock response from {agent_id} for query: {query[:50]}...",
                "confidence": 0.8,
                "processing_time": 0.1
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _aggregate_results_node(self, state):
        """Aggregate results node"""
        try:
            all_results = state["results"]
            
            # Simple aggregation - combine all results
            aggregated = {
                "total_stages": len(all_results),
                "stage_results": all_results,
                "summary": {}
            }
            
            # Create summary
            successful_stages = 0
            total_confidence = 0.0
            total_time = 0.0
            
            for stage_name, stage_result in all_results.items():
                if isinstance(stage_result, dict) and "error" not in stage_result:
                    successful_stages += 1
                
                # Aggregate agent results
                if isinstance(stage_result, dict):
                    for agent_result in stage_result.values():
                        if isinstance(agent_result, dict):
                            confidence = agent_result.get("confidence", 0)
                            processing_time = agent_result.get("processing_time", 0)
                            total_confidence += confidence
                            total_time += processing_time
            
            aggregated["summary"] = {
                "successful_stages": successful_stages,
                "total_stages": len(all_results),
                "average_confidence": total_confidence / max(1, len(all_results)),
                "total_processing_time": total_time
            }
            
            state["aggregated_results"] = aggregated
            return state
            
        except Exception as e:
            state["errors"].append(f"Aggregation failed: {e}")
            return state
    
    async def _validate_results_node(self, state):
        """Validate results node"""
        try:
            aggregated = state.get("aggregated_results", {})
            summary = aggregated.get("summary", {})
            
            validation = {
                "is_valid": True,
                "issues": [],
                "confidence_score": summary.get("average_confidence", 0),
                "recommendations": []
            }
            
            # Check for errors
            if state["errors"]:
                validation["is_valid"] = False
                validation["issues"].extend(state["errors"])
            
            # Check confidence threshold
            if validation["confidence_score"] < 0.6:
                validation["issues"].append("Low confidence in results")
                validation["recommendations"].append("Consider re-running with different agents")
            
            # Check successful stages
            successful_stages = summary.get("successful_stages", 0)
            total_stages = summary.get("total_stages", 0)
            
            if successful_stages < total_stages:
                validation["issues"].append(f"Only {successful_stages}/{total_stages} stages completed successfully")
            
            state["validation"] = validation
            return state
            
        except Exception as e:
            state["errors"].append(f"Validation failed: {e}")
            return state
    
    def _track_query_performance(
        self,
        query: str,
        execution_result: Dict[str, Any]
    ):
        """
        Track query performance for optimization
        """
        try:
            performance_data = {
                "query": query[:100],  # Truncate long queries
                "timestamp": datetime.now(),
                "execution_time": execution_result["metadata"]["total_time"],
                "stages_completed": len(execution_result["metadata"]["stages_completed"]),
                "errors": len(execution_result["errors"]),
                "confidence": execution_result.get("validation", {}).get("confidence_score", 0)
            }
            
            self.query_history.append(performance_data)
            
            # Keep only last 1000 queries
            if len(self.query_history) > 1000:
                self.query_history = self.query_history[-1000:]
                
        except Exception as e:
            logger.error(f"Performance tracking failed: {e}")
    
    async def _handle_plan_optimization(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle plan optimization request
        """
        try:
            current_plan = message.content.get("current_plan", {})
            performance_history = message.content.get("performance_history", [])
            
            # Optimize execution plan
            optimized_plan = await self._optimize_execution_plan(current_plan, performance_history)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "plan_optimization_response",
                    "original_plan": current_plan,
                    "optimized_plan": optimized_plan
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Plan optimization failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _optimize_execution_plan(
        self,
        current_plan: Dict[str, Any],
        performance_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Optimize execution plan based on performance history
        """
        try:
            optimized_plan = current_plan.copy()
            
            # Analyze performance patterns
            if performance_history:
                # Find best performing agent combinations
                successful_executions = [p for p in performance_history if p.get("errors", 0) == 0]
                
                if successful_executions:
                    avg_time = sum(p["execution_time"] for p in successful_executions) / len(successful_executions)
                    avg_confidence = sum(p["confidence"] for p in successful_executions) / len(successful_executions)
                    
                    # Adjust timeouts based on historical performance
                    stages = optimized_plan.get("stages", [])
                    for stage in stages:
                        historical_times = [p["execution_time"] for p in successful_executions]
                        if historical_times:
                            avg_stage_time = sum(historical_times) / len(historical_times)
                            stage["timeout"] = max(stage["timeout"], int(avg_stage_time * 1.5))
            
            # Optimize parallel execution
            stages = optimized_plan.get("stages", [])
            for stage in stages:
                agents = stage.get("agents", [])
                
                # Enable parallel execution for stages with multiple independent agents
                if len(agents) > 1 and not stage.get("parallel", False):
                    # Check if agents can work in parallel
                    if self._can_agents_run_parallel(agents):
                        stage["parallel"] = True
            
            return optimized_plan
            
        except Exception as e:
            logger.error(f"Plan optimization failed: {e}")
            return current_plan
    
    def _can_agents_run_parallel(self, agents: List[str]) -> bool:
        """
        Check if agents can run in parallel
        """
        try:
            # Agents that can run in parallel (no dependencies)
            parallel_safe = ["retriever_agent", "miner_agent", "forecast_agent", "corruption_detector_agent"]
            
            return all(agent in parallel_safe for agent in agents)
            
        except Exception as e:
            return False
    
    async def _handle_performance_request(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle performance metrics request
        """
        try:
            # Calculate performance metrics
            performance_metrics = self._calculate_performance_metrics()
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "performance_response",
                    "metrics": performance_metrics
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Performance request failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """
        Calculate performance metrics from query history
        """
        try:
            if not self.query_history:
                return {"error": "No performance data available"}
            
            metrics = {
                "total_queries": len(self.query_history),
                "avg_execution_time": 0.0,
                "avg_confidence": 0.0,
                "success_rate": 0.0,
                "performance_trends": {},
                "agent_performance": {}
            }
            
            # Calculate basic metrics
            execution_times = [q["execution_time"] for q in self.query_history]
            confidences = [q["confidence"] for q in self.query_history]
            errors = [q["errors"] for q in self.query_history]
            
            metrics["avg_execution_time"] = sum(execution_times) / len(execution_times)
            metrics["avg_confidence"] = sum(confidences) / len(confidences)
            metrics["success_rate"] = sum(1 for e in errors if e == 0) / len(errors)
            
            # Performance trends (last 10 vs previous 10)
            if len(self.query_history) >= 20:
                recent = self.query_history[-10:]
                previous = self.query_history[-20:-10]
                
                recent_avg_time = sum(q["execution_time"] for q in recent) / len(recent)
                previous_avg_time = sum(q["execution_time"] for q in previous) / len(previous)
                
                metrics["performance_trends"] = {
                    "execution_time_change": ((recent_avg_time - previous_avg_time) / previous_avg_time) * 100,
                    "trend_direction": "improving" if recent_avg_time < previous_avg_time else "degrading"
                }
            
            # Agent performance (mock data for now)
            metrics["agent_performance"] = {
                agent: {
                    "success_rate": 0.85 + (i * 0.01),  # Mock data
                    "avg_response_time": 2.0 + (i * 0.1),
                    "usage_count": 50 + i * 10
                }
                for i, agent in enumerate(self.agent_capabilities.keys())
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Performance calculation failed: {e}")
            return {"error": str(e)}


# ========== TEST ==========
if __name__ == "__main__":
    async def test_query_planner_agent():
        # Initialize query planner agent
        agent = QueryPlannerAgent()
        
        # Test query planning
        test_message = AgentMessage(
            id="test_plan",
            from_agent="test",
            to_agent="query_planner_agent",
            content={
                "type": "plan_query",
                "query": "Analyze corruption patterns in customs data for company ABC and its network"
            },
            timestamp=datetime.now()
        )
        
        print("Testing query planner agent...")
        async for response in agent.process_message(test_message):
            print(f"Response type: {response.content.get('type')}")
            if response.content.get("type") == "query_plan_response":
                analysis = response.content.get("analysis", {})
                plan = response.content.get("execution_plan", {})
                print(f"Query type: {analysis.get('query_type')}")
                print(f"Complexity: {analysis.get('complexity')}")
                print(f"Required agents: {analysis.get('required_agents')}")
                print(f"Estimated cost: ${analysis.get('estimated_cost', 0):.2f}")
                print(f"Stages: {len(plan.get('stages', []))}")
        
        print("Query planner agent test completed")
    
    # Run test
    asyncio.run(test_query_planner_agent())
