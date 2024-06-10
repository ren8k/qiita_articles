class ToolsList:
    def get_weather(prefecture, city):
        """
        指定された都道府県と市の天気情報を取得する関数。

        引数:
        - prefecture (str): 都道府県名を表す文字列。
        - city (str): 市区町村名を表す文字列。

        返り値:
        - result (str): 指定された都道府県と市の天気情報を含む文字列。
        """
        result = f"{prefecture}, {city} の天気は晴れで，最高気温は22度です．"
        return result


tool_definition = {
    "toolSpec": {
        "name": "get_weather",
        "description": "指定された場所の天気を取得します。",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "prefecture": {
                        "type": "string",
                        "description": "指定された場所の都道府県",
                    },
                    "city": {
                        "type": "string",
                        "description": "指定された場所の市区町村",
                    },
                },
                "required": ["prefecture", "city"],
            }
        },
    }
}


def main():
    from pprint import pprint

    import boto3

    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    prompt = "東京都墨田区の天気は？"
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
        },
    )
    pprint(response)
    messages.append(response["output"]["message"])

    def extract_tool_use(content):
        for item in content:
            if "toolUse" in item:
                return item["toolUse"]
        return None

    response_content = response["output"]["message"]["content"]

    # toolUseを抽出
    tool_use = extract_tool_use(response_content)
    # tool_nameを使って対応する関数を取得し、実行する
    tool_func = getattr(ToolsList, tool_use["name"])
    tool_result = tool_func(**tool_use["input"])
    print(tool_result)

    # 結果を Claude3 に送信
    tool_result_message = {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": tool_use["toolUseId"],
                    "content": [{"text": tool_result}],
                }
            }
        ],
    }
    messages.append(tool_result_message)
    response = client.converse(
        modelId=model_id,
        messages=messages,
        toolConfig={
            "tools": [tool_definition],
        },
    )
    pprint(response)
    messages.append(response["output"]["message"])
    print("#" * 50)
    pprint(messages)


if __name__ == "__main__":
    main()


hoge = hoge = [
    {
        "role": "user",
        "content": [{"text": "東京都墨田区の天気は？"}],
    },
    {
        "role": "assistant",
        "content": [
            {
                "toolUse": {
                    "input": {"city": "墨田区", "prefecture": "東京都"},
                    "name": "get_weather",
                    "toolUseId": "tooluse_UwHeZGCnSQusfLrwCp9CcQ",
                }
            },
        ],
    },
    {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "content": [
                        {
                            "text": "東京都, 墨田区 "
                            "の天気は晴れで，最高気温は22度です．"
                        }
                    ],
                    "toolUseId": "tooluse_UwHeZGCnSQusfLrwCp9CcQ",
                }
            }
        ],
    },
    {
        "role": "assistant",
        "content": [
            {
                "text": "分かりました。東京都墨田区の天気は晴れで、最高気温は22度だそうです。晴れの天気で気温も高めなので、過ごしやすい1日になりそうですね。外出する際は軽めの服装がおすすめです。"
            }
        ],
    },
]
