from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split


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
    cm_path = Path("models/model2_job_fit/confusion_matrix.csv")
    fi_path = Path("models/model2_job_fit/feature_importance.csv")

    df = pd.read_csv(input_path).dropna(subset=FEATURES + [TARGET]).copy()
    X = df[FEATURES]
    y_text = df[TARGET].astype(str)

    le = joblib.load(encoder_path)
    y = le.transform(y_text)

    _, X_temp, _, y_temp = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    _, X_test, _, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )

    model = joblib.load(model_path)
    y_pred = model.predict(X_test)

    cm = confusion_matrix(y_test, y_pred)
    cm_df = pd.DataFrame(cm, index=le.classes_, columns=le.classes_)
    cm_df.to_csv(cm_path, index=True)

    fi_df = pd.DataFrame(
        {"feature": FEATURES, "importance": model.feature_importances_}
    ).sort_values("importance", ascending=False)
    fi_df.to_csv(fi_path, index=False)

    print("Confusion matrix:")
    print(cm_df.to_string())
    p_macro, r_macro, f1_macro, _ = precision_recall_fscore_support(
        y_test, y_pred, average="macro", zero_division=0
    )
    print(f"\nMacro precision: {p_macro:.4f}")
    print(f"Macro recall: {r_macro:.4f}")
    print(f"Macro F1: {f1_macro:.4f}")
    print("\nPer-class performance:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))
    print("\nTop important features:")
    print(fi_df.head(10).to_string(index=False))
    print(f"\nSaved confusion matrix: {cm_path}")
    print(f"Saved feature importance: {fi_path}")


if __name__ == "__main__":
    main()
