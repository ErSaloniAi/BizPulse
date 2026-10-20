import csv
import io
import datetime
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse
from django.utils import timezone


def get_normalized_dict_reader(uploaded_file):
    """
    Reads an uploaded file object, detects encoding, strips whitespace,
    and returns a list of dictionaries with normalized lowercase keys.
    """
    raw_bytes = uploaded_file.read()
    
    # Try different encodings: UTF-8 with BOM, standard UTF-8, Windows CP1252, Latin-1
    text = None
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise ValueError("Unable to read file encoding. Please ensure the file is a valid CSV.")

    # Remove null bytes if any
    text = text.replace('\x00', '')
    
    stream = io.StringIO(text, newline=None)
    reader = csv.reader(stream)
    
    rows = list(reader)
    if not rows:
        return []

    # Find first non-empty header row
    header_idx = -1
    raw_headers = []
    for idx, row in enumerate(rows):
        if any(cell.strip() for cell in row):
            header_idx = idx
            raw_headers = [cell.strip() for cell in row]
            break

    if header_idx == -1 or not raw_headers:
        return []

    # Normalized header keys: lowercase, alphanumeric and underscores only
    def normalize_header(h):
        clean = h.strip().lower()
        clean = clean.replace(' ', '_').replace('-', '_').replace('.', '').replace('/', '_')
        clean = clean.replace('(', '').replace(')', '').replace('₹', '').replace('rs', '')
        while '__' in clean:
            clean = clean.replace('__', '_')
        return clean.strip('_')

    norm_headers = [normalize_header(h) for h in raw_headers]

    dict_rows = []
    for row_num, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not any(cell.strip() for cell in row):
            continue  # skip completely blank rows
        
        row_dict = {}
        for col_idx, key in enumerate(norm_headers):
            if key and col_idx < len(row):
                row_dict[key] = row[col_idx].strip()
            elif key:
                row_dict[key] = ''
        row_dict['_row_num'] = row_num
        dict_rows.append(row_dict)

    return dict_rows


def parse_decimal_safe(value, default=Decimal('0.00')):
    """
    Safely converts a string to a Decimal, stripping currency symbols, commas, and spaces.
    """
    if value is None:
        return default
    val_str = str(value).strip().replace('₹', '').replace('$', '').replace(',', '').replace(' ', '')
    if not val_str:
        return default
    try:
        return Decimal(val_str)
    except InvalidOperation:
        raise ValueError(f"Invalid numeric value '{value}'")


def parse_date_safe(value, default=None):
    """
    Safely parses dates in various common formats (YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, etc.).
    """
    if not value or not str(value).strip():
        return default or timezone.localdate()

    val_str = str(value).strip()
    formats = [
        '%Y-%m-%d',
        '%d-%m-%Y',
        '%d/%m/%Y',
        '%m/%d/%Y',
        '%Y/%m/%d',
        '%d.%m.%Y',
        '%d-%b-%Y',
        '%d %b %Y',
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(val_str, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Invalid date format '{value}'. Please use YYYY-MM-DD or DD-MM-YYYY.")


def generate_csv_download(filename, headers, sample_rows):
    """
    Returns an HttpResponse configured to download a sample CSV template with UTF-8 BOM.
    """
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Write UTF-8 BOM so Excel opens it with proper encoding
    response.write('\ufeff')
    
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in sample_rows:
        writer.writerow(row)
        
    return response
