# 🚀 MediaFlow API

MediaFlow API is a high-performance middleware designed to compress and optimize images before sending them to AI Vision Models (OpenAI GPT-4o, Llama 3 Vision, Groq, Anthropic Claude).

## 💡 Why MediaFlow?
- **Reduces AI API Costs:** Save up to 70-90% on Vision Token costs by reducing payload size.
- **Ultra Fast:** Response times < 100ms.
- **Automatic Format Conversion:** Converts heavy PNG/JPEG files into light, optimized WebP format.

## 📌 API Usage

### Endpoint: `POST /v1/optimize`

#### cURL Example:
```bash
curl -X POST "[https://your-domain.com/v1/optimize?max_dimension=1024&quality=80](https://your-domain.com/v1/optimize?max_dimension=1024&quality=80)" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/image.jpg" \
  --output optimized_image.webp
```

#### Python Example:
```python
import requests

url = "[https://your-domain.com/v1/optimize](https://your-domain.com/v1/optimize)"
files = {"file": open("product.png", "rb")}

response = requests.post(url, files=files)

# Response header shows saved ratio!
print("Original size:", response.headers.get("X-Original-Size-Bytes"))
print("Saved:", response.headers.get("X-Saved-Percentage"))

with open("optimized.webp", "wb") as f:
    f.write(response.content)
```
