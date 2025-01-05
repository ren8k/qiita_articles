# Lambda Web Adapter with Python

通常，Lambda における Python マネージドランタイムでは，以下の形式で一度にすべてのレスポンスを返す必要がある．

```py
def lambda_handler(event, context):
    # 処理
    return {
        'statusCode': 200,
        'body': 'レスポンス'
    }
```

一方，Python マネージドランタイムは，ストリーミングレスポンスを直接サポートしていない．具体的には，以下のようには実装できない．

```py
def lambda_handler(event, context):
    for chunk in generate_response():  # 本来はこのように少しずつデータを返したい
        yield chunk  # ← これができない
```

そこで，Lambda Web Adapter (LWA) と Web フレームワークを介してストリーミングを実現する必要がある．

```py
# Lambda Web Adapter + FastAPIを使用した場合
@app.post("/stream")
def stream_response():
    return StreamingResponse(
        generate_response(),  # yieldを使ったジェネレータ関数
        media_type="text/event-stream"
    )
```

LWA は，HTTP リクエストを受け取り，それを Web アプリケーションに転送するプロキシとして機能する．LWA は単なるアダプター（変換層）であり，実際の HTTP リクエスト/レスポンスの処理機能は持っていない．つまり，Web フレームワークを利用し，HTTP リクエストを処理する Web アプリケーションを用意する必要がある．LWA は以下のような Web フレームワークをサポートしている．

- FastAPI
- Flask
- Express.js
- Next.js
- SpringBoot
- ASP.NET
- Laravel
- その他 HTTP 1.1/1.0 に対応したフレームワーク

## 参考

### Lambda Web Adapter

- https://blog.serverworks.co.jp/gen-ai-aws-lambda-streaming
- https://github.com/awslabs/aws-lambda-web-adapter/tree/main/examples/fastapi-response-streaming
- https://serverless.co.jp/blog/g30vzpio0ww/
- https://aws.amazon.com/jp/blogs/news/implementing-ssr-streaming-on-nextjs-with-aws-lambda-response-streaming/
- https://aws.amazon.com/jp/builders-flash/202402/lambda-container-runtime/?awsf.filter-name=*all
- https://aws.amazon.com/jp/blogs/news/introducing-aws-lambda-response-streaming/

### FastAPI

- https://qiita.com/Isaka-code/items/00b4c672674932871b8a
- https://qiita.com/Isaka-code/items/34064820d893f71f2fb4

### Lambda

- https://qiita.com/eiji-noguchi/items/e226ed7b8da2cd85a06a
- https://zenn.dev/ovrsa/articles/4db3a7f206616b

### CloudFront

- https://techblog.kayac.com/cost-intensive-lambda

### Prompt Chaining

- https://aws.amazon.com/jp/blogs/machine-learning/implementing-advanced-prompt-engineering-with-amazon-bedrock/

### React

- https://zenn.dev/nyarufoy/articles/ef433a40d9b209
- https://github.com/aws-samples/react-cors-spa
- https://docs.aws.amazon.com/ja_jp/prescriptive-guidance/latest/patterns/deploy-a-react-based-single-page-application-to-amazon-s3-and-cloudfront.html
- https://qiita.com/nuco_YM/items/b4259d838be53a6f44ee
- https://qiita.com/Sicut_study/items/d520f9a858506b81e874

### Lambda@Edge

- https://dev.classmethod.jp/articles/cloudfront-lambda-url-with-post-put-request/

### 記事メモ

#### title

workflow 型の Agent を Lambda Web Adapter でサーバーレスでストリーミング実行する

#### 取り組み内容

LangGraph のストリーミング処理を，サーバーレスで実現したい．
LangGraph のストリーミング処理は，グラフの実行を待たずに，逐次的にノードの実行結果を返す処理である．
（実装は複雑になるが，ノード内でもストリーミング処理を行うことは可能だが，今回は実施していない．）
Python でのストリーミング処理は，Lambda Web Adapter と FastAPI を使用することで実現できる．
Lambda でコンテナイメージから関数を作成する．

#### 手順

- FastAPI でローカル実行
  - Lambda Web Adapter のデフォルトポートは 8080 であるため，uvicorn のポートを 8080 にしている
- ECR に Docker イメージを push

```
次の手順を使用して、リポジトリに対してイメージを認証し、プッシュします。Amazon ECR 認証情報ヘルパーなどの追加のレジストリ認証方法については、レジストリの認証  を参照してください。
Retrieve an authentication token and authenticate your Docker client to your registry. Use the AWS CLI:

aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin 684452318078.dkr.ecr.ap-northeast-1.amazonaws.com
注意: AWS CLI の使用中にエラーが発生した場合は、最新バージョンの AWS CLI と Docker がインストールされていることを確認してください。
以下のコマンドを使用して、Docker イメージを構築します。一から Docker ファイルを構築する方法については、「こちらをクリック 」の手順を参照してください。既にイメージが構築されている場合は、このステップをスキップします。

docker build -t lwa .
構築が完了したら、このリポジトリにイメージをプッシュできるように、イメージにタグを付けます。

docker tag lwa:latest 684452318078.dkr.ecr.ap-northeast-1.amazonaws.com/lwa:latest
以下のコマンドを実行して、新しく作成した AWS リポジトリにこのイメージをプッシュします:

docker push 684452318078.dkr.ecr.ap-northeast-1.amazonaws.com/lwa:latest
```

- Lambda の作成
  - Bedrock のポリシー付与
  - 関数 URL の作成
    - 今回は検証のため，認証タイプ: NONE とする
  - Lambda Web Adapter の設定
    - 関数 URL の設定で，呼び出しモード: RESPONSE_STREAM にする
    - 環境変数 AWS_LWA_INVOKE_MODE: RESPONSE_STREAM にする
  - Lambda の実行時間を伸ばす (5 分)
