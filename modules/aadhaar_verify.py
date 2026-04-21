# ─── aadhaar_verify.py ─ Put this in your project root ─────────
import re
import base64
import io
from PIL import Image

# ── Verhoeff checksum (UIDAI standard) ──────────────────────────
_D = [[0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],
      [2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
      [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
      [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
      [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0]]
_P = [[0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],
      [5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
      [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
      [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8]]
_INV = [0,4,3,2,1,9,8,7,6,5]

def verhoeff_validate(number):
    """Returns True if the 12-digit Aadhaar number passes Verhoeff checksum."""
    c = 0
    for i, n in enumerate(reversed(str(number))):
        c = _D[c][_P[i % 8][int(n)]]
    return c == 0

def validate_aadhaar_format(number):
    """Check format: 12 digits, not starting with 0 or 1."""
    n = str(number).replace(' ', '').replace('-', '')
    if not n.isdigit():        return False, "Aadhaar must contain only digits."
    if len(n) != 12:           return False, "Aadhaar must be exactly 12 digits."
    if n[0] in ('0', '1'):     return False, "Aadhaar cannot start with 0 or 1."
    if not verhoeff_validate(n): return False, "Invalid Aadhaar number (checksum failed)."
    return True, n

def extract_aadhaar_from_image(image_bytes):
    """
    Extract Aadhaar number from uploaded document image.
    Uses pattern matching on the image filename/data.
    Falls back to OCR if pytesseract is available.
    Returns (aadhaar_number, method_used) or (None, error_message)
    """
    # Try OCR first
    try:
        import pytesseract
        img = Image.open(io.BytesIO(image_bytes))
        # Preprocess: convert to grayscale, upscale for better OCR
        img = img.convert('L')
        w, h = img.size
        img = img.resize((w*2, h*2), Image.LANCZOS)
        text = pytesseract.image_to_string(img, config='--psm 6')

        # Find all 12-digit sequences in the extracted text
        candidates = re.findall(r'\b\d[\d\s\-]{10,13}\d\b', text)
        for raw in candidates:
            clean = re.sub(r'[\s\-]', '', raw)
            if len(clean) == 12:
                valid, result = validate_aadhaar_format(clean)
                if valid:
                    return result, 'OCR'

        # Also try finding spaced format like "2563 1219 1018"
        spaced = re.findall(r'\d{4}\s+\d{4}\s+\d{4}', text)
        for s in spaced:
            clean = s.replace(' ', '')
            valid, result = validate_aadhaar_format(clean)
            if valid:
                return result, 'OCR'

        return None, "Could not detect a valid Aadhaar number in the document."

    except ImportError:
        return None, "OCR not available. Please install pytesseract and Tesseract OCR."
    except Exception as e:
        return None, f"Processing error: {str(e)}"