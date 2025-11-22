from django.test import TestCase


import requests, json

API_KEY = "pub_619fe6b7598c49228a430b28ee8a8e22"
url = "https://newsdata.io/api/1/latest"
params = {
    "apikey": API_KEY,
    "q": "poland",
    "language": "en",
    "size": 5
}

r = requests.get(url, params=params, timeout=20)
data = r.json()

# Sadə “işləyirmi?” yoxlaması
ok = (r.status_code == 200) and (data.get("status") == "success")
print("API working:", ok)

# Gələn datadan qısa görünüş
print("results count:", len(data.get("results", [])))
for i, item in enumerate(data.get("results", []), start=1):
    print(f"{i}. {item.get('title')}")
    print("   link:", item.get("link"))
    print("   pubDate:", item.get("pubDate"))
