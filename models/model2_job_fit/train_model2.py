from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


FEATURES = [
    "matched_core_sum",
    "matched_important_sum",
    "matched_supporting_sum",
    "missing_core_sum",
    "missing_important_sum",
    "missing_supporting_sum",
    "weighted_match_total",
    "weighted_missing_total",
    "match_ratio",
    "experience_gap",
    "experience_score",
    "project_score",
    "cert_score",
    "education_score",
    "profile_job_similarity",
]
TARGET = "fit_label"


def main() -> None:
    input_path = Path("datasets/user_job_fit_balanced.csv")
    model_path = Path("models/model2_job_fit/model2.pkl")
    encoder_path = Path("models/model2_job_fit/label_encoder.pkl")
    metrics_path = Path("models/model2_job_fit/metrics.txt")

    df = pd.read_csv(input_path).dropna(subset=FEATURES + [TARGET]).copy()
    X = df[FEATURES]
    y_text = df[TARGET].astype(str)

    le = LabelEncoder()
    y = le.fit_transform(y_text)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )

    model = XGBClassifier(
        objective="multi:softprob",
        num_class=len(le.classes_),
        n_estimators=350,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=42,
        tree_method="hist",
        eval_metric="mlogloss",
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    p, r, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="macro")
    report = classification_report(y_test, y_pred, target_names=le.classes_)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    joblib.dump(le, encoder_path)

    metrics_text = (
        f"accuracy: {acc:.4f}\n"
        f"macro_precision: {p:.4f}\n"
        f"macro_recall: {r:.4f}\n"
        f"macro_f1: {f1:.4f}\n\n"
        f"{report}\n"
    )
    metrics_path.write_text(metrics_text, encoding="utf-8")

    print(f"Saved model: {model_path}")
    print(f"Saved label encoder: {encoder_path}")
    print(f"Saved metrics: {metrics_path}")
    print(f"accuracy: {acc:.4f}")
    print(f"macro_precision: {p:.4f}")
    print(f"macro_recall: {r:.4f}")
    print(f"macro_f1: {f1:.4f}")
    print("\nClassification report:")
    print(report)


if __name__ == "__main__":
    main()
