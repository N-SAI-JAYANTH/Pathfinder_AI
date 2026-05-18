from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split


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
    cm_path = Path("models/model1_skill_importance/confusion_matrix.csv")
    fi_path = Path("models/model1_skill_importance/feature_importance.csv")

    df = pd.read_csv(input_path)
    if "competency_type_code" in df.columns:
        df["competency_type_code"] = pd.to_numeric(
            df["competency_type_code"], errors="coerce"
        ).fillna(7)
    df = df.dropna(subset=FEATURES + [TARGET]).copy()
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
    print("\nClassification report:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))
    print("\nFeature importance:")
    print(fi_df.to_string(index=False))
    print(f"\nSaved confusion matrix: {cm_path}")
    print(f"Saved feature importance: {fi_path}")


if __name__ == "__main__":
    main()
