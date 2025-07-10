---
title: Amazon Nova Canvas の Virtual try-on の機能検証
tags:
  - Python
  - AWS
  - bedrock
  - 画像生成
  - 生成AI
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: true
---

## はじめに

株式会社 NTT データ デジタルサクセスソリューション事業部の [@ren8k](https://qiita.com/ren8k) です．

Virtual try-on について，Dive Deep していきます．

## Virtual try-on とは

Virtual try-on は，衣服の画像を，人物が写っている画像に重ね合わせ，試着をシミュレーションする機能です．具体的には，(1) ソース画像，(2) 参照画像，(3) マスク画像 の 3 つの画像を入力とし，マスク画像に示した編集領域に合うように，参照画像をソース画像に合成する Inpaint 機能です．

本機能の特徴として，既存の画像生成タスクのように，テキストプロンプトやネガティブプロンプトを利用しない点が挙げられます．また，推論パラメータを指定することで，マスク画像をモデルに自動生成させることが可能であり，この場合はマスク画像の入力は不要です．

| (1) ソース画像                                                                                                             | (2) 参照画像                                                                                                                            | (3) マスク画像                                                                                                                      | (4) 生成画像                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ![human.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9745df07-7280-46ec-ba57-d5b13d471afd.png) | ![swag_top_engineer.jpg](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8b1b105a-2357-451e-b4fb-a1498742b815.jpeg) | ![exp5-1_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/577c6716-8f7d-46d0-8caf-a58e8ede548c.png) | ![exp1-1_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/2653ea81-ca97-4194-ac40-66261afa02f3.png) |

:::note warn
本記事におけるソース画像・生成画像は，Amazon Nova Canvas で生成した画像であり，実在の人物ではありません．参照画像で利用している衣服は，AWS のイベントでいただいたものを使用しています．
:::

## 検証用 Python 関数

本節以降，AWS SDK for Python (boto3) を使用し，Virtual try-on の機能を検証します．説明のため，Amazon Nova Canvas により画像を生成して表示するヘルパー関数 `generate_image` を定義します．

```python
import base64
import io
import json

import boto3
from PIL import Image


def generate_image(
    payload: dict,
    num_image: int = 1,
    cfg_scale: float = 6.5,
    seed: int = 42,
    model_id: str = "amazon.nova-canvas-v1:0",
) -> None:

    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    body = json.dumps(
        {
            **payload,
            "imageGenerationConfig": {
                "numberOfImages": num_image,  # Range: 1 to 5
                "quality": "premium",  # Options: standard/premium
                "height": 1024,  # Supported height list above
                "width": 1024,  # Supported width list above
                "cfgScale": cfg_scale,  # Range: 1.0 (exclusive) to 10.0
                "seed": seed,  # Range: 0 to 214783647
            },
        }
    )

    response = client.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
    )

    response_body = json.loads(response.get("body").read())
    base64_image = response_body.get("images")[0]
    base64_bytes = base64_image.encode("ascii")
    image_bytes = base64.b64decode(base64_bytes)

    image = Image.open(io.BytesIO(image_bytes))
    image.show()
```

ヘルパー関数の引数 `payload` に Virtual try-on のパラメータを指定します．本パラメータの説明については後述します．

また，入力画像を Base64 エンコードするためのヘルパー関数 `load_image_as_base64` と，画像をリサイズするためのヘルパー関数 `resize_image` を定義します．Amazon Nova Canvas に入力可能な画像のサイズは 4,194,304pixel 未満であるため，`resize_image` では 2048x2048 のサイズにリサイズしております．

```python
def load_image_as_base64(image_path) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def resize_image(reference_img_path, resized_reference_img_path) -> None:
    img = Image.open(reference_img_path)
    img = img.resize((2048, 2048), Image.LANCZOS)
    img.save(resized_reference_img_path)
```

## 検証 1: T シャツの試着

本実験では，基本的な機能を確認することを目的とし，T シャツの試着を検証します．

```python
generate_image(
    {
        "taskType": "VIRTUAL_TRY_ON",
        "virtualTryOnParams": {
            "sourceImage": load_image_as_base64(source_img_path),
            "referenceImage": load_image_as_base64(resized_reference_img_path),
            "maskType": "GARMENT",
            "garmentBasedMask": {
                "garmentClass": "UPPER_BODY",
            },
        },
    },
)
```

## まとめ

summary
