"""
Lobby Map Agent: Network analysis for company relationships
Uses graph algorithms to detect lobbying networks and influence patterns
"""
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import networkx as nx
from collections import defaultdict

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import CustomsData, Company, HSCode, LobbyMap

logger = logging.getLogger(__name__)


class LobbyMapAgent(BaseAgent):
    """
    Lobby Map Agent for analyzing company relationship networks
    Detects lobbying patterns, influence networks, and connected entities
    """
    
    def __init__(
        self,
        agent_id: str = "lobby_map_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Network analysis settings
        self.min_relationship_strength = self.config.get("min_relationship_strength", 0.1)
        self.max_network_depth = self.config.get("max_network_depth", 3)
        self.influence_threshold = self.config.get("influence_threshold", 0.7)
        
        # Graph settings
        self.graph_update_frequency = self.config.get("graph_update_frequency", 24)  # hours
        
        # Cached graphs
        self.company_graph = None
        self.influence_graph = None
        self.last_graph_update = None
        
        logger.info(f"Lobby Map Agent initialized: {agent_id}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process lobby map analysis requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "lobby_network_analysis":
                async for response in self._handle_network_analysis(message):
                    yield response
                    
            elif message_type == "influence_mapping":
                async for response in self._handle_influence_mapping(message):
                    yield response
                    
            elif message_type == "company_relationships":
                async for response in self._handle_company_relationships(message):
                    yield response
                    
            elif message_type == "lobby_detection":
                async for response in self._handle_lobby_detection(message):
                    yield response
                    
            elif message_type == "graph_update":
                async for response in self._handle_graph_update(message):
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
            logger.error(f"Lobby map processing failed: {e}")
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
    
    async def _handle_network_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle network analysis request
        """
        try:
            company_id = message.content.get("company_id")
            analysis_depth = message.content.get("analysis_depth", self.max_network_depth)
            include_indirect = message.content.get("include_indirect", True)
            
            if not company_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "company_id required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Ensure graph is up to date
            await self._ensure_graph_updated()
            
            # Analyze network
            network_analysis = await self._analyze_company_network(
                company_id, analysis_depth, include_indirect
            )
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "network_analysis_response",
                    "company_id": company_id,
                    "analysis": network_analysis
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Network analysis failed: {e}")
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
    
    async def _ensure_graph_updated(self):
        """
        Ensure the relationship graph is up to date
        """
        try:
            if (self.last_graph_update is None or
                (datetime.now() - self.last_graph_update).total_seconds() / 3600 > self.graph_update_frequency):
                
                await self._build_relationship_graph()
                self.last_graph_update = datetime.now()
                logger.info("Relationship graph updated")
                
        except Exception as e:
            logger.error(f"Graph update failed: {e}")
    
    async def _build_relationship_graph(self):
        """
        Build company relationship graph
        """
        try:
            # Get relationship data
            relationships = await self._get_relationship_data()
            
            # Create graphs
            self.company_graph = nx.Graph()
            self.influence_graph = nx.DiGraph()
            
            # Add nodes (companies)
            companies = set()
            for rel in relationships:
                companies.add(rel["company_a"])
                companies.add(rel["company_b"])
            
            for company in companies:
                company_info = await self._get_company_info(company)
                self.company_graph.add_node(company, **company_info)
                self.influence_graph.add_node(company, **company_info)
            
            # Add edges (relationships)
            for rel in relationships:
                # Company graph (undirected)
                self.company_graph.add_edge(
                    rel["company_a"],
                    rel["company_b"],
                    weight=rel["strength"],
                    relationship_type=rel["type"],
                    evidence=rel["evidence"]
                )
                
                # Influence graph (directed)
                if rel.get("directional", False):
                    self.influence_graph.add_edge(
                        rel["company_a"],
                        rel["company_b"],
                        weight=rel["influence_strength"],
                        influence_type=rel["type"]
                    )
            
            logger.info(f"Built relationship graph with {len(companies)} companies and {len(relationships)} relationships")
            
        except Exception as e:
            logger.error(f"Graph building failed: {e}")
    
    async def _get_relationship_data(self) -> List[Dict[str, Any]]:
        """
        Get company relationship data from database
        """
        try:
            relationships = []
            
            async with get_db_session() as session:
                # Relationship 1: Shared addresses/directors (ownership)
                ownership_query = """
                SELECT DISTINCT
                    c1.id as company_a,
                    c2.id as company_b,
                    'ownership' as type,
                    0.8 as strength,
                    0.6 as influence_strength,
                    true as directional,
                    json_build_object('shared_owners', array_agg(distinct o1.owner_name)) as evidence
                FROM companies c1
                JOIN company_owners o1 ON c1.id = o1.company_id
                JOIN company_owners o2 ON o1.owner_name = o2.owner_name AND o1.company_id != o2.company_id
                JOIN companies c2 ON o2.company_id = c2.id
                WHERE c1.id < c2.id
                GROUP BY c1.id, c2.id
                """
                
                ownership_results = await session.execute(ownership_query)
                relationships.extend([
                    dict(row) for row in ownership_results.fetchall()
                ])
                
                # Relationship 2: Business partners (supplier-customer)
                partner_query = """
                SELECT DISTINCT
                    c1.id as company_a,
                    c2.id as company_b,
                    'business_partner' as type,
                    0.6 as strength,
                    0.4 as influence_strength,
                    false as directional,
                    json_build_object('transactions', count(*)) as evidence
                FROM companies c1
                JOIN customs_data cd1 ON c1.id = cd1.company_id
                JOIN customs_data cd2 ON cd1.declaration_number = cd2.declaration_number AND cd1.company_id != cd2.company_id
                JOIN companies c2 ON cd2.company_id = c2.id
                WHERE c1.id < c2.id
                GROUP BY c1.id, c2.id
                HAVING count(*) > 3
                """
                
                partner_results = await session.execute(partner_query)
                relationships.extend([
                    dict(row) for row in partner_results.fetchall()
                ])
                
                # Relationship 3: Industry clusters (same HS codes)
                industry_query = """
                SELECT DISTINCT
                    c1.id as company_a,
                    c2.id as company_b,
                    'industry_cluster' as type,
                    0.4 as strength,
                    0.2 as influence_strength,
                    false as directional,
                    json_build_object('shared_hs_codes', array_agg(distinct cd1.hs_code)) as evidence
                FROM companies c1
                JOIN customs_data cd1 ON c1.id = cd1.company_id
                JOIN customs_data cd2 ON cd1.hs_code = cd2.hs_code AND cd1.company_id != cd2.company_id
                JOIN companies c2 ON cd2.company_id = c2.id
                WHERE c1.id < c2.id
                GROUP BY c1.id, c2.id
                HAVING count(distinct cd1.hs_code) > 5
                """
                
                industry_results = await session.execute(industry_query)
                relationships.extend([
                    dict(row) for row in industry_results.fetchall()
                ])
            
            return relationships
            
        except Exception as e:
            logger.error(f"Relationship data retrieval failed: {e}")
            return []
    
    async def _get_company_info(self, company_id: str) -> Dict[str, Any]:
        """
        Get company information for graph node
        """
        try:
            async with get_db_session() as session:
                company = await session.get(Company, company_id)
                
                if company:
                    # Get company stats
                    stats_query = session.query(
                        CustomsData.value_usd,
                        CustomsData.quantity
                    ).filter(CustomsData.company_id == company_id)
                    
                    stats_results = await session.execute(stats_query)
                    stats = stats_results.fetchall()
                    
                    total_value = sum(float(s[0]) for s in stats if s[0])
                    total_quantity = sum(float(s[1]) for s in stats if s[1])
                    
                    return {
                        "name": company.company_name,
                        "activity_type": company.activity_type,
                        "registration_date": company.registration_date.isoformat() if company.registration_date else None,
                        "total_value_usd": total_value,
                        "total_quantity": total_quantity,
                        "declaration_count": len(stats)
                    }
                else:
                    return {"name": f"Company {company_id}", "error": "Company not found"}
                
        except Exception as e:
            logger.error(f"Company info retrieval failed: {e}")
            return {"name": f"Company {company_id}", "error": str(e)}
    
    async def _analyze_company_network(
        self,
        company_id: str,
        depth: int,
        include_indirect: bool
    ) -> Dict[str, Any]:
        """
        Analyze company relationship network
        """
        try:
            if not self.company_graph or company_id not in self.company_graph:
                return {"error": "Company not found in network"}
            
            # Get direct connections
            direct_connections = list(self.company_graph.neighbors(company_id))
            
            # Get network metrics
            network_analysis = {
                "company_id": company_id,
                "company_info": dict(self.company_graph.nodes[company_id]),
                "direct_connections": len(direct_connections),
                "network_metrics": {},
                "relationship_clusters": [],
                "influence_paths": [],
                "risk_assessment": {}
            }
            
            # Calculate network metrics
            if len(direct_connections) > 0:
                # Degree centrality
                degree_centrality = nx.degree_centrality(self.company_graph)
                network_analysis["network_metrics"]["degree_centrality"] = degree_centrality.get(company_id, 0)
                
                # Betweenness centrality
                betweenness_centrality = nx.betweenness_centrality(self.company_graph)
                network_analysis["network_metrics"]["betweenness_centrality"] = betweenness_centrality.get(company_id, 0)
                
                # Clustering coefficient
                clustering_coeff = nx.clustering(self.company_graph, company_id)
                network_analysis["network_metrics"]["clustering_coefficient"] = clustering_coeff
            
            # Find relationship clusters
            if len(direct_connections) > 1:
                clusters = self._find_relationship_clusters(company_id, direct_connections)
                network_analysis["relationship_clusters"] = clusters
            
            # Analyze influence paths
            if self.influence_graph and company_id in self.influence_graph:
                influence_paths = self._analyze_influence_paths(company_id, depth)
                network_analysis["influence_paths"] = influence_paths
            
            # Risk assessment
            risk_assessment = self._assess_network_risk(company_id, direct_connections)
            network_analysis["risk_assessment"] = risk_assessment
            
            # Get detailed connection info
            connection_details = []
            for conn_id in direct_connections:
                edge_data = self.company_graph.get_edge_data(company_id, conn_id, {})
                conn_info = {
                    "company_id": conn_id,
                    "company_info": dict(self.company_graph.nodes[conn_id]),
                    "relationship_type": edge_data.get("relationship_type"),
                    "relationship_strength": edge_data.get("weight", 0),
                    "evidence": edge_data.get("evidence", {})
                }
                connection_details.append(conn_info)
            
            network_analysis["connection_details"] = connection_details
            
            return network_analysis
            
        except Exception as e:
            logger.error(f"Network analysis failed: {e}")
            return {"error": str(e)}
    
    def _find_relationship_clusters(
        self,
        company_id: str,
        direct_connections: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Find clusters of related companies
        """
        try:
            clusters = []
            
            # Create subgraph of direct connections
            subgraph = self.company_graph.subgraph(direct_connections + [company_id])
            
            # Find connected components
            connected_components = list(nx.connected_components(subgraph))
            
            for i, component in enumerate(connected_components):
                if len(component) > 2:  # Only clusters with more than 2 companies
                    cluster_info = {
                        "cluster_id": f"cluster_{i}",
                        "companies": list(component),
                        "size": len(component),
                        "relationship_types": []
                    }
                    
                    # Get relationship types within cluster
                    cluster_edges = subgraph.edges(component, data=True)
                    rel_types = set()
                    total_strength = 0
                    
                    for _, _, edge_data in cluster_edges:
                        rel_types.add(edge_data.get("relationship_type", "unknown"))
                        total_strength += edge_data.get("weight", 0)
                    
                    cluster_info["relationship_types"] = list(rel_types)
                    cluster_info["avg_relationship_strength"] = total_strength / len(cluster_edges) if cluster_edges else 0
                    
                    clusters.append(cluster_info)
            
            return clusters
            
        except Exception as e:
            logger.error(f"Cluster finding failed: {e}")
            return []
    
    def _analyze_influence_paths(
        self,
        company_id: str,
        max_depth: int
    ) -> List[Dict[str, Any]]:
        """
        Analyze influence paths in the network
        """
        try:
            influence_paths = []
            
            if not self.influence_graph or company_id not in self.influence_graph:
                return influence_paths
            
            # Find all paths up to max_depth
            targets = [n for n in self.influence_graph.nodes() if n != company_id]
            
            for target in targets[:20]:  # Limit to first 20 targets
                try:
                    # Find shortest path
                    if nx.has_path(self.influence_graph, company_id, target):
                        path = nx.shortest_path(self.influence_graph, company_id, target)
                        
                        if len(path) <= max_depth + 1:  # +1 because path includes start
                            path_length = len(path) - 1
                            path_strength = self._calculate_path_strength(path)
                            
                            influence_paths.append({
                                "target_company": target,
                                "path": path,
                                "path_length": path_length,
                                "path_strength": path_strength,
                                "influence_type": "indirect"
                            })
                            
                except nx.NetworkXNoPath:
                    continue
            
            # Sort by path strength
            influence_paths.sort(key=lambda x: x["path_strength"], reverse=True)
            
            return influence_paths[:10]  # Return top 10
            
        except Exception as e:
            logger.error(f"Influence path analysis failed: {e}")
            return []
    
    def _calculate_path_strength(self, path: List[str]) -> float:
        """
        Calculate strength of influence path
        """
        try:
            total_strength = 1.0
            
            for i in range(len(path) - 1):
                edge_data = self.influence_graph.get_edge_data(path[i], path[i+1], {})
                edge_weight = edge_data.get("weight", 0.5)
                total_strength *= edge_weight
            
            return total_strength
            
        except Exception as e:
            return 0.0
    
    def _assess_network_risk(
        self,
        company_id: str,
        direct_connections: List[str]
    ) -> Dict[str, Any]:
        """
        Assess network-based risk
        """
        try:
            risk_assessment = {
                "overall_risk_score": 0.0,
                "risk_factors": {},
                "risk_level": "low"
            }
            
            # Risk factor 1: Network centrality
            degree_centrality = nx.degree_centrality(self.company_graph).get(company_id, 0)
            risk_assessment["risk_factors"]["network_centrality"] = degree_centrality
            
            # Risk factor 2: Connection to high-risk companies
            high_risk_connections = 0
            for conn_id in direct_connections:
                conn_info = self.company_graph.nodes[conn_id]
                # Simple heuristic: companies with very high transaction volumes might be higher risk
                if conn_info.get("total_value_usd", 0) > 10000000:  # $10M threshold
                    high_risk_connections += 1
            
            risk_assessment["risk_factors"]["high_risk_connections"] = high_risk_connections / max(1, len(direct_connections))
            
            # Risk factor 3: Cluster membership
            subgraph = self.company_graph.subgraph(direct_connections + [company_id])
            components = list(nx.connected_components(subgraph))
            largest_component = max(components, key=len) if components else set()
            
            risk_assessment["risk_factors"]["cluster_size"] = len(largest_component) / len(self.company_graph.nodes())
            
            # Calculate overall risk score
            risk_score = (
                degree_centrality * 0.4 +
                risk_assessment["risk_factors"]["high_risk_connections"] * 0.3 +
                risk_assessment["risk_factors"]["cluster_size"] * 0.3
            )
            
            risk_assessment["overall_risk_score"] = min(1.0, risk_score)
            
            # Determine risk level
            if risk_score > 0.7:
                risk_assessment["risk_level"] = "high"
            elif risk_score > 0.4:
                risk_assessment["risk_level"] = "medium"
            else:
                risk_assessment["risk_level"] = "low"
            
            return risk_assessment
            
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return {"error": str(e)}
    
    async def _handle_influence_mapping(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle influence mapping request
        """
        try:
            target_sector = message.content.get("target_sector")
            influence_threshold = message.content.get("influence_threshold", self.influence_threshold)
            
            # Map influence networks
            influence_map = await self._map_sector_influence(target_sector, influence_threshold)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "influence_mapping_response",
                    "target_sector": target_sector,
                    "influence_map": influence_map
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Influence mapping failed: {e}")
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
    
    async def _map_sector_influence(
        self,
        target_sector: Optional[str],
        influence_threshold: float
    ) -> Dict[str, Any]:
        """
        Map influence networks within a sector
        """
        try:
            await self._ensure_graph_updated()
            
            influence_map = {
                "sector": target_sector,
                "key_influencers": [],
                "influence_clusters": [],
                "power_distribution": {},
                "network_density": 0.0
            }
            
            if not self.influence_graph:
                return influence_map
            
            # Filter by sector if specified
            sector_nodes = []
            if target_sector:
                for node, node_data in self.influence_graph.nodes(data=True):
                    if node_data.get("activity_type") == target_sector:
                        sector_nodes.append(node)
            else:
                sector_nodes = list(self.influence_graph.nodes())
            
            if not sector_nodes:
                return influence_map
            
            # Create sector subgraph
            sector_graph = self.influence_graph.subgraph(sector_nodes)
            
            # Calculate influence metrics
            in_degree = dict(sector_graph.in_degree())
            out_degree = dict(sector_graph.out_degree())
            
            # Find key influencers (high out-degree)
            influencers = sorted(
                [(node, out_degree.get(node, 0)) for node in sector_nodes],
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Top 10
            
            influence_map["key_influencers"] = [
                {
                    "company_id": node,
                    "company_info": dict(sector_graph.nodes[node]),
                    "influence_score": score,
                    "connections": out_degree.get(node, 0)
                }
                for node, score in influencers
            ]
            
            # Find influence clusters
            clusters = self._find_influence_clusters(sector_graph, influence_threshold)
            influence_map["influence_clusters"] = clusters
            
            # Power distribution analysis
            influence_scores = [score for _, score in influencers]
            if influence_scores:
                influence_map["power_distribution"] = {
                    "concentration_ratio": influence_scores[0] / max(1, sum(influence_scores)),
                    "herfindahl_index": sum(score**2 for score in influence_scores) / max(1, sum(influence_scores))**2,
                    "gini_coefficient": self._calculate_gini_coefficient(influence_scores)
                }
            
            # Network density
            n_nodes = len(sector_nodes)
            if n_nodes > 1:
                n_possible_edges = n_nodes * (n_nodes - 1)
                n_actual_edges = sector_graph.number_of_edges()
                influence_map["network_density"] = n_actual_edges / n_possible_edges
            
            return influence_map
            
        except Exception as e:
            logger.error(f"Sector influence mapping failed: {e}")
            return {"error": str(e)}
    
    def _find_influence_clusters(
        self,
        graph: nx.DiGraph,
        threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Find clusters of influential companies
        """
        try:
            clusters = []
            
            # Use PageRank to find influential nodes
            pagerank = nx.pagerank(graph, alpha=0.85)
            
            # Group nodes by PageRank score
            influential_nodes = [
                (node, score) for node, score in pagerank.items()
                if score > threshold
            ]
            
            if not influential_nodes:
                return clusters
            
            # Create subgraph of influential nodes
            influential_subgraph = graph.subgraph([node for node, _ in influential_nodes])
            
            # Find strongly connected components
            scc = list(nx.strongly_connected_components(influential_subgraph))
            
            for i, component in enumerate(scc):
                if len(component) > 1:
                    cluster_info = {
                        "cluster_id": f"influence_cluster_{i}",
                        "companies": list(component),
                        "size": len(component),
                        "avg_influence": np.mean([pagerank[node] for node in component]),
                        "total_influence": sum(pagerank[node] for node in component)
                    }
                    
                    clusters.append(cluster_info)
            
            return clusters
            
        except Exception as e:
            logger.error(f"Influence cluster finding failed: {e}")
            return []
    
    def _calculate_gini_coefficient(self, values: List[float]) -> float:
        """
        Calculate Gini coefficient for inequality measurement
        """
        try:
            values = sorted(values)
            n = len(values)
            if n == 0:
                return 0.0
            
            cumsum = np.cumsum(values)
            return (n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n
            
        except Exception as e:
            return 0.0
    
    async def _handle_company_relationships(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle company relationships query
        """
        try:
            company_a = message.content.get("company_a")
            company_b = message.content.get("company_b")
            
            if not company_a or not company_b:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Both company_a and company_b required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Analyze relationship
            relationship = await self._analyze_company_relationship(company_a, company_b)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "company_relationships_response",
                    "company_a": company_a,
                    "company_b": company_b,
                    "relationship": relationship
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Company relationships query failed: {e}")
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
    
    async def _analyze_company_relationship(
        self,
        company_a: str,
        company_b: str
    ) -> Dict[str, Any]:
        """
        Analyze relationship between two companies
        """
        try:
            await self._ensure_graph_updated()
            
            relationship = {
                "company_a": company_a,
                "company_b": company_b,
                "direct_relationship": False,
                "relationship_types": [],
                "relationship_strength": 0.0,
                "common_connections": [],
                "shortest_path": None,
                "path_length": None
            }
            
            # Check direct relationship
            if self.company_graph.has_edge(company_a, company_b):
                edge_data = self.company_graph.get_edge_data(company_a, company_b)
                relationship["direct_relationship"] = True
                relationship["relationship_types"] = [edge_data.get("relationship_type")]
                relationship["relationship_strength"] = edge_data.get("weight", 0)
            
            # Find common connections
            if company_a in self.company_graph and company_b in self.company_graph:
                neighbors_a = set(self.company_graph.neighbors(company_a))
                neighbors_b = set(self.company_graph.neighbors(company_b))
                common = neighbors_a.intersection(neighbors_b)
                
                relationship["common_connections"] = list(common)
                
                # Find shortest path
                try:
                    if nx.has_path(self.company_graph, company_a, company_b):
                        path = nx.shortest_path(self.company_graph, company_a, company_b)
                        relationship["shortest_path"] = path
                        relationship["path_length"] = len(path) - 1
                except nx.NetworkXNoPath:
                    pass
            
            # Get company info
            company_a_info = await self._get_company_info(company_a)
            company_b_info = await self._get_company_info(company_b)
            
            relationship["company_a_info"] = company_a_info
            relationship["company_b_info"] = company_b_info
            
            return relationship
            
        except Exception as e:
            logger.error(f"Relationship analysis failed: {e}")
            return {"error": str(e)}
    
    async def _handle_lobby_detection(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle lobby detection request
        """
        try:
            target_policy_area = message.content.get("target_policy_area")
            detection_period_days = message.content.get("detection_period_days", 365)
            
            # Detect lobbying patterns
            lobby_patterns = await self._detect_lobbying_patterns(
                target_policy_area, detection_period_days
            )
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "lobby_detection_response",
                    "target_policy_area": target_policy_area,
                    "lobby_patterns": lobby_patterns
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Lobby detection failed: {e}")
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
    
    async def _detect_lobbying_patterns(
        self,
        target_policy_area: Optional[str],
        detection_period_days: int
    ) -> Dict[str, Any]:
        """
        Detect lobbying patterns in the network
        """
        try:
            # This is a simplified implementation
            # In a real system, this would analyze:
            # - Changes in customs activities around policy changes
            # - Network formation around specific HS codes
            # - Abnormal trading patterns
            
            lobby_patterns = {
                "detected_patterns": [],
                "suspicious_networks": [],
                "policy_influence_indicators": [],
                "risk_assessment": {}
            }
            
            # Simple pattern detection based on network analysis
            await self._ensure_graph_updated()
            
            if not self.company_graph:
                return lobby_patterns
            
            # Pattern 1: Sudden network formation
            # (Companies that became connected recently)
            
            # Pattern 2: Concentration around specific HS codes
            hs_code_clusters = await self._find_hs_code_clusters()
            lobby_patterns["detected_patterns"].extend(hs_code_clusters)
            
            # Pattern 3: Influence concentration
            influence_concentration = self._analyze_influence_concentration()
            lobby_patterns["policy_influence_indicators"].append(influence_concentration)
            
            return lobby_patterns
            
        except Exception as e:
            logger.error(f"Lobbying pattern detection failed: {e}")
            return {"error": str(e)}
    
    async def _find_hs_code_clusters(self) -> List[Dict[str, Any]]:
        """
        Find clusters of companies around specific HS codes
        """
        try:
            clusters = []
            
            async with get_db_session() as session:
                # Find HS codes with many companies
                hs_cluster_query = """
                SELECT
                    hs_code,
                    count(distinct company_id) as company_count,
                    sum(value_usd) as total_value,
                    count(*) as declaration_count
                FROM customs_data
                WHERE hs_code is not null
                GROUP BY hs_code
                HAVING count(distinct company_id) > 10
                ORDER BY total_value desc
                LIMIT 20
                """
                
                results = await session.execute(hs_cluster_query)
                hs_clusters = results.fetchall()
                
                for row in hs_clusters:
                    cluster_info = {
                        "pattern_type": "hs_code_cluster",
                        "hs_code": row[0],
                        "company_count": row[1],
                        "total_value_usd": float(row[2]),
                        "declaration_count": row[3],
                        "concentration_ratio": row[1] / row[3] if row[3] > 0 else 0,
                        "risk_level": "high" if row[1] > 50 else "medium" if row[1] > 20 else "low"
                    }
                    
                    clusters.append(cluster_info)
            
            return clusters
            
        except Exception as e:
            logger.error(f"HS code cluster finding failed: {e}")
            return []
    
    def _analyze_influence_concentration(self) -> Dict[str, Any]:
        """
        Analyze concentration of influence in the network
        """
        try:
            if not self.influence_graph:
                return {"error": "No influence graph available"}
            
            # Calculate influence distribution
            pagerank = nx.pagerank(self.influence_graph, alpha=0.85)
            influence_scores = list(pagerank.values())
            
            # Concentration metrics
            top_10_percent = sorted(influence_scores, reverse=True)[:max(1, int(len(influence_scores) * 0.1))]
            concentration_ratio = sum(top_10_percent) / max(1, sum(influence_scores))
            
            return {
                "metric_type": "influence_concentration",
                "concentration_ratio_top_10": concentration_ratio,
                "gini_coefficient": self._calculate_gini_coefficient(influence_scores),
                "network_centralization": nx.degree_centrality(self.influence_graph),
                "interpretation": "High concentration may indicate lobbying networks"
            }
            
        except Exception as e:
            logger.error(f"Influence concentration analysis failed: {e}")
            return {"error": str(e)}
    
    async def _handle_graph_update(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle graph update request
        """
        try:
            # Force graph update
            await self._build_relationship_graph()
            self.last_graph_update = datetime.now()
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "graph_update_response",
                    "status": "completed",
                    "update_time": self.last_graph_update.isoformat(),
                    "nodes": len(self.company_graph.nodes()) if self.company_graph else 0,
                    "edges": len(self.company_graph.edges()) if self.company_graph else 0
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Graph update failed: {e}")
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


# ========== TEST ==========
if __name__ == "__main__":
    async def test_lobby_map_agent():
        # Initialize lobby map agent
        agent = LobbyMapAgent()
        
        # Test message
        test_message = AgentMessage(
            id="test_lobby",
            from_agent="test",
            to_agent="lobby_map_agent",
            content={
                "type": "graph_update"
            },
            timestamp=datetime.now()
        )
        
        print("Testing lobby map agent...")
        async for response in agent.process_message(test_message):
            print(f"Response type: {response.content.get('type')}")
            if response.content.get("type") == "graph_update_response":
                print(f"Graph updated: {response.content.get('nodes', 0)} nodes, {response.content.get('edges', 0)} edges")
        
        print("Lobby map agent test completed")
    
    # Run test
    asyncio.run(test_lobby_map_agent())
