"""
date_parser.py — Rule-based date parsing service for CV employment timelines.
Supports Vietnamese & English formats:
- "03/2020", "3/2020"
- "T3/2020", "Tháng 3/2020", "Tháng 03/2020"
- "2019-2022", "2019 - nay", "2019 - hiện tại", "2019 - present"
- "Mar 2020", "March 2020"
- "present", "hiện tại", "nay", "current"
"""
import re
from typing import Optional, Tuple, List
import datetime

MONTH_MAP = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

PRESENT_TERMS = [
    'present', 'current', 'now', 'nay', 'hien tai', 'hiện tại',
    'till date', 'to date', 'den nay', 'đến nay'
]

def parse_single_date(date_str: Optional[str]) -> Tuple[Optional[str], bool, Optional[str]]:
    """
    Parses a single date string into ISO YYYY-MM.
    
    Returns:
        (iso_str or None, is_present: bool, error_or_flag: Optional[str])
    """
    if not date_str or not date_str.strip():
        return None, False, None
        
    s = date_str.strip().lower()
    
    # Check present / ongoing
    for term in PRESENT_TERMS:
        if term in s:
            return None, True, None
            
    # Pattern 1: ISO YYYY-MM
    m = re.match(r'^(\d{4})-(0?[1-9]|1[0-2])$', s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return f"{y:04d}-{mo:02d}", False, None

    # Pattern 2: MM/YYYY or MM-YYYY
    m = re.match(r'^(0?[1-9]|1[0-2])[/-](\d{4})$', s)
    if m:
        mo, y = int(m.group(1)), int(m.group(2))
        return f"{y:04d}-{mo:02d}", False, None

    # Pattern 3: Vietnamese T3/2020, T03/2020, Thang 3/2020, Tháng 3/2020
    m = re.match(r'^(?:t|thang\s*|tháng\s*)(0?[1-9]|1[0-2])[/-](\d{4})$', s)
    if m:
        mo, y = int(m.group(1)), int(m.group(2))
        return f"{y:04d}-{mo:02d}", False, None

    # Pattern 4: Mar 2020, March 2020
    m = re.match(r'^([a-z]+)[\s,.-]+(\d{4})$', s)
    if m and m.group(1) in MONTH_MAP:
        mo = MONTH_MAP[m.group(1)]
        y = int(m.group(2))
        return f"{y:04d}-{mo:02d}", False, None

    # Pattern 5: Year only YYYY (e.g. 2019) -> 2019-01
    m = re.match(r'^(\d{4})$', s)
    if m:
        y = int(m.group(1))
        return f"{y:04d}-01", False, None

    return None, False, f"invalid_date_format:{date_str}"

def parse_date_range(raw_start: Optional[str], raw_end: Optional[str], ref_date_iso: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Parses and validates a (start, end) date pair against reference date.
    
    Returns:
        (iso_start, iso_end, flags)
    """
    flags = []
    
    # Check if raw_start contains a full range like "2019-2022" or "2019 - nay"
    if raw_start and not raw_end:
        for sep in [' - ', ' to ', ' – ', ' — ', '-']:
            if sep in raw_start:
                parts = raw_start.split(sep, 1)
                raw_start, raw_end = parts[0].strip(), parts[1].strip()
                break

    iso_start, start_is_pres, flag_s = parse_single_date(raw_start)
    iso_end, end_is_pres, flag_e = parse_single_date(raw_end)

    if flag_s:
        flags.append(flag_s)
    if flag_e:
        flags.append(flag_e)

    # Validate against ref_date (no dates after reference date)
    ref_dt = datetime.datetime.strptime(ref_date_iso, "%Y-%m-%d").date()
    
    if iso_start:
        s_dt = datetime.datetime.strptime(iso_start, "%Y-%m").date()
        if s_dt > ref_dt:
            flags.append(f"start_after_ref_date:{iso_start}>{ref_date_iso}")

    if iso_end:
        e_dt = datetime.datetime.strptime(iso_end, "%Y-%m").date()
        if e_dt > ref_dt:
            flags.append(f"end_after_ref_date:{iso_end}>{ref_date_iso}")

    # Validate start <= end
    if iso_start and iso_end:
        s_dt = datetime.datetime.strptime(iso_start, "%Y-%m").date()
        e_dt = datetime.datetime.strptime(iso_end, "%Y-%m").date()
        if s_dt > e_dt:
            flags.append(f"start_after_end:{iso_start}>{iso_end}")

    return iso_start, iso_end, flags

def merge_date_intervals(intervals: List[Tuple[datetime.date, datetime.date]]) -> float:
    """
    Takes a list of (start_date, end_date) tuples, merges overlapping/adjacent intervals,
    and returns the total distinct calendar months duration (inclusive of start and end month,
    synchronized 100% with `ProficiencyEstimator._calculate_effective_months`).
    """
    valid = [(s, e) for s, e in intervals if s and e and s <= e]
    if not valid:
        return 0.0

    distinct_months = set()
    for s, e in valid:
        cur_y, cur_m = s.year, s.month
        end_y, end_m = e.year, e.month
        while (cur_y < end_y) or (cur_y == end_y and cur_m <= end_m):
            distinct_months.add((cur_y, cur_m))
            cur_m += 1
            if cur_m > 12:
                cur_m = 1
                cur_y += 1
    return float(len(distinct_months))
