# Dedplay Kütüphane
# Stüdyo imajının üstüne kurulur: OCR (tessdata_best), Amiri, Noto yazı tipleri, PyMuPDF, Zemberek ve
# Stüdyo'nun metin çıkarma kodu (/app/app) hazır gelir. Stüdyo'nun kendisine dokunulmaz.
FROM berzahbey/dedplay-studyo:latest

# epubcheck (W3C resmî EPUB denetimi) için Java
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless \
    && rm -rf /var/lib/apt/lists/*
ADD https://github.com/w3c/epubcheck/releases/download/v5.4.0/epubcheck-5.4.0.zip /tmp/epubcheck.zip
RUN python -c "import zipfile; zipfile.ZipFile('/tmp/epubcheck.zip').extractall('/opt')" && rm /tmp/epubcheck.zip \
    && java -jar /opt/epubcheck-5.4.0/epubcheck.jar --version

ENV PYTHONUNBUFFERED=1 DATA_DIR=/data EPUBCHECK=/opt/epubcheck-5.4.0/epubcheck.jar \
    FONT_DIR=/usr/share/fonts/truetype/amiri
WORKDIR /app
# OCR motoru: Surya 0.14.7 (Türkçe ve Arapçayı aynı satırda okur; işlemcide çalışır). torch/torchvision işlemci
# sürümü ve birbiriyle uyumlu olmalı: Surya'dan sonra ikisi birlikte işlemci deposundan yeniden kurulur.
RUN pip install --no-cache-dir "surya-ocr==0.14.7" "pillow<11" \
    && pip install --no-cache-dir --force-reinstall torch torchvision --index-url https://download.pytorch.org/whl/cpu
ENV OCR_MOTORU=surya MODEL_CACHE_DIR=/data/modeller/surya TORCH_DEVICE=cpu
COPY kutuphane ./kutuphane
EXPOSE 8000
CMD ["uvicorn", "kutuphane.main:app", "--host", "0.0.0.0", "--port", "8000"]
