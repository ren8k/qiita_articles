---
title: Amazon Bedrock から 4 つの方法で gpt-oss を streaming で利用する
tags:
  - AWS
  - bedrock
  - Python
  - OpenAI
  - 生成AI
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デジタルサクセスソリューション事業部の [@ren8k](https://qiita.com/ren8k) です．
2025/08/05 に，OpenAI が提供する OSS モデルである gpt-oss-120b と gpt-oss-20b が Amazon Bedrock で利用可能になりました．

https://aws.amazon.com/jp/blogs/aws/openai-open-weight-models-now-available-on-aws

リリース当時，ストリーミングには未対応でしたが，[先日ストリーミングに対応](https://x.com/_watany/status/1956330543265742859)しました．本記事では，以下の API やフレームワークから gpt-oss をストリーミングで利用するためのサンプルコードを紹介します．

- [Amazon Bedrock ConverseStream API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html)
- [OpenAI Completions API](https://platform.openai.com/docs/guides/completions)
- [Strands Agents](https://strandsagents.com/latest/)
  - strands.models.BedrockModel
  - strands.models.OpenAIModel

なお，実装については，以下の GitHub リポジトリにサンプルコードを公開しています．是非御覧下さい．

https://github.com/ren8k/aws-gpt-oss-samples/tree/main

## Bedrock ConverseStream API

```python
import boto3

MODEL_ID = "openai.gpt-oss-20b-1:0"


def main() -> None:
    client = boto3.client("bedrock-runtime", region_name="us-west-2")
    system = [{"text": "質問に対して日本語で回答してください。"}]
    messages = [
        {
            "role": "user",
            "content": [{"text": "3.11と3.9はどちらが大きいですか？"}],
        }
    ]
    inference_config = {"maxTokens": 1024, "temperature": 1.0, "topP": 1.0}
    additional_confg = {"reasoning_effort": "medium"}
    response = client.converse_stream(
        modelId=MODEL_ID,
        system=system,
        messages=messages,
        inferenceConfig=inference_config,
        additionalModelRequestFields=additional_confg,
    )

    for chunk in response["stream"]:
        if "contentBlockDelta" in chunk:
            # get reasoningContent and final answer
            delta = chunk["contentBlockDelta"]["delta"]
            if "text" in delta:
                print(delta["text"], end="", flush=True)


if __name__ == "__main__":
    main()
```

ConverseStreaming API のレスポンスでは，Reasoning 部と最終的な出力が以下のフィールドで分離されており，非常に便利です．

- `reasoningContent`: Reasoning 部の出力
- `text`: 最終的な出力

しかし，執筆時点（2025/08/20）において，レスポンスの `text` フィールドに Reasoning 部と思われる出力が含まれることがあります．具体的には，`text` フィールド中に `<reasoning>` タグを含む回答が混ざることがあります．これは API 側のバグの可能性があり，いずれは修正されると考えられます．

<details><summary>chunk["contentBlockDelta"]["delta"] の出力例 (折りたたんでます)</summary>

```
{'reasoningContent': {'text': 'The user says: "3.11と3.'}}
{'reasoningContent': {'text': '9はどちらが大きいですか？" They want to know which is larger: 3.11 or 3.'}}
{'reasoningContent': {'text': '9. The difference is 0.01 vs 0.09 difference. So 3.9 is larger than 3.'}}
{'reasoningContent': {'text': "11? Actually 3.9 is greater than 3.11? Wait, let's compare approximately: 3.9 is "}}
{'reasoningContent': {'text': '3.9, 3.11 is 3.11. 3.9 > 3.11? Wait 3'}}
{'reasoningContent': {'text': '.9 vs 3.11? 3.9 = 3.9 > 3.11? That seems not correct.'}}
{'reasoningContent': {'text': ' Because 3.9 = 3.90. So 3.9 > 3.11? Wait carefully: 3'}}
{'reasoningContent': {'text': '.9 vs 3.11. We compare 3.90 vs 3.11. 3.9 > 3.'}}
{'reasoningContent': {'text': '11? Actually 3.9 is larger because 3.9 > 3.11? 3.9 = 3'}}
{'reasoningContent': {'text': '.90. 3.90 > 3.11. Because 3.90 - 3.11 = 0.'}}
{'text': '<reasoning>79 > 0. So yes 3.9 > 3.11.\n\nThus answer: 3.9 is greater than</reasoning>'}
{'text': "<reasoning> 3.11. How to reflect: It's a straightforward math question. The correct answer: 3.9 is larger.\n\nNeed to</reasoning>"}
{'reasoningContent': {'text': ' respond in Japanese. Provide answer.'}}
{'text': '3.9 のほうが大きいです。  \n3'}
{'text': '.9 は 3.90 に相当し、3.11 は 3.11 に相当しますので、3'}
{'text': '.90 の方が数値的に高いです。'}
{'text': ''}
```

</details>

## OpenAI Completions API

:::note
Completions API で Bedrock のモデルのエンドポイントを利用する場合，[Amazon Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started-api-keys.html) の発行が必要です．以下のコードでは，`.env` ファイル上で `AWS_BEARER_TOKEN_BEDROCK` という環境変数に Bedrock API keys を設定していることを前提としています．
:::

```python
import os

from dotenv import load_dotenv
from openai import OpenAI

TAG_OPEN = "<reasoning>"
MODEL_ID = "openai.gpt-oss-20b-1:0"
load_dotenv(override=True)


def main() -> None:
    client = OpenAI(
        base_url="https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1",
        api_key=os.getenv("AWS_BEARER_TOKEN_BEDROCK"),
    )
    messages = [
        {"role": "developer", "content": "質問に対して日本語で回答してください。"},
        {
            "role": "user",
            "content": "3.11と3.9はどちらが大きいですか？",
        },
    ]
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=messages,
        max_completion_tokens=1024,
        temperature=1.0,
        top_p=1.0,
        stream=True,
        reasoning_effort="medium",
    )

    for chunk in response:
        content = chunk.choices[0].delta.content
        if content and TAG_OPEN not in content:
            print(content, end="", flush=True)


if __name__ == "__main__":
    main()
```

Completions API のレスポンスでは，Reasoning 部と最終的な出力が分離されていません．しかし，レスポンスの `content` フィールドにおいて，Reasoning 部は全て `<reasoning>` で確実に囲まれるので，最終的な出力のみをうまくフィルタリングすることができます．

<details><summary>chunk.choices[0].delta.content の出力例 (折りたたんでます)</summary>

```
None
<reasoning>We need to respond in Japanese to the user question:</reasoning>
<reasoning> "3.11と3.9はどちらが大きいですか？" They ask which is greater, 3</reasoning>
<reasoning>.11 or 3.9. Which is larger? 3.11 vs 3.9. Compare decimal numbers: 3</reasoning>
<reasoning>.11 is 3.1100, 3.9 is 3.9000. 3.9 > 3</reasoning>
<reasoning>.11. So answer: 3.9が大きい。 Provide explanation perhaps converting to same decimal places: 3.11</reasoning>
<reasoning> vs 3.90. 3.90 > 3.11. So 3.9。同じ質問: "ど</reasoning>
<reasoning>ちらが大きいか" The answer: 3.9. Provide in Japanese. Let's do a concise answer.</reasoning>
3.9 のほうが大きいです。
3.11 は 3.1100
で、3.9 は 3.9000 ですから、3.9000 の方が数値として大きく
なります。
```

</details>

## Strands Agents (strands.models.BedrockModel)

```python
import asyncio

from strands import Agent
from strands.models import BedrockModel

MODEL_ID = "openai.gpt-oss-20b-1:0"


async def main() -> None:
    model = BedrockModel(
        model_id=MODEL_ID,
        params={"temperature": 1.0, "top_p": 1.0},
        additional_request_fields={"reasoning_effort": "medium"},
    )
    agent = Agent(
        model=model,
        system_prompt="質問に対して日本語で回答してください。",
        callback_handler=None,
    )
    response = agent.stream_async("3.11と3.9はどちらが大きいですか？")

    async for chunk in response:
        if "data" in chunk:
            # Strands splits the response into reasoningText and data.
            print(chunk["data"], end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
```

Strands Agents のレスポンスでは，Reasoning 部と最終的な出力が以下のフィールドで分離されており，非常に便利です．

- `reasoningText`: Reasoning 部の出力
- `data`: 最終的な出力

しかし，Strands Agents で `strands.models.BedrockModel` を利用する場合，内部では ConverseStreaming API が利用されるため，最終的な出力に Reasoning 部が混ざることがあります．

<details><summary>chunk の出力例 (折りたたんでます)</summary>

```
{'init_event_loop': True}
{'start': True}
{'start_event_loop': True}
{'event': {'messageStart': {'role': 'assistant'}}}
{'event': {'contentBlockDelta': {'delta': {'reasoningContent': {'text': 'We ask: "3.11と3.9'}}, 'contentBlockIndex': 0}}}
{'reasoningText': 'We ask: "3.11と3.9', 'delta': {'reasoningContent': {'text': 'We ask: "3.11と3.9'}}, 'reasoning': True, 'agent': <strands.agent.agent.Agent object at 0x71a95e0323c0>, 'event_loop_cycle_id': UUID('1acf9679-2dac-4128-a112-aa27750be77e'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x71a95de51fd0>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'reasoningContent': {'text': 'はどちらが大きいですか？" This is a simple numeric comparison. 3.11 is greater than 3.'}}, 'contentBlockIndex': 0}}}
{'reasoningText': 'はどちらが大きいですか？" This is a simple numeric comparison. 3.11 is greater than 3.', 'delta': {'reasoningContent': {'text': 'はどちらが大きいですか？" This is a simple numeric comparison. 3.11 is greater than 3.'}}, 'reasoning': True, 'agent': <strands.agent.agent.Agent object at 0x71a95e0323c0>, 'event_loop_cycle_id': UUID('1acf9679-2dac-4128-a112-aa27750be77e'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x71a95de51fd0>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'reasoningContent': {'text': '9? Wait, consider decimal: 3.11 = 3.110 ... 3.9 = 3.900, so'}}, 'contentBlockIndex': 0}}}
{'reasoningText': '9? Wait, consider decimal: 3.11 = 3.110 ... 3.9 = 3.900, so', 'delta': {'reasoningContent': {'text': '9? Wait, consider decimal: 3.11 = 3.110 ... 3.9 = 3.900, so'}}, 'reasoning': True, 'agent': <strands.agent.agent.Agent object at 0x71a95e0323c0>, 'event_loop_cycle_id': UUID('1acf9679-2dac-4128-a112-aa27750be77e'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x71a95de51fd0>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'reasoningContent': {'text': ' 3.9 is larger. So answer: 3.9>3.11. But depends: 3.11 vs '}}, 'contentBlockIndex': 0}}}
{'reasoningText': ' 3.9 is larger. So answer: 3.9>3.11. But depends: 3.11 vs ', 'delta': {'reasoningContent': {'text': ' 3.9 is larger. So answer: 3.9>3.11. But depends: 3.11 vs '}}, 'reasoning': True, 'agent': <strands.agent.agent.Agent object at 0x71a95e0323c0>, 'event_loop_cycle_id': UUID('1acf9679-2dac-4128-a112-aa27750be77e'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x71a95de51fd0>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'reasoningContent': {'text': '3.9. 3.9 > 3.11. So answer in Japanese with explanation.'}}, 'contentBlockIndex': 0}}}
{'reasoningText': '3.9. 3.9 > 3.11. So answer in Japanese with explanation.', 'delta': {'reasoningContent': {'text': '3.9. 3.9 > 3.11. So answer in Japanese with explanation.'}}, 'reasoning': True, 'agent': <strands.agent.agent.Agent object at 0x71a95e0323c0>, 'event_loop_cycle_id': UUID('1acf9679-2dac-4128-a112-aa27750be77e'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x71a95de51fd0>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockStop': {'contentBlockIndex': 0}}}
{'event': {'contentBlockDelta': {'delta': {'text': '`3.9` の方が大きいです。  \n- 3.11 は 3.110… と表され'}, 'contentBlockIndex': 1}}}
{'data': '`3.9` の方が大きいです。  \n- 3.11 は 3.110… と表され', 'delta': {'text': '`3.9` の方が大きいです。  \n- 3.11 は 3.110… と表され'}, 'agent': <strands.agent.agent.Agent object at 0x71a95e0323c0>, 'event_loop_cycle_id': UUID('1acf9679-2dac-4128-a112-aa27750be77e'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x71a95de51fd0>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': '、3.9 は 3.900… と表されます。  \n- 小数点以下の数字を比較すると、'}, 'contentBlockIndex': 1}}}
{'data': '、3.9 は 3.900… と表されます。  \n- 小数点以下の数字を比較すると、', 'delta': {'text': '、3.9 は 3.900… と表されます。  \n- 小数点以下の数字を比較すると、'}, 'agent': <strands.agent.agent.Agent object at 0x71a95e0323c0>, 'event_loop_cycle_id': UUID('1acf9679-2dac-4128-a112-aa27750be77e'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x71a95de51fd0>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': '3.900… のほうが 3.110… よりも大きいです。'}, 'contentBlockIndex': 1}}}
{'data': '3.900… のほうが 3.110… よりも大きいです。', 'delta': {'text': '3.900… のほうが 3.110… よりも大きいです。'}, 'agent': <strands.agent.agent.Agent object at 0x71a95e0323c0>, 'event_loop_cycle_id': UUID('1acf9679-2dac-4128-a112-aa27750be77e'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x71a95de51fd0>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': ''}, 'contentBlockIndex': 1}}}
{'data': '', 'delta': {'text': ''}, 'agent': <strands.agent.agent.Agent object at 0x71a95e0323c0>, 'event_loop_cycle_id': UUID('1acf9679-2dac-4128-a112-aa27750be77e'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x71a95de51fd0>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockStop': {'contentBlockIndex': 1}}}
{'event': {'messageStop': {'stopReason': 'end_turn'}}}
{'event': {'metadata': {'usage': {'inputTokens': 69, 'outputTokens': 222, 'totalTokens': 291}, 'metrics': {'latencyMs': 887}}}}
{'message': {'role': 'assistant', 'content': [{'reasoningContent': {'reasoningText': {'text': 'We ask: "3.11と3.9はどちらが大きいですか？" This is a simple numeric comparison. 3.11 is greater than 3.9? Wait, consider decimal: 3.11 = 3.110 ... 3.9 = 3.900, so 3.9 is larger. So answer: 3.9>3.11. But depends: 3.11 vs 3.9. 3.9 > 3.11. So answer in Japanese with explanation.', 'signature': ''}}}, {'text': '`3.9` の方が大きいです。  \n- 3.11 は 3.110… と表され、3.9 は 3.900… と表されます。  \n- 小数点以下の数字を比較すると、3.900… のほうが 3.110… よりも大きいです。'}]}}
{'result': AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': [{'reasoningContent': {'reasoningText': {'text': 'We ask: "3.11と3.9はどちらが大きいですか？" This is a simple numeric comparison. 3.11 is greater than 3.9? Wait, consider decimal: 3.11 = 3.110 ... 3.9 = 3.900, so 3.9 is larger. So answer: 3.9>3.11. But depends: 3.11 vs 3.9. 3.9 > 3.11. So answer in Japanese with explanation.', 'signature': ''}}}, {'text': '`3.9` の方が大きいです。  \n- 3.11 は 3.110… と表され、3.9 は 3.900… と表されます。  \n- 小数点以下の数字を比較すると、3.900… のほうが 3.110… よりも大きいです。'}]}, metrics=EventLoopMetrics(cycle_count=1, tool_metrics={}, cycle_durations=[1.367772102355957], traces=[<strands.telemetry.metrics.Trace object at 0x71a95de51fd0>], accumulated_usage={'inputTokens': 69, 'outputTokens': 222, 'totalTokens': 291}, accumulated_metrics={'latencyMs': 887}), state={})}
```

</details>

## Strands Agents (strands.models.OpenAIModel)

```python
import asyncio
import os

from dotenv import load_dotenv
from strands import Agent
from strands.models.openai import OpenAIModel

MODEL_ID = "openai.gpt-oss-20b-1:0"
load_dotenv(override=True)


async def main() -> None:
    model = OpenAIModel(
        client_args={
            "base_url": "https://bedrock-runtime.us-west-2.amazonaws.com/openai/v1",
            "api_key": os.getenv("AWS_BEARER_TOKEN_BEDROCK"),
        },
        # **model_config
        model_id=MODEL_ID,
        params={
            "max_completion_tokens": 1024,
            "temperature": 1.0,
            "top_p": 1.0,
            "reasoning_effort": "medium",
        },
    )
    agent = Agent(
        model=model,
        system_prompt="質問に対して日本語で回答してください。",
        callback_handler=None,
    )
    response = agent.stream_async("3.11と3.9はどちらが大きいですか？")

    async for event in response:
        if "data" in event:
            if "<reasoning>" not in event["data"]:
                print(event["data"], end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
```

Strands Agents の `strands.models.OpenAIModel` の内部実装では， OpenAI Completions API が利用されているので，レスポンスは Reasoning 部と最終的な出力が分離されていません．しかし，レスポンスの `data` フィールドにおいて，Reasoning 部は全て `<reasoning>` で確実に囲まれるので，最終的な出力のみをうまくフィルタリングすることができます．

<details><summary>event の出力例 (折りたたんでます)</summary>

```
{'init_event_loop': True}
{'start': True}
{'start_event_loop': True}
{'event': {'messageStart': {'role': 'assistant'}}}
{'event': {'contentBlockStart': {'start': {}}}}
{'event': {'contentBlockDelta': {'delta': {'text': '<reasoning>The user asks: "3.11と3</reasoning>'}}}}
{'data': '<reasoning>The user asks: "3.11と3</reasoning>', 'delta': {'text': '<reasoning>The user asks: "3.11と3</reasoning>'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': '<reasoning>.9はどちらが大きいですか？" ("Which is larger, 3.11 or 3.9</reasoning>'}}}}
{'data': '<reasoning>.9はどちらが大きいですか？" ("Which is larger, 3.11 or 3.9</reasoning>', 'delta': {'text': '<reasoning>.9はどちらが大きいですか？" ("Which is larger, 3.11 or 3.9</reasoning>'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': '<reasoning>?") It\'s a straightforward comparison: 3.11 > 3.9? Actually 3.11 is greater than 3.</reasoning>'}}}}
{'data': '<reasoning>?") It\'s a straightforward comparison: 3.11 > 3.9? Actually 3.11 is greater than 3.</reasoning>', 'delta': {'text': '<reasoning>?") It\'s a straightforward comparison: 3.11 > 3.9? Actually 3.11 is greater than 3.</reasoning>'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': "<reasoning>9? Wait 3.11 vs 3.9. 3.9 is greater than 3.11? Let's compare</reasoning>"}}}}
{'data': "<reasoning>9? Wait 3.11 vs 3.9. 3.9 is greater than 3.11? Let's compare</reasoning>", 'delta': {'text': "<reasoning>9? Wait 3.11 vs 3.9. 3.9 is greater than 3.11? Let's compare</reasoning>"}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': '<reasoning>: 3.9 = 3.90. 3.11 is 3.11. 3.9 > </reasoning>'}}}}
{'data': '<reasoning>: 3.9 = 3.90. 3.11 is 3.11. 3.9 > </reasoning>', 'delta': {'text': '<reasoning>: 3.9 = 3.90. 3.11 is 3.11. 3.9 > </reasoning>'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': '<reasoning>3.11 indeed. So answer: 3.9 is larger. Provide explanation. No other constraints.</reasoning>'}}}}
{'data': '<reasoning>3.11 indeed. So answer: 3.9 is larger. Provide explanation. No other constraints.</reasoning>', 'delta': {'text': '<reasoning>3.11 indeed. So answer: 3.9 is larger. Provide explanation. No other constraints.</reasoning>'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': '3.11 と 3.9 を比べると、**3.9 のほうが大きい**'}}}}
{'data': '3.11 と 3.9 を比べると、**3.9 のほうが大きい**', 'delta': {'text': '3.11 と 3.9 を比べると、**3.9 のほうが大きい**'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': 'です。  \n数値を小数点以下の桁で比較すると、3.9 は 3.90 と書け'}}}}
{'data': 'です。  \n数値を小数点以下の桁で比較すると、3.9 は 3.90 と書け', 'delta': {'text': 'です。  \n数値を小数点以下の桁で比較すると、3.9 は 3.90 と書け'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': 'ます。  \n3.90（3.9） と 3.11 を比較すると、小数第1位（10分'}}}}
{'data': 'ます。  \n3.90（3.9） と 3.11 を比較すると、小数第1位（10分', 'delta': {'text': 'ます。  \n3.90（3.9） と 3.11 を比較すると、小数第1位（10分'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': 'の1位）が 9 と 1 なので 9 の方が大きく、数字全体として 3.'}}}}
{'data': 'の1位）が 9 と 1 なので 9 の方が大きく、数字全体として 3.', 'delta': {'text': 'の1位）が 9 と 1 なので 9 の方が大きく、数字全体として 3.'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockDelta': {'delta': {'text': '9 の方が大きいと判断できます。'}}}}
{'data': '9 の方が大きいと判断できます。', 'delta': {'text': '9 の方が大きいと判断できます。'}, 'agent': <strands.agent.agent.Agent object at 0x7b2f96cba7b0>, 'event_loop_cycle_id': UUID('f96219e8-6d45-4296-96dd-b876b20ed9a5'), 'request_state': {}, 'event_loop_cycle_trace': <strands.telemetry.metrics.Trace object at 0x7b2f96b68440>, 'event_loop_cycle_span': NonRecordingSpan(SpanContext(trace_id=0x00000000000000000000000000000000, span_id=0x0000000000000000, trace_flags=0x00, trace_state=[], is_remote=False))}
{'event': {'contentBlockStop': {}}}
{'event': {'messageStop': {'stopReason': 'end_turn'}}}
{'event': {'metadata': {'usage': {'inputTokens': 69, 'outputTokens': 269, 'totalTokens': 338}, 'metrics': {'latencyMs': 0}}}}
{'message': {'role': 'assistant', 'content': [{'text': '<reasoning>The user asks: "3.11と3</reasoning><reasoning>.9はどちらが大きいですか？" ("Which is larger, 3.11 or 3.9</reasoning><reasoning>?") It\'s a straightforward comparison: 3.11 > 3.9? Actually 3.11 is greater than 3.</reasoning><reasoning>9? Wait 3.11 vs 3.9. 3.9 is greater than 3.11? Let\'s compare</reasoning><reasoning>: 3.9 = 3.90. 3.11 is 3.11. 3.9 > </reasoning><reasoning>3.11 indeed. So answer: 3.9 is larger. Provide explanation. No other constraints.</reasoning>3.11 と 3.9 を比べると、**3.9 のほうが大きい**です。  \n数値を小数点以下の桁で比較すると、3.9 は 3.90 と書けます。  \n3.90（3.9） と 3.11 を比較すると、小数第1位（10分の1位）が 9 と 1 なので 9 の方が大きく、数字全体として 3.9 の方が大きいと判断できます。'}]}}
{'result': AgentResult(stop_reason='end_turn', message={'role': 'assistant', 'content': [{'text': '<reasoning>The user asks: "3.11と3</reasoning><reasoning>.9はどちらが大きいですか？" ("Which is larger, 3.11 or 3.9</reasoning><reasoning>?") It\'s a straightforward comparison: 3.11 > 3.9? Actually 3.11 is greater than 3.</reasoning><reasoning>9? Wait 3.11 vs 3.9. 3.9 is greater than 3.11? Let\'s compare</reasoning><reasoning>: 3.9 = 3.90. 3.11 is 3.11. 3.9 > </reasoning><reasoning>3.11 indeed. So answer: 3.9 is larger. Provide explanation. No other constraints.</reasoning>3.11 と 3.9 を比べると、**3.9 のほうが大きい**です。  \n数値を小数点以下の桁で比較すると、3.9 は 3.90 と書けます。  \n3.90（3.9） と 3.11 を比較すると、小数第1位（10分の1位）が 9 と 1 なので 9 の方が大きく、数字全体として 3.9 の方が大きいと判断できます。'}]}, metrics=EventLoopMetrics(cycle_count=1, tool_metrics={}, cycle_durations=[1.9280362129211426], traces=[<strands.telemetry.metrics.Trace object at 0x7b2f96b68440>], accumulated_usage={'inputTokens': 69, 'outputTokens': 269, 'totalTokens': 338}, accumulated_metrics={'latencyMs': 0}), state={})}
```

</details>

## まとめ

Amazon Bedrock の gpt-oss を，Bedrock ConverseStream API，OpenAI Completions API，Strands Agents を通して利用する方法を紹介しました．執筆時点（2025/08/20）では，gpt-oss の最終的な回答と Reasoning 部を完全に分離するためには，OpenAI Completions API を利用すると良さそうです．

## 仲間募集

NTT データ テクノロジーコンサルティング事業本部 では、以下の職種を募集しています。

<details><summary>1. クラウド技術を活用したデータ分析プラットフォームの開発・構築(ITアーキテクト/クラウドエンジニア)</summary>

クラウド／プラットフォーム技術の知見に基づき、DWH、BI、ETL 領域におけるソリューション開発を推進します。
https://enterprise-aiiot.nttdata.com/recruitment/career_sp/cloud_engineer

</details>

<details><summary>2. データサイエンス領域（データサイエンティスト／データアナリスト）</summary>

データ活用／情報処理／AI／BI／統計学などの情報科学を活用し、よりデータサイエンスの観点から、データ分析プロジェクトのリーダーとしてお客様の DX／デジタルサクセスを推進します。
https://enterprise-aiiot.nttdata.com/recruitment/career_sp/datascientist

</details>

<details><summary>3.お客様のAI活用の成功を推進するAIサクセスマネージャー</summary>

DataRobot をはじめとした AI ソリューションやサービスを使って、
お客様の AI プロジェクトを成功させ、ビジネス価値を創出するための活動を実施し、
お客様内での AI 活用を拡大、NTT データが提供する AI ソリューションの利用継続を推進していただく人材を募集しています。
https://nttdata.jposting.net/u/job.phtml?job_code=804

</details>

<details><summary>4.DX／デジタルサクセスを推進するデータサイエンティスト《管理職/管理職候補》</summary>
データ分析プロジェクトのリーダとして、正確な課題の把握、適切な評価指標の設定、分析計画策定や適切な分析手法や技術の評価・選定といったデータ活用の具現化、高度化を行い分析結果の見える化・お客様の納得感醸成を行うことで、ビジネス成果・価値を出すアクションへとつなげることができるデータサイエンティスト人材を募集しています。

https://nttdata.jposting.net/u/job.phtml?job_code=898

</details>

## ソリューション紹介

<details><summary> Trusted Data Foundationについて</summary><div>

～データ資産を分析活用するための環境をオールインワンで提供するソリューション～
https://www.nttdata.com/jp/ja/lineup/tdf/
最新のクラウド技術を採用して弊社が独自に設計したリファレンスアーキテクチャ（Datalake+DWH+AI/BI）を顧客要件に合わせてカスタマイズして提供します。
可視化、機械学習、DeepLearning などデータ資産を分析活用するための環境がオールインワンで用意されており、これまでとは別次元の量と質のデータを用いてアジリティ高く DX 推進を実現できます。

</div></details>

<details><summary> TDFⓇ-AM（Trusted Data Foundation - Analytics Managed Service）について</summary><div>

～データ活用基盤の段階的な拡張支援 (Quick Start) と保守運用のマネジメント（Analytics Managed）をご提供することでお客様の DX を成功に導く、データ活用プラットフォームサービス～
https://www.nttdata.com/jp/ja/lineup/tdf_am/
TDFⓇ-AM は、データ活用を Quick に始めることができ、データ活用の成熟度に応じて段階的に環境を拡張します。プラットフォームの保守運用は NTT データが一括で実施し、お客様は成果創出に専念することが可能です。また、日々最新のテクノロジーをキャッチアップし、常に活用しやすい環境を提供します。なお、ご要望に応じて上流のコンサルティングフェーズから AI/BI などのデータ活用支援に至るまで、End to End で課題解決に向けて伴走することも可能です。

</div></details>

<details><summary> NTTデータとDatabricksについて </summary>
NTTデータは、お客様企業のデジタル変革・DXの成功に向けて、「databricks」のソリューションの提供に加え、情報活用戦略の立案から、AI技術の活用も含めたアナリティクス、分析基盤構築・運用、分析業務のアウトソースまで、ワンストップの支援を提供いたします。

https://www.nttdata.com/jp/ja/lineup/databricks/

</details>

<details><summary>NTTデータとTableauについて </summary><div>

ビジュアル分析プラットフォームの Tableau と 2014 年にパートナー契約を締結し、自社の経営ダッシュボード基盤への採用や独自のコンピテンシーセンターの設置などの取り組みを進めてきました。さらに 2019 年度には Salesforce とワンストップでのサービスを提供開始するなど、積極的にビジネスを展開しています。

これまで Partner of the Year, Japan を 4 年連続で受賞しており、2021 年にはアジア太平洋地域で最もビジネスに貢献したパートナーとして表彰されました。
また、2020 年度からは、Tableau を活用したデータ活用促進のコンサルティングや導入サービスの他、AI 活用やデータマネジメント整備など、お客さまの企業全体のデータ活用民主化を成功させるためのノウハウ・方法論を体系化した「デジタルサクセス」プログラムを提供開始しています。

https://www.nttdata.com/jp/ja/lineup/tableau/

</div></details>

<details><summary>NTTデータとAlteryxについて </summary><div>
Alteryxは、業務ユーザーからIT部門まで誰でも使えるセルフサービス分析プラットフォームです。

Alteryx 導入の豊富な実績を持つ NTT データは、最高位にあたる Alteryx Premium パートナーとしてお客さまをご支援します。

導入時のプロフェッショナル支援など独自メニューを整備し、特定の業種によらない多くのお客さまに、Alteryx を活用したサービスの強化・拡充を提供します。

https://www.nttdata.com/jp/ja/lineup/alteryx/

</div></details>

<details><summary>NTTデータとDataRobotについて </summary><div>
DataRobotは、包括的なAIライフサイクルプラットフォームです。

NTT データは DataRobot 社と戦略的資本業務提携を行い、経験豊富なデータサイエンティストが AI・データ活用を起点にお客様のビジネスにおける価値創出をご支援します。

https://www.nttdata.com/jp/ja/lineup/datarobot/

</div></details>

<details><summary> NTTデータとInformaticaについて</summary><div>

データ連携や処理方式を専門領域として 10 年以上取り組んできたプロ集団である NTT データは、データマネジメント領域でグローバルでの高い評価を得ている Informatica 社とパートナーシップを結び、サービス強化を推進しています。

https://www.nttdata.com/jp/ja/lineup/informatica/

</div></details>

<details><summary>NTTデータとSnowflakeについて </summary><div>
NTTデータでは、Snowflake Inc.とソリューションパートナー契約を締結し、クラウド・データプラットフォーム「Snowflake」の導入・構築、および活用支援を開始しています。

NTT データではこれまでも、独自ノウハウに基づき、ビッグデータ・AI など領域に係る市場競争力のあるさまざまなソリューションパートナーとともにエコシステムを形成し、お客さまのビジネス変革を導いてきました。
Snowflake は、これら先端テクノロジーとのエコシステムの形成に強みがあり、NTT データはこれらを組み合わせることでお客さまに最適なインテグレーションをご提供いたします。

https://www.nttdata.com/jp/ja/lineup/snowflake/

</div></details>
