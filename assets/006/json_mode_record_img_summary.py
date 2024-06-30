tool_name = "record_image_summary"
description = """
与えられた画像を分析し、要約を記録します。
具体的には、以下の要素を含む要約をJSON形式で出力します。

<summary>
- key_colors: 画像で利用されている代表的なrgb値と色の名前のリスト。3~4色程度。
- description: 画像の説明。1~2文程度。
- estimated_year: 撮影された年の推定値
- tags: 画像のトピックのリスト。3~5個程度。
</summary>
"""

tool_definition = {
    "toolSpec": {
        "name": tool_name,
        "description": description,
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "key_colors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "r": {
                                    "type": "number",
                                    "description": "赤の値。値の範囲: [0.0, 255.0]",
                                },
                                "g": {
                                    "type": "number",
                                    "description": "緑の値。値の範囲: [0.0, 255.0]",
                                },
                                "b": {
                                    "type": "number",
                                    "description": "青の値。値の範囲: [0.0, 255.0]",
                                },
                                "name": {
                                    "type": "string",
                                    "description": 'スネークケースの人間が読める色の名前。例: "olive_green" や "turquoise" など。',
                                },
                            },
                            "required": ["r", "g", "b", "name"],
                        },
                        "description": "画像の主要な色。4色未満に制限すること。",
                    },
                    "description": {
                        "type": "string",
                        "description": "画像の説明。1〜2文程度。",
                    },
                    "estimated_year": {
                        "type": "integer",
                        "description": "写真の場合、撮影された年の推定値。画像がフィクションではないと思われる場合にのみ設定してください。おおよその推定で構いません。",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'トピックの配列。例えば ["building-name", "region"] など。。できるだけ具体的であるべきで、重複しても構いません。',
                    },
                },
                "required": ["key_colors", "description", "tags"],
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

    image_path = "./skytree.jpeg"
    prompt = f"""
    {tool_name} ツールのみを利用すること。
    """

    with open(image_path, "rb") as f:
        image = f.read()

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "image": {
                        "format": "jpeg",
                        "source": {"bytes": image},
                    }
                },
                {
                    "text": prompt,
                },
            ],
        }
    ]

    # Send the message to the model
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
{'description': '東京スカイツリーの夜景。ライトアップされたタワーと周辺の建物や木々が美しく映えています。',
 'estimated_year': 2022,
 'key_colors': [{'b': 0.3, 'g': 0.1, 'name': 'navy_blue', 'r': 0.1},
                {'b': 0.8, 'g': 0.8, 'name': 'turquoise', 'r': 0.0},
                {'b': 0.0, 'g': 0.8, 'name': 'golden_yellow', 'r': 1.0},
                {'b': 0.0, 'g': 0.5, 'name': 'dark_green', 'r': 0.0}],
 'tags': ['Tokyo Skytree',
          'night_view',
          'city_landmark',
          'illumination',
          'urban_landscape']}
"""
