tool_name = "print_sentiment_scores"
description = "与えられたテキストの感情スコアを出力します。"

tool_definition = {
    "toolSpec": {
        "name": tool_name,
        "description": description,
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "positive_score": {
                        "type": "number",
                        "description": "ポジティブな感情のスコアで、0.0から1.0の範囲です。",
                    },
                    "negative_score": {
                        "type": "number",
                        "description": "ネガティブな感情のスコアで、0.0から1.0の範囲です。",
                    },
                    "neutral_score": {
                        "type": "number",
                        "description": "中立的な感情のスコアで、0.0から1.0の範囲です。",
                    },
                },
                "required": ["positive_score", "negative_score", "neutral_score"],
            }
        },
    }
}

# tool_choice = {
#     "tool": {
#         "name": "print_sentiment_scores",
#     },
# }


def main():
    import json
    from pprint import pprint

    import boto3

    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    target_text = "私はとても幸せです。"

    prompt = f"""
    <text>
    {target_text}
    </text>

    {tool_name} ツールのみを利用すること。
    """

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
        toolConfig={
            "tools": [tool_definition],
            "toolChoice": {
                "tool": {
                    "name": tool_name,
                },
            },
        },
    )
    pprint(response)

    def extract_tool_use_args(content):
        for item in content:
            if "toolUse" in item:
                return item["toolUse"]["input"]
        return None

    response_content = response["output"]["message"]["content"]

    # json部を抽出
    tool_use_args = extract_tool_use_args(response_content)
    print(json.dumps(tool_use_args, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
