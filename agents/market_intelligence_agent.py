"""
Market Intelligence Agent: Market analysis and intelligence gathering
Analyzes market trends, competitor activities, and economic indicators
"""
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import asyncio
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
import uuid
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import xgboost as xgb
import lightgbm as lgb
from scipy.stats import linregress
import requests
from bs4 import BeautifulSoup
import feedparser
from textblob import TextBlob
import yfinance as yf
from alpha_vantage.timeseries import TimeSeries
from fredapi import Fred
import tweepy
from newsapi import NewsApiClient
import praw
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import MarketIntelligence, CompetitorAnalysis, EconomicIndicators

logger = logging.getLogger(__name__)


class MarketIntelligenceAgent(BaseAgent):
    """
    Market Intelligence Agent for comprehensive market analysis and intelligence gathering
    Uses multiple data sources and ML models for market trend analysis and forecasting
    """
    
    def __init__(
        self,
        agent_id: str = "market_intelligence_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Market intelligence configuration
        self.market_config = {
            "analysis_methods": self.config.get("analysis_methods", [
                "technical_analysis", "fundamental_analysis", "sentiment_analysis",
                "competitor_tracking", "economic_indicators", "social_media_monitoring"
            ]),
            "data_sources": self.config.get("data_sources", [
                "yahoo_finance", "alpha_vantage", "fred", "news_api", "twitter", "reddit",
                "web_scraping", "rss_feeds"
            ]),
            "forecast_horizon": self.config.get("forecast_horizon", 30),  # days
            "sentiment_update_frequency": self.config.get("sentiment_update_frequency", 3600),  # seconds
            "market_update_frequency": self.config.get("market_update_frequency", 300),  # seconds
            "competitor_tracking": self.config.get("competitor_tracking", True)
        }
        
        # Market analysis models
        self.forecast_models = {}
        self.sentiment_models = {}
        self.scalers = {}
        
        # Market data storage
        self.market_data = defaultdict(lambda: deque(maxlen=10000))  # Per symbol
        self.sentiment_data = defaultdict(list)
        self.economic_indicators = {}
        self.competitor_data = defaultdict(dict)
        
        # Data source clients
        self.data_clients = {}
        
        # Market intelligence storage
        self.market_intelligence = defaultdict(dict)
        self.forecast_cache = {}
        self.sentiment_cache = {}
        
        # Background tasks
        self.market_monitor_task = None
        self.sentiment_analysis_task = None
        self.forecast_update_task = None
        self.competitor_tracking_task = None
        
        logger.info(f"Market Intelligence Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the market intelligence agent
        """
        await super().start()
        
        # Initialize data clients
        await self._initialize_data_clients()
        
        # Initialize analysis models
        await self._initialize_analysis_models()
        
        # Start monitoring tasks
        self.market_monitor_task = asyncio.create_task(self._market_monitoring_loop())
        self.sentiment_analysis_task = asyncio.create_task(self._sentiment_analysis_loop())
        self.forecast_update_task = asyncio.create_task(self._forecast_update_loop())
        self.competitor_tracking_task = asyncio.create_task(self._competitor_tracking_loop())
        
        logger.info("Market intelligence monitoring started")
    
    async def stop(self):
        """
        Stop the market intelligence agent
        """
        if self.market_monitor_task:
            self.market_monitor_task.cancel()
            try:
                await self.market_monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.sentiment_analysis_task:
            self.sentiment_analysis_task.cancel()
            try:
                await self.sentiment_analysis_task
            except asyncio.CancelledError:
                pass
        
        if self.forecast_update_task:
            self.forecast_update_task.cancel()
            try:
                await self.forecast_update_task
            except asyncio.CancelledError:
                pass
        
        if self.competitor_tracking_task:
            self.competitor_tracking_task.cancel()
            try:
                await self.competitor_tracking_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        logger.info("Market intelligence agent stopped")
    
    async def _initialize_data_clients(self):
        """
        Initialize data source clients
        """
        try:
            # Yahoo Finance
            self.data_clients["yahoo_finance"] = yf.Ticker
            
            # Alpha Vantage (requires API key)
            alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
            if alpha_vantage_key:
                self.data_clients["alpha_vantage"] = TimeSeries(key=alpha_vantage_key)
            
            # FRED (Federal Reserve Economic Data)
            fred_key = os.getenv("FRED_API_KEY")
            if fred_key:
                self.data_clients["fred"] = Fred(api_key=fred_key)
            
            # News API
            news_api_key = os.getenv("NEWS_API_KEY")
            if news_api_key:
                self.data_clients["news_api"] = NewsApiClient(api_key=news_api_key)
            
            # Twitter API
            twitter_keys = {
                "consumer_key": os.getenv("TWITTER_CONSUMER_KEY"),
                "consumer_secret": os.getenv("TWITTER_CONSUMER_SECRET"),
                "access_token": os.getenv("TWITTER_ACCESS_TOKEN"),
                "access_token_secret": os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
            }
            if all(twitter_keys.values()):
                auth = tweepy.OAuth1UserHandler(**twitter_keys)
                self.data_clients["twitter"] = tweepy.API(auth)
            
            # Reddit API
            reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
            reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
            if reddit_client_id and reddit_client_secret:
                self.data_clients["reddit"] = praw.Reddit(
                    client_id=reddit_client_id,
                    client_secret=reddit_client_secret,
                    user_agent="MarketIntelligenceAgent/1.0"
                )
            
            # Web scraping (Selenium)
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            self.data_clients["web_scraper"] = webdriver.Chrome(options=chrome_options)
            
            logger.info("Data clients initialized")
            
        except Exception as e:
            logger.error(f"Data client initialization failed: {e}")
    
    async def _initialize_analysis_models(self):
        """
        Initialize market analysis models
        """
        try:
            # Forecasting models
            self.forecast_models = {
                "random_forest": RandomForestRegressor(
                    n_estimators=100,
                    random_state=42
                ),
                "gradient_boosting": GradientBoostingRegressor(
                    n_estimators=100,
                    random_state=42
                ),
                "xgboost": xgb.XGBRegressor(
                    n_estimators=100,
                    random_state=42
                ),
                "lightgbm": lgb.LGBMRegressor(
                    n_estimators=100,
                    random_state=42
                )
            }
            
            # Sentiment analysis models (placeholder - would be trained)
            self.sentiment_models = {
                "textblob": TextBlob,
                "custom_model": None  # Would be loaded from disk
            }
            
            # Initialize scalers
            for model_name in self.forecast_models:
                self.scalers[model_name] = StandardScaler()
            
            logger.info("Analysis models initialized")
            
        except Exception as e:
            logger.error(f"Analysis model initialization failed: {e}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process market intelligence requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "analyze_market":
                async for response in self._handle_market_analysis(message):
                    yield response
                    
            elif message_type == "forecast_price":
                async for response in self._handle_price_forecast(message):
                    yield response
                    
            elif message_type == "analyze_sentiment":
                async for response in self._handle_sentiment_analysis(message):
                    yield response
                    
            elif message_type == "track_competitor":
                async for response in self._handle_competitor_tracking(message):
                    yield response
                    
            elif message_type == "get_economic_indicators":
                async for response in self._handle_economic_indicators(message):
                    yield response
                    
            elif message_type == "market_intelligence_report":
                async for response in self._handle_intelligence_report(message):
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
            logger.error(f"Market intelligence processing failed: {e}")
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
    
    async def _market_monitoring_loop(self):
        """
        Continuous market data monitoring loop
        """
        try:
            while True:
                try:
                    # Update market data
                    await self._update_market_data()
                    
                    # Update economic indicators
                    await self._update_economic_indicators()
                    
                except Exception as e:
                    logger.error(f"Market monitoring error: {e}")
                
                # Wait before next update
                await asyncio.sleep(self.market_config["market_update_frequency"])
                
        except asyncio.CancelledError:
            logger.info("Market monitoring loop cancelled")
            raise
    
    async def _sentiment_analysis_loop(self):
        """
        Continuous sentiment analysis loop
        """
        try:
            while True:
                try:
                    # Update sentiment data
                    await self._update_sentiment_data()
                    
                    # Analyze market sentiment
                    await self._analyze_market_sentiment()
                    
                except Exception as e:
                    logger.error(f"Sentiment analysis error: {e}")
                
                # Wait before next analysis
                await asyncio.sleep(self.market_config["sentiment_update_frequency"])
                
        except asyncio.CancelledError:
            logger.info("Sentiment analysis loop cancelled")
            raise
    
    async def _forecast_update_loop(self):
        """
        Periodic forecast update loop
        """
        try:
            while True:
                try:
                    # Update price forecasts
                    await self._update_price_forecasts()
                    
                    # Update market intelligence
                    await self._update_market_intelligence()
                    
                except Exception as e:
                    logger.error(f"Forecast update error: {e}")
                
                # Wait for forecast update interval
                await asyncio.sleep(3600)  # Update every hour
                
        except asyncio.CancelledError:
            logger.info("Forecast update loop cancelled")
            raise
    
    async def _competitor_tracking_loop(self):
        """
        Competitor tracking and analysis loop
        """
        try:
            while True:
                try:
                    # Track competitor activities
                    await self._track_competitor_activities()
                    
                    # Analyze competitive landscape
                    await self._analyze_competitive_landscape()
                    
                except Exception as e:
                    logger.error(f"Competitor tracking error: {e}")
                
                # Wait for competitor tracking interval
                await asyncio.sleep(7200)  # Update every 2 hours
                
        except asyncio.CancelledError:
            logger.info("Competitor tracking loop cancelled")
            raise
    
    async def _update_market_data(self):
        """
        Update market data from various sources
        """
        try:
            # Major indices and symbols to track
            symbols = ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
            
            for symbol in symbols:
                try:
                    # Get data from Yahoo Finance
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="1d", interval="1m")
                    
                    if not hist.empty:
                        # Store recent data
                        for idx, row in hist.iterrows():
                            data_point = {
                                "symbol": symbol,
                                "timestamp": idx,
                                "open": row["Open"],
                                "high": row["High"],
                                "low": row["Low"],
                                "close": row["Close"],
                                "volume": row["Volume"]
                            }
                            self.market_data[symbol].append(data_point)
                    
                except Exception as e:
                    logger.error(f"Market data update failed for {symbol}: {e}")
            
        except Exception as e:
            logger.error(f"Market data update failed: {e}")
    
    async def _update_economic_indicators(self):
        """
        Update economic indicators
        """
        try:
            fred_client = self.data_clients.get("fred")
            if not fred_client:
                return
            
            # Key economic indicators
            indicators = {
                "GDP": "GDP",  # Gross Domestic Product
                "UNRATE": "UNRATE",  # Unemployment Rate
                "CPIAUCSL": "CPIAUCSL",  # Consumer Price Index
                "FEDFUNDS": "FEDFUNDS",  # Federal Funds Rate
                "DEXUSEU": "DEXUSEU",  # USD/EUR Exchange Rate
                "DGS10": "DGS10"  # 10-Year Treasury Rate
            }
            
            for name, series_id in indicators.items():
                try:
                    data = fred_client.get_series(series_id, limit=1)
                    if not data.empty:
                        self.economic_indicators[name] = {
                            "value": data.iloc[-1],
                            "date": data.index[-1],
                            "updated_at": datetime.now()
                        }
                        
                except Exception as e:
                    logger.error(f"Economic indicator update failed for {name}: {e}")
            
        except Exception as e:
            logger.error(f"Economic indicators update failed: {e}")
    
    async def _update_sentiment_data(self):
        """
        Update sentiment data from social media and news
        """
        try:
            # Get news sentiment
            await self._update_news_sentiment()
            
            # Get social media sentiment
            await self._update_social_sentiment()
            
            # Get web sentiment
            await self._update_web_sentiment()
            
        except Exception as e:
            logger.error(f"Sentiment data update failed: {e}")
    
    async def _update_news_sentiment(self):
        """
        Update sentiment from news sources
        """
        try:
            news_client = self.data_clients.get("news_api")
            if not news_client:
                return
            
            # Get financial news
            news = news_client.get_everything(
                q="stock market OR economy OR financial",
                language="en",
                sort_by="publishedAt",
                page_size=100
            )
            
            for article in news.get("articles", []):
                try:
                    title = article.get("title", "")
                    description = article.get("description", "")
                    content = f"{title} {description}"
                    
                    # Analyze sentiment
                    sentiment = self._analyze_text_sentiment(content)
                    
                    sentiment_data = {
                        "source": "news_api",
                        "content": content,
                        "sentiment": sentiment,
                        "timestamp": datetime.fromisoformat(article["publishedAt"].replace('Z', '+00:00')),
                        "url": article.get("url"),
                        "collected_at": datetime.now()
                    }
                    
                    self.sentiment_data["news"].append(sentiment_data)
                    
                except Exception as e:
                    logger.error(f"News sentiment analysis failed: {e}")
            
        except Exception as e:
            logger.error(f"News sentiment update failed: {e}")
    
    async def _update_social_sentiment(self):
        """
        Update sentiment from social media
        """
        try:
            # Twitter sentiment
            await self._update_twitter_sentiment()
            
            # Reddit sentiment
            await self._update_reddit_sentiment()
            
        except Exception as e:
            logger.error(f"Social sentiment update failed: {e}")
    
    async def _update_twitter_sentiment(self):
        """
        Update sentiment from Twitter
        """
        try:
            twitter_client = self.data_clients.get("twitter")
            if not twitter_client:
                return
            
            # Search for financial tweets
            tweets = twitter_client.search_tweets(
                q="$SPY OR $AAPL OR economy OR stock market",
                lang="en",
                count=100,
                tweet_mode="extended"
            )
            
            for tweet in tweets:
                try:
                    content = tweet.full_text
                    sentiment = self._analyze_text_sentiment(content)
                    
                    sentiment_data = {
                        "source": "twitter",
                        "content": content,
                        "sentiment": sentiment,
                        "timestamp": tweet.created_at,
                        "user": tweet.user.screen_name,
                        "collected_at": datetime.now()
                    }
                    
                    self.sentiment_data["twitter"].append(sentiment_data)
                    
                except Exception as e:
                    logger.error(f"Twitter sentiment analysis failed: {e}")
            
        except Exception as e:
            logger.error(f"Twitter sentiment update failed: {e}")
    
    async def _update_reddit_sentiment(self):
        """
        Update sentiment from Reddit
        """
        try:
            reddit_client = self.data_clients.get("reddit")
            if not reddit_client:
                return
            
            # Monitor financial subreddits
            subreddits = ["wallstreetbets", "investing", "stocks", "StockMarket"]
            
            for subreddit_name in subreddits:
                try:
                    subreddit = reddit_client.subreddit(subreddit_name)
                    
                    for post in subreddit.hot(limit=50):
                        content = f"{post.title} {post.selftext}"
                        sentiment = self._analyze_text_sentiment(content)
                        
                        sentiment_data = {
                            "source": "reddit",
                            "subreddit": subreddit_name,
                            "content": content,
                            "sentiment": sentiment,
                            "timestamp": datetime.fromtimestamp(post.created_utc),
                            "score": post.score,
                            "collected_at": datetime.now()
                        }
                        
                        self.sentiment_data["reddit"].append(sentiment_data)
                        
                except Exception as e:
                    logger.error(f"Reddit sentiment update failed for {subreddit_name}: {e}")
            
        except Exception as e:
            logger.error(f"Reddit sentiment update failed: {e}")
    
    async def _update_web_sentiment(self):
        """
        Update sentiment from web scraping
        """
        try:
            scraper = self.data_clients.get("web_scraper")
            if not scraper:
                return
            
            # Financial websites to scrape
            urls = [
                "https://www.investing.com/news/stock-market-news",
                "https://www.marketwatch.com/investing",
                "https://finance.yahoo.com/news"
            ]
            
            for url in urls:
                try:
                    scraper.get(url)
                    soup = BeautifulSoup(scraper.page_source, 'html.parser')
                    
                    # Extract headlines
                    headlines = soup.find_all(['h1', 'h2', 'h3'])
                    
                    for headline in headlines[:10]:  # Limit to 10 headlines per page
                        content = headline.get_text().strip()
                        if len(content) > 20:  # Filter short titles
                            sentiment = self._analyze_text_sentiment(content)
                            
                            sentiment_data = {
                                "source": "web_scraping",
                                "url": url,
                                "content": content,
                                "sentiment": sentiment,
                                "collected_at": datetime.now()
                            }
                            
                            self.sentiment_data["web"].append(sentiment_data)
                            
                except Exception as e:
                    logger.error(f"Web scraping failed for {url}: {e}")
            
        except Exception as e:
            logger.error(f"Web sentiment update failed: {e}")
    
    def _analyze_text_sentiment(self, text: str) -> Dict[str, float]:
        """
        Analyze sentiment of text
        """
        try:
            # Use TextBlob for basic sentiment analysis
            blob = TextBlob(text)
            
            sentiment = {
                "polarity": blob.sentiment.polarity,  # -1 to 1
                "subjectivity": blob.sentiment.subjectivity,  # 0 to 1
                "sentiment": "positive" if blob.sentiment.polarity > 0.1 else "negative" if blob.sentiment.polarity < -0.1 else "neutral"
            }
            
            return sentiment
            
        except Exception as e:
            logger.error(f"Text sentiment analysis failed: {e}")
            return {"polarity": 0.0, "subjectivity": 0.0, "sentiment": "neutral"}
    
    async def _analyze_market_sentiment(self):
        """
        Analyze overall market sentiment
        """
        try:
            # Aggregate sentiment from all sources
            all_sentiment = []
            
            for source, sentiments in self.sentiment_data.items():
                recent_sentiments = [s for s in sentiments 
                                   if (datetime.now() - s["collected_at"]).seconds < 3600]  # Last hour
                
                if recent_sentiments:
                    avg_polarity = np.mean([s["sentiment"]["polarity"] for s in recent_sentiments])
                    all_sentiment.append(avg_polarity)
            
            if all_sentiment:
                overall_sentiment = np.mean(all_sentiment)
                
                self.market_intelligence["sentiment"] = {
                    "overall_score": overall_sentiment,
                    "sentiment": "bullish" if overall_sentiment > 0.1 else "bearish" if overall_sentiment < -0.1 else "neutral",
                    "sources_count": len(all_sentiment),
                    "analyzed_at": datetime.now()
                }
            
        except Exception as e:
            logger.error(f"Market sentiment analysis failed: {e}")
    
    async def _update_price_forecasts(self):
        """
        Update price forecasts for tracked symbols
        """
        try:
            symbols = ["SPY", "AAPL", "MSFT", "GOOGL"]
            
            for symbol in symbols:
                try:
                    forecast = await self._forecast_symbol_price(symbol)
                    
                    self.forecast_cache[symbol] = {
                        "forecast": forecast,
                        "generated_at": datetime.now()
                    }
                    
                except Exception as e:
                    logger.error(f"Price forecast failed for {symbol}: {e}")
            
        except Exception as e:
            logger.error(f"Price forecast update failed: {e}")
    
    async def _forecast_symbol_price(self, symbol: str) -> Dict[str, Any]:
        """
        Forecast price for a symbol using ensemble of models
        """
        try:
            # Get historical data
            data = list(self.market_data[symbol])
            if len(data) < 100:  # Need sufficient data
                return {"error": "Insufficient data"}
            
            # Prepare features
            df = pd.DataFrame(data)
            df = df.sort_values("timestamp")
            
            # Create technical indicators
            df = self._add_technical_indicators(df)
            
            # Prepare training data
            feature_cols = ["close", "volume", "sma_20", "sma_50", "rsi", "macd", "bb_upper", "bb_lower"]
            target_col = "close"
            
            # Shift target for prediction
            df["target"] = df[target_col].shift(-self.market_config["forecast_horizon"])
            df = df.dropna()
            
            if len(df) < 50:
                return {"error": "Insufficient data after processing"}
            
            X = df[feature_cols].values
            y = df["target"].values
            
            # Train/test split
            train_size = int(len(X) * 0.8)
            X_train, X_test = X[:train_size], X[train_size:]
            y_train, y_test = y[:train_size], y[train_size:]
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train models and generate forecasts
            forecasts = {}
            accuracies = {}
            
            for model_name, model in self.forecast_models.items():
                try:
                    # Train model
                    model.fit(X_train_scaled, y_train)
                    
                    # Generate forecast
                    last_features = X[-1:].copy()
                    last_features_scaled = scaler.transform(last_features)
                    forecast_price = model.predict(last_features_scaled)[0]
                    
                    # Calculate accuracy on test set
                    test_predictions = model.predict(X_test_scaled)
                    mae = mean_absolute_error(y_test, test_predictions)
                    rmse = np.sqrt(mean_squared_error(y_test, test_predictions))
                    
                    forecasts[model_name] = float(forecast_price)
                    accuracies[model_name] = {
                        "mae": float(mae),
                        "rmse": float(rmse),
                        "accuracy_score": 1 - (mae / np.mean(y_test))  # Simple accuracy metric
                    }
                    
                except Exception as e:
                    logger.error(f"Model forecast failed for {model_name}: {e}")
            
            # Ensemble forecast (weighted average)
            if forecasts:
                weights = {name: acc.get("accuracy_score", 0.5) for name, acc in accuracies.items()}
                total_weight = sum(weights.values())
                
                if total_weight > 0:
                    ensemble_forecast = sum(forecasts[name] * weights[name] for name in forecasts) / total_weight
                else:
                    ensemble_forecast = np.mean(list(forecasts.values()))
                
                current_price = df["close"].iloc[-1]
                
                return {
                    "symbol": symbol,
                    "current_price": float(current_price),
                    "ensemble_forecast": float(ensemble_forecast),
                    "forecast_horizon_days": self.market_config["forecast_horizon"],
                    "expected_change_percent": float(((ensemble_forecast - current_price) / current_price) * 100),
                    "model_forecasts": forecasts,
                    "model_accuracies": accuracies,
                    "forecast_confidence": np.std(list(forecasts.values())) / current_price,  # Lower std = higher confidence
                    "generated_at": datetime.now()
                }
            
            return {"error": "No forecasts generated"}
            
        except Exception as e:
            logger.error(f"Symbol price forecast failed: {e}")
            return {"error": str(e)}
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add technical indicators to dataframe
        """
        try:
            # Simple Moving Averages
            df["sma_20"] = df["close"].rolling(window=20).mean()
            df["sma_50"] = df["close"].rolling(window=50).mean()
            
            # RSI (Relative Strength Index)
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df["rsi"] = 100 - (100 / (1 + rs))
            
            # MACD (Moving Average Convergence Divergence)
            ema_12 = df["close"].ewm(span=12).mean()
            ema_26 = df["close"].ewm(span=26).mean()
            df["macd"] = ema_12 - ema_26
            
            # Bollinger Bands
            sma_20 = df["close"].rolling(window=20).mean()
            std_20 = df["close"].rolling(window=20).std()
            df["bb_upper"] = sma_20 + (std_20 * 2)
            df["bb_lower"] = sma_20 - (std_20 * 2)
            
            # Fill NaN values
            df = df.fillna(method="bfill").fillna(method="ffill")
            
            return df
            
        except Exception as e:
            logger.error(f"Technical indicators calculation failed: {e}")
            return df
    
    async def _track_competitor_activities(self):
        """
        Track competitor activities and news
        """
        try:
            competitors = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META"]
            
            for competitor in competitors:
                try:
                    # Get competitor news
                    news_client = self.data_clients.get("news_api")
                    if news_client:
                        news = news_client.get_everything(
                            q=competitor,
                            language="en",
                            sort_by="publishedAt",
                            page_size=20
                        )
                        
                        competitor_news = []
                        for article in news.get("articles", []):
                            competitor_news.append({
                                "title": article.get("title"),
                                "description": article.get("description"),
                                "url": article.get("url"),
                                "published_at": article.get("publishedAt"),
                                "sentiment": self._analyze_text_sentiment(
                                    f"{article.get('title', '')} {article.get('description', '')}"
                                )
                            })
                        
                        self.competitor_data[competitor]["news"] = competitor_news
                    
                    # Get stock data
                    ticker = yf.Ticker(competitor)
                    info = ticker.info
                    
                    self.competitor_data[competitor]["stock_info"] = {
                        "price": info.get("currentPrice"),
                        "market_cap": info.get("marketCap"),
                        "pe_ratio": info.get("trailingPE"),
                        "revenue_growth": info.get("revenueGrowth"),
                        "updated_at": datetime.now()
                    }
                    
                except Exception as e:
                    logger.error(f"Competitor tracking failed for {competitor}: {e}")
            
        except Exception as e:
            logger.error(f"Competitor tracking failed: {e}")
    
    async def _analyze_competitive_landscape(self):
        """
        Analyze competitive landscape
        """
        try:
            # Calculate market share based on market cap
            market_caps = {}
            
            for competitor, data in self.competitor_data.items():
                stock_info = data.get("stock_info", {})
                market_cap = stock_info.get("market_cap")
                if market_cap:
                    market_caps[competitor] = market_cap
            
            if market_caps:
                total_market_cap = sum(market_caps.values())
                
                market_shares = {
                    comp: (cap / total_market_cap) * 100
                    for comp, cap in market_caps.items()
                }
                
                self.market_intelligence["competitive_landscape"] = {
                    "market_shares": market_shares,
                    "total_competitors": len(market_caps),
                    "analyzed_at": datetime.now()
                }
            
        except Exception as e:
            logger.error(f"Competitive landscape analysis failed: {e}")
    
    async def _update_market_intelligence(self):
        """
        Update comprehensive market intelligence
        """
        try:
            intelligence = {
                "market_trends": await self._analyze_market_trends(),
                "sector_analysis": await self._analyze_sector_performance(),
                "risk_assessment": await self._assess_market_risks(),
                "investment_opportunities": await self._identify_opportunities(),
                "updated_at": datetime.now()
            }
            
            self.market_intelligence.update(intelligence)
            
            # Save to database
            await self._save_market_intelligence(intelligence)
            
        except Exception as e:
            logger.error(f"Market intelligence update failed: {e}")
    
    async def _analyze_market_trends(self) -> Dict[str, Any]:
        """
        Analyze market trends
        """
        try:
            # Analyze major indices
            indices = ["^GSPC", "^IXIC", "^DJI"]  # S&P 500, NASDAQ, Dow Jones
            
            trends = {}
            
            for index in indices:
                try:
                    ticker = yf.Ticker(index)
                    hist = ticker.history(period="1y")
                    
                    if not hist.empty:
                        # Calculate trend metrics
                        current_price = hist["Close"].iloc[-1]
                        year_ago_price = hist["Close"].iloc[0]
                        year_return = ((current_price - year_ago_price) / year_ago_price) * 100
                        
                        # Calculate volatility
                        daily_returns = hist["Close"].pct_change().dropna()
                        volatility = daily_returns.std() * np.sqrt(252) * 100  # Annualized volatility
                        
                        # Trend direction
                        recent_prices = hist["Close"].tail(30)
                        slope, _, _, _, _ = linregress(range(len(recent_prices)), recent_prices)
                        trend = "upward" if slope > 0 else "downward"
                        
                        trends[index] = {
                            "current_price": float(current_price),
                            "year_return_percent": float(year_return),
                            "volatility_percent": float(volatility),
                            "trend": trend,
                            "trend_slope": float(slope)
                        }
                        
                except Exception as e:
                    logger.error(f"Market trend analysis failed for {index}: {e}")
            
            return trends
            
        except Exception as e:
            logger.error(f"Market trends analysis failed: {e}")
            return {}
    
    async def _analyze_sector_performance(self) -> Dict[str, Any]:
        """
        Analyze sector performance
        """
        try:
            # Major sector ETFs
            sectors = {
                "Technology": "XLK",
                "Healthcare": "XLV",
                "Financials": "XLF",
                "Consumer Discretionary": "XLY",
                "Communication Services": "XLC",
                "Industrials": "XLI",
                "Consumer Staples": "XLP",
                "Energy": "XLE",
                "Utilities": "XLU",
                "Real Estate": "XLRE",
                "Materials": "XLB"
            }
            
            sector_performance = {}
            
            for sector_name, symbol in sectors.items():
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="3mo")
                    
                    if not hist.empty:
                        current_price = hist["Close"].iloc[-1]
                        three_month_ago = hist["Close"].iloc[0]
                        return_pct = ((current_price - three_month_ago) / three_month_ago) * 100
                        
                        sector_performance[sector_name] = {
                            "symbol": symbol,
                            "current_price": float(current_price),
                            "three_month_return_percent": float(return_pct),
                            "performance": "outperforming" if return_pct > 5 else "underperforming" if return_pct < -5 else "neutral"
                        }
                        
                except Exception as e:
                    logger.error(f"Sector performance analysis failed for {sector_name}: {e}")
            
            return sector_performance
            
        except Exception as e:
            logger.error(f"Sector performance analysis failed: {e}")
            return {}
    
    async def _assess_market_risks(self) -> Dict[str, Any]:
        """
        Assess market risks
        """
        try:
            risks = {}
            
            # Volatility risk
            spy_data = list(self.market_data.get("SPY", []))
            if len(spy_data) > 30:
                recent_prices = [d["close"] for d in spy_data[-30:]]
                daily_returns = np.diff(recent_prices) / recent_prices[:-1]
                volatility = np.std(daily_returns) * np.sqrt(252) * 100
                
                risks["volatility_risk"] = {
                    "level": "high" if volatility > 30 else "medium" if volatility > 20 else "low",
                    "volatility_percent": float(volatility)
                }
            
            # Economic indicator risks
            gdp = self.economic_indicators.get("GDP", {}).get("value")
            unemployment = self.economic_indicators.get("UNRATE", {}).get("value")
            inflation = self.economic_indicators.get("CPIAUCSL", {}).get("value")
            
            if unemployment and unemployment > 5:
                risks["unemployment_risk"] = {
                    "level": "high",
                    "rate": float(unemployment)
                }
            
            if inflation and inflation > 3:
                risks["inflation_risk"] = {
                    "level": "high",
                    "rate": float(inflation)
                }
            
            # Sentiment risk
            sentiment = self.market_intelligence.get("sentiment", {})
            sentiment_score = sentiment.get("overall_score", 0)
            
            if abs(sentiment_score) > 0.3:
                risks["sentiment_risk"] = {
                    "level": "high",
                    "sentiment": sentiment.get("sentiment"),
                    "score": float(sentiment_score)
                }
            
            return risks
            
        except Exception as e:
            logger.error(f"Market risk assessment failed: {e}")
            return {}
    
    async def _identify_opportunities(self) -> List[Dict[str, Any]]:
        """
        Identify investment opportunities
        """
        try:
            opportunities = []
            
            # Analyze undervalued stocks (simplified)
            symbols = ["AAPL", "MSFT", "GOOGL", "AMZN"]
            
            for symbol in symbols:
                try:
                    forecast = self.forecast_cache.get(symbol, {})
                    
                    if forecast and "expected_change_percent" in forecast:
                        change_pct = forecast["expected_change_percent"]
                        
                        if change_pct > 10:  # Expected >10% growth
                            opportunities.append({
                                "symbol": symbol,
                                "type": "growth_opportunity",
                                "expected_return_percent": float(change_pct),
                                "confidence": forecast.get("forecast_confidence", 0),
                                "reason": "Strong price forecast momentum"
                            })
                            
                except Exception as e:
                    logger.error(f"Opportunity identification failed for {symbol}: {e}")
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Investment opportunities identification failed: {e}")
            return []
    
    async def _save_market_intelligence(self, intelligence: Dict[str, Any]):
        """
        Save market intelligence to database
        """
        try:
            async with get_db_session() as session:
                intelligence_entry = MarketIntelligence(
                    intelligence_type="comprehensive",
                    intelligence_data=json.dumps(intelligence),
                    generated_at=datetime.now()
                )
                
                session.add(intelligence_entry)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Market intelligence save failed: {e}")
    
    async def _handle_market_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle market analysis request
        """
        try:
            symbol = message.content.get("symbol", "SPY")
            analysis_type = message.content.get("analysis_type", "comprehensive")
            
            if analysis_type == "technical":
                analysis = await self._perform_technical_analysis(symbol)
            elif analysis_type == "fundamental":
                analysis = await self._perform_fundamental_analysis(symbol)
            else:
                analysis = await self._perform_comprehensive_analysis(symbol)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "market_analysis_response",
                    "symbol": symbol,
                    "analysis_type": analysis_type,
                    "analysis": analysis
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Market analysis handling failed: {e}")
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
    
    async def _perform_technical_analysis(self, symbol: str) -> Dict[str, Any]:
        """
        Perform technical analysis
        """
        try:
            data = list(self.market_data[symbol])
            if not data:
                return {"error": "No data available"}
            
            df = pd.DataFrame(data)
            df = self._add_technical_indicators(df)
            
            # Current technical indicators
            latest = df.iloc[-1]
            
            analysis = {
                "current_price": float(latest["close"]),
                "sma_20": float(latest["sma_20"]),
                "sma_50": float(latest["sma_50"]),
                "rsi": float(latest["rsi"]),
                "macd": float(latest["macd"]),
                "bollinger_upper": float(latest["bb_upper"]),
                "bollinger_lower": float(latest["bb_lower"]),
                "signal": self._generate_technical_signal(latest)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Technical analysis failed: {e}")
            return {"error": str(e)}
    
    def _generate_technical_signal(self, indicators: pd.Series) -> str:
        """
        Generate technical trading signal
        """
        try:
            signals = []
            
            # RSI signals
            if indicators["rsi"] < 30:
                signals.append("oversold")
            elif indicators["rsi"] > 70:
                signals.append("overbought")
            
            # Moving average signals
            if indicators["close"] > indicators["sma_20"] > indicators["sma_50"]:
                signals.append("golden_cross")
            elif indicators["close"] < indicators["sma_20"] < indicators["sma_50"]:
                signals.append("death_cross")
            
            # Bollinger Band signals
            if indicators["close"] > indicators["bb_upper"]:
                signals.append("breakout_upper")
            elif indicators["close"] < indicators["bb_lower"]:
                signals.append("breakout_lower")
            
            return ", ".join(signals) if signals else "neutral"
            
        except Exception as e:
            return "error"
    
    async def _perform_fundamental_analysis(self, symbol: str) -> Dict[str, Any]:
        """
        Perform fundamental analysis
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            analysis = {
                "company_name": info.get("longName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
                "revenue_growth": info.get("revenueGrowth"),
                "earnings_growth": info.get("earningsGrowth"),
                "dividend_yield": info.get("dividendYield"),
                "debt_to_equity": info.get("debtToEquity"),
                "return_on_equity": info.get("returnOnEquity"),
                "profit_margins": info.get("profitMargins")
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Fundamental analysis failed: {e}")
            return {"error": str(e)}
    
    async def _perform_comprehensive_analysis(self, symbol: str) -> Dict[str, Any]:
        """
        Perform comprehensive market analysis
        """
        try:
            technical = await self._perform_technical_analysis(symbol)
            fundamental = await self._perform_fundamental_analysis(symbol)
            
            # Combine with sentiment and forecast
            sentiment = self.market_intelligence.get("sentiment", {})
            forecast = self.forecast_cache.get(symbol, {})
            
            analysis = {
                "technical": technical,
                "fundamental": fundamental,
                "sentiment": sentiment,
                "forecast": forecast,
                "overall_rating": self._calculate_overall_rating(technical, fundamental, sentiment, forecast)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Comprehensive analysis failed: {e}")
            return {"error": str(e)}
    
    def _calculate_overall_rating(self, technical: Dict, fundamental: Dict, sentiment: Dict, forecast: Dict) -> str:
        """
        Calculate overall investment rating
        """
        try:
            score = 0
            
            # Technical score (0-25)
            if technical.get("signal") and "golden_cross" in technical["signal"]:
                score += 20
            elif technical.get("signal") and "oversold" in technical["signal"]:
                score += 15
            
            # Fundamental score (0-25)
            pe_ratio = fundamental.get("pe_ratio")
            if pe_ratio and 10 <= pe_ratio <= 25:
                score += 20
            elif pe_ratio and pe_ratio < 15:
                score += 15
            
            # Sentiment score (0-25)
            sentiment_score = sentiment.get("overall_score", 0)
            if sentiment_score > 0.1:
                score += 20
            elif sentiment_score > -0.1:
                score += 10
            
            # Forecast score (0-25)
            expected_change = forecast.get("expected_change_percent", 0)
            if expected_change > 10:
                score += 20
            elif expected_change > 0:
                score += 10
            
            # Convert to rating
            if score >= 70:
                return "strong_buy"
            elif score >= 50:
                return "buy"
            elif score >= 30:
                return "hold"
            else:
                return "sell"
                
        except Exception as e:
            return "neutral"
    
    async def _handle_price_forecast(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle price forecast request
        """
        try:
            symbol = message.content.get("symbol")
            horizon = message.content.get("horizon", self.market_config["forecast_horizon"])
            
            if not symbol:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Symbol required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Get cached forecast or generate new one
            forecast = self.forecast_cache.get(symbol)
            
            if not forecast or (datetime.now() - forecast.get("generated_at", datetime.min)).seconds > 3600:
                forecast = await self._forecast_symbol_price(symbol)
                self.forecast_cache[symbol] = forecast
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "price_forecast_response",
                    "symbol": symbol,
                    "forecast": forecast
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Price forecast handling failed: {e}")
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
    
    async def _handle_sentiment_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle sentiment analysis request
        """
        try:
            source = message.content.get("source", "all")
            time_window = message.content.get("time_window", 3600)  # seconds
            
            sentiment_data = {}
            
            if source == "all":
                sentiment_data = dict(self.sentiment_data)
            else:
                sentiment_data = {source: self.sentiment_data.get(source, [])}
            
            # Filter by time window
            filtered_data = {}
            cutoff_time = datetime.now() - timedelta(seconds=time_window)
            
            for src, sentiments in sentiment_data.items():
                filtered_sentiments = [
                    s for s in sentiments 
                    if s.get("collected_at", datetime.min) > cutoff_time
                ]
                filtered_data[src] = filtered_sentiments
            
            # Calculate aggregate sentiment
            aggregate_sentiment = self._calculate_aggregate_sentiment(filtered_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "sentiment_analysis_response",
                    "source": source,
                    "time_window_seconds": time_window,
                    "sentiment_data": filtered_data,
                    "aggregate_sentiment": aggregate_sentiment
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Sentiment analysis handling failed: {e}")
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
    
    def _calculate_aggregate_sentiment(self, sentiment_data: Dict[str, List]) -> Dict[str, Any]:
        """
        Calculate aggregate sentiment across sources
        """
        try:
            all_polarities = []
            source_counts = {}
            
            for source, sentiments in sentiment_data.items():
                polarities = [s["sentiment"]["polarity"] for s in sentiments if "sentiment" in s]
                all_polarities.extend(polarities)
                source_counts[source] = len(sentiments)
            
            if not all_polarities:
                return {"overall_sentiment": "neutral", "average_polarity": 0.0}
            
            avg_polarity = np.mean(all_polarities)
            
            sentiment_label = (
                "very_positive" if avg_polarity > 0.3 else
                "positive" if avg_polarity > 0.1 else
                "neutral" if avg_polarity > -0.1 else
                "negative" if avg_polarity > -0.3 else
                "very_negative"
            )
            
            return {
                "overall_sentiment": sentiment_label,
                "average_polarity": float(avg_polarity),
                "total_samples": len(all_polarities),
                "source_breakdown": source_counts
            }
            
        except Exception as e:
            logger.error(f"Aggregate sentiment calculation failed: {e}")
            return {"error": str(e)}
    
    async def _handle_competitor_tracking(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle competitor tracking request
        """
        try:
            competitor = message.content.get("competitor")
            
            if not competitor:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Competitor symbol required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            competitor_info = self.competitor_data.get(competitor, {})
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "competitor_tracking_response",
                    "competitor": competitor,
                    "info": competitor_info
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Competitor tracking handling failed: {e}")
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
    
    async def _handle_economic_indicators(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle economic indicators request
        """
        try:
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "economic_indicators_response",
                    "indicators": self.economic_indicators
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Economic indicators handling failed: {e}")
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
    
    async def _handle_intelligence_report(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle market intelligence report request
        """
        try:
            report_type = message.content.get("report_type", "comprehensive")
            
            if report_type == "comprehensive":
                report = self.market_intelligence
            elif report_type == "trends":
                report = {"market_trends": self.market_intelligence.get("market_trends", {})}
            elif report_type == "sentiment":
                report = {"sentiment": self.market_intelligence.get("sentiment", {})}
            elif report_type == "risks":
                report = {"risks": self.market_intelligence.get("risk_assessment", {})}
            else:
                report = self.market_intelligence
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "intelligence_report_response",
                    "report_type": report_type,
                    "report": report
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Intelligence report handling failed: {e}")
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
    async def test_market_intelligence_agent():
        # Initialize market intelligence agent
        agent = MarketIntelligenceAgent()
        await agent.start()
        
        # Test market analysis
        analysis_message = AgentMessage(
            id="test_analyze",
            from_agent="test",
            to_agent="market_intelligence_agent",
            content={
                "type": "analyze_market",
                "symbol": "AAPL",
                "analysis_type": "technical"
            },
            timestamp=datetime.now()
        )
        
        print("Testing market intelligence agent...")
        async for response in agent.process_message(analysis_message):
            print(f"Analysis response: {response.content.get('type')}")
            if response.content.get("type") == "market_analysis_response":
                analysis = response.content.get("analysis", {})
                print(f"Technical analysis for AAPL: RSI={analysis.get('rsi', 'N/A')}")
        
        # Test sentiment analysis
        sentiment_message = AgentMessage(
            id="test_sentiment",
            from_agent="test",
            to_agent="market_intelligence_agent",
            content={
                "type": "analyze_sentiment",
                "source": "news",
                "time_window": 3600
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(sentiment_message):
            print(f"Sentiment analysis response: {response.content.get('type')}")
        
        # Test price forecast
        forecast_message = AgentMessage(
            id="test_forecast",
            from_agent="test",
            to_agent="market_intelligence_agent",
            content={
                "type": "forecast_price",
                "symbol": "MSFT"
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(forecast_message):
            print(f"Price forecast response: {response.content.get('type')}")
            if response.content.get("type") == "price_forecast_response":
                forecast = response.content.get("forecast", {})
                print(f"MSFT forecast: ${forecast.get('ensemble_forecast', 'N/A'):.2f}")
        
        # Stop agent
        await agent.stop()
        print("Market intelligence agent test completed")
    
    # Run test
    asyncio.run(test_market_intelligence_agent())
