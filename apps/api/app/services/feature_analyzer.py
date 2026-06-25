import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def analyze_dataset_features(df: pd.DataFrame, profile: dict) -> dict:
    """
    Diagnose columns for quality issues like constant variance, collinearity,
    leakage, redundancy, target imbalance, and feature importance.
    """
    num_rows = len(df)
    if num_rows == 0:
        return {}

    # 1. Target column detection
    target_col = None
    for col in df.columns:
        col_lower = col.lower()
        if any(k in col_lower for k in ("target", "label", "class", "outcome", "purchased", "clicked")) or col_lower == "y":
            target_col = col
            break

    # 2. Constant & Near-Zero Variance
    constant_columns = []
    near_zero_variance = []
    
    # 3. Identifier detection
    identifiers = []

    for col in df.columns:
        col_lower = col.lower()
        nunique = df[col].nunique(dropna=True)
        
        # Constant columns
        if nunique <= 1:
            constant_columns.append(col)
            continue
            
        # Identifier detection
        if any(k in col_lower for k in ("id", "key", "index", "pk", "fk")) or (nunique == num_rows and df[col].dtype == object):
            identifiers.append(col)
            
        # Near zero variance
        if df[col].dtype in [np.number]:
            std = df[col].std()
            if pd.isna(std) or std < 0.01:
                near_zero_variance.append(col)
        else:
            # Categorical zero variance: top class makes up > 98%
            top_pct = df[col].value_counts(normalize=True).iloc[0]
            if top_pct > 0.98:
                near_zero_variance.append(col)

    # 4. High Cardinality Categorical
    high_cardinality = []
    categorical_cols = df.select_dtypes(include=[object, "category"]).columns
    for col in categorical_cols:
        nunique = df[col].nunique()
        if nunique > 30 or (num_rows > 0 and nunique / num_rows > 0.20):
            high_cardinality.append(col)

    # 5. Collinearity (Pearson Correlation > 0.8)
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    high_correlations = []
    multicollinear_features = set()
    
    if len(numeric_cols) > 1:
        corr_matrix = df[numeric_cols].corr().abs()
        for i in range(len(numeric_cols)):
            for j in range(i + 1, len(numeric_cols)):
                col1 = numeric_cols[i]
                col2 = numeric_cols[j]
                val = corr_matrix.loc[col1, col2]
                if not pd.isna(val) and val > 0.80:
                    high_correlations.append({
                        "feature_a": col1,
                        "feature_b": col2,
                        "correlation": round(float(val), 3)
                    })
                    # Add feature to multicollinear features set
                    multicollinear_features.add(col1)
                    multicollinear_features.add(col2)

    # 6. Target Leakage & Class Imbalance
    leakage_columns = []
    imbalance_status = "No target detected"
    
    if target_col:
        # Check target imbalance
        target_series = df[target_col].dropna()
        target_nunique = target_series.nunique()
        is_categorical_target = df[target_col].dtype in [object, bool] or target_nunique <= 10
        
        if is_categorical_target and target_nunique > 1:
            vc = target_series.value_counts()
            ratio = vc.iloc[0] / max(1, vc.iloc[-1])
            if ratio > 3.0:
                imbalance_status = f"Severe Imbalance ({ratio:.1f}:1)"
            elif ratio > 1.5:
                imbalance_status = f"Moderate Imbalance ({ratio:.1f}:1)"
            else:
                imbalance_status = "Balanced"
        elif not is_categorical_target:
            imbalance_status = "Continuous Target"
            
        # Target leakage detection (correlation > 0.95)
        for col in numeric_cols:
            if col != target_col:
                corr_val = df[[col, target_col]].corr().abs().iloc[0, 1]
                if not pd.isna(corr_val) and corr_val > 0.95:
                    leakage_columns.append(col)
    
    # 7. Compute Feature Importance (if target exists)
    feature_importances = []
    if target_col and target_col not in constant_columns:
        feature_importances = compute_feature_importance(df, target_col)

    return {
        "target_column": target_col,
        "constant_columns": constant_columns,
        "near_zero_variance_columns": near_zero_variance,
        "high_cardinality_columns": high_cardinality,
        "identifiers": identifiers,
        "high_correlations": high_correlations,
        "multicollinear_features": list(multicollinear_features),
        "leakage_columns": leakage_columns,
        "target_imbalance": imbalance_status,
        "feature_importances": feature_importances
    }

def compute_feature_importance(df: pd.DataFrame, target_col: str) -> list[dict]:
    """
    Run a lightweight Decision Tree classifier or regressor to calculate feature importances.
    """
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
    
    try:
        X = df.drop(columns=[target_col]).copy()
        y = df[target_col].copy()
        
        # Simple factorize of categories
        for col in X.columns:
            if X[col].dtype == object or isinstance(X[col].dtype, pd.CategoricalDtype) or X[col].dtype == bool:
                X[col] = X[col].astype(str).factorize()[0]
            # Impute
            X[col] = X[col].fillna(X[col].median() if X[col].dtype in [np.number] else -1)
            
        unique_y = y.nunique()
        is_classification = y.dtype == object or y.dtype == bool or unique_y <= 10
        
        if is_classification:
            y = y.astype(str).factorize()[0]
            model = DecisionTreeClassifier(max_depth=4, random_state=42)
        else:
            y = y.fillna(y.median())
            model = DecisionTreeRegressor(max_depth=4, random_state=42)
            
        model.fit(X, y)
        importances = model.feature_importances_
        results = []
        for name, imp in zip(X.columns, importances):
            if imp > 0.01:
                results.append({"feature": name, "importance": round(float(imp), 3)})
        return sorted(results, key=lambda x: x["importance"], reverse=True)
    except Exception as e:
        logger.warning(f"Feature importance computation failed: {e}")
        return []
