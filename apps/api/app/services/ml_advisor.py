import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def get_ml_recommendations(profile: dict, features_info: dict) -> dict:
    """
    Formulate deterministic machine learning recommendations (algorithms, metrics, validation,
    scaling, encoding, feature selection) based on target attributes and data characteristics.
    """
    target_col = features_info.get("target_column")
    
    # Normalize columns stats into a list of dicts (supports both list and dict formats)
    cols_stats = profile.get("columns", {})
    columns_list = []
    if isinstance(cols_stats, dict):
        for col_name, info in cols_stats.items():
            if isinstance(info, dict):
                col_info = dict(info)
                col_info["column"] = col_name
                columns_list.append(col_info)
    elif isinstance(cols_stats, list):
        columns_list = cols_stats

    has_categorical = any(col.get("type") == "categorical" for col in columns_list if isinstance(col, dict))
    has_datetime = any(col.get("type") == "datetime" for col in columns_list if isinstance(col, dict))
    
    # 1. Determine problem type
    if not target_col:
        task = "Unsupervised (Clustering/Dim Reduction)"
        target_name = "None"
        problem_type = "Clustering"
        suggested_models = [
            {
                "model": "K-Means",
                "explanation": "Standard centroid-based clustering algorithm to group similar observations."
            },
            {
                "model": "DBSCAN",
                "explanation": "Density-based clustering that handles irregular cluster shapes and detects noise outliers."
            },
            {
                "model": "PCA (Principal Component Analysis)",
                "explanation": "Dimensionality reduction technique for visualization and simplifying input spaces."
            }
        ]
        metrics = ["Silhouette Coefficient", "Davies-Bouldin Index"]
        validation = "Silhouette analysis and elbow method elbow plotting"
    else:
        target_name = target_col
        # Check target stats
        is_categorical = features_info.get("target_imbalance") != "Continuous Target"
        
        if is_categorical:
            task = "Supervised (Classification)"
            problem_type = "Classification"
            suggested_models = [
                {
                    "model": "XGBoost Classifier",
                    "explanation": "State-of-the-art gradient boosted trees for high performance classification."
                },
                {
                    "model": "Random Forest Classifier",
                    "explanation": "Robust bagging ensemble that limits overfitting and handles non-linear relationships."
                },
                {
                    "model": "Logistic Regression",
                    "explanation": "Highly interpretable linear baseline model for linear feature spaces."
                }
            ]
            metrics = ["F1-Score", "ROC-AUC", "Precision", "Recall", "Accuracy"]
            validation = "Stratified 5-Fold Cross-Validation"
        else:
            task = "Supervised (Regression)"
            problem_type = "Regression"
            suggested_models = [
                {
                    "model": "XGBoost Regressor",
                    "explanation": "High-performance gradient boosted decision trees for continuous target regression."
                },
                {
                    "model": "Random Forest Regressor",
                    "explanation": "Ensemble regressor combining multiple decision trees to reduce variance."
                },
                {
                    "model": "Ridge Regression / ElasticNet",
                    "explanation": "Regularized linear regression models that handle multicollinearity."
                }
            ]
            metrics = ["Root Mean Squared Error (RMSE)", "Mean Absolute Error (MAE)", "R-squared (R2)"]
            
            if has_datetime:
                validation = "TimeSeriesSplit (Rolling window walk-forward validation)"
            else:
                validation = "Standard 5-Fold Cross-Validation"

    # 2. Preprocessing & Engineering pipeline advice
    preprocessing = []
    
    # Encoding recommendations
    if has_categorical:
        high_card = features_info.get("high_cardinality_columns", [])
        if high_card:
            preprocessing.append(f"Use Target Encoding, Binary Encoding, or Hash Encoding for high cardinality fields: {', '.join(high_card)}")
        
        low_card = [col.get("column", "") for col in columns_list if col.get("type") == "categorical" and col.get("column") not in high_card]
        if low_card:
            preprocessing.append(f"Use One-Hot Encoding for low cardinality features: {', '.join(low_card[:5])}...")
            
    # Scaling recommendations
    numeric_names = [col.get("column", "") for col in columns_list if col.get("type") == "numeric"]
    if numeric_names:
        preprocessing.append(f"Use StandardScaler (or RobustScaler if outliers are present) on numerical columns: {', '.join(numeric_names[:5])}...")
        
    # Feature Selection recommendations
    selection = []
    const_cols = features_info.get("constant_columns", [])
    if const_cols:
        selection.append(f"Drop constant columns: {', '.join(const_cols)}")
        
    ident_cols = features_info.get("identifiers", [])
    if ident_cols:
        selection.append(f"Drop non-predictive identifier columns: {', '.join(ident_cols)}")
        
    correlated_cols = features_info.get("multicollinear_features", [])
    if correlated_cols:
        selection.append(f"Drop one feature from highly correlated pairs to handle multicollinearity: {', '.join(correlated_cols[:4])}...")

    return {
        "task": task,
        "problem_type": problem_type,
        "target_column": target_name,
        "suggested_algorithms": suggested_models,
        "suggested_metrics": metrics,
        "suggested_validation": validation,
        "preprocessing_recommendations": preprocessing,
        "feature_selection_recommendations": selection
    }
