from google.cloud import secretmanager

def create_secret(project_id, secret_id, secret_value):
    client = secretmanager.SecretManagerServiceClient()
    
    parent = f"projects/{project_id}"
    
    secret = client.create_secret(
        request={
            "parent": parent,
            "secret_id": secret_id,
            "secret": {"replication": {"automatic": {}}},
        }
    )
    
    response = client.add_secret_version(
        request={
            "parent": secret.name,
            "payload": {"data": secret_value.encode("UTF-8")},
        }
    )
    
    print(f"Secret {secret_id} created successfully.")
    print(f"Secret version: {response.name}")

def setup_secrets():
    project_id = "PROJECT_ID"  # あなたのプロジェクトID
    
    # 各種APIキーの保存
    create_secret(project_id, "line-channel-secret", "YOUR_LINE_CHANNEL_SECRET")
    create_secret(project_id, "line-channel-access-token", "YOUR_LINE_CHANNEL_ACCESS_TOKEN")
    create_secret(project_id, "gemini-api-key", "YOUR_GOOGLE_GEMINI_API_KEY")

if __name__ == "__main__":
    setup_secrets()
