from PIL import Image, ImageDraw, ImageFont
import random

def create_fake_aadhaar(name, dob, gender, address, aadhaar_num):
    # 1. Create a blank light-blue/white background (Aadhaar style)
    width, height = 800, 500
    img = Image.new('RGB', (width, height), color=(240, 248, 255))
    draw = ImageDraw.Draw(img)

    # 2. Add Header (Simulating 'Government of India')
    try:
        # Note: You may need to provide a path to a .ttf file on your system
        header_font = ImageFont.truetype("arial.ttf", 30)
        label_font = ImageFont.truetype("arial.ttf", 20)
        data_font = ImageFont.truetype("arial.ttf", 22)
        number_font = ImageFont.truetype("arial.ttf", 40)
    except:
        header_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
        data_font = ImageFont.load_default()
        number_font = ImageFont.load_default()

    draw.text((250, 20), "Government of India", fill=(0, 0, 128), font=header_font)
    draw.text((280, 60), "Unique Identification Authority of India", fill=(0, 0, 0), font=label_font)

    # 3. Add Photo Placeholder
    draw.rectangle([50, 120, 200, 300], outline=(0, 0, 0), width=2)
    draw.text((80, 200), "PHOTO", fill=(100, 100, 100), font=label_font)

    # 4. Add Personal Details (The target for your OCR)
    start_x, start_y = 250, 130
    
    # Name
    draw.text((start_x, start_y), name, fill=(0, 0, 0), font=data_font)
    
    # DOB
    draw.text((start_x, start_y + 40), f"DOB: {dob}", fill=(0, 0, 0), font=data_font)
    
    # Gender
    draw.text((start_x, start_y + 80), f"Gender: {gender}", fill=(0, 0, 0), font=data_font)
    
    # Address Label and Content
    draw.text((start_x, start_y + 120), "Address:", fill=(0, 0, 0), font=label_font)
    draw.text((start_x, start_y + 150), address, fill=(0, 0, 0), font=data_font)

    # 5. Add Aadhaar Number (The Big 12 Digits)
    # Format: XXXX XXXX XXXX
    formatted_num = f"{aadhaar_num[:4]} {aadhaar_num[4:8]} {aadhaar_num[8:]}"
    draw.text((250, 400), formatted_num, fill=(0, 0, 0), font=number_font)

    # 6. Save the image
    filename = "test_aadhaar.png"
    img.save(filename)
    print(f"✅ Synthetic Aadhaar generated as {filename}")
    return filename

if __name__ == "__main__":
    # Generate a test card
    create_fake_aadhaar(
        name="SYED ARIFUDDIN",
        dob="15/08/1990",
        gender="Male",
        address="H.No 12-2-417/B/53, Gagan Mahal, Hyderabad, Telangana, 500029",
        aadhaar_num="542189021234"
    )