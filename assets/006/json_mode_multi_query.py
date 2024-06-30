description = """
与えられる質問文に基づいて、類義語や日本語と英語の表記揺れを考慮し、多角的な視点からクエリを生成します。
検索エンジンに入力するクエリを最適化し、様々な角度から検索を行うことで、より適切で幅広い検索結果が得られるようにします。

<example>
question: Knowledge Bases for Amazon Bedrock ではどのベクトルデータベースを使えますか？
query_1: Knowledge Bases for Amazon Bedrock vector databases engine DB
query_2: Amazon Bedrock ナレッジベース ベクトルエンジン vector databases DB
query_3: Amazon Bedrock RAG 検索拡張生成 埋め込みベクトル データベース エンジン
</example>

<rule>
- 与えられた質問文に基づいて、3個の検索用クエリを生成してください。
- 各クエリは30トークン以内とし、日本語と英語を適切に混ぜて使用すること。
- 広範囲の文書が取得できるよう、多様な単語をクエリに含むこと。
</rule>
"""
tool_name = "multi_query_generator"

tool_definition = {
    "toolSpec": {
        "name": tool_name,
        "description": description,
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "query_1": {
                        "type": "string",
                        "description": "検索用クエリ。多様な単語を空白で区切って記述される。",
                    },
                    "query_2": {
                        "type": "string",
                        "description": "検索用クエリ。多様な単語を空白で区切って記述される。",
                    },
                    "query_3": {
                        "type": "string",
                        "description": "検索用クエリ。多様な単語を空白で区切って記述される。",
                    },
                },
                "required": ["query_1", "query_2", "query_3"],
            }
        },
    }
}

# tool_choice = {
#     "tool": {
#         "name": tool_name,
#     },
# }


def main():
    import json
    from pprint import pprint

    import boto3

    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    target_text = "Amazon Kendra がサポートしているユーザーアクセス制御の方法は"
    prompt = f"""
    <text>
    {target_text}
    </text>

    {tool_name} ツールのみを利用すること。
    """
    print(prompt)
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


"""
{'query_1': 'Amazon Kendra user access control methods',
 'query_2': 'Amazon Kendra ユーザーアクセス制御 方式',
 'query_3': 'Amazon Kendra アクセス制御 制限 セキュリティ'}

"""
