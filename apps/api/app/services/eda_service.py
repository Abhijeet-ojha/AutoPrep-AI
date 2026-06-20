"""Enhanced EDA visualization service with complete chart suite."""

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


class EDAService:
    """Service for generating comprehensive EDA visualizations."""
    
    def generate_all_charts(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Generate all available EDA charts.
        
        Args:
            df: DataFrame to analyze
        
        Returns:
            Dictionary of chart configurations for Plotly
        """
        charts = {}
        
        # Identify column types
        numeric_cols = self._get_numeric_columns(df)
        categorical_cols = self._get_categorical_columns(df)
        
        # 1. Missing values chart
        charts["missing_values"] = self._missing_values_chart(df)
        
        # 2. Correlation heatmap (numeric only)
        if len(numeric_cols) >= 2:
            charts["correlation_heatmap"] = self._correlation_heatmap(df, numeric_cols)
        
        # 3. Histograms for numeric columns
        charts["histograms"] = [
            self._histogram(df, col) for col in numeric_cols[:10]  # Limit to first 10
        ]
        
        # 4. Box plots for numeric columns
        charts["box_plots"] = [
            self._box_plot(df, col) for col in numeric_cols[:10]
        ]
        
        # 5. Distribution plots
        charts["distribution_plots"] = [
            self._distribution_plot(df, col) for col in numeric_cols[:5]
        ]
        
        # 6. Bar charts for categorical columns
        charts["bar_charts"] = [
            self._bar_chart(df, col) for col in categorical_cols[:10]
        ]
        
        # 7. Pie charts for low-cardinality categorical
        low_card_cats = [c for c in categorical_cols if df[c].nunique() <= 8]
        charts["pie_charts"] = [
            self._pie_chart(df, col) for col in low_card_cats[:5]
        ]
        
        # 8. Scatter plots (first numeric vs others)
        if len(numeric_cols) >= 2:
            base_col = numeric_cols[0]
            charts["scatter_plots"] = [
                self._scatter_plot(df, base_col, col)
                for col in numeric_cols[1:6]  # Up to 5 scatter plots
            ]
        
        # 9. Violin plots
        charts["violin_plots"] = [
            self._violin_plot(df, col) for col in numeric_cols[:5]
        ]
        
        # 10. Outlier plot
        if numeric_cols:
            charts["outlier_plot"] = self._outlier_plot(df, numeric_cols[:10])
        
        # 11. Class balance (if target detected)
        target_col = self._detect_target_column(df)
        if target_col:
            charts["class_balance"] = self._class_balance_chart(df, target_col)
        
        return charts

    
    def _get_numeric_columns(self, df: pd.DataFrame) -> list[str]:
        """Get list of numeric columns."""
        return [
            col for col in df.columns
            if pd.to_numeric(df[col], errors='coerce').notna().sum() > 0
        ]
    
    def _get_categorical_columns(self, df: pd.DataFrame) -> list[str]:
        """Get list of categorical columns."""
        return [
            col for col in df.columns
            if df[col].dtype == 'object' and df[col].nunique() <= 50
        ]
    
    def _detect_target_column(self, df: pd.DataFrame) -> str | None:
        """Detect potential target column."""
        for col in df.columns:
            name_lower = col.lower()
            if any(k in name_lower for k in ['target', 'label', 'class', 'outcome', 'y']):
                return col
        return None
    
    def _missing_values_chart(self, df: pd.DataFrame) -> dict[str, Any]:
        """Generate missing values bar chart."""
        missing = df.isnull().sum()
        missing = missing[missing > 0].sort_values(ascending=False)
        
        return {
            "type": "bar",
            "data": {
                "x": missing.index.tolist(),
                "y": missing.values.tolist(),
                "name": "Missing Values"
            },
            "layout": {
                "title": "Missing Values by Column",
                "xaxis": {"title": "Column"},
                "yaxis": {"title": "Count"}
            }
        }
    
    def _correlation_heatmap(self, df: pd.DataFrame, numeric_cols: list[str]) -> dict[str, Any]:
        """Generate correlation heatmap."""
        corr_df = df[numeric_cols].corr()
        
        return {
            "type": "heatmap",
            "data": {
                "z": corr_df.values.tolist(),
                "x": corr_df.columns.tolist(),
                "y": corr_df.index.tolist(),
                "colorscale": "RdBu",
                "zmid": 0
            },
            "layout": {
                "title": "Correlation Heatmap",
                "xaxis": {"title": "Features"},
                "yaxis": {"title": "Features"}
            }
        }
    
    def _histogram(self, df: pd.DataFrame, column: str) -> dict[str, Any]:
        """Generate histogram for a column."""
        values = pd.to_numeric(df[column], errors='coerce').dropna()
        
        return {
            "type": "histogram",
            "column": column,
            "data": {
                "x": values.tolist(),
                "nbinsx": 30,
                "name": column
            },
            "layout": {
                "title": f"Distribution of {column}",
                "xaxis": {"title": column},
                "yaxis": {"title": "Frequency"}
            }
        }
    
    def _box_plot(self, df: pd.DataFrame, column: str) -> dict[str, Any]:
        """Generate box plot for a column."""
        values = pd.to_numeric(df[column], errors='coerce').dropna()
        
        return {
            "type": "box",
            "column": column,
            "data": {
                "y": values.tolist(),
                "name": column
            },
            "layout": {
                "title": f"Box Plot: {column}",
                "yaxis": {"title": "Value"}
            }
        }
    
    def _distribution_plot(self, df: pd.DataFrame, column: str) -> dict[str, Any]:
        """Generate distribution plot (histogram + KDE)."""
        values = pd.to_numeric(df[column], errors='coerce').dropna()
        
        return {
            "type": "distribution",
            "column": column,
            "data": {
                "x": values.tolist(),
                "name": column
            },
            "layout": {
                "title": f"Distribution: {column}",
                "xaxis": {"title": column},
                "yaxis": {"title": "Density"}
            }
        }
    
    def _bar_chart(self, df: pd.DataFrame, column: str) -> dict[str, Any]:
        """Generate bar chart for categorical column."""
        value_counts = df[column].value_counts().head(15)
        
        return {
            "type": "bar",
            "column": column,
            "data": {
                "x": value_counts.index.tolist(),
                "y": value_counts.values.tolist(),
                "name": column
            },
            "layout": {
                "title": f"Top Values: {column}",
                "xaxis": {"title": column},
                "yaxis": {"title": "Count"}
            }
        }
    
    def _pie_chart(self, df: pd.DataFrame, column: str) -> dict[str, Any]:
        """Generate pie chart for categorical column."""
        value_counts = df[column].value_counts().head(8)
        
        return {
            "type": "pie",
            "column": column,
            "data": {
                "labels": value_counts.index.tolist(),
                "values": value_counts.values.tolist(),
                "name": column
            },
            "layout": {
                "title": f"Distribution: {column}"
            }
        }
    
    def _scatter_plot(self, df: pd.DataFrame, x_col: str, y_col: str) -> dict[str, Any]:
        """Generate scatter plot."""
        x_values = pd.to_numeric(df[x_col], errors='coerce')
        y_values = pd.to_numeric(df[y_col], errors='coerce')
        
        # Filter out NaN
        mask = x_values.notna() & y_values.notna()
        
        return {
            "type": "scatter",
            "columns": [x_col, y_col],
            "data": {
                "x": x_values[mask].tolist(),
                "y": y_values[mask].tolist(),
                "mode": "markers",
                "name": f"{x_col} vs {y_col}"
            },
            "layout": {
                "title": f"{x_col} vs {y_col}",
                "xaxis": {"title": x_col},
                "yaxis": {"title": y_col}
            }
        }
    
    def _violin_plot(self, df: pd.DataFrame, column: str) -> dict[str, Any]:
        """Generate violin plot."""
        values = pd.to_numeric(df[column], errors='coerce').dropna()
        
        return {
            "type": "violin",
            "column": column,
            "data": {
                "y": values.tolist(),
                "name": column,
                "box_visible": True,
                "meanline_visible": True
            },
            "layout": {
                "title": f"Violin Plot: {column}",
                "yaxis": {"title": "Value"}
            }
        }
    
    def _outlier_plot(self, df: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
        """Generate outlier detection plot using IQR method."""
        outlier_counts = {}
        
        for col in columns:
            values = pd.to_numeric(df[col], errors='coerce').dropna()
            if values.empty:
                continue
            
            q1, q3 = values.quantile(0.25), values.quantile(0.75)
            iqr = q3 - q1
            
            if iqr == 0:
                outlier_counts[col] = 0
            else:
                mask = (values < (q1 - 1.5 * iqr)) | (values > (q3 + 1.5 * iqr))
                outlier_counts[col] = int(mask.sum())
        
        return {
            "type": "bar",
            "data": {
                "x": list(outlier_counts.keys()),
                "y": list(outlier_counts.values()),
                "name": "Outlier Count"
            },
            "layout": {
                "title": "Outliers Detected by Column (IQR Method)",
                "xaxis": {"title": "Column"},
                "yaxis": {"title": "Outlier Count"}
            }
        }
    
    def _class_balance_chart(self, df: pd.DataFrame, target_col: str) -> dict[str, Any]:
        """Generate class balance chart."""
        value_counts = df[target_col].value_counts()
        
        return {
            "type": "bar",
            "column": target_col,
            "data": {
                "x": value_counts.index.astype(str).tolist(),
                "y": value_counts.values.tolist(),
                "name": "Class Distribution"
            },
            "layout": {
                "title": f"Class Balance: {target_col}",
                "xaxis": {"title": "Class"},
                "yaxis": {"title": "Count"}
            }
        }


# Global instance
eda_service = EDAService()
