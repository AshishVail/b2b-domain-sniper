
# B2B Domain Sniper
# Apify Python 3.13 runtime

FROM apify/actor-python:3.13

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /home/myuser

COPY --chown=myuser:myuser requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=myuser:myuser . ./

CMD ["python", "-m", "src"]
