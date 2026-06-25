import logging

logger = logging.getLogger(__name__)

DOMAIN_KEYWORDS = {
    "Retail": ["customer", "product", "price", "quantity", "invoice", "transaction date", "transaction_date", "order", "revenue", "sales", "cost", "store", "ecom", "sales_channel", "payment"],
    "Healthcare": ["patient", "diagnosis", "blood pressure", "blood_pressure", "bmi", "heart rate", "heart_rate", "cholesterol", "blood", "sugar", "glucose", "disease", "treatment", "doctor", "hospital", "patient_id"],
    "Finance": ["account", "balance", "credit score", "credit_score", "transaction amount", "transaction_amount", "loan", "debt", "income", "interest", "equity", "portfolio", "asset", "checking", "savings"],
    "HR": ["employee", "salary", "department", "job", "hire", "tenure", "manager", "performance", "rating", "wage", "employee_id"],
    "Education": ["student", "grade", "course", "score", "gpa", "exam", "class", "subject", "teacher", "tuition", "enroll", "student_id"],
    "Marketing": ["campaign", "clicks", "impressions", "conversion", "lead", "ad", "advertiser", "ctr", "reach", "spend"],
    "Manufacturing": ["machine", "sensor", "temperature", "pressure", "vibration", "cycle_time", "maintenance", "error_code", "speed", "factory", "device"]
}

def detect_dataset_domain(profile_summary: dict) -> dict:
    """
    Infers the business domain of a dataset by scanning its column list
    against key domain terms.
    If maximum match confidence < 60%, returns "General Tabular Dataset".
    """
    columns = profile_summary.get("columns", [])
    num_cols = len(columns)
    
    if num_cols == 0:
        return {"domain": "General Tabular Dataset", "confidence": 0.0}

    domain_scores = {d: 0 for d in DOMAIN_KEYWORDS}
    
    # Handle dict vs list format for columns
    col_names = []
    if isinstance(columns, dict):
        col_names = [str(k).lower() for k in columns.keys()]
    else:
        for col_info in columns:
            if isinstance(col_info, dict):
                col_names.append(col_info.get("column", "").lower())
            else:
                col_names.append(str(col_info).lower())

    for col_name in col_names:
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(k in col_name for k in keywords):
                domain_scores[domain] += 1

    max_domain = max(domain_scores, key=domain_scores.get)
    max_score = domain_scores[max_domain]

    if max_score == 0:
        return {"domain": "General Tabular Dataset", "confidence": 0.0}

    confidence = round(max_score / len(col_names), 2)
    
    if confidence >= 0.60:
        logger.info(f"DomainDetector: Classified domain as '{max_domain}' with confidence {confidence}")
        return {"domain": max_domain, "confidence": confidence}
    else:
        logger.info(f"DomainDetector: Classified domain as 'General Tabular Dataset' (max match {max_domain} at {confidence})")
        return {"domain": "General Tabular Dataset", "confidence": confidence}
