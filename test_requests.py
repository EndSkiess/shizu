import requests
import os

url = "https://a.free.shizubot.ravendb.cloud/databases"
cert_path = r"c:\Users\USER\Documents\Shizu\free.shizubot.client.certificate\PEM\free.shizubot.client.certificate.pem"

print(f"Testing connection to {url} using {cert_path}...")

try:
    # Use the PEM file as both cert and key, and disable compression
    response = requests.get(url, cert=cert_path, timeout=10, headers={'Accept-Encoding': 'identity'})
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text[:500]}")
except Exception as e:
    print(f"Request failed: {e}")
