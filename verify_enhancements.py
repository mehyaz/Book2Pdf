from PIL import Image, ImageEnhance, ImageOps
import os

def verify_enhancements():
    # Create a dummy image
    width, height = 100, 100
    img = Image.new('RGB', (width, height), color = 'red')
    
    print(f"Original Size: {img.size}")
    
    # 1. Test Grayscale
    gray_img = ImageOps.grayscale(img).convert("RGB")
    print("Applied Grayscale")
    
    # 2. Test Contrast
    enhancer = ImageEnhance.Contrast(gray_img)
    contrast_img = enhancer.enhance(1.5)
    print("Applied Contrast")
    
    # 3. Test Sharpness
    enhancer = ImageEnhance.Sharpness(contrast_img)
    sharp_img = enhancer.enhance(2.0)
    print("Applied Sharpness")
    
    # 4. Test Upscaling (Lanczos)
    new_width = int(width * 2)
    new_height = int(height * 2)
    upscaled_img = sharp_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    print(f"Upscaled Size: {upscaled_img.size}")
    
    if upscaled_img.size == (200, 200):
        print("SUCCESS: Upscaling worked correctly.")
    else:
        print("FAILURE: Upscaling size mismatch.")

if __name__ == "__main__":
    verify_enhancements()
