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

| (1) ソース画像                                                                                                             | (2) 参照画像                                                                                                                            | (3) マスク画像                                                                                                                           | (4) 試着画像                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ![human.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9745df07-7280-46ec-ba57-d5b13d471afd.png) | ![swag_top_engineer.jpg](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8b1b105a-2357-451e-b4fb-a1498742b815.jpeg) | ![exp1-1_mask_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a91f9558-f278-4f03-a6c8-f5fe76294b18.png) | ![exp1-1_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/2653ea81-ca97-4194-ac40-66261afa02f3.png) |

:::note warn
本記事におけるソース画像・生成画像は，Amazon Nova Canvas で生成した画像であり，実在の人物ではありません．参照画像で利用している衣服は，AWS のイベントでいただいたものを使用しています．
:::

## 検証用 Python 関数

本節以降，AWS SDK for Python (boto3) を使用し，Virtual try-on の機能を検証します．説明のため，Amazon Nova Canvas によりマスク画像，試着画像を生成して表示するヘルパー関数 `generate_image` を定義します．

```python
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

    if "returnMask" in payload.get("virtualTryOnParams", {}):
        mask_base64 = response_body.get("maskImage")
        mask_bytes = base64.b64decode(mask_base64.encode("ascii"))
        mask_image = Image.open(io.BytesIO(mask_bytes))
        mask_image.show()
```

ヘルパー関数の引数 `payload` に Virtual try-on のパラメータを指定します．本パラメータの説明については後述します．

また，入力画像を Base64 エンコードするためのヘルパー関数 `load_image_as_base64` と，画像をリサイズするためのヘルパー関数 `resize_image` を定義します．Amazon Nova Canvas に入力可能な画像のサイズは [4,194,304pixel 未満](https://docs.aws.amazon.com/ja_jp/nova/latest/userguide/image-gen-access.html#image-gen-resolutions)であるため，`resize_image` では 2048x2048 のサイズにリサイズしております．

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

本検証では，基本的な機能を確認することを目的とし，男性が写ったソース画像に対し，T シャツ (2025 Japan AWS Top Engineer の Swag) の参照画像を合成した試着が可能かを確認します．

| ソース画像                                                                                                                 | 参照画像                                                                                                                                |
| -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| ![human.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9745df07-7280-46ec-ba57-d5b13d471afd.png) | ![swag_top_engineer.jpg](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8b1b105a-2357-451e-b4fb-a1498742b815.jpeg) |

以下のパラメータをヘルパー関数 `generate_image` に指定することで， Virtual try-on による試着を実現できます．`taskType` には `VIRTUAL_TRY_ON` を指定し，`virtualTryOnParams` に，ソース画像，参照画像，マスク画像に関するパラメータを指定します．以下に，各パラメータの説明を示します．

- `sourceImage`: ソース画像．`source_img_path` にはソース画像のパスを指定しています．
- `referenceImage`: 参照画像．`reference_img_path` には参照画像のパスを指定しています．
- `maskType`: マスク画像の設定．`GARMENT` を指定することで，衣服に特化したマスクを自動生成しています．
- `garmentBasedMask`: 置換対象の衣服の設定．本設定に基づき，マスク画像を生成します．
- `garmentClass`: 衣服のクラス．"UPPER_BODY" を指定することで，上半身の衣服 (T シャツ) のマスクを自動生成します．
- `returnMask`: マスク画像を返すかどうか．`True` を指定することで，マスク画像を返します．

参考に，`garmentClass` の[一覧](https://docs.aws.amazon.com/nova/latest/userguide/image-gen-req-resp-structure.html)を以下に示します．

<details><summary>garmentClass 一覧</summary>

- `UPPER_BODY` - 上半身
- `LOWER_BODY` - 下半身
- `FULL_BODY` - 全身
- `FOOTWEAR` - 履物
- `LONG_SLEEVE_SHIRT` - 長袖シャツ
- `SHORT_SLEEVE_SHIRT` - 半袖シャツ
- `NO_SLEEVE_SHIRT` - ノースリーブシャツ（袖なしシャツ）
- `OTHER_UPPER_BODY` - その他の上半身衣服
- `LONG_PANTS` - 長ズボン
- `SHORT_PANTS` - 短パン（ショートパンツ）
- `OTHER_LOWER_BODY` - その他の下半身衣服
- `LONG_DRESS` - ロングドレス
- `SHORT_DRESS` - ショートドレス
- `FULL_BODY_OUTFIT` - 全身衣装
- `OTHER_FULL_BODY` - その他の全身衣服
- `SHOES` - 靴
- `BOOTS` - ブーツ
- `OTHER_FOOTWEAR` - その他の履物

</details>

```python
generate_image(
    {
        "taskType": "VIRTUAL_TRY_ON",
        "virtualTryOnParams": {
            "sourceImage": load_image_as_base64(source_img_path),
            "referenceImage": load_image_as_base64(resized_reference_img_path),
            "maskType": "GARMENT", # マスク画像 (衣服) を自動生成
            "garmentBasedMask": {
                "garmentClass": "UPPER_BODY",
            },
            "returnMask": True,  # マスクを返す
        },
    },
)
```

以下に，自動生成されたマスク画像と，試着画像を示します．

| マスク画像                                                                                                                               | 試着画像                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ![exp1-1_mask_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a91f9558-f278-4f03-a6c8-f5fe76294b18.png) | ![exp1-1_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/2653ea81-ca97-4194-ac40-66261afa02f3.png) |

`maskType` に `GARMENT` を指定し，`garmentBasedMask` の `garmentClass` に `UPPER_BODY` を指定しているので，上半身の衣服の領域を黒で示したマスク画像が自動生成されいることが確認できます．また，マスク画像の黒色の領域に，参照画像 (T シャツ) が自然に合成されていることも確認できます．

## 検証 2: 上着の試着

本検証では，

## まとめ

summary
