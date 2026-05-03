import requests

res = requests.post('http://localhost:8000/api/fs/mkdir', json={"path": "test_folder_from_python"})
print(res.status_code)
print(res.text)
