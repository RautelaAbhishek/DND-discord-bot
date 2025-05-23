import boto3
from botocore.exceptions import ClientError

def get_secret():
    secret_name = "dnd"
    region_name = "us-east-2"

    # Create a Secrets Manager client
    client = boto3.client("secretsmanager", region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        # Decrypts secret using the associated KMS key.
        if "SecretString" in get_secret_value_response:
            return get_secret_value_response["SecretString"]
        else:
            return get_secret_value_response["SecretBinary"]
    except ClientError as e:
        print(f"Error retrieving secret: {e}")
        return None
