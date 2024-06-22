---
title: 「Amazon Bedrock」で始める生成AIアプリ開発入門バイブルの登場！！
tags:
  - AWS
  - 技術書
  - bedrock
  - 生成AI
  - LLM
private: true
updated_at: '2024-06-22T23:55:13+09:00'
id: 6134d2457211e5a285c4
organization_url_name: null
slide: false
ignorePublish: false
---

:::note
本記事は，著者の@minorun365 さんよりご恵贈いただき，発売前の書籍レビューをするものです．
:::

## はじめに

幸運なことに，来週 6/26 発売予定の書籍『[Amazon Bedrock 生成 AI アプリ開発入門](https://www.sbcr.jp/product/4815626440/)』を @minorun365 さんからご恵贈賜りました．本記事では，学んだ点や特徴をまとめようと思います．

<img width="450" src="https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/73262961-2960-139b-b87a-26bde3763a06.jpeg">

## Amazon Bedrock 生成 AI アプリ開発入門

- 御田 稔 (著), 熊田 寛 (著), 森田 和明 (著)
- SB Creative より 2024/6/26 発売予定

https://amzn.asia/d/03xAyTFd

## 対象読者と所感

書名には "入門" とありますが，**あらゆるレベルの方が手に取ってみる価値がある**と思います．特に，**各章の Column には応用的な Tips** が散りばめられており，初学者から上級者まで幅広く楽しめる内容となっています．

また，どの章も初学者に親切な解説（用語の説明，全ページフルカラーでコンソールのスクリーンショットの添付）がなされており，スムーズに学習ができる内容となっております．

個人的に良いと思った点としては，以下が挙げられます．

- なぜ Amazon Bedrock を選ぶのか？という点にしっかり言及している
- 先進的で実践的な内容を幅広く学べる（chat app のサーバーレス化，RAG，Agent, Step Functions を利用したローコード開発...）

## なぜ Amazon Bedrock を選ぶのか？

本書では，Bedrock を選定する理由として，複数の会社が提供する最先端モデルを幅広く利用可能である点や，アプリケーション開発との親和性，本番利用に耐えうる高いセキュリティ・ガバナンスを挙げております．

以下に，[Chatbot Arena Leaderboard](https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard) のデータを基にした，直近リリースされた代表的な LLM のリリース日と性能を示します．縦軸が Chatbot Arena の Elo Rate (人間による評価)，横軸がリリース日です．また，赤色のプロットは，Amazon Bedrock で利用可能なモデルです．

![chatbot_arena_elo_scores.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/f42500a1-a1b5-106c-87d1-747db073a1e8.png)

図から，昨今，様々な企業から，GPT-3.5 を凌駕するモデルが短スパンでリリースされていることがわかります．Amazon Bedrock は提携社数が多く，様々な最先端の LLM を利用可能であり，ユースケースに応じて柔軟にモデルを使い分けることができます．加え，文章生成以外にも，画像生成やベクトル変換用のモデルも提供されております．また，Bedrock ではモデルのデプロイが不要のため，各社の多様な LLM をクイックかつ手軽に導入することが可能です．

GPT-4 などの特定の LLM に依存した生成 AI のサービス運用は，少なからずリスクが伴います．その他，AWS 外への接続が制限されており，AWS 環境外にデータを出せない場合，GPT-4 などのモデルは利用できません．これらの点も考慮すると，Amazon Bedrock を利用するメリットは大きいのではないでしょうか．

:::note warn
上記の散布図は，執筆時点（2024/06/22）のデータを基に作成しております．また，Claude3.5 Sonnet については，リリース直後のため Chatbot Arena のリーダーボードには表示されておりませんが，複数の指標において [GPT-4o を超える精度を達成した](https://www.anthropic.com/news/claude-3-5-sonnet)と報告されているため，スコアは筆者による推定値となっている点，ご了承下さい．
:::

:::note
上記の散布図において，Mistral-8x22b は Bedrock では利用できないように示しておりますが，[SageMaker JumpStart 経由で利用が可能](https://aws.amazon.com/jp/blogs/machine-learning/mixtral-8x22b-is-now-available-in-amazon-sagemaker-jumpstart/)です．その他の OSS モデルについても，Amazon SageMaker 上にデプロイすることで利用が可能です．
:::

## 先進的で実践的な内容

RAG アプリの実装方法や RAG の精度改善方法なども解説されており，これ 1 冊で基礎〜最新情報をキャッチアップできる内容となっております．また，Agents for Amazon Bedrock も丁寧に解説されており，Column には最近のアップデートに関する情報もまとめられております．

その他には，DynamoDB による会話履歴の永続化，Lambda によるサーバーレス化という内容や，CloudWatch，CloudTrail，PrivateLink，CloudFormation との連携，Step Functions を利用したローコード開発など，実践的な内容が多く含まれています．（アーキテクチャー図やスクリーンショットが豊富で非常にわかりやすいです．）

## その他特徴

- **サンプルコードが Github 上で公開**
  - 初学者にもわかりやすいように，コード中に丁寧なコメントがあります．
  - https://github.com/minorun365/bedrock-book
- **情報の鮮度**
  - Converse API や Tool Use にも触れており，2024/5/31 までの情報は網羅されてそうです．
  - 著者陣の熱量が凄まじいですね．．！
- **Bedrock 以外の AWS サービスや生成 AI ツールの紹介**
  - Amazon Q Business や Dify などの最新ツールのキャッチアップも可能です．
- **お勧めの最新情報のキャッチアップ方法の紹介**
  - 惜しげもなく紹介されており，非常に参考になります．
- **どの章から読んでも問題ない設計**
  - 好きな分野・苦手分野から読む等も可能です．

## おわりに

非常に変化の早い時代です．生成 AI は知識の鮮度が重要な分野でもあるため，本書籍を購入された際は，積読せずに，即座に読み進めることをお勧めします！（私もあと 3 周くらい読もうと思います！笑）
