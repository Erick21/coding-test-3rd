"""
Table parser - classifies and parses tables from fund performance PDFs.

Main challenge: PDFs have different table formats, so we use keyword matching
to figure out what type of table we're looking at.
"""
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal
import re
from sqlalchemy.orm import Session


class TableParser:
    """Parse and classify tables from PDFs"""
    
    def __init__(self):
        # Keywords for table classification
        self.capital_call_keywords = [
            "capital call", "capital contribution", "drawdown", 
            "call date", "call number", "contribution date"
        ]
        self.distribution_keywords = [
            "distribution", "return of capital", "dividend",
            "distribution date", "payment", "return"
        ]
        self.adjustment_keywords = [
            "adjustment", "rebalance", "recall", "recallable",
            "correction", "amendment"
        ]
    
    def parse_tables(
        self, 
        tables: List[List[List[str]]], 
        db: Session,
        fund_id: int
    ) -> Dict[str, Any]:
        """
        Parse extracted tables and store in database
        
        Args:
            tables: List of tables (each table is a list of rows, each row is a list of cells)
            db: Database session
            fund_id: Fund ID to associate transactions with
            
        Returns:
            Dictionary with parsing statistics
        """
        stats = {
            "capital_calls": 0,
            "distributions": 0,
            "adjustments": 0,
            "errors": []
        }
        
        for table_idx, table in enumerate(tables):
            if not table or len(table) < 2:  # Skip empty or single-row tables
                continue
            
            try:
                # Classify table type
                table_type = self._classify_table(table)
                
                if table_type == "capital_call":
                    count = self._parse_capital_calls(table, db, fund_id)
                    stats["capital_calls"] += count
                
                elif table_type == "distribution":
                    count = self._parse_distributions(table, db, fund_id)
                    stats["distributions"] += count
                
                elif table_type == "adjustment":
                    count = self._parse_adjustments(table, db, fund_id)
                    stats["adjustments"] += count
                
            except Exception as e:
                stats["errors"].append(f"Error parsing table {table_idx}: {str(e)}")
        
        return stats
    
    def _classify_table(self, table: List[List[str]]) -> Optional[str]:
        """Figure out what type of table this is by looking at the headers"""
        if not table:
            return None
        
        # Check first few rows for keywords
        header_text = " ".join([
            " ".join(cell.lower() for cell in row)
            for row in table[:3]
        ])
        
        # Score each type based on keyword matches
        capital_score = sum(1 for kw in self.capital_call_keywords if kw in header_text)
        distribution_score = sum(1 for kw in self.distribution_keywords if kw in header_text)
        adjustment_score = sum(1 for kw in self.adjustment_keywords if kw in header_text)
        
        max_score = max(capital_score, distribution_score, adjustment_score)
        
        if max_score == 0:
            return None
        
        if capital_score == max_score:
            return "capital_call"
        elif distribution_score == max_score:
            return "distribution"
        else:
            return "adjustment"
    
    def _parse_capital_calls(
        self, 
        table: List[List[str]], 
        db: Session, 
        fund_id: int
    ) -> int:
        """Parse capital call table and store in database"""
        from app.models.transaction import CapitalCall
        
        # Find header row (usually contains 'date', 'amount', etc.)
        header_idx = self._find_header_row(table)
        if header_idx is None:
            return 0
        
        headers = [cell.lower().strip() for cell in table[header_idx]]
        
        # Map column indices
        date_col = self._find_column(headers, ["date", "call date", "contribution date"])
        amount_col = self._find_column(headers, ["amount", "call amount", "contribution"])
        type_col = self._find_column(headers, ["type", "call type", "description"])
        
        if date_col is None or amount_col is None:
            return 0
        
        count = 0
        # Parse data rows
        for row_idx in range(header_idx + 1, len(table)):
            row = table[row_idx]
            
            if len(row) <= max(date_col, amount_col):
                continue
            
            try:
                # Parse date
                date_str = row[date_col].strip()
                call_date = self._parse_date(date_str)
                
                if not call_date:
                    continue
                
                # Parse amount
                amount_str = row[amount_col].strip()
                amount = self._parse_amount(amount_str)
                
                if not amount or amount <= 0:
                    continue
                
                # Parse type/description
                call_type = row[type_col].strip() if type_col is not None and len(row) > type_col else "Capital Call"
                
                # Create capital call record
                capital_call = CapitalCall(
                    fund_id=fund_id,
                    call_date=call_date,
                    call_type=call_type,
                    amount=amount,
                    description=call_type
                )
                
                db.add(capital_call)
                count += 1
                
            except Exception as e:
                print(f"Error parsing capital call row {row_idx}: {e}")
                continue
        
        # Commit all capital calls
        db.commit()
        
        return count
    
    def _parse_distributions(
        self, 
        table: List[List[str]], 
        db: Session, 
        fund_id: int
    ) -> int:
        """Parse distribution table and store in database"""
        from app.models.transaction import Distribution
        
        # Find header row
        header_idx = self._find_header_row(table)
        if header_idx is None:
            return 0
        
        headers = [cell.lower().strip() for cell in table[header_idx]]
        
        # Map column indices
        date_col = self._find_column(headers, ["date", "distribution date", "payment date"])
        amount_col = self._find_column(headers, ["amount", "distribution", "payment"])
        type_col = self._find_column(headers, ["type", "distribution type", "description"])
        recallable_col = self._find_column(headers, ["recallable", "recall", "is recallable"])
        
        if date_col is None or amount_col is None:
            return 0
        
        count = 0
        # Parse data rows
        for row_idx in range(header_idx + 1, len(table)):
            row = table[row_idx]
            
            if len(row) <= max(date_col, amount_col):
                continue
            
            try:
                # Parse date
                date_str = row[date_col].strip()
                distribution_date = self._parse_date(date_str)
                
                if not distribution_date:
                    continue
                
                # Parse amount
                amount_str = row[amount_col].strip()
                amount = self._parse_amount(amount_str)
                
                if not amount or amount <= 0:
                    continue
                
                # Parse type
                dist_type = row[type_col].strip() if type_col is not None and len(row) > type_col else "Distribution"
                
                # Parse recallable flag
                is_recallable = False
                if recallable_col is not None and len(row) > recallable_col:
                    recallable_str = row[recallable_col].strip().lower()
                    is_recallable = recallable_str in ["yes", "true", "y", "1"]
                
                # Create distribution record
                distribution = Distribution(
                    fund_id=fund_id,
                    distribution_date=distribution_date,
                    distribution_type=dist_type,
                    is_recallable=is_recallable,
                    amount=amount,
                    description=dist_type
                )
                
                db.add(distribution)
                count += 1
                
            except Exception as e:
                print(f"Error parsing distribution row {row_idx}: {e}")
                continue
        
        # Commit all distributions
        db.commit()
        
        return count
    
    def _parse_adjustments(
        self, 
        table: List[List[str]], 
        db: Session, 
        fund_id: int
    ) -> int:
        """Parse adjustment table and store in database"""
        from app.models.transaction import Adjustment
        
        # Find header row
        header_idx = self._find_header_row(table)
        if header_idx is None:
            return 0
        
        headers = [cell.lower().strip() for cell in table[header_idx]]
        
        # Map column indices
        date_col = self._find_column(headers, ["date", "adjustment date"])
        amount_col = self._find_column(headers, ["amount", "adjustment"])
        type_col = self._find_column(headers, ["type", "adjustment type", "category"])
        
        if date_col is None or amount_col is None:
            return 0
        
        count = 0
        # Parse data rows
        for row_idx in range(header_idx + 1, len(table)):
            row = table[row_idx]
            
            if len(row) <= max(date_col, amount_col):
                continue
            
            try:
                # Parse date
                date_str = row[date_col].strip()
                adjustment_date = self._parse_date(date_str)
                
                if not adjustment_date:
                    continue
                
                # Parse amount (can be negative)
                amount_str = row[amount_col].strip()
                amount = self._parse_amount(amount_str, allow_negative=True)
                
                if amount is None:
                    continue
                
                # Parse type
                adj_type = row[type_col].strip() if type_col is not None and len(row) > type_col else "Adjustment"
                
                # Determine if it's a contribution adjustment
                is_contribution_adjustment = "capital" in adj_type.lower() or "contribution" in adj_type.lower()
                
                # Create adjustment record
                adjustment = Adjustment(
                    fund_id=fund_id,
                    adjustment_date=adjustment_date,
                    adjustment_type=adj_type,
                    category=adj_type,
                    amount=amount,
                    is_contribution_adjustment=is_contribution_adjustment,
                    description=adj_type
                )
                
                db.add(adjustment)
                count += 1
                
            except Exception as e:
                print(f"Error parsing adjustment row {row_idx}: {e}")
                continue
        
        # Commit all adjustments
        db.commit()
        
        return count
    
    def _find_header_row(self, table: List[List[str]]) -> Optional[int]:
        """Find the header row in a table"""
        # Look for common header keywords in first 3 rows
        header_keywords = ["date", "amount", "type", "description"]
        
        for idx, row in enumerate(table[:3]):
            row_text = " ".join(cell.lower() for cell in row)
            if any(kw in row_text for kw in header_keywords):
                return idx
        
        # Default to first row
        return 0
    
    def _find_column(
        self, 
        headers: List[str], 
        possible_names: List[str]
    ) -> Optional[int]:
        """Find column index by matching possible header names"""
        for idx, header in enumerate(headers):
            for name in possible_names:
                if name in header:
                    return idx
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Try to parse date - PDFs have many different formats"""
        if not date_str or date_str.strip() == "":
            return None
        
        # Try different formats until one works
        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%m-%d-%Y",
            "%d-%m-%Y",
            "%b %d, %Y",
            "%B %d, %Y",
            "%d %b %Y",
            "%d %B %Y"
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None
    
    def _parse_amount(
        self, 
        amount_str: str, 
        allow_negative: bool = False
    ) -> Optional[Decimal]:
        """Parse amount - strip currency symbols and convert to number"""
        if not amount_str or amount_str.strip() == "":
            return None
        
        # Remove currency symbols, commas, spaces - just keep numbers and decimal
        cleaned = re.sub(r'[^\d.\-\+]', '', amount_str.strip())
        
        if not cleaned:
            return None
        
        try:
            amount = Decimal(cleaned)
            
            if not allow_negative and amount < 0:
                return abs(amount)
            
            return amount
            
        except Exception:
            return None

