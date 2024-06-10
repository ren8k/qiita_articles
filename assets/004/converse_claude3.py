import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")

model_id = "anthropic.claude-3-haiku-20240307-v1:0"
prompt = "富士山について教えて．"
messages = [
    {
        "role": "user",
        "content": [{"text": prompt}],
    }
]

# Send the message to the model, using a basic inference configuration.
response = client.converse(
    modelId=model_id,
    messages=messages,
    inferenceConfig={"maxTokens": 512, "temperature": 0.5, "topP": 0.9},
)

# Extract and print the response text.
response_text = response["output"]["message"]["content"][0]["text"]
print(response_text)
