import os
from google.oauth2 import service_account

# Point to your service account JSON file
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "../podcast-453414-c05b2436ab0b.json"

credentials = service_account.Credentials.from_service_account_file(
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
)

print("Authenticated successfully!")

