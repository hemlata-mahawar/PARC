# broker_url ="redis://localhost:6379/0"
# result_backend = "redis://localhost:6379/1"
# Timezone = "Asia/Kolkata"

from os import getenv

broker_url = getenv("CELERY_BROKER_URL")
result_backend = getenv("CELERY_RESULT_BACKEND")

timezone = "Asia/Kolkata"

broker_connection_retry_on_startup = True