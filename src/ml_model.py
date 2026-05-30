"""
ml_model.py
~~~~~~~~~~~
Ensemble ML prediction layer.

Models:
  1. XGBoost classifier   – next-candle direction (binary: 1=up, 0=down)
  2. LightGBM regressor   – 4h forward price target
  3. LSTM (Keras)         – 60-candle sequence → direction probability
  4. Random Forest        – feature importance ranking / signal weighting
  5. Meta-learner         – logistic regression on model outputs → final probability

Training:
  - Walk-forward validation (no lookahead bias)
  - Weekly retraining trigger
  - SHAP explainability on XGB + RF

Signal: only emit when ensemble confidence > settings.ml_confidence_threshold
"""

from __future__ import annotations

import os
import pickle
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import shap
import structlog
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

import lightgbm as lgb
import xgboost as xgb

from config import settings
from indicators import compute_all_indicators, get_feature_columns

logger = structlog.get_logger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

SEQUENCE_LENGTH = 60  # candles for LSTM
N_SPLITS = 5          # walk-forward folds
PREDICTION_HORIZON = 4  # candles ahead for regression target


# ─── Feature engineering ──────────────────────────────────────────────────────


def build_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Returns X (features), y_cls (direction label), y_reg (future price).
    Applies strict temporal caution: targets are forward-shifted, no future data leaks.
    """
    df = df.copy()

    # Binary classification target: 1 if close n-periods ahead > current close
    df["y_cls"] = (df["close"].shift(-PREDICTION_HORIZON) > df["close"]).astype(int)
    # Regression target: forward close price
    df["y_reg"] = df["close"].shift(-PREDICTION_HORIZON)

    # Drop the last PREDICTION_HORIZON rows (no target yet)
    df = df.iloc[:-PREDICTION_HORIZON]

    feature_cols = get_feature_columns(df)
    X = df[feature_cols].copy()

    # Replace ±inf and drop all-NaN columns
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.dropna(axis=1, how="all")
    X = X.fillna(method="ffill").fillna(0)

    y_cls = df["y_cls"].loc[X.index]
    y_reg = df["y_reg"].loc[X.index]

    return X, y_cls, y_reg


def make_sequences(X: np.ndarray, y: np.ndarray, seq_len: int = SEQUENCE_LENGTH):
    """Build overlapping sequences for LSTM."""
    Xs, ys = [], []
    for i in range(seq_len, len(X)):
        Xs.append(X[i - seq_len : i])
        ys.append(y[i])
    return np.array(Xs), np.array(ys)


# ─── Model definitions ────────────────────────────────────────────────────────


def build_xgb(n_features: int) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )


def build_lgbm(n_features: int) -> lgb.LGBMRegressor:
    return lgb.LGBMRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )


def build_rf(n_features: int) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        min_samples_split=10,
        random_state=42,
        n_jobs=-1,
    )


def build_lstm(seq_len: int, n_features: int):
    """Build Keras LSTM; import lazily to avoid slow startup."""
    try:
        import tensorflow as tf
        from tensorflow import keras

        tf.get_logger().setLevel("ERROR")
        model = keras.Sequential(
            [
                keras.layers.LSTM(128, input_shape=(seq_len, n_features), return_sequences=True),
                keras.layers.Dropout(0.2),
                keras.layers.LSTM(64, return_sequences=False),
                keras.layers.Dropout(0.2),
                keras.layers.Dense(32, activation="relu"),
                keras.layers.Dense(1, activation="sigmoid"),
            ]
        )
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=1e-3),
            loss="binary_crossentropy",
            metrics=["accuracy"],
        )
        return model
    except ImportError:
        logger.warning("tensorflow_not_available")
        return None


# ─── Walk-forward trainer ─────────────────────────────────────────────────────


class WalkForwardTrainer:
    """
    Trains all models using time-series cross-validation.
    No data from the future is ever used to train on past data.
    """

    def __init__(self, n_splits: int = N_SPLITS) -> None:
        self.n_splits = n_splits
        self.scaler = StandardScaler()

    def train(
        self, X: pd.DataFrame, y_cls: pd.Series, y_reg: pd.Series
    ) -> Dict[str, Any]:
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        xgb_preds, rf_preds, lgbm_preds, lstm_preds = [], [], [], []
        y_true_all: List[int] = []

        X_arr = X.values
        y_cls_arr = y_cls.values
        y_reg_arr = y_reg.values

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X_arr)):
            logger.info("training_fold", fold=fold + 1, n_train=len(train_idx))
            X_tr, X_val = X_arr[train_idx], X_arr[val_idx]
            y_tr, y_val = y_cls_arr[train_idx], y_cls_arr[val_idx]
            y_reg_tr = y_reg_arr[train_idx]

            scaler = StandardScaler()
            X_tr_sc = scaler.fit_transform(X_tr)
            X_val_sc = scaler.transform(X_val)

            # XGBoost
            xgb_model = build_xgb(X_tr.shape[1])
            xgb_model.fit(X_tr_sc, y_tr, eval_set=[(X_val_sc, y_val)], verbose=False)
            xgb_proba = xgb_model.predict_proba(X_val_sc)[:, 1]
            xgb_preds.extend(xgb_proba)

            # LightGBM (regression)
            lgbm_model = build_lgbm(X_tr.shape[1])
            lgbm_model.fit(X_tr_sc, y_reg_tr)
            # Convert price prediction to direction probability
            lgbm_pred_price = lgbm_model.predict(X_val_sc)
            lgbm_dir_prob = (lgbm_pred_price > X_val[:, 0]).astype(float)
            lgbm_preds.extend(lgbm_dir_prob)

            # Random Forest
            rf_model = build_rf(X_tr.shape[1])
            rf_model.fit(X_tr_sc, y_tr)
            rf_proba = rf_model.predict_proba(X_val_sc)[:, 1]
            rf_preds.extend(rf_proba)

            # LSTM
            lstm_model = build_lstm(SEQUENCE_LENGTH, X_tr_sc.shape[1])
            if lstm_model is not None and len(X_tr_sc) > SEQUENCE_LENGTH:
                X_seq_tr, y_seq_tr = make_sequences(X_tr_sc, y_tr)
                X_seq_val, _ = make_sequences(X_val_sc, y_val)
                if len(X_seq_tr) > 0 and len(X_seq_val) > 0:
                    lstm_model.fit(
                        X_seq_tr, y_seq_tr,
                        epochs=10, batch_size=32, verbose=0,
                        validation_split=0.1,
                    )
                    lstm_proba = lstm_model.predict(X_seq_val, verbose=0).flatten()
                    # Pad front with 0.5 for alignment
                    pad = len(y_val) - len(lstm_proba)
                    lstm_preds.extend([0.5] * pad + list(lstm_proba))
                else:
                    lstm_preds.extend([0.5] * len(y_val))
            else:
                lstm_preds.extend([0.5] * len(y_val))

            y_true_all.extend(y_val)

        # Final training on full dataset
        X_sc = self.scaler.fit_transform(X_arr)
        final_xgb = build_xgb(X_arr.shape[1])
        final_xgb.fit(X_sc, y_cls_arr, verbose=False)

        final_lgbm = build_lgbm(X_arr.shape[1])
        final_lgbm.fit(X_sc, y_reg_arr)

        final_rf = build_rf(X_arr.shape[1])
        final_rf.fit(X_sc, y_cls_arr)

        final_lstm = build_lstm(SEQUENCE_LENGTH, X_sc.shape[1])
        if final_lstm is not None and len(X_sc) > SEQUENCE_LENGTH:
            X_seq_all, y_seq_all = make_sequences(X_sc, y_cls_arr)
            if len(X_seq_all) > 0:
                final_lstm.fit(X_seq_all, y_seq_all, epochs=15, batch_size=32, verbose=0)

        # Meta-learner: train on OOF predictions
        min_len = min(len(xgb_preds), len(lgbm_preds), len(rf_preds), len(lstm_preds))
        meta_X = np.column_stack([
            xgb_preds[:min_len],
            lgbm_preds[:min_len],
            rf_preds[:min_len],
            lstm_preds[:min_len],
        ])
        meta_y = np.array(y_true_all[:min_len])
        meta_model = LogisticRegression(max_iter=500, random_state=42)
        meta_model.fit(meta_X, meta_y)

        auc = roc_auc_score(meta_y, meta_model.predict_proba(meta_X)[:, 1])
        logger.info("training_complete", oof_auc=round(auc, 4))

        return {
            "xgb": final_xgb,
            "lgbm": final_lgbm,
            "rf": final_rf,
            "lstm": final_lstm,
            "meta": meta_model,
            "scaler": self.scaler,
            "feature_cols": list(X.columns),
            "oof_auc": auc,
            "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        }


# ─── Model bundle ─────────────────────────────────────────────────────────────


class EnsemblePredictor:
    """
    Loads or trains the ensemble, provides predict() method.
    Handles SHAP explainability and feature importance.
    """

    BUNDLE_PATH = MODELS_DIR / "ensemble.pkl"
    LSTM_PATH = MODELS_DIR / "lstm.keras"

    def __init__(self) -> None:
        self._bundle: Optional[Dict[str, Any]] = None

    def is_trained(self) -> bool:
        return self.BUNDLE_PATH.exists()

    def load(self) -> None:
        if not self.BUNDLE_PATH.exists():
            raise FileNotFoundError("No trained model found. Run train() first.")
        self._bundle = joblib.load(self.BUNDLE_PATH)
        if self._bundle.get("lstm") is None and self.LSTM_PATH.exists():
            try:
                import tensorflow as tf
                self._bundle["lstm"] = tf.keras.models.load_model(str(self.LSTM_PATH))
            except Exception:
                pass
        logger.info("ensemble_loaded", trained_at=self._bundle.get("trained_at"))

    def save(self, bundle: Dict[str, Any]) -> None:
        lstm = bundle.pop("lstm", None)
        joblib.dump(bundle, self.BUNDLE_PATH)
        if lstm is not None:
            try:
                lstm.save(str(self.LSTM_PATH))
                bundle["lstm"] = lstm
            except Exception:
                pass
        self._bundle = bundle
        logger.info("ensemble_saved")

    def train(self, df: pd.DataFrame) -> Dict[str, Any]:
        logger.info("building_features")
        df_ind = compute_all_indicators(df)
        X, y_cls, y_reg = build_features(df_ind)
        logger.info("starting_walk_forward_training", samples=len(X))
        trainer = WalkForwardTrainer()
        bundle = trainer.train(X, y_cls, y_reg)
        self.save(bundle)
        return bundle

    def predict(
        self, df: pd.DataFrame, extra_features: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Predict on the latest candle.
        extra_features: cross-asset / sentiment values injected as extra columns.
        Returns dict with confidence, direction, price_target, shap_values.
        """
        if self._bundle is None:
            self.load()
        bundle = self._bundle
        scaler: StandardScaler = bundle["scaler"]
        feature_cols: List[str] = bundle["feature_cols"]

        df_ind = compute_all_indicators(df.copy())
        # Inject any extra numeric features
        if extra_features:
            for k, v in extra_features.items():
                df_ind[k] = v

        # Align feature columns
        missing = [c for c in feature_cols if c not in df_ind.columns]
        for c in missing:
            df_ind[c] = 0.0
        X_latest = df_ind[feature_cols].tail(1).copy()
        X_latest = X_latest.replace([np.inf, -np.inf], np.nan).fillna(0)
        X_sc = scaler.transform(X_latest.values)

        # Individual model predictions
        xgb_prob = float(bundle["xgb"].predict_proba(X_sc)[0, 1])
        rf_prob = float(bundle["rf"].predict_proba(X_sc)[0, 1])

        lgbm_price = float(bundle["lgbm"].predict(X_sc)[0])
        current_price = float(df["close"].iloc[-1])
        lgbm_prob = float(np.clip((lgbm_price - current_price) / current_price * 10 + 0.5, 0, 1))

        lstm_prob = 0.5
        lstm = bundle.get("lstm")
        if lstm is not None:
            X_hist = df_ind[feature_cols].tail(SEQUENCE_LENGTH + 1).copy()
            X_hist = X_hist.replace([np.inf, -np.inf], np.nan).fillna(0)
            if len(X_hist) >= SEQUENCE_LENGTH:
                X_seq = scaler.transform(X_hist.values)[-SEQUENCE_LENGTH:]
                try:
                    lstm_prob = float(lstm.predict(X_seq[np.newaxis], verbose=0)[0, 0])
                except Exception:
                    pass

        # Meta ensemble
        meta_input = np.array([[xgb_prob, lgbm_prob, rf_prob, lstm_prob]])
        meta_prob = float(bundle["meta"].predict_proba(meta_input)[0, 1])

        direction = "long" if meta_prob > 0.5 else "short"
        confident = meta_prob >= settings.ml_confidence_threshold or meta_prob <= (1 - settings.ml_confidence_threshold)

        # SHAP (XGBoost-based)
        shap_values: Dict[str, float] = {}
        try:
            explainer = shap.TreeExplainer(bundle["xgb"])
            sv = explainer.shap_values(X_sc)
            shap_values = dict(
                sorted(
                    zip(feature_cols, sv[0]),
                    key=lambda x: abs(x[1]),
                    reverse=True,
                )[:20]
            )
        except Exception:
            pass

        return {
            "confidence": meta_prob,
            "direction": direction,
            "confident": confident,
            "price_target": lgbm_price,
            "current_price": current_price,
            "models": {
                "xgb": xgb_prob,
                "lgbm": lgbm_prob,
                "rf": rf_prob,
                "lstm": lstm_prob,
                "meta": meta_prob,
            },
            "shap_top": shap_values,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        }

    def feature_importance(self) -> pd.DataFrame:
        if self._bundle is None:
            self.load()
        rf: RandomForestClassifier = self._bundle["rf"]
        xgb_model: xgb.XGBClassifier = self._bundle["xgb"]
        cols = self._bundle["feature_cols"]
        rf_imp = rf.feature_importances_
        xgb_imp = xgb_model.feature_importances_
        df = pd.DataFrame({
            "feature": cols,
            "rf_importance": rf_imp,
            "xgb_importance": xgb_imp,
            "avg_importance": (rf_imp + xgb_imp) / 2,
        }).sort_values("avg_importance", ascending=False)
        return df


# ─── Optuna hyperparameter search ────────────────────────────────────────────


def optimize_xgb_params(X: pd.DataFrame, y: pd.Series, n_trials: int = 50) -> Dict:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 800),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "min_child_weight": trial.suggest_int("min_child_weight", 1, 20),
            "eval_metric": "logloss",
            "use_label_encoder": False,
            "random_state": 42,
        }
        tscv = TimeSeriesSplit(n_splits=3)
        scores = []
        X_arr, y_arr = X.values, y.values
        sc = StandardScaler()
        for tr_idx, val_idx in tscv.split(X_arr):
            X_tr = sc.fit_transform(X_arr[tr_idx])
            X_val = sc.transform(X_arr[val_idx])
            model = xgb.XGBClassifier(**params)
            model.fit(X_tr, y_arr[tr_idx], verbose=False)
            prob = model.predict_proba(X_val)[:, 1]
            scores.append(roc_auc_score(y_arr[val_idx], prob))
        return np.mean(scores)

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    logger.info("optuna_best", value=study.best_value, params=study.best_params)
    return study.best_params
