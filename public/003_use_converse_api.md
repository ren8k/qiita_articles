---
title: Bedrock の Converse API と Streamlit で10分でチャットアプリを作成する
tags:
  - Python
  - AWS
  - bedrock
  - Streamlit
  - 生成AI
private: false
updated_at: '2024-05-31T17:53:28+09:00'
id: 0191f5e3f02b5b824df0
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

最近 SageMaker ではなく Bedrock で検証することが多くなった [@ren8k](https://qiita.com/ren8k) です。
本日（2024/05/31）深夜，Amazon Bedrock の新機能である [Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html) がリリースされました．本 API はチャット用途に特化しており，会話履歴が扱いやすい特徴がございます．加えて，本 API は [Streamlit の ChatUI 機能](https://docs.streamlit.io/develop/tutorials/llms/build-conversational-apps)との親和性が高く，非常に容易にチャットアプリを作成することが可能です．

本記事では，Converse API の基本的な機能と，実際に Streamlit を用いてチャットアプリを作成する場合の実装例をご紹介いたします．

https://aws.amazon.com/jp/about-aws/whats-new/2024/05/amazon-bedrock-new-converse-api/

https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html

## Converse API とは

Amazon Bedrock のモデルを利用して，チャットアプリケーションを容易に開発することが可能な API です．[InvokeModel API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html)との差分として，以下の特徴がございます．

- Bedrock のモデルを統一的なインターフェースで利用することができ，モデル固有の推論パラメータを気にせずモデルの切り替えが可能です．
- API リクエストの一部に，会話履歴（`role`と`content`の辞書）を含めることができ，マルチターンの対話が容易に行えます．
- 一部のモデルでは function calling にも対応しております．本日（2024/05/31）時点では以下が対応モデルです．
  - Anthropic Claude 3
  - Mistral AI Large
  - Cohere Command R / Command R+

なお，Converse API にはストリーミング用のメソッド（[ConverseStream](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html)）も存在しますが，本記事では通常の [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html) メソッド に焦点を当て解説いたします．

## API を利用してみる

以下に，API を利用するための Python コードを示します．なお，以下のコードは，AWS の公式ドキュメント [Use the Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)を参考にしており，簡単のため，必要最低限の処理のみ記載しております．

```python:converse_api.py
import boto3
from pprint import pprint

model_id = "anthropic.claude-3-haiku-20240307-v1:0"
system_prompt = "あなたは多くのデータにアクセス可能な経済学者です。"
prompt = "高インフレが国のGDPに与える影響について30文字で述べなさい。"

bedrock_client = boto3.client(service_name='bedrock-runtime', region_name='us-west-2')


# Message to send.
message = {
    "role": "user",
    "content": [{"text": prompt}]
}
messages = [message]
system_prompts = [{"text" : system_prompt}]

# Inference parameters to use.
temperature = 0.5
top_k = 200

# Base inference parameters to use.
inference_config = {"temperature": temperature}
# Additional inference parameters to use.
additional_model_fields = {"top_k": top_k}

# Send the message.
response = bedrock_client.converse(
    modelId=model_id,
    messages=messages,
    system=system_prompts,
    inferenceConfig=inference_config,
    additionalModelRequestFields=additional_model_fields
)
pprint(response)
print("=" * 30)

output_message = response['output']['message']

print(f"Role: {output_message['role']}")

for content in output_message['content']:
    print(f"Text: {content['text']}")

token_usage = response['usage']
print(f"Input tokens:  {token_usage['inputTokens']}")
print(f"Output tokens:  {token_usage['outputTokens']}")
print(f"Total tokens:  {token_usage['totalTokens']}")
print(f"Stop reason: {response['stopReason']}")

```

上記を実行した結果は以下となります．以降，コードの簡易説明を行います．

```
{'ResponseMetadata': {'HTTPHeaders': {'connection': 'keep-alive',
                                      'content-length': '289',
                                      'content-type': 'application/json',
                                      'date': 'Fri, 31 May 2024 06:33:30 GMT',
                                      'x-amzn-requestid': '6a518989-80a6-4a35-baa1-468dbe886ef8'},
                      'HTTPStatusCode': 200,
                      'RequestId': '6a518989-80a6-4a35-baa1-468dbe886ef8',
                      'RetryAttempts': 0},
 'metrics': {'latencyMs': 696},
 'output': {'message': {'content': [{'text': '高インフレは消費と投資を抑制し、経済成長を減速させ、国のGDPを低下させる。'}],
                        'role': 'assistant'}},
 'stopReason': 'end_turn',
 'usage': {'inputTokens': 57, 'outputTokens': 41, 'totalTokens': 98}}
==============================
Role: assistant
Text: 高インフレは消費と投資を抑制し、経済成長を減速させ、国のGDPを低下させる。
Input tokens:  57
Output tokens:  41
Total tokens:  98
Stop reason: end_turn
```

### メッセージ・会話履歴の送信

コードの以下の部分では，モデルに送信するメッセージを定義しており，話者のロールと会話内容を含んでいます．

```python
message = {
    "role": "user",
    "content": [{"text": prompt}]
}
messages = [message] # include chat history
```

なお，マルチターンの対話を行う場合は，引数`messages`に以下のように`user`と`assistant`のメッセージ（会話履歴）を交互に格納したリストを渡す必要があります．

```python
[
    {
        "role": "user",
        "content": [{"text": "<ユーザーのプロンプト>"}]
    },
    {
        "role": "assistant",
        "content": [{"text": "<LLMの生成内容>"}]
    }
]
```

ここで，Converse API のレスポンス中の`output`フィールドを見ると，以下のように，`role` (assistant)と`content` (text)が含まれています．

```
{'message': {'content': [{'text': '高インフレは消費と投資を抑制し、経済成長を減速させ、国のGDPを低下させる。'}],
             'role': 'assistant'}},
```

つまり，チャットアプリを作成する際には，レスポンスの`output`の要素をリスト`messages`に append することで，容易に会話履歴を API に送信できそうです．

### 推論パラメータの設定

コードの以下の部分では，推論パラメータを定義しております．

```python
# Inference parameters to use.
temperature = 0.5
top_k = 200

# Base inference parameters to use.
inference_config = {"temperature": temperature}
# Additional inference parameters to use.
additional_model_fields = {"top_k": top_k}
```

Conversation API では，パラメータ`inference_config`に対し，辞書の形式で以下の推論パラメータを指定することが可能です．

- maxTokens: 生成トークンの最大数
- stopSequences: 停止シーケンスのリスト
- temperature: 温度パラメータ
- topP: 予測トークンの予測確率の累積値

`top_k`のようなモデル固有の推論パラメータを指定したい場合，引数`additionalModelRequestFields`に辞書形式で指定することが可能です．

### レスポンスについて

整形したレスポンスを以下に再掲いたします．

```json
{
  "ResponseMetadata": {
    "HTTPHeaders": {
      "connection": "keep-alive",
      "content-length": "289",
      "content-type": "application/json",
      "date": "Fri, 31 May 2024 06:33:30 GMT",
      "x-amzn-requestid": "6a518989-80a6-4a35-baa1-468dbe886ef8"
    },
    "HTTPStatusCode": 200,
    "RequestId": "6a518989-80a6-4a35-baa1-468dbe886ef8",
    "RetryAttempts": 0
  },
  "metrics": { "latencyMs": 696 },
  "output": {
    "message": {
      "content": [
        {
          "text": "高インフレは消費と投資を抑制し、経済成長を減速させ、国のGDPを低下させる。"
        }
      ],
      "role": "assistant"
    }
  },
  "stopReason": "end_turn",
  "usage": { "inputTokens": 57, "outputTokens": 41, "totalTokens": 98 }
}
```

前述の通り，`output`フィールドに，生成されたメッセージが含まれており，`role` (assistant)と`content` (text)が含まれています．また，`usage`フィールドには，入力トークン数，出力トークン数，合計トークン数が含まれています．

コードでは，以下の部分で，LLM の生成内容のみを出力しております．

```python
for content in output_message['content']:
    print(f"Text: {content['text']}")
```

:::note info
個人的な印象として，`output`フィールドのロールとメッセージ内容が構造的に保持されている点が，[Streamlit の ChatUI 機能](https://docs.streamlit.io/develop/tutorials/llms/build-conversational-apps)との親和性が非常に高いと感じております．
:::

## チャットアプリを作成する

Converse API を利用し，70 行未満の Python コードでチャットアプリを作成します．以下の手順でアプリケーションを作成してみましょう．

:::note info
簡単のため，コードでは最低限の機能のみを実装しております．
:::

- 以下を実行し，必要なライブラリをインストールします．

```bash
pip install "streamlit>=1.35.0" "boto3>=1.34.116"
```

- 以下のコードを `app.py` として保存します．

```python:app.py
import boto3
import streamlit as st


class CFG:
    model_id = "anthropic.claude-3-haiku-20240307-v1:0"
    system_prompt = "あなたは多くのデータにアクセス可能な経済学者です。"
    temperature = 0.5
    top_k = 200


@st.cache_resource
def get_bedrock_client():
    return boto3.client(service_name="bedrock-runtime", region_name="us-west-2")


def generate_response(messages):
    bedrock_client = get_bedrock_client()
    system_prompts = [{"text": CFG.system_prompt}]

    inference_config = {"temperature": CFG.temperature}
    additional_model_fields = {"top_k": CFG.top_k}

    response = bedrock_client.converse(
        modelId=CFG.model_id,
        messages=messages,
        system=system_prompts,
        inferenceConfig=inference_config,
        additionalModelRequestFields=additional_model_fields,
    )

    return response["output"]["message"]


def display_history(messages):
    for message in st.session_state.messages:
        display_msg_content(message)


def display_msg_content(message):
    with st.chat_message(message["role"]):
        st.write(content["text"] for content in message["content"])


def main():
    st.title("Bedrock Conversation API Chatbot")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    display_history(st.session_state.messages)

    if prompt := st.chat_input("What's up?"):
        input_msg = {"role": "user", "content": [{"text": prompt}]}
        display_msg_content(input_msg)
        st.session_state.messages.append(input_msg)

        response_msg = generate_response(st.session_state.messages)
        display_msg_content(response_msg)
        st.session_state.messages.append(response_msg)


if __name__ == "__main__":
    main()
```

- 以下のコマンドを実行し，アプリケーションを起動します．

```bash
streamlit run app.py
```

- 以下のような画面が表示されます．

![001.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/e7534218-0252-3b02-d38e-8eab81f44c89.png)

- チャット欄にメッセージを入力すると，Claude3 Haiku との会話が可能です．

![002.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/1e0ca0f2-7245-9157-0511-3ae3d4e5a429.png)

![003.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/829771b4-4402-4c4c-440b-d6dc6714a0b4.png)

- 会話履歴を保持できていることも確認できます．

![004.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/be4c1717-3b55-0ce3-69c9-07507c360c21.png)

![005.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/2a3573e1-12d6-f3b2-a956-4c632c9842fd.png)

### コードの簡易説明

関数`display_msg_content`で利用している`st.chat_message`は，以下のようにメッセージの話者（`user` or `assistant`）を渡すことで，メッセージ内容を ChatGPT ライクに表示することが可能です．Converse API のレスポンスの`output`フィールドの`role`と`content`を引数に渡すだけで，メッセージ内容を容易に表示可能です．

```python
def display_msg_content(message):
    with st.chat_message(message["role"]):
        st.write(content["text"] for content in message["content"])
```

また，チャット履歴は，`st.session_state`を用いて保持しており，`st.session_state.messages`に Converse API の`output`フィールドの中身を append しています．

```python
input_msg = {"role": "user", "content": [{"text": prompt}]}
display_msg_content(input_msg)
st.session_state.messages.append(input_msg)

response_msg = generate_response(st.session_state.messages)
display_msg_content(response_msg)
st.session_state.messages.append(response_msg)
```

参考に，会話履歴（`st.session_state.messages`）の中身の例を示します．

```json
[
  {
    "role": "user",
    "content": [
      { "text": "高インフレが国のGDPに与える影響について30文字で述べなさい。" }
    ]
  },
  {
    "role": "assistant",
    "content": [
      {
        "text": "高インフレは消費と投資を抑制し、経済成長を阻害する。国のGDPは低下する。"
      }
    ]
  },
  { "role": "user", "content": [{ "text": "具体的には？" }] },
  {
    "role": "assistant",
    "content": [
      {
        "text": "高インフレは以下のようにGDPに影響を与えます:\n\n- 消費者の購買力が低下し、個人消費が減少する\n- 企業の投資意欲が冷え込み、設備投資が抑制される\n- 輸出競争力が低下し、純輸出が減少する\n- 金融政策の引き締めにより、経済全体の活動が停滞する\n- 結果として、国内総生産(GDP)の伸びが鈍化または減少する\n\nつまり、高インフレは消費、投資、輸出などの需要を減退させ、経済成長の足かせとなるのです。"
      }
    ]
  },
  {
    "role": "user",
    "content": [{ "text": "冒頭で，私は何と質問しましたか？" }]
  },
  {
    "role": "assistant",
    "content": [
      {
        "text": "冒頭で、あなたは「高インフレが国のGDPに与える影響について30文字で述べなさい」と質問されました。"
      }
    ]
  }
]
```

## まとめ

本記事では，Amazon Bedrock の新機能である Converse API の基本的な使い方と，Streamlit を用いたチャットアプリの実装例をご紹介いたしました．本チャットアプリで，モデルを切り替えたり，ストリーミング処理機能を追加すると，応用的な利用ができそうです．Bedrock のアップデートは日々激しいので，今後もキャッチアップした内容をご共有いたします．

<!--

## 仲間募集

NTT データ デザイン＆テクノロジーコンサルティング事業本部 では、以下の職種を募集しています。

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
https://enterprise-aiiot.nttdata.com/tdf/
最新のクラウド技術を採用して弊社が独自に設計したリファレンスアーキテクチャ（Datalake+DWH+AI/BI）を顧客要件に合わせてカスタマイズして提供します。
可視化、機械学習、DeepLearning などデータ資産を分析活用するための環境がオールインワンで用意されており、これまでとは別次元の量と質のデータを用いてアジリティ高く DX 推進を実現できます。

</div></details>

<details><summary> TDF-AM（Trusted Data FoundationⓇ - Analytics Managed Service）について</summary><div>

～データ活用基盤の段階的な拡張支援（Quick Start) と保守運用のマネジメント（Analytics Managed）をご提供することでお客様の DX を成功に導く、データ活用プラットフォームサービス～
https://enterprise-aiiot.nttdata.com/service/tdf/tdf_am
TDFⓇ-AM は、データ活用を Quick に始めることができ、データ活用の成熟度に応じて段階的に環境を拡張します。プラットフォームの保守運用は NTT データが一括で実施し、お客様は成果創出に専念することが可能です。また、日々最新のテクノロジーをキャッチアップし、常に活用しやすい環境を提供します。なお、ご要望に応じて上流のコンサルティングフェーズから AI/BI などのデータ活用支援に至るまで、End to End で課題解決に向けて伴走することも可能です。

</div></details>

<details><summary>NTTデータとTableauについて </summary><div>

ビジュアル分析プラットフォームの Tableau と 2014 年にパートナー契約を締結し、自社の経営ダッシュボード基盤への採用や独自のコンピテンシーセンターの設置などの取り組みを進めてきました。さらに 2019 年度には Salesforce とワンストップでのサービスを提供開始するなど、積極的にビジネスを展開しています。

これまで Partner of the Year, Japan を 4 年連続で受賞しており、2021 年にはアジア太平洋地域で最もビジネスに貢献したパートナーとして表彰されました。
また、2020 年度からは、Tableau を活用したデータ活用促進のコンサルティングや導入サービスの他、AI 活用やデータマネジメント整備など、お客さまの企業全体のデータ活用民主化を成功させるためのノウハウ・方法論を体系化した「デジタルサクセス」プログラムを提供開始しています。
https://enterprise-aiiot.nttdata.com/service/tableau

</div></details>

<details><summary>NTTデータとAlteryxについて </summary><div>
Alteryxは、業務ユーザーからIT部門まで誰でも使えるセルフサービス分析プラットフォームです。

Alteryx 導入の豊富な実績を持つ NTT データは、最高位にあたる Alteryx Premium パートナーとしてお客さまをご支援します。

導入時のプロフェッショナル支援など独自メニューを整備し、特定の業種によらない多くのお客さまに、Alteryx を活用したサービスの強化・拡充を提供します。

https://enterprise-aiiot.nttdata.com/service/alteryx

</div></details>

<details><summary>NTTデータとDataRobotについて </summary><div>
DataRobotは、包括的なAIライフサイクルプラットフォームです。

NTT データは DataRobot 社と戦略的資本業務提携を行い、経験豊富なデータサイエンティストが AI・データ活用を起点にお客様のビジネスにおける価値創出をご支援します。

https://enterprise-aiiot.nttdata.com/service/datarobot

</div></details>

<details><summary> NTTデータとInformaticaについて</summary><div>

データ連携や処理方式を専門領域として 10 年以上取り組んできたプロ集団である NTT データは、データマネジメント領域でグローバルでの高い評価を得ている Informatica 社とパートナーシップを結び、サービス強化を推進しています。
https://enterprise-aiiot.nttdata.com/service/informatica

</div></details>

<details><summary>NTTデータとSnowflakeについて </summary><div>
NTTデータでは、Snowflake Inc.とソリューションパートナー契約を締結し、クラウド・データプラットフォーム「Snowflake」の導入・構築、および活用支援を開始しています。

NTT データではこれまでも、独自ノウハウに基づき、ビッグデータ・AI など領域に係る市場競争力のあるさまざまなソリューションパートナーとともにエコシステムを形成し、お客さまのビジネス変革を導いてきました。
Snowflake は、これら先端テクノロジーとのエコシステムの形成に強みがあり、NTT データはこれらを組み合わせることでお客さまに最適なインテグレーションをご提供いたします。

https://enterprise-aiiot.nttdata.com/service/snowflake

</div></details>
-->
