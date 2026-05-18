from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


FEATURES = [
    "context_score",
    "section_score",
    "title_similarity",
    "semantic_similarity",
    "frequency_score",
    "competency_type_code",
]
TARGET = "importance_label"


def main() -> None:
    input_path = Path("datasets/skill_importance_labeled.csv")
    model_path = Path("models/model1_skill_importance/model1.pkl")
    encoder_path = Path("models/model1_skill_importance/label_encoder.pkl")
    metrics_path = Path("models/model1_skill_importance/metrics.txt")

    df = pd.read_csv(input_path)
    for col in FEATURES:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    if "competency_type_code" in df.columns:
        df["competency_type_code"] = pd.to_numeric(
            df["competency_type_code"], errors="coerce"
        ).fillna(7)
    df = df.dropna(subset=FEATURES + [TARGET]).copy()

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
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=42,
        tree_method="hist",
        eval_metric="mlogloss",
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    fi_df = (
        pd.DataFrame({"feature": FEATURES, "importance": model.feature_importances_})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

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
    print("\nFeature importance:")
    print(fi_df.to_string(index=False))


if __name__ == "__main__":
    main()
