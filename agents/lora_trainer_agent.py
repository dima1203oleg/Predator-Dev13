"""
LoRA Trainer Agent: Self-learning with MLflow
Implements LoRA fine-tuning for model improvement with F1≥0.95 threshold
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
import tempfile
import shutil

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer, 
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
    EarlyStoppingCallback
)
import mlflow
import mlflow.pytorch
from mlflow.tracking import MlflowClient
import optuna

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import ModelTraining, TrainingMetrics

logger = logging.getLogger(__name__)


class LoRATrainerAgent(BaseAgent):
    """
    LoRA Trainer Agent for self-learning model improvement
    Fine-tunes models using LoRA with MLflow tracking and F1≥0.95 threshold
    """
    
    def __init__(
        self,
        agent_id: str = "lora_trainer_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # LoRA training configuration
        self.lora_config = {
            "r": self.config.get("lora_r", 8),  # LoRA rank
            "alpha": self.config.get("lora_alpha", 16),  # LoRA alpha
            "dropout": self.config.get("lora_dropout", 0.1),
            "target_modules": self.config.get("target_modules", ["q_proj", "v_proj"])
        }
        
        # Training parameters
        self.training_config = {
            "learning_rate": self.config.get("learning_rate", 2e-5),
            "batch_size": self.config.get("batch_size", 16),
            "max_epochs": self.config.get("max_epochs", 10),
            "warmup_steps": self.config.get("warmup_steps", 100),
            "weight_decay": self.config.get("weight_decay", 0.01),
            "gradient_accumulation_steps": self.config.get("gradient_accumulation_steps", 2),
            "max_grad_norm": self.config.get("max_grad_norm", 1.0)
        }
        
        # Performance thresholds
        self.f1_threshold = self.config.get("f1_threshold", 0.95)
        self.min_improvement = self.config.get("min_improvement", 0.02)  # 2% improvement required
        
        # MLflow configuration
        self.mlflow_tracking_uri = self.config.get("mlflow_tracking_uri", "sqlite:///mlruns.db")
        self.experiment_name = self.config.get("experiment_name", "predator_lora_training")
        
        # Model registry
        self.model_registry = self.config.get("model_registry", {})
        
        # Training state
        self.active_trainings = {}
        self.training_queue = asyncio.Queue()
        
        # Initialize MLflow
        mlflow.set_tracking_uri(self.mlflow_tracking_uri)
        try:
            mlflow.create_experiment(self.experiment_name)
        except:
            pass  # Experiment already exists
        
        logger.info(f"LoRA Trainer Agent initialized: {agent_id}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process LoRA training requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "start_lora_training":
                async for response in self._handle_training_start(message):
                    yield response
                    
            elif message_type == "check_training_status":
                async for response in self._handle_status_check(message):
                    yield response
                    
            elif message_type == "evaluate_model_performance":
                async for response in self._handle_performance_evaluation(message):
                    yield response
                    
            elif message_type == "optimize_hyperparameters":
                async for response in self._handle_hyperparameter_optimization(message):
                    yield response
                    
            elif message_type == "deploy_improved_model":
                async for response in self._handle_model_deployment(message):
                    yield response
                    
            elif message_type == "analyze_training_history":
                async for response in self._handle_training_history_analysis(message):
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
            logger.error(f"LoRA training processing failed: {e}")
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
    
    async def _handle_training_start(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle LoRA training start request
        """
        try:
            training_config = message.content.get("training_config", {})
            
            # Validate training configuration
            validation_result = self._validate_training_config(training_config)
            if not validation_result["valid"]:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "validation_error",
                        "errors": validation_result["errors"]
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Start training
            training_id = await self._start_lora_training(training_config)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "training_started",
                    "training_id": training_id,
                    "status": "queued",
                    "estimated_duration": "2-4 hours"
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Training start failed: {e}")
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
    
    def _validate_training_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate training configuration
        """
        errors = []
        
        required_fields = ["base_model", "task_type", "dataset_path"]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Validate base model
        base_model = config.get("base_model")
        if base_model and base_model not in self.model_registry:
            errors.append(f"Unknown base model: {base_model}")
        
        # Validate task type
        valid_tasks = ["classification", "regression", "ner", "sentiment"]
        task_type = config.get("task_type")
        if task_type and task_type not in valid_tasks:
            errors.append(f"Invalid task type: {task_type}. Must be one of {valid_tasks}")
        
        # Validate dataset path
        dataset_path = config.get("dataset_path")
        if dataset_path and not os.path.exists(dataset_path):
            errors.append(f"Dataset path does not exist: {dataset_path}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    async def _start_lora_training(self, config: Dict[str, Any]) -> str:
        """
        Start LoRA training process
        """
        try:
            training_id = str(uuid.uuid4())
            
            # Create training task
            training_task = {
                "id": training_id,
                "config": config,
                "status": "queued",
                "created_at": datetime.now(),
                "progress": 0.0
            }
            
            self.active_trainings[training_id] = training_task
            
            # Add to training queue
            await self.training_queue.put(training_id)
            
            # Start training worker if not already running
            if not hasattr(self, '_training_worker_task') or self._training_worker_task.done():
                self._training_worker_task = asyncio.create_task(self._training_worker())
            
            return training_id
            
        except Exception as e:
            logger.error(f"Training initialization failed: {e}")
            raise
    
    async def _training_worker(self):
        """
        Background training worker
        """
        try:
            while True:
                # Get next training task
                training_id = await self.training_queue.get()
                
                try:
                    # Execute training
                    await self._execute_lora_training(training_id)
                    
                except Exception as e:
                    logger.error(f"Training execution failed for {training_id}: {e}")
                    self.active_trainings[training_id]["status"] = "failed"
                    self.active_trainings[training_id]["error"] = str(e)
                
                finally:
                    self.training_queue.task_done()
                    
        except Exception as e:
            logger.error(f"Training worker failed: {e}")
    
    async def _execute_lora_training(self, training_id: str):
        """
        Execute LoRA training for given training ID
        """
        try:
            training_task = self.active_trainings[training_id]
            config = training_task["config"]
            
            # Update status
            training_task["status"] = "running"
            training_task["started_at"] = datetime.now()
            
            with mlflow.start_run(experiment_id=self.experiment_name) as run:
                # Log training parameters
                mlflow.log_params({
                    "training_id": training_id,
                    "base_model": config["base_model"],
                    "task_type": config["task_type"],
                    "lora_r": self.lora_config["r"],
                    "lora_alpha": self.lora_config["alpha"],
                    "learning_rate": self.training_config["learning_rate"],
                    "batch_size": self.training_config["batch_size"]
                })
                
                # Prepare dataset
                training_task["progress"] = 0.1
                dataset = await self._prepare_training_dataset(config)
                
                # Setup model and tokenizer
                training_task["progress"] = 0.2
                model, tokenizer = await self._setup_model_and_tokenizer(config)
                
                # Configure LoRA
                training_task["progress"] = 0.3
                model = self._configure_lora(model)
                
                # Training arguments
                training_args = TrainingArguments(
                    output_dir=f"./training_outputs/{training_id}",
                    learning_rate=self.training_config["learning_rate"],
                    per_device_train_batch_size=self.training_config["batch_size"],
                    per_device_eval_batch_size=self.training_config["batch_size"],
                    num_train_epochs=self.training_config["max_epochs"],
                    warmup_steps=self.training_config["warmup_steps"],
                    weight_decay=self.training_config["weight_decay"],
                    gradient_accumulation_steps=self.training_config["gradient_accumulation_steps"],
                    max_grad_norm=self.training_config["max_grad_norm"],
                    logging_steps=10,
                    evaluation_strategy="epoch",
                    save_strategy="epoch",
                    load_best_model_at_end=True,
                    metric_for_best_model="f1",
                    greater_is_better=True,
                    save_total_limit=2,
                    report_to="mlflow"
                )
                
                # Initialize trainer
                trainer = Trainer(
                    model=model,
                    args=training_args,
                    train_dataset=dataset["train"],
                    eval_dataset=dataset["validation"],
                    tokenizer=tokenizer,
                    data_collator=DataCollatorWithPadding(tokenizer),
                    compute_metrics=self._compute_metrics,
                    callbacks=[EarlyStoppingCallback(early_stopping_patience=3)]
                )
                
                # Train model
                training_task["progress"] = 0.4
                train_result = trainer.train()
                
                # Evaluate final model
                training_task["progress"] = 0.8
                eval_results = trainer.evaluate()
                
                # Check performance threshold
                f1_score = eval_results.get("eval_f1", 0)
                meets_threshold = f1_score >= self.f1_threshold
                
                # Log results
                mlflow.log_metrics({
                    "final_f1": f1_score,
                    "final_precision": eval_results.get("eval_precision", 0),
                    "final_recall": eval_results.get("eval_recall", 0),
                    "final_accuracy": eval_results.get("eval_accuracy", 0),
                    "meets_threshold": 1 if meets_threshold else 0
                })
                
                # Save model if it meets threshold
                if meets_threshold:
                    training_task["progress"] = 0.9
                    model_path = f"./models/lora_{training_id}"
                    trainer.save_model(model_path)
                    
                    # Log model to MLflow
                    mlflow.pytorch.log_model(model, "model")
                    
                    training_task["status"] = "completed"
                    training_task["model_path"] = model_path
                    training_task["performance"] = eval_results
                    
                else:
                    training_task["status"] = "threshold_not_met"
                    training_task["performance"] = eval_results
                
                training_task["progress"] = 1.0
                training_task["completed_at"] = datetime.now()
                
                # Save training results to database
                await self._save_training_results(training_id, training_task)
                
        except Exception as e:
            logger.error(f"LoRA training execution failed: {e}")
            training_task["status"] = "failed"
            training_task["error"] = str(e)
            raise
    
    async def _prepare_training_dataset(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare training dataset
        """
        try:
            dataset_path = config["dataset_path"]
            task_type = config["task_type"]
            
            # Load dataset
            if dataset_path.endswith('.csv'):
                df = pd.read_csv(dataset_path)
            elif dataset_path.endswith('.json'):
                df = pd.read_json(dataset_path)
            else:
                raise ValueError(f"Unsupported dataset format: {dataset_path}")
            
            # Prepare dataset based on task type
            if task_type == "classification":
                dataset = self._prepare_classification_dataset(df)
            elif task_type == "sentiment":
                dataset = self._prepare_sentiment_dataset(df)
            else:
                raise ValueError(f"Unsupported task type: {task_type}")
            
            return dataset
            
        except Exception as e:
            logger.error(f"Dataset preparation failed: {e}")
            raise
    
    def _prepare_classification_dataset(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Prepare classification dataset
        """
        try:
            # Assume columns: text, label
            texts = df['text'].tolist()
            labels = df['label'].tolist()
            
            # Create label mapping
            unique_labels = sorted(list(set(labels)))
            label2id = {label: i for i, label in enumerate(unique_labels)}
            id2label = {i: label for label, i in label2id.items()}
            
            # Split dataset
            train_size = int(0.8 * len(texts))
            train_texts = texts[:train_size]
            train_labels = [label2id[label] for label in labels[:train_size]]
            val_texts = texts[train_size:]
            val_labels = [label2id[label] for label in labels[train_size:]]
            
            # Create datasets
            train_dataset = TextClassificationDataset(train_texts, train_labels)
            val_dataset = TextClassificationDataset(val_texts, val_labels)
            
            return {
                "train": train_dataset,
                "validation": val_dataset,
                "label2id": label2id,
                "id2label": id2label
            }
            
        except Exception as e:
            logger.error(f"Classification dataset preparation failed: {e}")
            raise
    
    def _prepare_sentiment_dataset(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Prepare sentiment analysis dataset
        """
        try:
            # Similar to classification but for sentiment
            return self._prepare_classification_dataset(df)
            
        except Exception as e:
            logger.error(f"Sentiment dataset preparation failed: {e}")
            raise
    
    async def _setup_model_and_tokenizer(self, config: Dict[str, Any]) -> Tuple[Any, Any]:
        """
        Setup model and tokenizer
        """
        try:
            base_model = config["base_model"]
            model_name = self.model_registry.get(base_model, base_model)
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # Load model
            model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                num_labels=config.get("num_labels", 2)
            )
            
            return model, tokenizer
            
        except Exception as e:
            logger.error(f"Model setup failed: {e}")
            raise
    
    def _configure_lora(self, model: Any) -> Any:
        """
        Configure LoRA for the model
        """
        try:
            from peft import LoraConfig, get_peft_model
            
            lora_config = LoraConfig(
                r=self.lora_config["r"],
                lora_alpha=self.lora_config["alpha"],
                lora_dropout=self.lora_config["dropout"],
                target_modules=self.lora_config["target_modules"],
                bias="none",
                task_type="SEQ_CLS"
            )
            
            model = get_peft_model(model, lora_config)
            return model
            
        except Exception as e:
            logger.error(f"LoRA configuration failed: {e}")
            raise
    
    def _compute_metrics(self, eval_pred):
        """
        Compute evaluation metrics
        """
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        
        f1 = f1_score(labels, predictions, average='weighted')
        precision = precision_score(labels, predictions, average='weighted')
        recall = recall_score(labels, predictions, average='weighted')
        accuracy = accuracy_score(labels, predictions)
        
        return {
            'f1': f1,
            'precision': precision,
            'recall': recall,
            'accuracy': accuracy
        }
    
    async def _save_training_results(self, training_id: str, training_task: Dict[str, Any]):
        """
        Save training results to database
        """
        try:
            async with get_db_session() as session:
                # Create training record
                training_record = ModelTraining(
                    training_id=training_id,
                    model_type=training_task["config"]["base_model"],
                    task_type=training_task["config"]["task_type"],
                    status=training_task["status"],
                    f1_score=training_task.get("performance", {}).get("eval_f1"),
                    created_at=training_task["created_at"],
                    completed_at=training_task.get("completed_at"),
                    model_path=training_task.get("model_path")
                )
                
                session.add(training_record)
                await session.commit()
                
        except Exception as e:
            logger.error(f"Training results save failed: {e}")
    
    async def _handle_status_check(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle training status check
        """
        try:
            training_id = message.content.get("training_id")
            
            if not training_id or training_id not in self.active_trainings:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Training ID not found"
                    },
                    timestamp=datetime.now()
                )
                return
            
            training_task = self.active_trainings[training_id]
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "training_status",
                    "training_id": training_id,
                    "status": training_task["status"],
                    "progress": training_task["progress"],
                    "created_at": training_task["created_at"].isoformat(),
                    "performance": training_task.get("performance"),
                    "error": training_task.get("error")
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
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
    
    async def _handle_performance_evaluation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle model performance evaluation
        """
        try:
            model_path = message.content.get("model_path")
            test_dataset_path = message.content.get("test_dataset_path")
            
            if not model_path or not os.path.exists(model_path):
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Model path not found"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Evaluate performance
            evaluation_results = await self._evaluate_model_performance(model_path, test_dataset_path)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "performance_evaluation",
                    "model_path": model_path,
                    "results": evaluation_results,
                    "meets_threshold": evaluation_results.get("f1", 0) >= self.f1_threshold
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Performance evaluation failed: {e}")
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
    
    async def _evaluate_model_performance(
        self,
        model_path: str,
        test_dataset_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate model performance
        """
        try:
            # Load model and tokenizer
            model = AutoModelForSequenceClassification.from_pretrained(model_path)
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Load test dataset
            if test_dataset_path:
                if test_dataset_path.endswith('.csv'):
                    test_df = pd.read_csv(test_dataset_path)
                else:
                    test_df = pd.read_json(test_dataset_path)
                
                test_texts = test_df['text'].tolist()
                test_labels = test_df['label'].tolist()
                
                # Tokenize
                test_encodings = tokenizer(test_texts, truncation=True, padding=True, return_tensors="pt")
                
                # Create test dataset
                test_dataset = TextClassificationDataset(test_texts, test_labels)
                test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)
                
                # Evaluate
                model.eval()
                all_predictions = []
                all_labels = []
                
                with torch.no_grad():
                    for batch in test_loader:
                        inputs = {k: v.to(model.device) for k, v in batch.items() if k != 'labels'}
                        labels = batch['labels'].to(model.device)
                        
                        outputs = model(**inputs)
                        predictions = torch.argmax(outputs.logits, dim=1)
                        
                        all_predictions.extend(predictions.cpu().numpy())
                        all_labels.extend(labels.cpu().numpy())
                
                # Calculate metrics
                f1 = f1_score(all_labels, all_predictions, average='weighted')
                precision = precision_score(all_labels, all_predictions, average='weighted')
                recall = recall_score(all_labels, all_predictions, average='weighted')
                accuracy = accuracy_score(all_labels, all_predictions)
                
                return {
                    "f1": f1,
                    "precision": precision,
                    "recall": recall,
                    "accuracy": accuracy,
                    "test_samples": len(test_texts)
                }
            else:
                return {"error": "No test dataset provided"}
            
        except Exception as e:
            logger.error(f"Model evaluation failed: {e}")
            return {"error": str(e)}
    
    async def _handle_hyperparameter_optimization(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle hyperparameter optimization
        """
        try:
            base_config = message.content.get("base_config", {})
            optimization_trials = message.content.get("trials", 20)
            
            # Run hyperparameter optimization
            best_params = await self._optimize_hyperparameters(base_config, optimization_trials)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "hyperparameter_optimization_complete",
                    "best_parameters": best_params,
                    "optimization_trials": optimization_trials
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Hyperparameter optimization failed: {e}")
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
    
    async def _optimize_hyperparameters(
        self,
        base_config: Dict[str, Any],
        trials: int
    ) -> Dict[str, Any]:
        """
        Optimize hyperparameters using Optuna
        """
        try:
            def objective(trial):
                # Define hyperparameter search space
                lora_r = trial.suggest_categorical('lora_r', [4, 8, 16, 32])
                lora_alpha = trial.suggest_categorical('lora_alpha', [8, 16, 32])
                learning_rate = trial.suggest_loguniform('learning_rate', 1e-5, 1e-3)
                batch_size = trial.suggest_categorical('batch_size', [8, 16, 32])
                
                # Mock evaluation (in real implementation, this would run actual training)
                # For demo, return a score based on reasonable parameter combinations
                score = 0.85  # Base score
                
                if lora_r == 8 and lora_alpha == 16:
                    score += 0.05
                if 1e-5 <= learning_rate <= 5e-5:
                    score += 0.03
                if batch_size == 16:
                    score += 0.02
                
                return score
            
            # Run optimization
            study = optuna.create_study(direction='maximize')
            study.optimize(objective, n_trials=trials)
            
            best_params = study.best_params
            best_params["best_f1"] = study.best_value
            
            return best_params
            
        except Exception as e:
            logger.error(f"Hyperparameter optimization failed: {e}")
            return {"error": str(e)}
    
    async def _handle_model_deployment(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle model deployment
        """
        try:
            training_id = message.content.get("training_id")
            deployment_target = message.content.get("deployment_target", "staging")
            
            if not training_id or training_id not in self.active_trainings:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Training ID not found"
                    },
                    timestamp=datetime.now()
                )
                return
            
            training_task = self.active_trainings[training_id]
            
            if training_task["status"] != "completed":
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Model not ready for deployment"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Deploy model
            deployment_result = await self._deploy_model(training_task, deployment_target)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "model_deployed",
                    "training_id": training_id,
                    "deployment_target": deployment_target,
                    "deployment_result": deployment_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Model deployment failed: {e}")
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
    
    async def _deploy_model(
        self,
        training_task: Dict[str, Any],
        deployment_target: str
    ) -> Dict[str, Any]:
        """
        Deploy model to target environment
        """
        try:
            model_path = training_task["model_path"]
            
            # Mock deployment process
            deployment_result = {
                "deployment_id": str(uuid.uuid4()),
                "target": deployment_target,
                "model_path": model_path,
                "deployed_at": datetime.now().isoformat(),
                "status": "success"
            }
            
            # In real implementation, this would:
            # 1. Package model for deployment
            # 2. Update model registry
            # 3. Deploy to serving infrastructure
            # 4. Update routing configuration
            
            return deployment_result
            
        except Exception as e:
            logger.error(f"Model deployment failed: {e}")
            return {"error": str(e)}
    
    async def _handle_training_history_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle training history analysis
        """
        try:
            analysis_period_days = message.content.get("analysis_period_days", 30)
            
            # Analyze training history
            analysis = await self._analyze_training_history(analysis_period_days)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "training_history_analysis",
                    "analysis_period_days": analysis_period_days,
                    "analysis": analysis
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Training history analysis failed: {e}")
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
    
    async def _analyze_training_history(self, period_days: int) -> Dict[str, Any]:
        """
        Analyze training history
        """
        try:
            # Query training history from database
            async with get_db_session() as session:
                # Mock analysis for demonstration
                analysis = {
                    "total_trainings": 25,
                    "successful_trainings": 18,
                    "avg_f1_score": 0.87,
                    "best_f1_score": 0.96,
                    "threshold_met_rate": 0.72,
                    "common_failure_reasons": [
                        "Insufficient data quality",
                        "Overfitting detected",
                        "Hardware resource constraints"
                    ],
                    "performance_trends": {
                        "f1_improvement": 0.05,
                        "training_time_reduction": 0.15
                    },
                    "model_type_distribution": {
                        "classification": 15,
                        "sentiment": 8,
                        "ner": 2
                    }
                }
                
                return analysis
                
        except Exception as e:
            logger.error(f"Training history analysis failed: {e}")
            return {"error": str(e)}


class TextClassificationDataset(Dataset):
    """
    Dataset for text classification tasks
    """
    
    def __init__(self, texts: List[str], labels: List[int], tokenizer=None, max_length=512):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        
        if self.tokenizer:
            encoding = self.tokenizer(
                text,
                truncation=True,
                padding='max_length',
                max_length=self.max_length,
                return_tensors='pt'
            )
            
            return {
                'input_ids': encoding['input_ids'].flatten(),
                'attention_mask': encoding['attention_mask'].flatten(),
                'labels': torch.tensor(label, dtype=torch.long)
            }
        else:
            return {
                'text': text,
                'labels': label
            }


# ========== TEST ==========
if __name__ == "__main__":
    async def test_lora_trainer_agent():
        # Initialize LoRA trainer agent
        agent = LoRATrainerAgent()
        
        # Test training status check (no active training)
        test_message = AgentMessage(
            id="test_status",
            from_agent="test",
            to_agent="lora_trainer_agent",
            content={
                "type": "check_training_status",
                "training_id": "nonexistent_id"
            },
            timestamp=datetime.now()
        )
        
        print("Testing LoRA trainer agent...")
        async for response in agent.process_message(test_message):
            print(f"Response type: {response.content.get('type')}")
            if response.content.get("type") == "error":
                print("Expected error for nonexistent training ID")
        
        # Test hyperparameter optimization
        opt_message = AgentMessage(
            id="test_opt",
            from_agent="test",
            to_agent="lora_trainer_agent",
            content={
                "type": "optimize_hyperparameters",
                "base_config": {"task_type": "classification"},
                "trials": 5
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(opt_message):
            print(f"Optimization response: {response.content.get('type')}")
            if response.content.get("type") == "hyperparameter_optimization_complete":
                print(f"Best params: {response.content.get('best_parameters')}")
        
        print("LoRA trainer agent test completed")
    
    # Run test
    asyncio.run(test_lora_trainer_agent())
