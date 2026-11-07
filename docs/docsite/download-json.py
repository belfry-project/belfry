import requests

downloads = [
    # The OpenAPI schema of the latest Belfry release, attached by .github/workflows/api_schema_release.yml
    {"url": "https://github.com/belfry-project/belfry/releases/latest/download/schema.json", "path": "./docs/docsite/rst/open_api/schema.json"},
]

for item in downloads:
    url = item["url"]
    filepath = item["path"]

    response = requests.get(url, timeout=60)
    # Fail the docs build rather than publish the manual without the schema
    response.raise_for_status()

    with open(filepath, 'wb') as file:
        file.write(response.content)
    print(f"JSON file downloaded to {filepath}")
