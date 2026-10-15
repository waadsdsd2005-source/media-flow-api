import io
from PIL import Image, ImageOps

def optimize_image_for_ai(image_bytes: bytes, max_dimension: int = 1024, quality: int = 80) -> bytes:
    """
    تقوم بتلقي بيانات الصورة كـ Bytes، تعديل الاتجاه، ضبط الأبعاد، وضغط الحجم لتقليل استهلاك الـ Tokens.
    """
    # فتح الصورة من الميموري
    image = Image.open(io.BytesIO(image_bytes))
    
    # إصلاح اتجاه الصورة التلقائي (EXIF Orientation)
    image = ImageOps.exif_transpose(image)
    
    # تحويل الصورة إلى RGB للتعامل مع ملفات PNG أو الألوان المتباينة
    if image.mode in ("RGBA", "P"):
        # إنشاء خلفية بيضاء لتفريغ الشفافية
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "RGBA":
            background.paste(image, mask=image.split()[3])
        else:
            background.paste(image)
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    # تصغير الأبعاد مع الحفاظ على النسبة والتناسب (Aspect Ratio)
    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    # تصدير بصيغة WebP عالية الضغط والكفاءة
    output_buffer = io.BytesIO()
    image.save(
        output_buffer,
        format="WEBP",
        quality=quality,
        optimize=True
    )

    return output_buffer.getvalue()
