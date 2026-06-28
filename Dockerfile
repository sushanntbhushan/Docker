FROM python:3.9
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENTRYPOINT ["/bin/sh", "-c", "python app.py & sleep 5 && python admin_creation.py && wait"]
