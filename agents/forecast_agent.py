"""
Forecast Agent: Time-series forecasting and prediction
Uses Prophet/LightGBM for customs data forecasting
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
import pickle

from prophet import Prophet
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import StandardScaler
import optuna

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import CustomsData, ForecastResult
from ..model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class ForecastAgent(BaseAgent):
    """
    Forecast Agent for time-series predictions
    Handles customs data forecasting using multiple models
    """
    
    def __init__(
        self,
        agent_id: str = "forecast_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Forecasting settings
        self.forecast_horizon = self.config.get("forecast_horizon", 90)  # days
        self.confidence_level = self.config.get("confidence_level", 0.95)
        self.min_training_days = self.config.get("min_training_days", 365)
        
        # Model settings
        self.use_prophet = self.config.get("use_prophet", True)
        self.use_lightgbm = self.config.get("use_lightgbm", True)
        self.ensemble_weight_prophet = self.config.get("ensemble_weight_prophet", 0.6)
        self.ensemble_weight_lightgbm = self.config.get("ensemble_weight_lightgbm", 0.4)
        
        # Model registry
        self.model_registry = ModelRegistry()
        
        # Cached models
        self.models_cache = {}
        self.scalers_cache = {}
        
        logger.info(f"Forecast Agent initialized: {agent_id}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process forecasting requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "forecast_request":
                async for response in self._handle_forecast_request(message):
                    yield response
                    
            elif message_type == "forecast_evaluation":
                async for response in self._handle_forecast_evaluation(message):
                    yield response
                    
            elif message_type == "forecast_update_models":
                async for response in self._handle_model_update(message):
                    yield response
                    
            elif message_type == "forecast_historical":
                async for response in self._handle_historical_forecast(message):
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
            logger.error(f"Forecast agent processing failed: {e}")
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
    
    async def _handle_forecast_request(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle forecast request for specific data
        """
        try:
            # Extract parameters
            target_variable = message.content.get("target_variable", "value_usd")
            filters = message.content.get("filters", {})
            forecast_periods = message.content.get("forecast_periods", self.forecast_horizon)
            model_type = message.content.get("model_type", "ensemble")
            
            # Get historical data
            historical_data = await self._get_historical_data(target_variable, filters)
            
            if len(historical_data) < self.min_training_days:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "forecast_response",
                        "status": "insufficient_data",
                        "message": f"Need at least {self.min_training_days} days of data, got {len(historical_data)}",
                        "target_variable": target_variable,
                        "filters": filters
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Generate forecast
            forecast_result = await self._generate_forecast(
                historical_data,
                target_variable,
                forecast_periods,
                model_type
            )
            
            # Save forecast to database
            forecast_id = await self._save_forecast_result(
                target_variable,
                filters,
                forecast_result,
                message.content.get("user_id")
            )
            
            # Return forecast
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "forecast_response",
                    "status": "success",
                    "forecast_id": forecast_id,
                    "target_variable": target_variable,
                    "filters": filters,
                    "forecast": forecast_result,
                    "metadata": {
                        "historical_points": len(historical_data),
                        "forecast_periods": forecast_periods,
                        "model_type": model_type,
                        "confidence_level": self.confidence_level
                    }
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Forecast request failed: {e}")
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
    
    async def _get_historical_data(
        self,
        target_variable: str,
        filters: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Get historical data for forecasting
        """
        try:
            async with get_db_session() as session:
                # Build query
                query = session.query(
                    CustomsData.declaration_date,
                    getattr(CustomsData, target_variable)
                ).filter(
                    CustomsData.declaration_date.isnot(None),
                    getattr(CustomsData, target_variable).isnot(None)
                )
                
                # Apply filters
                if filters.get("company_id"):
                    query = query.filter(CustomsData.company_id == filters["company_id"])
                
                if filters.get("hs_code"):
                    query = query.filter(CustomsData.hs_code.like(f"{filters['hs_code']}%"))
                
                if filters.get("country_origin"):
                    query = query.filter(CustomsData.country_origin == filters["country_origin"])
                
                if filters.get("date_from"):
                    query = query.filter(CustomsData.declaration_date >= filters["date_from"])
                
                if filters.get("date_to"):
                    query = query.filter(CustomsData.declaration_date <= filters["date_to"])
                
                # Execute query
                results = await session.execute(query)
                rows = results.fetchall()
                
                # Convert to DataFrame
                df = pd.DataFrame(rows, columns=["ds", target_variable])
                df["ds"] = pd.to_datetime(df["ds"])
                df = df.sort_values("ds").groupby("ds")[target_variable].sum().reset_index()
                
                return df
                
        except Exception as e:
            logger.error(f"Historical data retrieval failed: {e}")
            return pd.DataFrame()
    
    async def _generate_forecast(
        self,
        historical_data: pd.DataFrame,
        target_variable: str,
        periods: int,
        model_type: str
    ) -> Dict[str, Any]:
        """
        Generate forecast using specified model
        """
        try:
            forecast_result = {
                "forecast_dates": [],
                "forecast_values": [],
                "lower_bound": [],
                "upper_bound": [],
                "model_performance": {},
                "forecast_quality": {}
            }
            
            if model_type == "prophet" or model_type == "ensemble":
                prophet_forecast = await self._forecast_with_prophet(
                    historical_data, target_variable, periods
                )
                if prophet_forecast:
                    forecast_result["prophet"] = prophet_forecast
            
            if model_type == "lightgbm" or model_type == "ensemble":
                lgb_forecast = await self._forecast_with_lightgbm(
                    historical_data, target_variable, periods
                )
                if lgb_forecast:
                    forecast_result["lightgbm"] = lgb_forecast
            
            if model_type == "ensemble" and "prophet" in forecast_result and "lightgbm" in forecast_result:
                ensemble_forecast = self._create_ensemble_forecast(
                    forecast_result["prophet"],
                    forecast_result["lightgbm"]
                )
                forecast_result["ensemble"] = ensemble_forecast
                
                # Use ensemble as main forecast
                forecast_result["forecast_dates"] = ensemble_forecast["dates"]
                forecast_result["forecast_values"] = ensemble_forecast["values"]
                forecast_result["lower_bound"] = ensemble_forecast["lower_bound"]
                forecast_result["upper_bound"] = ensemble_forecast["upper_bound"]
                
            elif "prophet" in forecast_result:
                prophet_data = forecast_result["prophet"]
                forecast_result["forecast_dates"] = prophet_data["dates"]
                forecast_result["forecast_values"] = prophet_data["values"]
                forecast_result["lower_bound"] = prophet_data["lower_bound"]
                forecast_result["upper_bound"] = prophet_data["upper_bound"]
                
            elif "lightgbm" in forecast_result:
                lgb_data = forecast_result["lightgbm"]
                forecast_result["forecast_dates"] = lgb_data["dates"]
                forecast_result["forecast_values"] = lgb_data["values"]
                forecast_result["lower_bound"] = lgb_data["lower_bound"]
                forecast_result["upper_bound"] = lgb_data["upper_bound"]
            
            # Calculate forecast quality metrics
            forecast_result["forecast_quality"] = self._calculate_forecast_quality(
                historical_data[target_variable].values,
                forecast_result["forecast_values"]
            )
            
            return forecast_result
            
        except Exception as e:
            logger.error(f"Forecast generation failed: {e}")
            return {}
    
    async def _forecast_with_prophet(
        self,
        data: pd.DataFrame,
        target_variable: str,
        periods: int
    ) -> Optional[Dict[str, Any]]:
        """
        Generate forecast using Facebook Prophet
        """
        try:
            # Prepare data for Prophet
            prophet_data = data.rename(columns={target_variable: "y"})
            
            # Create and fit model
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,
                interval_width=self.confidence_level
            )
            
            model.fit(prophet_data)
            
            # Create future dates
            future = model.make_future_dataframe(periods=periods, freq='D')
            
            # Generate forecast
            forecast = model.predict(future)
            
            # Extract results
            forecast_dates = forecast.tail(periods)["ds"].dt.strftime("%Y-%m-%d").tolist()
            forecast_values = forecast.tail(periods)["yhat"].tolist()
            lower_bound = forecast.tail(periods)["yhat_lower"].tolist()
            upper_bound = forecast.tail(periods)["yhat_upper"].tolist()
            
            # Calculate performance on historical data
            historical_forecast = forecast.head(len(prophet_data))
            mae = mean_absolute_error(prophet_data["y"], historical_forecast["yhat"])
            rmse = np.sqrt(mean_squared_error(prophet_data["y"], historical_forecast["yhat"]))
            
            return {
                "dates": forecast_dates,
                "values": forecast_values,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "performance": {
                    "mae": mae,
                    "rmse": rmse,
                    "mape": np.mean(np.abs((prophet_data["y"] - historical_forecast["yhat"]) / prophet_data["y"])) * 100
                },
                "model_type": "prophet"
            }
            
        except Exception as e:
            logger.error(f"Prophet forecasting failed: {e}")
            return None
    
    async def _forecast_with_lightgbm(
        self,
        data: pd.DataFrame,
        target_variable: str,
        periods: int
    ) -> Optional[Dict[str, Any]]:
        """
        Generate forecast using LightGBM
        """
        try:
            # Prepare data for LightGBM
            df = data.copy()
            df["ds"] = pd.to_datetime(df["ds"])
            df = df.set_index("ds")
            
            # Create time series features
            df["day_of_week"] = df.index.dayofweek
            df["month"] = df.index.month
            df["quarter"] = df.index.quarter
            df["year"] = df.index.year
            
            # Create lag features
            for lag in [1, 7, 30]:
                df[f"lag_{lag}"] = df[target_variable].shift(lag)
            
            # Create rolling statistics
            df["rolling_mean_7"] = df[target_variable].rolling(window=7).mean()
            df["rolling_std_7"] = df[target_variable].rolling(window=7).std()
            
            # Drop NaN values
            df = df.dropna()
            
            if len(df) < 30:  # Need minimum data
                return None
            
            # Split data
            train_size = int(len(df) * 0.8)
            train_data = df.iloc[:train_size]
            test_data = df.iloc[train_size:]
            
            # Prepare features
            feature_cols = [col for col in df.columns if col != target_variable]
            X_train = train_data[feature_cols]
            y_train = train_data[target_variable]
            X_test = test_data[feature_cols]
            y_test = test_data[target_variable]
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train model
            train_dataset = lgb.Dataset(X_train_scaled, y_train)
            valid_dataset = lgb.Dataset(X_test_scaled, y_test, reference=train_dataset)
            
            params = {
                'objective': 'regression',
                'metric': 'mae',
                'boosting_type': 'gbdt',
                'num_leaves': 31,
                'learning_rate': 0.05,
                'feature_fraction': 0.9
            }
            
            model = lgb.train(
                params,
                train_dataset,
                num_boost_round=100,
                valid_sets=[train_dataset, valid_dataset],
                valid_names=['train', 'valid'],
                callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)]
            )
            
            # Generate future predictions
            last_date = df.index[-1]
            future_dates = pd.date_range(last_date + timedelta(days=1), periods=periods, freq='D')
            
            future_features = []
            for future_date in future_dates:
                # Create features for future date
                future_row = {
                    "day_of_week": future_date.dayofweek,
                    "month": future_date.month,
                    "quarter": future_date.quarter,
                    "year": future_date.year
                }
                
                # Add lag features (use last known values)
                for lag in [1, 7, 30]:
                    lag_date = future_date - timedelta(days=lag)
                    if lag_date in df.index:
                        future_row[f"lag_{lag}"] = df.loc[lag_date, target_variable]
                    else:
                        future_row[f"lag_{lag}"] = df[target_variable].iloc[-1]
                
                # Add rolling statistics (approximate)
                future_row["rolling_mean_7"] = df[target_variable].rolling(window=7).mean().iloc[-1]
                future_row["rolling_std_7"] = df[target_variable].rolling(window=7).std().iloc[-1]
                
                future_features.append(future_row)
            
            future_df = pd.DataFrame(future_features)
            future_scaled = scaler.transform(future_df)
            
            # Predict
            predictions = model.predict(future_scaled)
            
            # Calculate confidence intervals (simple approach)
            test_predictions = model.predict(X_test_scaled)
            errors = np.abs(y_test - test_predictions)
            error_std = np.std(errors)
            
            lower_bound = (predictions - 1.96 * error_std).tolist()
            upper_bound = (predictions + 1.96 * error_std).tolist()
            
            # Calculate performance
            mae = mean_absolute_error(y_test, test_predictions)
            rmse = np.sqrt(mean_squared_error(y_test, test_predictions))
            
            return {
                "dates": [d.strftime("%Y-%m-%d") for d in future_dates],
                "values": predictions.tolist(),
                "lower_bound": lower_bound,
                "upper_bound": upper_bound,
                "performance": {
                    "mae": mae,
                    "rmse": rmse,
                    "mape": np.mean(np.abs((y_test - test_predictions) / y_test)) * 100
                },
                "model_type": "lightgbm"
            }
            
        except Exception as e:
            logger.error(f"LightGBM forecasting failed: {e}")
            return None
    
    def _create_ensemble_forecast(
        self,
        prophet_forecast: Dict[str, Any],
        lgb_forecast: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create ensemble forecast from multiple models
        """
        try:
            # Weighted average
            prophet_weight = self.ensemble_weight_prophet
            lgb_weight = self.ensemble_weight_lightgbm
            
            ensemble_values = []
            ensemble_lower = []
            ensemble_upper = []
            
            for p_val, p_low, p_up, l_val, l_low, l_up in zip(
                prophet_forecast["values"],
                prophet_forecast["lower_bound"],
                prophet_forecast["upper_bound"],
                lgb_forecast["values"],
                lgb_forecast["lower_bound"],
                lgb_forecast["upper_bound"]
            ):
                # Ensemble prediction
                ensemble_val = prophet_weight * p_val + lgb_weight * l_val
                ensemble_values.append(ensemble_val)
                
                # Ensemble confidence intervals (conservative approach)
                ensemble_lower.append(min(p_low, l_low))
                ensemble_upper.append(max(p_up, l_up))
            
            return {
                "dates": prophet_forecast["dates"],
                "values": ensemble_values,
                "lower_bound": ensemble_lower,
                "upper_bound": ensemble_upper,
                "weights": {
                    "prophet": prophet_weight,
                    "lightgbm": lgb_weight
                }
            }
            
        except Exception as e:
            logger.error(f"Ensemble creation failed: {e}")
            return prophet_forecast  # Fallback to prophet
    
    def _calculate_forecast_quality(
        self,
        historical_values: np.ndarray,
        forecast_values: List[float]
    ) -> Dict[str, Any]:
        """
        Calculate forecast quality metrics
        """
        try:
            # Use last N values for comparison
            n_compare = min(len(historical_values), len(forecast_values))
            hist_sample = historical_values[-n_compare:]
            forecast_sample = forecast_values[:n_compare]
            
            mae = mean_absolute_error(hist_sample, forecast_sample)
            rmse = np.sqrt(mean_squared_error(hist_sample, forecast_sample))
            
            # Mean absolute percentage error
            mape = np.mean(np.abs((hist_sample - forecast_sample) / hist_sample)) * 100
            
            # Forecast bias
            bias = np.mean(forecast_sample - hist_sample)
            
            return {
                "mae": mae,
                "rmse": rmse,
                "mape": mape,
                "bias": bias,
                "accuracy_score": max(0, 100 - mape)  # Simple accuracy score
            }
            
        except Exception as e:
            logger.error(f"Forecast quality calculation failed: {e}")
            return {}
    
    async def _save_forecast_result(
        self,
        target_variable: str,
        filters: Dict[str, Any],
        forecast_result: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> str:
        """
        Save forecast result to database
        """
        try:
            async with get_db_session() as session:
                forecast_record = ForecastResult(
                    user_id=user_id,
                    target_variable=target_variable,
                    filters=json.dumps(filters),
                    forecast_data=json.dumps(forecast_result),
                    forecast_periods=len(forecast_result.get("forecast_dates", [])),
                    model_performance=json.dumps(forecast_result.get("forecast_quality", {})),
                    created_at=datetime.now()
                )
                
                session.add(forecast_record)
                await session.commit()
                
                return str(forecast_record.id)
                
        except Exception as e:
            logger.error(f"Forecast save failed: {e}")
            return ""
    
    async def _handle_forecast_evaluation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle forecast evaluation request
        """
        try:
            forecast_id = message.content.get("forecast_id")
            
            if not forecast_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "forecast_id required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Get forecast from database
            async with get_db_session() as session:
                forecast = await session.get(ForecastResult, forecast_id)
                
                if not forecast:
                    yield AgentMessage(
                        id=str(uuid.uuid4()),
                        from_agent=self.agent_id,
                        to_agent=message.from_agent,
                        content={
                            "type": "error",
                            "error": "Forecast not found"
                        },
                        timestamp=datetime.now()
                    )
                    return
                
                # Get actual data for comparison
                actual_data = await self._get_actual_vs_forecast(
                    forecast.target_variable,
                    json.loads(forecast.filters),
                    forecast.created_at.date()
                )
                
                # Calculate evaluation metrics
                evaluation = self._evaluate_forecast_accuracy(
                    json.loads(forecast.forecast_data),
                    actual_data
                )
                
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "forecast_evaluation_response",
                        "forecast_id": forecast_id,
                        "evaluation": evaluation,
                        "actual_data": actual_data
                    },
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Forecast evaluation failed: {e}")
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
    
    async def _get_actual_vs_forecast(
        self,
        target_variable: str,
        filters: Dict[str, Any],
        forecast_date: datetime.date
    ) -> List[Dict[str, Any]]:
        """
        Get actual data vs forecast for evaluation
        """
        try:
            async with get_db_session() as session:
                # Get data from forecast date onwards
                query = session.query(
                    CustomsData.declaration_date,
                    getattr(CustomsData, target_variable)
                ).filter(
                    CustomsData.declaration_date >= forecast_date,
                    getattr(CustomsData, target_variable).isnot(None)
                )
                
                # Apply same filters
                if filters.get("company_id"):
                    query = query.filter(CustomsData.company_id == filters["company_id"])
                
                if filters.get("hs_code"):
                    query = query.filter(CustomsData.hs_code.like(f"{filters['hs_code']}%"))
                
                results = await session.execute(query)
                rows = results.fetchall()
                
                return [
                    {
                        "date": row[0].isoformat(),
                        "actual_value": float(row[1])
                    }
                    for row in rows
                ]
                
        except Exception as e:
            logger.error(f"Actual data retrieval failed: {e}")
            return []
    
    def _evaluate_forecast_accuracy(
        self,
        forecast_data: Dict[str, Any],
        actual_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate forecast accuracy against actual data
        """
        try:
            forecast_dates = forecast_data.get("forecast_dates", [])
            forecast_values = forecast_data.get("forecast_values", [])
            
            # Create lookup dict for actual values
            actual_lookup = {item["date"]: item["actual_value"] for item in actual_data}
            
            matched_forecasts = []
            matched_actuals = []
            
            for date, forecast_val in zip(forecast_dates, forecast_values):
                if date in actual_lookup:
                    matched_forecasts.append(forecast_val)
                    matched_actuals.append(actual_lookup[date])
            
            if not matched_forecasts:
                return {"error": "No matching actual data found for evaluation period"}
            
            # Calculate metrics
            mae = mean_absolute_error(matched_actuals, matched_forecasts)
            rmse = np.sqrt(mean_squared_error(matched_actuals, matched_forecasts))
            mape = np.mean(np.abs(np.array(matched_actuals) - np.array(matched_forecasts)) / np.array(matched_actuals)) * 100
            
            return {
                "matched_points": len(matched_forecasts),
                "mae": mae,
                "rmse": rmse,
                "mape": mape,
                "accuracy_score": max(0, 100 - mape),
                "matched_dates": list(zip(forecast_dates, forecast_values, matched_actuals))[:10]  # First 10 for display
            }
            
        except Exception as e:
            logger.error(f"Forecast evaluation calculation failed: {e}")
            return {"error": str(e)}
    
    async def _handle_model_update(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle model update/retraining request
        """
        try:
            target_variable = message.content.get("target_variable", "value_usd")
            filters = message.content.get("filters", {})
            
            # Retrain models
            success = await self._retrain_models(target_variable, filters)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "model_update_response",
                    "success": success,
                    "target_variable": target_variable,
                    "filters": filters
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Model update failed: {e}")
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
    
    async def _retrain_models(
        self,
        target_variable: str,
        filters: Dict[str, Any]
    ) -> bool:
        """
        Retrain forecasting models
        """
        try:
            # Get latest data
            data = await self._get_historical_data(target_variable, filters)
            
            if len(data) < self.min_training_days:
                logger.warning(f"Insufficient data for retraining: {len(data)} days")
                return False
            
            # Clear cache for this variable/filters combination
            cache_key = f"{target_variable}_{json.dumps(filters, sort_keys=True)}"
            if cache_key in self.models_cache:
                del self.models_cache[cache_key]
            
            # Models will be retrained on next forecast request
            logger.info(f"Models marked for retraining: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"Model retraining failed: {e}")
            return False
    
    async def _handle_historical_forecast(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle historical forecast generation (backtesting)
        """
        try:
            target_variable = message.content.get("target_variable", "value_usd")
            filters = message.content.get("filters", {})
            backtest_periods = message.content.get("backtest_periods", 30)  # days
            
            # Generate historical forecasts
            backtest_results = await self._generate_backtest_forecasts(
                target_variable, filters, backtest_periods
            )
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "historical_forecast_response",
                    "target_variable": target_variable,
                    "filters": filters,
                    "backtest_results": backtest_results
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Historical forecast failed: {e}")
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
    
    async def _generate_backtest_forecasts(
        self,
        target_variable: str,
        filters: Dict[str, Any],
        backtest_periods: int
    ) -> Dict[str, Any]:
        """
        Generate backtest forecasts for model validation
        """
        try:
            # Get all historical data
            all_data = await self._get_historical_data(target_variable, filters)
            
            if len(all_data) < self.min_training_days + backtest_periods:
                return {"error": "Insufficient data for backtesting"}
            
            backtest_results = []
            
            # Generate forecasts for different periods
            for i in range(backtest_periods):
                # Use data up to this point
                train_end_idx = len(all_data) - backtest_periods + i
                train_data = all_data.iloc[:train_end_idx]
                
                # Generate forecast for next period
                forecast = await self._generate_forecast(
                    train_data, target_variable, 1, "ensemble"
                )
                
                # Get actual value
                actual_idx = train_end_idx
                if actual_idx < len(all_data):
                    actual_value = all_data.iloc[actual_idx][target_variable]
                    forecast_value = forecast.get("forecast_values", [None])[0]
                    
                    if forecast_value is not None:
                        backtest_results.append({
                            "date": all_data.iloc[actual_idx]["ds"].strftime("%Y-%m-%d"),
                            "forecast": forecast_value,
                            "actual": actual_value,
                            "error": abs(forecast_value - actual_value),
                            "percentage_error": abs(forecast_value - actual_value) / actual_value * 100
                        })
            
            # Calculate overall backtest metrics
            if backtest_results:
                errors = [r["error"] for r in backtest_results]
                percentage_errors = [r["percentage_error"] for r in backtest_results]
                
                return {
                    "backtest_points": len(backtest_results),
                    "mae": np.mean(errors),
                    "mape": np.mean(percentage_errors),
                    "accuracy_score": 100 - np.mean(percentage_errors),
                    "results": backtest_results[-10:]  # Last 10 results
                }
            
            return {"error": "No backtest results generated"}
            
        except Exception as e:
            logger.error(f"Backtest generation failed: {e}")
            return {"error": str(e)}


# ========== TEST ==========
if __name__ == "__main__":
    async def test_forecast_agent():
        # Initialize forecast agent
        agent = ForecastAgent()
        
        # Test message
        test_message = AgentMessage(
            id="test_forecast",
            from_agent="test",
            to_agent="forecast_agent",
            content={
                "type": "forecast_request",
                "target_variable": "value_usd",
                "filters": {},
                "forecast_periods": 7,
                "model_type": "prophet"
            },
            timestamp=datetime.now()
        )
        
        print("Testing forecast agent...")
        async for response in agent.process_message(test_message):
            print(f"Response type: {response.content.get('type')}")
            if response.content.get("type") == "forecast_response":
                forecast = response.content.get("forecast", {})
                print(f"Forecast points: {len(forecast.get('forecast_values', []))}")
        
        print("Forecast agent test completed")
    
    # Run test
    asyncio.run(test_forecast_agent())
