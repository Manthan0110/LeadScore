import requests

resp = requests.post("http://127.0.0.1:8080/score", json={
    "company_size": "large",
    "engagement": {"email_clicks": 3},
    "last_contact_days": 7
})
print(resp.json())
