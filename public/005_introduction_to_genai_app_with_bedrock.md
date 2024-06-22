---
title: 「Amazon Bedrock」で始める生成AIアプリ開発入門バイブルの登場！！
tags:
  - AWS
  - bedrock
  - 技術書
  - LLM
  - 生成AI
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: true
---

:::note
本記事は，著者の@minorun365 さんよりご恵贈いただき，発売前の書籍レビューをするものです．
:::

## はじめに

幸運なことに，来週 6/26 発売予定の書籍『[Amazon Bedrock 生成 AI アプリ開発入門](https://www.sbcr.jp/product/4815626440/)』を @minorun365 さんからご恵贈賜りました．本記事では，学んだ点や特徴をまとめようと思います．

<img width="450" src="https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/955e5ccd-88f6-5805-83d8-bbaefe6f2b11.jpeg">

## Amazon Bedrock 生成 AI アプリ開発入門

- 御田 稔 (著), 熊田 寛 (著), 森田 和明 (著)
- SB Creative より 2024/6/26 発売予定

https://amzn.asia/d/03xAyTFd

## 対象読者と所感

書名には "入門" とありますが，あらゆるレベルの方が手に取ってみる価値があると思います．特に，各章の Column には応用的な Tips が散りばめられており，初学者から上級者まで幅広く楽しめる内容となっています．

また，どの章も初学者に親切な解説（用語の説明，全ページフルカラーでコンソールのスクショ添付）がなされており，スムーズに学習ができる設計となっております．

個人的に良いと思った点としては，以下の点が挙げられます．

- なぜ Amazon Bedrock を選ぶのか？という点にしっかり言及している
- かなり実践的な内容を幅広く学べる（chat app のサーバーレス化，RAG，Agent, Step Functions を利用したローコード開発...）

## なぜ Amazon Bedrock を選ぶのか？

本書では，Bedrock を選定する理由として，複数の会社が提供する最先端モデルを幅広く利用可能である点や，アプリケーション開発との親和性，本番利用に耐えうる高いセキュリティ・ガバナンスを挙げております．

以下に，[Chatbot Arena](https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard) のデータを基に，直近リリースされた代表的な LLM のリリース日と Elo Rate を示します．縦軸が Chatbot Arena の Elo Rate，横軸がリリース日です．また，赤色のプロットは，Amazon Bedrock で利用可能なモデルです．

![chatbot_arena_elo_scores.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/f42500a1-a1b5-106c-87d1-747db073a1e8.png)

図から，昨今，様々な企業から，GPT-3.5 を凌駕するモデルが短スパンでリリースされていることがわかります．Amazon Bedrock は，提携社数が多く，様々な最先端の LLM を利用可能であり，ユースケースに応じて柔軟にモデルを使い分けることができます．加え，文章生成以外にも，画像生成やベクトル変換用のモデルも提供されております．

また，GPT-4 などの特定の LLM に依存した生成 AI のサービス運用は，少なからずリスクが伴います．その他，AWS 外への接続が制限されており，AWS 環境外にデータを出せない場合，GPT-4 などのモデルは利用できません．これらの点も考慮すると，Amazon Bedrock を利用するメリットはあるのではないでしょうか．

:::note warn
上記の散布図は，執筆時点（2024/06/22）のデータを基に作成しております．また，Claude3.5 Sonnet については，リリース直後のため Chatbot Arena のリーダーボードには表示されておりませんが，複数の指標において [GPT-4o を超える精度を達成した](https://www.anthropic.com/news/claude-3-5-sonnet)と報告されているため，スコアは筆者による推定値となっている点，ご了承下さい．
:::

## かなり実践的な内容を学べる

- かなり実践的

  - p160：DynamoDB
  - p168: Lambda を利用したサーバーレス化

- 7 章では，Bedrock のみならず，CloudWatch，CloudTrail，PrivateLink，CloudFormation，Step Functions，Lambda，DynamoDB などの AWS サービスについても触れている

## その他特徴

- **サンプルコードが Github 上で公開**
  - 初学者にもわかりやすいように，コード中に丁寧なコメントがあります．
  - https://github.com/minorun365/bedrock-book
- **情報の鮮度**
  - Converse API や Tool Use にも触れており，2024/5/31 までの情報は網羅されてそうです．
  - 著者陣の熱量がすごいですね．．！
- **お勧めの最新情報のキャッチアップ方法の紹介**
  - 惜しげもなく紹介されており，非常に参考になります．
- **どの章から読んでも問題ない設計**
  - 好きな分野・苦手分野から読む等も可能です．

## おわりに

非常に変化の早い時代です．本書籍を購入された際は，積読せずに，すぐに読み進めることをお勧めします！（私もあと 3 周くらい読もうと思います！笑）
