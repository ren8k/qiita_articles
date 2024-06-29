tool_name = "record_image_summary"

description = """
整形式JSONを使用して画像の要約を記録する。
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
                                    "description": "赤の値 [0.0, 1.0]",
                                },
                                "g": {
                                    "type": "number",
                                    "description": "緑の値 [0.0, 1.0]",
                                },
                                "b": {
                                    "type": "number",
                                    "description": "青の値 [0.0, 1.0]",
                                },
                                "name": {
                                    "type": "string",
                                    "description": 'スネークケースの人間が読める色の名前、例: "olive_green" や "turquoise"',
                                },
                            },
                            "required": ["r", "g", "b", "name"],
                        },
                        "description": "画像の主要な色。4色未満に制限してください。",
                    },
                    "description": {
                        "type": "string",
                        "description": "画像の説明。1〜2文程度。",
                    },
                    "estimated_year": {
                        "type": "integer",
                        "description": "写真の場合、撮影された年の推定値。画像がフィクションではないと思われる場合にのみ設定してください。おおよその推定で構いません!",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'Array of topics, e.g. ["building-name", "region"]. Should be as specific as possible, and can overlap.',
                    },
                },
                "required": ["key_colors", "description", "tags"],
            }
        },
    }
}

tool_choice = {
    "tool": {
        "name": tool_name,
    },
}


def main():
    from pprint import pprint

    import boto3

    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    image_path = "./skytree.jpeg"
    prompt = f"""
    {tool_name} ツールのみを利用すること．
    """
    print(prompt)
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

    # Send the message to the model, using a basic inference configuration.
    response = client.converse(
        modelId=model_id,
        messages=messages,
        toolConfig={
            "tools": [tool_definition],
            "toolChoice": tool_choice,
        },
    )
    pprint(response)
    messages.append(response["output"]["message"])

    def extract_tool_use_args(content):
        for item in content:
            if "toolUse" in item:
                return item["toolUse"]["input"]
        return None

    response_content = response["output"]["message"]["content"]

    # toolUseを抽出
    tool_use_args = extract_tool_use_args(response_content)
    pprint(tool_use_args)
    # for key, value in tool_use_args.items():
    #     print(f"{key}: {value}")
    #     print(f"{key}: {type(value)}")


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
