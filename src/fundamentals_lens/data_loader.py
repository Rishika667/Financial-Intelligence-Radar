import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import Company, FinancialFact

DEFAULT_DATASET_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "fundamentals_lens"


def get_dataset_dir(custom_path: Optional[str] = None) -> Path:
    if custom_path:
        return Path(custom_path)
    env_path = os.environ.get("FUNDAMENTALS_LENS_DATA_DIR")
    if env_path:
        return Path(env_path)
    return DEFAULT_DATASET_DIR


def load_companies(dataset_dir: Optional[Path] = None) -> List[Company]:
    base_dir = dataset_dir or get_dataset_dir()
    file_path = base_dir / "companies.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Companies file not found at {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    return [Company(**item) for item in data]


def load_financial_facts(dataset_dir: Optional[Path] = None) -> List[FinancialFact]:
    base_dir = dataset_dir or get_dataset_dir()
    file_path = base_dir / "financial_facts_5yr.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Financial facts file not found at {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    return [FinancialFact(**item) for item in data]


def load_source_register(dataset_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    base_dir = dataset_dir or get_dataset_dir()
    file_path = base_dir / "source_register.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Source register file not found at {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_coverage_report(dataset_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    base_dir = dataset_dir or get_dataset_dir()
    file_path = base_dir / "coverage_report.json"
    if not file_path.exists():
        raise FileNotFoundError(f"Coverage report file not found at {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_company_by_ticker(ticker: str, dataset_dir: Optional[Path] = None) -> Optional[Company]:
    companies = load_companies(dataset_dir)
    for c in companies:
        if c.ticker.upper() == ticker.upper():
            return c
    return None


def get_facts_for_company(ticker: str, dataset_dir: Optional[Path] = None) -> List[FinancialFact]:
    all_facts = load_financial_facts(dataset_dir)
    return [f for f in all_facts if f.ticker.upper() == ticker.upper()]
