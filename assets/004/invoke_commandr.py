import json

import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")

model_id = "cohere.command-r-v1:0"
prompt = "富士山について教えて．"

# Format the request payload using the model's native structure.
native_request = {
    "message": prompt,
    "max_tokens": 512,
    "temperature": 0.5,
}

# Convert the native request to JSON.
request = json.dumps(native_request)

# Invoke the model with the request.
response = client.invoke_model(modelId=model_id, body=request)
model_response = json.loads(response["body"].read())

# Extract and print the response text.
response_text = model_response["text"]
print(response_text)
