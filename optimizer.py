import io
from PIL import Image, ImageOps

def optimize_image_for_ai(image_bytes: bytes, max_dimension: int = 1024, quality: int = 80) -> bytes:
    """
    محرك معالجة آمن ومقاوم للصور التالفة وصيغ الألوان المعقدة.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # تصحيح اتجاه الصورة بناءً على بيانات الـ EXIF إن وجدت
        image = ImageOps.exif_transpose(image)
        
        # معالجة الشفافية وصيغ الألوان المختلفة بأمان تام لمنع الأخطاء
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            if "transparency" in image.info:
                background.paste(image, mask=image.convert("RGBA").split()[3])
            elif image.mode == "RGBA":
                background.paste(image, mask=image.split()[3])
            else:
                background.paste(image)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        # تصغير الأبعاد الذكي مع الحفاظ على النسبة والتناسب
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        # الحفظ بصيغة WebP المضغوطة وعالية الجودة
        output_buffer = io.BytesIO()
        image.save(
            output_buffer,
            format="WEBP",
            quality=quality,
            optimize=True
        )

        return output_buffer.getvalue()
        
    except Exception as e:
        raise ValueError(f"Core Optimizer Error: Unable to process image data. Details: {str(e)}")
        
