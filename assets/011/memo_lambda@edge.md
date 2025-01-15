### Lambda@Edge

## アーキテクチャ

https://dev.classmethod.jp/articles/cloudfront-lambda-url-with-post-put-request/
https://github.com/aws-samples/cloudfront-authorization-at-edge

## POST/PUT リクエストは追加の署名が必要らしいので、要注意。

https://qiita.com/Kanahiro/items/85573c9ae724df435a6a
https://qiita.com/watany/items/4e3df4c6eef5ff01dc8f
https://dev.classmethod.jp/articles/aws-cdk-cloudfront-oac-lambda-function-url/
https://dev.classmethod.jp/articles/aws-cdk-cloudfront-oac-lambda-function-url/
https://qiita.com/Kanahiro/items/85573c9ae724df435a6a

## その他

https://speakerdeck.com/watany/aws-lambda-response-streaming-shi-zhuang-qian-nisiritaiyatu
https://speakerdeck.com/_kensh/monolith-first-serverless-development
https://qiita.com/itkz1016/items/b6920ac6b41906ff21e8

## メモ

- Lambda@Edge により SHA256 でコンテンツハッシュを計算し，Lambda Function URL の POST リクエスト時に，x-amz-content-sha256 ヘッダーでハッシュ値を含める必要がある．（かも？）

  - https://dev.classmethod.jp/articles/cloudfront-lambda-url-with-post-put-request/
  - sigv4 は OAC で署名すれば問題ないらしい
  - https://github.com/joe-king-sh/lambda-function-urls-with-post-put-sample/issues/1

- Lambda Function URL は，CloudFront の OAC に対応しているが，POST/PUT リクエストは追加の署名が必要．つまり，CloudFront + Lambda@Edge の構成は避けられない．

- Lambda@Edge で利用する Lambda 関数はバージニア北部で作成しておく必要がある．

- 必要になる機能 (実装) は以下．

  - 認証チェック機能: ユーザーが保護されたコンテンツにアクセスする権限があるかを確認 (SHA256 ハッシュを計算)
  - 認証情報解析機能: ユーザーがログインした後の処理を担当(Cookie に保存など)
  - トークン更新機能: 認証トークンの有効期限が切れた時の更新処理
  - ログアウト機能: ユーザーのログアウト処理を実行
  - セキュリティヘッダー設定: Web サイトのセキュリティを強化
  - URL リライト機能: URL の末尾がスラッシュの場合のファイル指定を補完

- 上記の機能は[本リポジトリ](https://github.com/aws-samples/cloudfront-authorization-at-edge)で実装されているが，ボリュームが多く，それなりに理解と実装（修正）に時間がかかりそう．

- 色々調査したが，実装例としては以下のみ．（若干古く，非推奨の OAI を利用している）

  - https://github.com/aws-samples/cloudfront-authorization-at-edge

- 理解した上で組み込むのに（初学者の場合），1~2 weeks 以上かかる可能性あり．

- 現在，Lambda を利用した API の開発は着手できておらず，そもそも時間的にも厳しいかも（サーバーレス化する場合は，以下のタスクを実行する必要あり）
  - Lambda Web Adapter でのストリーミング処理の実装（FastAPI を利用して Docker 化）
  - Lambda Function URL のタイプを IAM とし，CloudFront+Lambda@Edge による認証の実装
  - React によるフロントエンドの実装
    - LangGraph のロジックの表示部分
    - 認証部分の実装

## 結論

Lambda Web Adapter による LangGraph のレスポンスストリーミングが可能であることを検証した．

https://qiita.com/ren8k/items/8525fb170c13ec861857

検証では，Lambda Function URL を認証無しで利用したが，本番運用時には，IAM 認証を利用することが望ましい．IAM 認証を利用する場合，CloudFront 側で以下の処理を実行する必要がある．

- 1. Lambda@Edge により，Cognito で認証．認証後，JWT トークンを発行し，Cookie に保存．
- 2. Lambda@Edge により SHA256 でコンテンツハッシュを計算
- 3. Lambda Function URL の POST リクエスト時に以下を含める．
  - Authorization ヘッダー: sigv4 で署名したヘッダー
  - x-amz-content-sha256 ヘッダー: 2. で計算したハッシュ u 値
    - CloudFront で OAC 実施時，これは必要なのか？

上記を実現する上で，Lambda@Edge で以下の機能を実装する必要がある．

- 認証チェック機能: ユーザーが保護されたコンテンツにアクセスする権限があるかを確認 (SHA256 ハッシュを計算)
- 認証情報解析機能: ユーザーがログインした後の処理を担当(Cookie に保存など)
- トークン更新機能: 認証トークンの有効期限が切れた時の更新処理
- ログアウト機能: ユーザーのログアウト処理を実行
- セキュリティヘッダー設定: Web サイトのセキュリティを強化
- URL リライト機能: URL の末尾がスラッシュの場合のファイル指定を補完

### 参考

- https://github.com/aws-samples/cloudfront-authorization-at-edge
- https://speakerdeck.com/tmokmss/aws-lambda-web-adapterwohuo-yong-suruxin-siisabaresunoshi-zhuang-patan
- https://dev.classmethod.jp/articles/cloudfront-lambda-url-with-post-put-request/
- https://dev.classmethod.jp/articles/cloud-front-cognito-auth/
