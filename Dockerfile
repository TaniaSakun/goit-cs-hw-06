FROM python:3.10 

ENV APP_HOME /app

WORKDIR /app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt


EXPOSE 5000

ENTRYPOINT ["python", "main.py"]